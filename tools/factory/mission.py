#!/usr/bin/env python3
"""Ledger của nhà máy agent — trạng thái mission nằm ở FILE, không ở hội thoại.

Cách dùng trong nhà máy: skill `factory` (.claude/skills/factory/SKILL.md); lịch sử thiết kế nằm ở repo template.

    python3 tools/factory/mission.py new --goal "…" --playbook feature [--slug x] [--dod "…"]…
    python3 tools/factory/mission.py add-task --title "…" --role ios-engineer \
        --accept "tiêu chí kiểm được" [--verify "lệnh"] [--depends T1]
    python3 tools/factory/mission.py set T1 --status doing
    python3 tools/factory/mission.py set T1 --status verified --by factory-verifier --evidence "…"
    python3 tools/factory/mission.py gate open --kind push --ask "Push develop?"
    python3 tools/factory/mission.py set T1 --status failed --fail-class preview-state --note "…"
    python3 tools/factory/mission.py tick [n] --what "verifier T1 vòng 2"
    python3 tools/factory/mission.py budget --set 30 --why "plan thêm 4 task iOS"
    python3 tools/factory/mission.py gate approve G1
    python3 tools/factory/mission.py next | show [--json] | list [--all] | check | close [--abandon "…"]

Mặc định thao tác trên mission ACTIVE duy nhất; có nhiều ⇒ `--mission <id>`.
Gốc repo = 2 cấp trên file này; test đổi bằng biến môi trường FACTORY_ROOT.

Luật nằm trong code (không trông vào kỷ luật của model — research: JSON + luật cứng ít bị "viết đè"):
- `verified` cần ≥1 evidence và `--by` là `factory-verifier` hoặc `director`;
- `failed` ⇒ attempts+1; attempts ≥ MAX_ATTEMPTS ⇒ tự chuyển `blocked`;
- `failed` qua CLI bắt buộc `--fail-class`; cùng lớp FAIL lần ESCALATE_AFTER ⇒ cờ `escalate` (đổi cách, đừng vá);
- `tick` đếm lượt agent so với `--budget` của `new`; vượt = mốc XÉT LẠI (có lặp không?), KHÔNG phải trần — việc
  thật sự lớn hơn ước tính ⇒ `budget --set N --why` (ghi lịch sử), không cắt việc;
- `close` nhắc commit hồ sơ mission (`FACTORY-UNTRACKED`): mission.json/plan.json/report.md thuộc git theo thiết
  kế, chỉ `artifacts/` bị .gitignore;
- `close` từ chối khi `check` chưa đạt (trừ `--abandon "<lý do>"`).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = 1
PLAYBOOKS = ("feature", "fix", "research", "growth", "analytics", "release", "ops")
TASK_STATUSES = ("todo", "doing", "review", "verified", "failed", "blocked", "skipped")
DONE_STATUSES = ("verified", "skipped")
GATE_KINDS = ("push", "deploy", "asc", "spend", "device", "send", "decision", "publish", "delete")
VERIFIERS = ("factory-verifier", "director")
# Trần 2 lần FAIL (vòng FAIL lặp lại là nguồn tốn chi phí lớn nhất) ⇒ blocked, giám đốc đổi cách/hỏi user.
MAX_ATTEMPTS = 2
# Cùng một lớp lỗi FAIL lần thứ 2 ⇒ ngừng vá từng lỗ, đổi cách (bất biến + test thuộc tính, thu hẹp, hỏi user).
ESCALATE_AFTER = 2
MISSION_STATUSES = ("active", "blocked", "done", "abandoned")
# Dấu "phiên này là giám đốc" — CHỈ `new` và `claim` in ra. Hook Stop tìm dấu này trong transcript của phiên.
# Không bao giờ in nó ở summary()/SessionStart: nếu SessionStart in mã mission vào
# transcript MỌI phiên ⇒ phiên lạ bị chặn dừng nếu chỉ tìm mã mission trần.
DIRECTOR_MARK = "FACTORY-DIRECTOR"


def director_mark(mid: str) -> str:
    return f"{DIRECTOR_MARK} {mid} :: phiên này là giám đốc"


class LedgerError(Exception):
    """Lỗi người dùng (sai lệnh/vi phạm luật) — in ra stderr, exit 2."""


# ----------------------------------------------------------------- đường dẫn + IO

def repo_root() -> Path:
    env = os.environ.get("FACTORY_ROOT")
    return Path(env) if env else Path(__file__).resolve().parents[2]


def missions_dir() -> Path:
    return repo_root() / ".factory" / "missions"


def now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def slugify(text: str, limit: int = 40) -> str:
    s = text.casefold()
    # bỏ dấu tiếng Việt thô (đủ cho slug thư mục)
    table = str.maketrans("àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ",
                          "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd")
    s = s.translate(table)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:limit].rstrip("-")) or "mission"


def mission_path(mid: str) -> Path:
    return missions_dir() / mid / "mission.json"


def load(mid: str) -> dict:
    p = mission_path(mid)
    if not p.exists():
        raise LedgerError(f"không có mission '{mid}' ({p})")
    return json.loads(p.read_text(encoding="utf-8"))


def save(m: dict) -> None:
    m["updated"] = now()
    p = mission_path(m["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".mission-", suffix=".json", dir=str(p.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, p)


def all_missions() -> list[dict]:
    d = missions_dir()
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*/mission.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def active_missions() -> list[dict]:
    return [m for m in all_missions() if m.get("status") in ("active", "blocked")]


def resolve(mid: str | None) -> dict:
    if mid:
        return load(mid)
    act = [m for m in all_missions() if m.get("status") == "active"]
    if len(act) == 1:
        return act[0]
    if not act:
        raise LedgerError("không có mission active — chỉ định --mission <id> hoặc tạo bằng `new`")
    raise LedgerError("có nhiều mission active: " + ", ".join(m["id"] for m in act) + " — dùng --mission")


def add_log(m: dict, msg: str) -> None:
    m.setdefault("log", []).append({"at": now(), "msg": msg})


def find_task(m: dict, tid: str) -> dict:
    for t in m.get("tasks", []):
        if t["id"] == tid:
            return t
    raise LedgerError(f"mission {m['id']} không có task {tid}")


# ----------------------------------------------------------------- logic thuần (test được)

def new_mission(goal: str, playbook: str, slug: str | None = None, branch: str = "",
                dod: list[str] | None = None, autopilot: bool = True, today: str | None = None,
                budget: int | None = None) -> dict:
    if playbook not in PLAYBOOKS:
        raise LedgerError(f"playbook phải thuộc {PLAYBOOKS}")
    if not goal.strip():
        raise LedgerError("goal rỗng")
    day = today or _dt.date.today().isoformat()
    base = f"{day}-{slugify(slug or goal)}"
    mid, n = base, 2
    while mission_path(mid).exists():
        mid, n = f"{base}-{n}", n + 1
    m = {"schema": SCHEMA, "id": mid, "goal": goal.strip(), "playbook": playbook,
         "status": "active", "autopilot": autopilot, "branch": branch, "dod": list(dod or []),
         "created": now(), "updated": now(), "tasks": [], "gates": [], "stop_blocks": {}, "log": [],
         "budget": budget, "agent_runs": 0}
    add_log(m, "tạo mission" + (f", ngân sách {budget} lượt agent" if budget else ""))
    return m


def add_task(m: dict, title: str, role: str, accept: list[str], verify: list[str] | None = None,
             depends: list[str] | None = None, tid: str | None = None) -> dict:
    if not accept:
        raise LedgerError("task phải có ít nhất một --accept (tiêu chí kiểm được)")
    ids = {t["id"] for t in m["tasks"]}
    for d in depends or []:
        if d not in ids:
            raise LedgerError(f"phụ thuộc {d} chưa có trong mission")
    if tid is None:
        k = len(m["tasks"]) + 1
        while f"T{k}" in ids:
            k += 1
        tid = f"T{k}"
    elif tid in ids:
        raise LedgerError(f"task {tid} đã tồn tại")
    t = {"id": tid, "title": title, "role": role, "depends": list(depends or []),
         "acceptance": list(accept), "verify": list(verify or []), "status": "todo",
         "attempts": 0, "evidence": [], "notes": ""}
    m["tasks"].append(t)
    add_log(m, f"thêm {tid} ({role}): {title}")
    return t


def set_status(m: dict, tid: str, status: str, evidence: list[str] | None = None,
               by: str | None = None, note: str | None = None,
               fail_class: list[str] | None = None) -> dict:
    if status not in TASK_STATUSES:
        raise LedgerError(f"status phải thuộc {TASK_STATUSES}")
    t = find_task(m, tid)
    ev = [e for e in (evidence or []) if e.strip()]
    if status == "verified":
        if by not in VERIFIERS:
            raise LedgerError("chỉ factory-verifier (hoặc director cho task không code) được đánh verified — dùng --by")
        if not ev and not t["evidence"]:
            raise LedgerError("verified cần ít nhất một --evidence (lệnh đã chạy + kết quả)")
        unmet = [d for d in t["depends"] if find_task(m, d)["status"] not in DONE_STATUSES]
        if unmet:
            raise LedgerError(f"{tid} còn phụ thuộc chưa xong: {', '.join(unmet)}")
    if status == "skipped" and not (note and note.strip()):
        raise LedgerError("skipped cần --note lý do")
    t["evidence"].extend(ev)
    if note:
        t["notes"] = (t["notes"] + "\n" if t["notes"] else "") + note
    t.pop("escalate", None)
    if status == "failed":
        t["attempts"] += 1
        counts = t.setdefault("fail_classes", {})
        hot = []
        for c in dict.fromkeys(x.strip() for x in (fail_class or []) if x.strip()):
            counts[c] = counts.get(c, 0) + 1
            if counts[c] >= ESCALATE_AFTER:
                hot.append(c)
        if hot:
            t["escalate"] = hot
            add_log(m, f"{tid} ESCALATE: lớp {', '.join(hot)} FAIL lần {ESCALATE_AFTER}+ — ngừng vá từng lỗ, đổi cách")
        if t["attempts"] >= MAX_ATTEMPTS:
            status = "blocked"
            add_log(m, f"{tid} FAIL lần {t['attempts']} ⇒ blocked (cần giám đốc/user quyết)")
    t["status"] = status
    add_log(m, f"{tid} → {status}" + (f" (by {by})" if by else ""))
    # trạng thái mission đi theo task blocked / gate mở
    m["status"] = derive_status(m)
    m["stop_blocks"] = {}
    return t


def derive_status(m: dict) -> str:
    if m["status"] in ("done", "abandoned"):
        return m["status"]
    if any(t["status"] == "blocked" for t in m["tasks"]):
        return "blocked"
    return "active"


def open_gate(m: dict, kind: str, ask: str) -> dict:
    if kind not in GATE_KINDS:
        raise LedgerError(f"kind phải thuộc {GATE_KINDS}")
    if not ask.strip():
        raise LedgerError("gate cần --ask (một câu hỏi cho user)")
    g = {"id": f"G{len(m['gates']) + 1}", "kind": kind, "ask": ask.strip(), "status": "open",
         "opened": now()}
    m["gates"].append(g)
    add_log(m, f"mở cổng {g['id']} [{kind}]: {ask}")
    m["stop_blocks"] = {}
    return g


def resolve_gate(m: dict, gid: str, approve: bool, note: str = "") -> dict:
    for g in m["gates"]:
        if g["id"] == gid:
            if g["status"] != "open":
                raise LedgerError(f"{gid} đã {g['status']}")
            g["status"] = "approved" if approve else "rejected"
            g["closed"] = now()
            if note:
                g["note"] = note
            add_log(m, f"cổng {gid} → {g['status']}" + (f": {note}" if note else ""))
            m["stop_blocks"] = {}
            return g
    raise LedgerError(f"không có cổng {gid}")


def amend(m: dict, what: str, index: int, text: str, why: str, task: str | None = None) -> None:
    """Sửa một mục DoD (`what='dod'`) hoặc một tiêu chí của task (`what='accept'`, cần `task`), đánh số từ 1.
    Bắt buộc có lý do; bản cũ + lý do ghi vào log — đổi tiêu chí giữa chừng không được lặng lẽ."""
    if not (why and why.strip()):
        raise LedgerError("amend cần --why (vì sao đổi tiêu chí)")
    if what == "dod":
        lst, label = m["dod"], "DoD"
    elif what == "accept":
        if not task:
            raise LedgerError("amend accept cần id task")
        lst, label = find_task(m, task)["acceptance"], f"{task}.accept"
    else:
        raise LedgerError("amend: chỉ 'dod' hoặc 'accept'")
    if not 1 <= index <= len(lst):
        raise LedgerError(f"{label} không có mục {index} (có {len(lst)})")
    old = lst[index - 1]
    lst[index - 1] = text.strip()
    add_log(m, f"amend {label}[{index}]: {old!r} → {text.strip()!r} — vì: {why.strip()}")
    m["stop_blocks"] = {}


def ready_tasks(m: dict) -> list[dict]:
    """Task có thể làm tiếp: chưa xong/không blocked và mọi phụ thuộc đã xong."""
    done = {t["id"] for t in m["tasks"] if t["status"] in DONE_STATUSES}
    return [t for t in m["tasks"]
            if t["status"] in ("todo", "doing", "review", "failed") and all(d in done for d in t["depends"])]


def check(m: dict) -> list[str]:
    """Danh sách lý do CHƯA xong (rỗng = đạt DoD của ledger)."""
    problems = []
    if not m["tasks"]:
        problems.append("mission chưa có task nào")
    for t in m["tasks"]:
        if t["status"] not in DONE_STATUSES:
            problems.append(f"{t['id']} [{t['status']}] {t['title']}")
        elif t["status"] == "verified" and not t["evidence"]:
            problems.append(f"{t['id']} verified mà không có evidence")
    for g in m["gates"]:
        if g["status"] == "open":
            problems.append(f"cổng {g['id']} [{g['kind']}] đang chờ user: {g['ask']}")
    return problems


def tick(m: dict, n: int = 1, what: str = "") -> bool:
    """Đếm lượt agent đã chạy. Trả True đúng lần đầu vượt ngân sách (giám đốc phải dừng lại xét)."""
    if n < 1:
        raise LedgerError("tick cần n ≥ 1")
    before = m.get("agent_runs", 0)
    m["agent_runs"] = before + n
    b = m.get("budget")
    if what:
        add_log(m, f"agent +{n}: {what}")
    if b and before <= b < m["agent_runs"]:
        add_log(m, f"VƯỢT NGÂN SÁCH: {m['agent_runs']}/{b} lượt agent")
        return True
    return False


def set_budget(m: dict, n: int, why: str) -> None:
    """Đổi ngân sách khi phạm vi thật lớn hơn ước tính — có lý do, giữ lịch sử. Vượt lại mốc mới ⇒ `tick` báo lần nữa."""
    if n < 1:
        raise LedgerError("ngân sách phải ≥ 1")
    if not why.strip():
        raise LedgerError("budget --set cần --why (vì sao phạm vi lớn hơn ước tính)")
    old = m.get("budget")
    m.setdefault("budget_history", []).append({"at": now(), "from": old, "to": n, "runs": m.get("agent_runs", 0),
                                               "why": why})
    m["budget"] = n
    add_log(m, f"ngân sách {old} → {n} (đã chạy {m.get('agent_runs', 0)}): {why}")


def uncommitted_files(mid: str) -> list[str] | None:
    """File hồ sơ mission chưa commit (untracked/sửa) — None nếu không đọc được git. `artifacts/` đã bị .gitignore."""
    rel = f".factory/missions/{mid}"
    try:
        # Bỏ GIT_DIR/GIT_INDEX_FILE/GIT_WORK_TREE kế thừa (hook git đặt chúng) — nếu không, `-C` vẫn bị GIT_DIR
        # kéo về repo khác. Sự cố 2026-11-07: test chạy trong pre-commit ghi đè config repo thật.
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        p = subprocess.run(["git", "-C", str(repo_root()), "status", "--porcelain", "--untracked-files=all", "--", rel],
                           capture_output=True, text=True, timeout=20, env=env)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return [ln[3:].strip() for ln in p.stdout.splitlines() if ln.strip()]


def budget_line(m: dict) -> str:
    runs, b = m.get("agent_runs", 0), m.get("budget")
    if not b:
        return f"Agent: {runs} lượt (chưa đặt ngân sách)"
    return f"Agent: {runs}/{b} lượt" + (" — VƯỢT NGÂN SÁCH" if runs > b else "")


def close(m: dict, abandon: str | None = None) -> None:
    if abandon is not None:
        if not abandon.strip():
            raise LedgerError("--abandon cần lý do")
        m["status"] = "abandoned"
        add_log(m, f"bỏ mission: {abandon}")
        return
    probs = check(m)
    if probs:
        raise LedgerError("chưa đạt DoD, không close được:\n  - " + "\n  - ".join(probs))
    m["status"] = "done"
    add_log(m, "close: đạt DoD")


def summary(m: dict, limit: int = 1500) -> str:
    """Tóm tắt ngắn cho hook SessionStart / Stop."""
    counts: dict[str, int] = {}
    for t in m["tasks"]:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    lines = [f"Mission {m['id']} [{m['status']}{', autopilot' if m.get('autopilot') else ''}] "
             f"playbook={m['playbook']}: {m['goal']}",
             "Task: " + (", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "chưa có"),
             budget_line(m)]
    nxt = ready_tasks(m)
    if nxt:
        lines.append("Kế tiếp: " + "; ".join(f"{t['id']} ({t['role']}) {t['title']}" for t in nxt[:3]))
    opened = [g for g in m["gates"] if g["status"] == "open"]
    if opened:
        lines.append("Cổng đang chờ user: " + "; ".join(f"{g['id']} {g['ask']}" for g in opened))
    esc = [t for t in m["tasks"] if t.get("escalate")]
    if esc:
        lines.append("ESCALATE (đổi cách, đừng vá tiếp): " + "; ".join(f"{t['id']} lớp {','.join(t['escalate'])}" for t in esc))
    blocked = [t for t in m["tasks"] if t["status"] == "blocked"]
    if blocked:
        lines.append("Blocked: " + "; ".join(f"{t['id']} {t['title']}" for t in blocked))
    lines.append(f"Ledger: python3 tools/factory/mission.py show --mission {m['id']}")
    s = "\n".join(lines)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def render(m: dict) -> str:
    out = [f"# {m['id']}  [{m['status']}]  playbook={m['playbook']}  autopilot={m.get('autopilot')}",
           f"Mục tiêu: {m['goal']}"]
    if m.get("branch"):
        out.append(f"Nhánh: {m['branch']}")
    if m["dod"]:
        out.append("DoD:")
        out += [f"  - {d}" for d in m["dod"]]
    out.append("Task:")
    for t in m["tasks"]:
        dep = f" ← {','.join(t['depends'])}" if t["depends"] else ""
        out.append(f"  {t['id']} [{t['status']}] ({t['role']}) {t['title']}{dep}"
                   + (f"  attempts={t['attempts']}" if t["attempts"] else "")
                   + (f"  ESCALATE={','.join(t['escalate'])}" if t.get("escalate") else ""))
        for a in t["acceptance"]:
            out.append(f"      ✓? {a}")
        for e in t["evidence"]:
            out.append(f"      ⮑ {e}")
    if m["gates"]:
        out.append("Cổng:")
        out += [f"  {g['id']} [{g['kind']}/{g['status']}] {g['ask']}" for g in m["gates"]]
    out.append(budget_line(m))
    probs = check(m)
    out.append("DoD ledger: " + ("ĐẠT" if not probs else f"chưa ({len(probs)} mục)"))
    return "\n".join(out)


# ----------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ledger nhà máy agent (.factory/missions)")
    ap.add_argument("--mission", help="id mission (mặc định: mission active duy nhất)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mission", default=argparse.SUPPRESS, help="id mission (đặt trước hoặc sau lệnh con đều được)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", parents=[common])
    p.add_argument("--goal", required=True)
    p.add_argument("--playbook", required=True, choices=PLAYBOOKS)
    p.add_argument("--slug")
    p.add_argument("--branch", default="")
    p.add_argument("--dod", action="append", default=[])
    p.add_argument("--no-autopilot", action="store_true")
    p.add_argument("--budget", type=int, help="ngân sách lượt agent (ước: số task × 2,5 + 4)")

    p = sub.add_parser("add-task", parents=[common])
    p.add_argument("--title", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--accept", action="append", default=[])
    p.add_argument("--verify", action="append", default=[])
    p.add_argument("--depends", action="append", default=[])
    p.add_argument("--id")

    p = sub.add_parser("set", parents=[common])
    p.add_argument("task")
    p.add_argument("--status", required=True, choices=TASK_STATUSES)
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--by")
    p.add_argument("--note")
    p.add_argument("--fail-class", action="append", default=[],
                   help="lớp lỗi (slug) của FAIL này, vd preview-state; bắt buộc khi --status failed")

    p = sub.add_parser("gate", parents=[common])
    p.add_argument("action", choices=("open", "approve", "reject"))
    p.add_argument("gate", nargs="?")
    p.add_argument("--kind", choices=GATE_KINDS)
    p.add_argument("--ask", default="")
    p.add_argument("--note", default="")

    p = sub.add_parser("log", parents=[common])
    p.add_argument("msg")

    p = sub.add_parser("tick", parents=[common], help="đếm lượt agent vừa chạy (giám đốc gọi sau mỗi Agent)")
    p.add_argument("n", nargs="?", type=int, default=1)
    p.add_argument("--what", default="", help="vai + task, vd 'verifier T3 vòng 2'")

    p = sub.add_parser("budget", parents=[common], help="đổi ngân sách lượt agent khi phạm vi lớn hơn ước tính")
    p.add_argument("--set", type=int, required=True, dest="n")
    p.add_argument("--why", required=True)

    p = sub.add_parser("show", parents=[common])
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("list", parents=[common])
    p.add_argument("--all", action="store_true")
    sub.add_parser("next", parents=[common])
    sub.add_parser("check", parents=[common])
    p = sub.add_parser("close", parents=[common])
    p.add_argument("--abandon")
    p = sub.add_parser("active", parents=[common])
    p.add_argument("--json", action="store_true")
    sub.add_parser("claim", parents=[common])
    p = sub.add_parser("amend", parents=[common])
    p.add_argument("what", choices=("dod", "accept"))
    p.add_argument("pos", nargs="+", help="dod: <số>; accept: <task> <số>")
    p.add_argument("--text", required=True)
    p.add_argument("--why", required=True)

    a = ap.parse_args(argv)
    try:
        if a.cmd == "new":
            m = new_mission(a.goal, a.playbook, a.slug, a.branch, a.dod, not a.no_autopilot, budget=a.budget)
            save(m)
            print(f"FACTORY-MISSION {m['id']} tạo xong → {mission_path(m['id'])}")
            print(director_mark(m["id"]))
            return 0
        if a.cmd == "claim":
            m = resolve(a.mission)
            add_log(m, "một phiên nhận làm giám đốc (claim)")
            save(m)
            print(director_mark(m["id"]))
            return 0
        if a.cmd == "list":
            ms = all_missions() if a.all else active_missions()
            for m in ms:
                n_done = sum(t["status"] in DONE_STATUSES for t in m["tasks"])
                print(f"{m['id']}  [{m['status']}]  {n_done}/{len(m['tasks'])} task  {m['goal'][:70]}")
            if not ms:
                print("(không có mission" + ("" if a.all else " active") + ")")
            return 0
        if a.cmd == "active":
            ms = active_missions()
            if a.json:
                print(json.dumps([{"id": m["id"], "status": m["status"], "autopilot": m.get("autopilot"),
                                   "summary": summary(m)} for m in ms], ensure_ascii=False))
            else:
                print("\n\n".join(summary(m) for m in ms) or "(không có mission active)")
            return 0

        m = resolve(a.mission)
        if a.cmd == "show":
            print(json.dumps(m, ensure_ascii=False, indent=2) if a.json else render(m))
            return 0
        if a.cmd == "next":
            nxt = ready_tasks(m)
            for t in nxt:
                print(f"{t['id']} ({t['role']}) [{t['status']}] {t['title']}")
            if not nxt:
                print("(không có task sẵn sàng)" + (" — " + "; ".join(check(m)) if check(m) else " — DoD đạt, chạy `close`"))
            return 0
        if a.cmd == "check":
            probs = check(m)
            if probs:
                print(f"FACTORY-MISSION {m['id']} CHƯA xong:")
                print("\n".join(f"  - {x}" for x in probs))
                return 1
            print(f"FACTORY-MISSION {m['id']} đạt DoD ledger (mọi task verified/skipped, không cổng mở)")
            return 0
        if a.cmd == "add-task":
            t = add_task(m, a.title, a.role, a.accept, a.verify, a.depends, a.id)
            save(m)
            print(f"FACTORY-MISSION {m['id']}: thêm {t['id']}")
            return 0
        if a.cmd == "set":
            if a.status == "failed" and not any(c.strip() for c in a.fail_class):
                raise LedgerError("--status failed cần --fail-class <lớp lỗi> (lấy từ findings[].class của verifier)")
            t = set_status(m, a.task, a.status, a.evidence, a.by, a.note, a.fail_class)
            save(m)
            print(f"FACTORY-MISSION {m['id']}: {t['id']} → {t['status']}"
                  + (f" (attempts={t['attempts']})" if t["attempts"] else ""))
            if t.get("escalate"):
                print(f"FACTORY-ESCALATE {t['id']}: lớp {', '.join(t['escalate'])} đã FAIL {ESCALATE_AFTER} lần. "
                      "KHÔNG gửi thợ vá tiếp. Chọn một: (a) viết lại tiêu chí thành BẤT BIẾN + test thuộc tính/fuzz "
                      "phủ cả lớp, (b) thu hẹp phạm vi task, (c) mở cổng decision hỏi user.")
            if a.status in ("doing", "review") and m.get("budget") and m.get("agent_runs", 0) > m["budget"]:
                print(f"FACTORY-BUDGET {budget_line(m)} — ghi lý do bằng `log` trước khi giao tiếp.")
            return 0
        if a.cmd == "tick":
            over = tick(m, a.n, a.what)
            save(m)
            print(f"FACTORY-MISSION {m['id']}: {budget_line(m)}")
            if over:
                print("FACTORY-BUDGET vừa vượt ngân sách — mốc XÉT LẠI, không phải trần: task nào đang lặp cùng lớp lỗi? "
                      "Có ⇒ đổi cách (escalate). Không, chỉ là phạm vi lớn hơn ước tính ⇒ "
                      "`mission.py budget --set <N> --why \"…\"` rồi làm tiếp, KHÔNG cắt việc.")
            return 0
        if a.cmd == "budget":
            set_budget(m, a.n, a.why)
            save(m)
            print(f"FACTORY-MISSION {m['id']}: {budget_line(m)}")
            return 0
        if a.cmd == "gate":
            if a.action == "open":
                if not a.kind:
                    raise LedgerError("gate open cần --kind")
                g = open_gate(m, a.kind, a.ask)
            else:
                if not a.gate:
                    raise LedgerError("cần id cổng (G1…)")
                g = resolve_gate(m, a.gate, a.action == "approve", a.note)
            save(m)
            print(f"FACTORY-MISSION {m['id']}: cổng {g['id']} [{g['status']}]")
            return 0
        if a.cmd == "amend":
            try:
                if a.what == "dod":
                    task, idx = None, int(a.pos[0])
                else:
                    task, idx = a.pos[0], int(a.pos[1])
            except (IndexError, ValueError):
                raise LedgerError("amend dod <số> | amend accept <task> <số>")
            amend(m, a.what, idx, a.text, a.why, task)
            save(m)
            print(f"FACTORY-MISSION {m['id']}: đã sửa {a.what} {' '.join(a.pos)}")
            return 0
        if a.cmd == "log":
            add_log(m, a.msg)
            save(m)
            print(f"FACTORY-MISSION {m['id']}: đã ghi log")
            return 0
        if a.cmd == "close":
            close(m, a.abandon)
            save(m)
            print(f"FACTORY-MISSION {m['id']} → {m['status']}")
            left = uncommitted_files(m["id"])
            if left:
                print(f"FACTORY-UNTRACKED hồ sơ mission chưa commit ({', '.join(left)}). Theo thiết kế nó thuộc git: "
                      f"`git add .factory/missions/{m['id']}` (artifacts/ đã bị .gitignore) và commit cùng commit cuối "
                      "của nhánh mission, TRƯỚC khi mở PR/merge.")
            return 0
    except LedgerError as e:
        print(f"mission.py: {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
