#!/usr/bin/env python3
"""Lint harness .claude/ — bắt lỗi cấu hình agent/skill/workflow/hook TRƯỚC khi phiên mới nạp chúng
(lỗi frontmatter bị Claude Code lờ đi im lặng: khoá sai tên = tính năng mất mà không ai biết).

    python3 tools/factory/lint_harness.py            # toàn bộ, exit 1 nếu có lỗi
    python3 tools/factory/lint_harness.py --quiet    # chỉ in lỗi

Kiểm:
- agent `.claude/agents/*.md`: frontmatter đọc được; `name` = tên file; khoá thuộc danh sách docs Claude Code;
  `model`/`effort`/`memory`/`permissionMode` hợp lệ; `tools` là tool có thật; `skills` tồn tại trong repo.
- skill `.claude/skills/*/SKILL.md`: `name` = tên thư mục, có `description`, khoá hợp lệ, link .md tương đối tồn tại.
- workflow `.claude/workflows/*.js`: `export const meta = {` đứng đầu, meta là literal (không `${`, không gọi
  hàm, không spread), có name = tên file + description, cú pháp JS hợp lệ (`node --check`), không dùng
  `Date.now()`/`Math.random()`/`new Date()`; tiêu đề phase dùng trong body có trong meta.phases.
- `.claude/settings.json`: JSON hợp lệ, file hook được trỏ tới tồn tại.
- Đường dẫn repo trong backtick ở agent/skill (`tools/…`, `docs/…`, `.claude/…`, `web/…`, `store/…`, `AppHost/…`, `Core/…`) tồn tại.
- `.claude/agent-memory/<x>/` ứng với agent có thật.
- Định tuyến model: bảng `const ROLE_TIER = {…}` trong workflow khớp `model`/`effort` frontmatter của vai (fallback
  general-purpose mất frontmatter, bảng này là thứ duy nhất giữ bậc).
Khoá hợp lệ lấy theo docs Claude Code 2.1.31x (code.claude.com/docs/en/sub-agents, /skills) đọc 2026-11-05.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

AGENT_KEYS = {"name", "description", "tools", "disallowedTools", "model", "permissionMode", "maxTurns",
              "autoCompactWindow", "skills", "mcpServers", "hooks", "memory", "background", "omitClaudeMd",
              "effort", "isolation", "color", "initialPrompt", "experimental"}
SKILL_KEYS = {"name", "description", "when_to_use", "argument-hint", "arguments", "disable-model-invocation",
              "user-invocable", "allowed-tools", "disallowed-tools", "model", "effort", "context", "agent",
              "background", "hooks", "paths", "shell", "metadata", "license", "version"}
MODELS = {"sonnet", "opus", "haiku", "fable", "inherit", "best", "default", "opusplan", "sonnet[1m]", "opus[1m]"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
MEMORY = {"user", "project", "local"}
PERMISSION = {"default", "acceptEdits", "auto", "dontAsk", "bypassPermissions", "plan", "manual"}
TOOLS = {"Read", "Write", "Edit", "MultiEdit", "Bash", "Grep", "Glob", "WebSearch", "WebFetch", "Agent", "Task",
         "Skill", "NotebookEdit", "TodoWrite", "LSP", "ToolSearch", "AskUserQuestion", "Monitor", "SendMessage",
         "Workflow", "BashOutput", "KillShell"}
PATH_RE = re.compile(r"`((?:tools|docs|\.claude|web|store|AppHost|Core)/[^`\s]+)`")
TIER_BLOCK_RE = re.compile(r"const ROLE_TIER = \{(.*?)\n\}", re.S)
TIER_ROW_RE = re.compile(r"'([\w-]+)'\s*:\s*\{\s*model:\s*'(\w+)'\s*,\s*effort:\s*'(\w+)'\s*\}")
BAD_WF = [(re.compile(r"\bDate\.now\s*\("), "Date.now() (làm hỏng resume)"),
          (re.compile(r"\bMath\.random\s*\("), "Math.random() (làm hỏng resume)"),
          (re.compile(r"\bnew Date\s*\(\s*\)"), "new Date() không tham số (làm hỏng resume)")]


def parse_frontmatter(text: str):
    """YAML tối giản: `key: value`, list `  - x`, giá trị có ngoặc kép. Trả (dict, lỗi|None)."""
    if not text.startswith("---\n"):
        return None, "thiếu frontmatter (dòng đầu phải là ---)"
    end = text.find("\n---", 4)
    if end < 0:
        return None, "frontmatter không đóng ---"
    data, key = {}, None
    for raw in text[4:end].splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            data[key] = val if val != "" else []
            continue
        m = re.match(r"^\s+-\s+(.*)$", raw)
        if m and key is not None:
            if not isinstance(data[key], list):
                data[key] = []
            data[key].append(m.group(1).strip().strip('"\''))
            continue
        if raw.startswith((" ", "\t")) and key is not None:
            continue  # giá trị lồng (hooks, mcpServers) — không kiểm sâu
        return None, f"dòng frontmatter không đọc được: {raw!r}"
    return data, None


def as_list(v):
    if isinstance(v, list):
        return v
    return [x.strip() for x in str(v).split(",") if x.strip()]


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def check_paths(r: Report, where: str, text: str):
    for m in PATH_RE.finditer(text):
        p = m.group(1).rstrip(".,;:)")
        if any(c in p for c in "<>*{}$") or "…" in p:
            continue
        p = re.sub(r":\d+(-\d+)?$", "", p)  # file:dòng
        if not (ROOT / p).exists():
            r.err(where, f"đường dẫn không tồn tại: {p}")


def lint_agents(r: Report, root: Path, skill_names: set[str]) -> set[str]:
    names = set()
    for f in sorted((root / ".claude" / "agents").glob("*.md")):
        where = rel(f)
        text = f.read_text(encoding="utf-8")
        fm, e = parse_frontmatter(text)
        if e:
            r.err(where, e)
            continue
        names.add(f.stem)
        for k in fm:
            if k not in AGENT_KEYS:
                r.err(where, f"khoá frontmatter lạ `{k}` (Claude Code lờ đi im lặng)")
        if fm.get("name") != f.stem:
            r.err(where, f"name `{fm.get('name')}` ≠ tên file `{f.stem}`")
        if not fm.get("description") or len(str(fm.get("description"))) < 40:
            r.err(where, "description thiếu/quá ngắn (<40 ký tự) — Claude dựa vào nó để chọn agent")
        if "model" in fm and fm["model"] not in MODELS and not str(fm["model"]).startswith("claude-"):
            r.err(where, f"model `{fm['model']}` không hợp lệ")
        if "effort" in fm and fm["effort"] not in EFFORTS:
            r.err(where, f"effort `{fm['effort']}` không hợp lệ")
        if "memory" in fm and fm["memory"] not in MEMORY:
            r.err(where, f"memory `{fm['memory']}` không hợp lệ")
        if "permissionMode" in fm and fm["permissionMode"] not in PERMISSION:
            r.err(where, f"permissionMode `{fm['permissionMode']}` không hợp lệ")
        if fm.get("isolation") == "worktree":
            r.err(where, "isolation: worktree rẽ từ nhánh mặc định (main), không phải HEAD — cấm ở repo này")
        for t in as_list(fm.get("tools", [])):
            base = t.split("(")[0]
            if base not in TOOLS and not base.startswith("mcp__"):
                r.err(where, f"tool lạ `{t}`")
        for s in as_list(fm.get("skills", [])):
            if s not in skill_names and ":" not in s:
                r.err(where, f"skill `{s}` không có trong .claude/skills/")
        check_paths(r, where, text)
    return names


def lint_skills(r: Report, root: Path) -> set[str]:
    names = set()
    for f in sorted((root / ".claude" / "skills").glob("*/SKILL.md")):
        where = rel(f)
        text = f.read_text(encoding="utf-8")
        fm, e = parse_frontmatter(text)
        if e:
            r.err(where, e)
            continue
        names.add(f.parent.name)
        for k in fm:
            if k not in SKILL_KEYS:
                r.err(where, f"khoá frontmatter lạ `{k}`")
        if fm.get("name") not in (None, f.parent.name):
            r.err(where, f"name `{fm.get('name')}` ≠ tên thư mục `{f.parent.name}`")
        if not fm.get("description"):
            r.err(where, "thiếu description")
        n_lines = text.count("\n")
        if n_lines > 500:
            r.warn(where, f"{n_lines} dòng > 500 (docs khuyên tách file phụ)")
        for sub in [f] + sorted(f.parent.glob("*.md")):
            body = sub.read_text(encoding="utf-8")
            for m in re.finditer(r"\]\(([^)#\s]+\.md)(#[^)]*)?\)", body):
                if not m.group(1).startswith("http") and not (sub.parent / m.group(1)).exists():
                    r.err(rel(sub), f"link tương đối không tồn tại: {m.group(1)}")
            check_paths(r, rel(sub), body)
    return names


def _meta_block(src: str):
    m = re.search(r"export\s+const\s+meta\s*=\s*\{", src)
    if not m:
        return None, None
    i, depth = m.end() - 1, 0
    for j in range(i, len(src)):
        ch = src[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return m.start(), src[i:j + 1]
    return m.start(), None


def lint_workflows(r: Report, root: Path):
    wdir = root / ".claude" / "workflows"
    node = shutil.which("node")
    for f in sorted(wdir.glob("*.js")) if wdir.exists() else []:
        where = rel(f)
        src = f.read_text(encoding="utf-8")
        head = re.sub(r"^(\s|//[^\n]*\n|/\*.*?\*/)*", "", src, flags=re.S)
        if not head.startswith("export const meta"):
            r.err(where, "`export const meta = {…}` phải là câu lệnh đầu tiên")
        start, block = _meta_block(src)
        if block is None:
            r.err(where, "không tìm thấy/không đóng được khối meta")
            continue
        code = re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", "''", block)  # bỏ nội dung chuỗi
        if "`" in code or "..." in code or re.search(r"[A-Za-z_\])]\s*\(", code):
            r.err(where, "meta phải là literal thuần (không template, spread, gọi hàm)")
        name = re.search(r"\bname\s*:\s*'([^']+)'", block) or re.search(r'\bname\s*:\s*"([^"]+)"', block)
        if not name or name.group(1) != f.stem:
            r.err(where, f"meta.name phải = tên file `{f.stem}`")
        if not re.search(r"\bdescription\s*:", block):
            r.err(where, "meta thiếu description")
        titles = set(re.findall(r"title\s*:\s*'([^']+)'", block))
        body = src[start + len("export const meta = ") + len(block):]
        used = set(re.findall(r"\bphase\(\s*'([^']+)'\s*\)", body)) | set(re.findall(r"\bphase\s*:\s*'([^']+)'", body))
        for u in sorted(used - titles):
            r.warn(where, f"phase '{u}' dùng trong body nhưng không có trong meta.phases")
        for rx, msg in BAD_WF:
            if rx.search(body):
                r.err(where, f"dùng {msg}")
        if node:
            meta_src = src[start:start + len("export const meta = ") + len(block)].replace("export const", "const", 1)
            wrapped = meta_src + "\nasync function __workflow(agent, parallel, pipeline, phase, log, args, budget, workflow) {\n" + body + "\n}\n"
            with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as t:
                t.write(wrapped)
            try:
                p = subprocess.run([node, "--check", t.name], capture_output=True, text=True, timeout=30)
                if p.returncode != 0:
                    msg = (p.stderr.strip().splitlines() or ["?"])
                    r.err(where, "cú pháp JS lỗi: " + " | ".join(x for x in msg if "SyntaxError" in x or "^" not in x)[-300:])
            finally:
                Path(t.name).unlink(missing_ok=True)
        else:
            r.warn(where, "không có node — bỏ qua kiểm cú pháp")


def _agent_tiers(root: Path) -> dict:
    out = {}
    for f in sorted((root / ".claude" / "agents").glob("*.md")):
        fm, e = parse_frontmatter(f.read_text(encoding="utf-8"))
        if not e:
            out[f.stem] = (fm.get("model"), fm.get("effort"))
    return out


def lint_role_tiers(r: Report, root: Path):
    tiers = _agent_tiers(root)
    wdir = root / ".claude" / "workflows"
    for f in sorted(wdir.glob("*.js")) if wdir.exists() else []:
        src = f.read_text(encoding="utf-8")
        for block in TIER_BLOCK_RE.findall(src):
            for role, model, effort in TIER_ROW_RE.findall(block):
                if role not in tiers:
                    r.err(rel(f), f"ROLE_TIER có vai `{role}` không tồn tại trong .claude/agents/")
                elif tiers[role] != (model, effort):
                    r.err(rel(f), f"ROLE_TIER `{role}` = {model}/{effort} ≠ frontmatter {tiers[role][0]}/{tiers[role][1]}")


def lint_settings(r: Report, root: Path):
    f = root / ".claude" / "settings.json"
    if not f.exists():
        return
    try:
        s = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        r.err(rel(f), f"JSON lỗi: {e}")
        return
    for event, groups in (s.get("hooks") or {}).items():
        for g in groups:
            for h in g.get("hooks", []):
                cmd = h.get("command", "")
                for m in re.finditer(r"\$\{?CLAUDE_PROJECT_DIR\}?/([^\s\"']+)", cmd):
                    if not (root / m.group(1)).exists():
                        r.err(rel(f), f"hook {event} trỏ tới file không tồn tại: {m.group(1)}")


def lint_agent_memory(r: Report, root: Path, agents: set[str]):
    d = root / ".claude" / "agent-memory"
    if not d.exists():
        return
    for sub in sorted(p for p in d.iterdir() if p.is_dir()):
        if sub.name not in agents:
            r.err(rel(sub), "thư mục memory của agent không tồn tại")
        if not (sub / "MEMORY.md").exists():
            r.warn(rel(sub), "thiếu MEMORY.md")


def run(root: Path = ROOT) -> Report:
    r = Report()
    skills = lint_skills(r, root)
    agents = lint_agents(r, root, skills)
    lint_workflows(r, root)
    lint_role_tiers(r, root)
    lint_settings(r, root)
    lint_agent_memory(r, root, agents)
    return r


def main(argv=None) -> int:
    global ROOT
    ap = argparse.ArgumentParser(description="Lint harness .claude/")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args(argv)
    ROOT = Path(a.root)
    r = run(ROOT)
    for e in r.errors:
        print(f"LỖI  {e}")
    if not a.quiet:
        for w in r.warnings:
            print(f"cảnh báo  {w}")
        print(f"lint_harness: {len(r.errors)} lỗi, {len(r.warnings)} cảnh báo")
    return 1 if r.errors else 0


if __name__ == "__main__":
    sys.exit(main())
