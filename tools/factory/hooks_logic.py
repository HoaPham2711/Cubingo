"""Logic thuần của 3 hook nhà máy (test được, hook chỉ là vỏ mỏng đọc stdin/ghi stdout).

- autonomy_decision(cmd, cwd)  → ("ask", lý do) | None      — PreToolUse(Bash), .claude/hooks/guard_autonomy.py
- stop_decision(payload)       → {"decision":"block",…} | None — Stop, .claude/hooks/factory_stop_gate.py
- session_context(payload)     → str | None                  — SessionStart, .claude/hooks/factory_context.py

Bảng tự chủ: .claude/skills/factory/autonomy.md (lịch sử thiết kế nhà máy agent nằm ở repo template).
guard_autonomy KHÔNG bao giờ chặn cứng — chỉ "ask" (user luôn bấm Allow được). Hai guard cũ
(guard_test_config, guard_asc — logic ở tools/aso/policy.py) giữ phần chặn cứng của chúng.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

import mission as M

PROTECTED_BRANCHES = ("main", "develop", "master")
MAX_STOP_BLOCKS = 3

# Tách lệnh ghép THEO TOKEN, hiểu dấu nháy (shlex + punctuation_chars): `bash -c "cd x && git push"` giữ nguyên
# chuỗi nháy để đệ quy; `2>&1` không bị coi là `&`. Bản tách regex trên chuỗi thô làm lọt cổng (review vòng 2).
# Backtick = biên subshell. Xuống dòng NGOÀI dấu nháy = biên lệnh.
PREFIX_CMDS = {"env", "command", "time", "nohup", "sudo", "exec", "nice", "caffeinate", "builtin", "noglob",
               # từ khoá shell đứng trước lệnh thật: `if x; then git push …`, `for …; do git push …`, `! cmd`
               "then", "do", "else", "elif", "if", "while", "until", "!"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
_SEP_CHARS = set("();|&")
_FALLBACK_SPLIT = re.compile(r"\$\(|`|\(|\)|\{|\}|&&|\|\||;|\||&|\n")


def _lines_outside_quotes(cmd: str) -> list[str]:
    out, buf, q, esc = [], [], None, False
    for ch in cmd:
        if esc:
            buf.append(ch)
            esc = False
            continue
        if ch == "\\" and q != "'":
            esc = True
            buf.append(ch)
            continue
        if q:
            if ch == q:
                q = None
        elif ch in "'\"":
            q = ch
        elif ch == "\n":
            out.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    out.append("".join(buf))
    return out


# Command substitution chạy cả TRONG nháy kép ("$(git push …)", "`…`") và process substitution <(…)/>(…): trích
# nội dung trên chuỗi THÔ để đệ quy (review vòng 3). Một tầng ngoặc lồng là đủ; trích thừa trong nháy đơn chỉ
# làm hỏi thừa, không lọt.
_SUBST = re.compile(r"[$<>]\(((?:[^()]|\([^()]*\))*)\)|`([^`]*)`")


def _substitutions(cmd: str) -> list[str]:
    return [m.group(1) if m.group(1) is not None else m.group(2) for m in _SUBST.finditer(cmd or "")]


def _segments(cmd: str) -> list[list[str]]:
    segs: list[list[str]] = []
    for line in _lines_outside_quotes((cmd or "").replace("`", " ; ")):
        try:
            lex = shlex.shlex(line, posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            lex.commenters = ""  # '#' giữa từ (#97, $#, URL#frag) KHÔNG phải chú thích — review vòng 3
            toks = list(lex)
        except ValueError:  # nháy không đóng ⇒ lùi về tách thô (thà tách thừa)
            segs += [p.split() for p in _FALLBACK_SPLIT.split(line) if p.strip()]
            continue
        cur: list[str] = []
        for t in toks:
            if (t and set(t) <= _SEP_CHARS) or t in ("{", "}", "$"):
                if cur:
                    segs.append(cur)
                cur = []
            else:
                cur.append(t)
        if cur:
            segs.append(cur)
    return segs


def _strip_prefixes(tokens: list[str]) -> tuple[dict, list[str]]:
    """Bỏ VAR=x, env [-i] [-u N], command/time/nohup/sudo…, timeout <dur> ở đầu lệnh."""
    env, i = {}, 0
    while i < len(tokens):
        t = tokens[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            k, _, v = t.partition("=")
            env[k] = v
            i += 1
        elif t.rsplit("/", 1)[-1] in PREFIX_CMDS:
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 2 if tokens[i] in ("-u", "-n", "-S", "-C", "-g") else 1
        elif t.rsplit("/", 1)[-1] == "timeout":
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 2 if tokens[i] in ("-s", "-k", "--signal", "--kill-after") else 1
            i += 1  # thời lượng
        else:
            break
    return env, tokens[i:]


def current_branch(cwd: str | None) -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd or None,
                           capture_output=True, text=True, timeout=3)
        return (r.stdout.strip() or None) if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _join(cwd: str | None, path: str) -> str:
    p = os.path.expanduser(path)
    return os.path.normpath(p if os.path.isabs(p) or not cwd else os.path.join(cwd, p))


def _git_push_reason(args: list[str], cwd: str | None, branch_of=current_branch) -> str | None:
    """args = phần sau `git push`."""
    flags = [a for a in args if a.startswith("-")]
    pos = [a for a in args if not a.startswith("-")]
    if any(f in ("-f", "--force", "--force-with-lease", "--mirror", "--delete", "-d", "--prune") or
           f.startswith("--force") for f in flags):
        return "git push có --force/--mirror/--delete/--prune (viết đè hoặc xoá trên remote)"
    if "--all" in flags:
        return "git push --all (đẩy mọi nhánh, gồm develop/main)"
    refs = pos[1:]  # pos[0] = remote
    for r in refs:
        if r.startswith("+"):
            return "git push refspec có + (force)"
        if r.startswith(":"):
            return f"git push {r} (xoá nhánh remote)"
        if "$" in r:
            return f"git push tới đích là biến `{r}` (không biết trước có phải nhánh bảo vệ)"
        dst = r.split(":", 1)[-1].removeprefix("refs/heads/")
        if dst in PROTECTED_BRANCHES or (dst == "HEAD" and (branch_of(cwd) in PROTECTED_BRANCHES)):
            return f"git push lên nhánh bảo vệ `{dst}`"
    if "--tags" in flags or any(re.match(r"^(refs/tags/)?v\d+\.\d+", r) for r in refs):
        return "git push tag phát hành"
    if not refs:
        b = branch_of(cwd)
        if b in PROTECTED_BRANCHES:
            return f"git push từ nhánh `{b}` (đẩy thẳng nhánh bảo vệ)"
        if b is None:
            return "git push không xác định được nhánh hiện tại"
    return None


_GH_WRITE_METHODS = ("post", "put", "patch", "delete")


def _gh_api_writes(low: list[str]) -> bool:
    method = None
    for i, t in enumerate(low):
        if t in ("-x", "--method") and i + 1 < len(low):
            method = low[i + 1]
        elif t.startswith("--method="):
            method = t.split("=", 1)[1]
        elif t.startswith("-x") and len(t) > 2:
            method = t[2:]
    if method:
        return method in _GH_WRITE_METHODS
    # gh api mặc định POST khi có field/input
    return any(t in ("-f", "-F", "--field", "--raw-field", "--input") or t.startswith(("--field=", "--raw-field=",
               "--input=")) for t in low)


def _reasons(cmd: str, cwd: str | None, branch_of, depth: int = 0) -> list[str]:
    reasons: list[str] = []
    if depth > 4:
        return ["lệnh lồng quá sâu (bash -c/eval nhiều tầng) — không phân tích hết"]
    for inner in _substitutions(cmd):
        reasons += _reasons(inner, cwd, branch_of, depth + 1)
    for seg in _segments(cmd):
        env, tok = _strip_prefixes(seg)
        if not tok:
            continue
        low = [t.lower() for t in tok]
        head = low[0].rsplit("/", 1)[-1]
        if head in ("cd", "pushd") and len(tok) > 1 and tok[1] != "-":
            cwd = _join(cwd, tok[1])
            continue
        cflag = next((k for k, t in enumerate(low[1:], 1) if re.fullmatch(r"-[a-z]*c[a-z]*", t)), None)
        if head in SHELLS and cflag is not None:  # -c, -lc, -ec, -xc…
            if cflag + 1 < len(tok):
                reasons += _reasons(tok[cflag + 1], cwd, branch_of, depth + 1)
            continue
        if head == "eval":
            reasons += _reasons(" ".join(tok[1:]), cwd, branch_of, depth + 1)
            continue
        if head == "git":
            i, gcwd = 1, cwd
            while i < len(tok) and tok[i].startswith("-"):
                if tok[i] == "-C" and i + 1 < len(tok):
                    gcwd = _join(gcwd, tok[i + 1])
                    i += 2
                elif tok[i] in ("-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
                    i += 2
                else:
                    i += 1  # --no-pager, -p, --paginate, --bare, --git-dir=…
            if i < len(tok) and tok[i] == "push":
                r = _git_push_reason(tok[i + 1:], gcwd, branch_of)
                if r:
                    reasons.append(r)
        elif head == "gh":
            if low[1:3] == ["pr", "merge"]:
                reasons.append("gh pr merge (merge PR)")
            elif low[1:2] == ["release"] and low[2:3] and low[2] in ("create", "upload", "edit", "delete",
                                                                     "delete-asset"):
                reasons.append(f"gh release {low[2]} (phát hành công khai)")
            elif low[1:2] == ["repo"] and low[2:3] and low[2] in ("delete", "archive", "rename", "edit"):
                reasons.append(f"gh repo {low[2]}")
            elif low[1:3] == ["workflow", "run"]:
                reasons.append("gh workflow run (kích hoạt CI/CD)")
            elif low[1:2] == ["api"] and _gh_api_writes(low):
                reasons.append("gh api ghi (POST/PUT/PATCH/DELETE hoặc -f/--input)")
        elif head in ("npm", "pnpm", "yarn"):
            if any(re.fullmatch(r"deploy(:prod)?", t) for t in low[1:]):
                reasons.append("deploy web PRODUCTION")
        elif head in ("wrangler", "npx") or "wrangler" in low[:2]:
            w = low[low.index("wrangler") + 1:] if "wrangler" in low else []
            is_dev = ("--env" in w and w[w.index("--env") + 1:w.index("--env") + 2] == ["dev"]) or \
                     any(t == "--env=dev" for t in w) or env.get("CLOUDFLARE_ENV") == "dev"
            if w[:1] == ["deploy"] and not is_dev:
                reasons.append("wrangler deploy không có --env dev (= PRODUCTION)")
            elif w[:1] == ["d1"] and "--remote" in w and not is_dev:
                reasons.append("wrangler d1 … --remote trên DB production")
            elif w[:2] in (["secret", "put"], ["secret", "delete"]):
                reasons.append("wrangler secret (đổi bí mật trên Cloudflare)")
            elif w[:1] == ["r2"] and "delete" in w:
                reasons.append("wrangler r2 … delete (xoá dữ liệu)")
        elif head == "firebase" and "deploy" in low:
            reasons.append("firebase deploy (rules/cấu hình production)")
        elif head == "xcrun" and any(t in ("altool", "notarytool") for t in low):
            reasons.append("xcrun altool/notarytool (upload lên Apple)")
        elif head == "xcodebuild" and "-exportarchive" in low and any("upload" in t for t in low):
            reasons.append("xcodebuild -exportArchive upload lên App Store Connect")
        if any(t.endswith("bump_version.sh") for t in tok[:2]):
            reasons.append("bump_version.sh (commit + tag phát hành)")
    return reasons


def autonomy_decision(cmd: str, cwd: str | None = None, branch_of=current_branch):
    """Trả ("ask", lý do) cho lệnh thuộc lớp 'cổng con người'; None = không ý kiến."""
    reasons = _reasons(cmd, cwd, branch_of)
    if not reasons:
        return None
    uniq = list(dict.fromkeys(reasons))
    return ("ask", "Cổng con người (nhà máy agent — bảng tự chủ): " + "; ".join(uniq)
            + ". Chỉ Allow nếu bạn đã đồng ý việc này.")


# ----------------------------------------------------------------- Stop gate

def _transcript_mentions(path: str | None, needle: str) -> bool:
    if not path or not needle:
        return False
    try:
        data = needle.encode("utf-8")
        with open(path, "rb") as f:
            tail = b""
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    return False
                if data in tail + chunk:
                    return True
                tail = chunk[-len(data):]
    except OSError:
        return False


def stop_decision(payload: dict):
    """Chặn dừng khi phiên này đang làm giám đốc một mission autopilot chưa xong.

    Cho dừng (None) khi: không mission nào nhắc trong transcript; mission có cổng mở (đang chờ user);
    mission blocked; đã chặn MAX_STOP_BLOCKS lần liên tiếp mà ledger không đổi.
    """
    tpath = payload.get("transcript_path")
    sid = str(payload.get("session_id") or "?")
    for m in M.all_missions():
        if m.get("status") != "active" or not m.get("autopilot"):
            continue
        # Chỉ phiên đã chạy `mission.py new|claim` (in dấu giám đốc) — KHÔNG tìm mã mission trần.
        if not _transcript_mentions(tpath, M.director_mark(m["id"])):
            continue
        if any(g["status"] == "open" for g in m.get("gates", [])):
            continue
        probs = M.check(m)
        blocks = m.get("stop_blocks")
        if not isinstance(blocks, dict):  # ledger schema cũ lưu số nguyên dùng chung
            blocks = {}
        if blocks.get(sid, 0) >= MAX_STOP_BLOCKS:
            continue
        blocks[sid] = blocks.get(sid, 0) + 1
        m["stop_blocks"] = blocks
        M.save(m)
        n = blocks[sid]
        if probs:
            nxt = M.ready_tasks(m)
            hint = (f"Task kế: {nxt[0]['id']} ({nxt[0]['role']}) {nxt[0]['title']}." if nxt
                    else "Không task nào sẵn sàng — giải phụ thuộc, hoặc đánh blocked/mở cổng nếu cần user.")
            reason = (f"[factory] Mission {m['id']} (autopilot) CHƯA đạt DoD: " + "; ".join(probs[:5])
                      + f". {hint} Làm tiếp theo skill `factory`. Nếu thật sự cần user: "
                      "`mission.py gate open --kind <kind> --ask \"…\"` rồi mới dừng; không làm được: "
                      "`mission.py set <task> --status blocked --note \"…\"`. "
                      f"(chặn dừng {n}/{MAX_STOP_BLOCKS})")
        else:
            reason = (f"[factory] Mission {m['id']} đã đạt DoD ledger nhưng chưa close. Chạy "
                      f"`python3 tools/factory/mission.py close --mission {m['id']}`, viết report.md, rồi "
                      f"báo cáo user. (chặn dừng {n}/{MAX_STOP_BLOCKS})")
        return {"decision": "block", "reason": reason}
    return None


# ----------------------------------------------------------------- SessionStart

def session_context(payload: dict):
    ms = M.active_missions()
    if not ms:
        return None
    parts = ["[factory] Mission đang mở trong checkout này (ledger .factory/missions):"]
    for m in ms[:3]:
        parts.append(M.summary(m, limit=600))
    if len(ms) > 3:
        parts.append(f"… và {len(ms) - 3} mission khác (`python3 tools/factory/mission.py list`).")
    parts.append("Nếu phiên này là giám đốc của mission trên: tiếp tục theo skill `factory` "
                 "(đọc ledger trước, không làm lại việc đã verified). Nếu không: bỏ qua.")
    s = "\n".join(parts)
    return s[:1500]


def project_root_from_env() -> Path | None:
    p = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(p) if p else None
