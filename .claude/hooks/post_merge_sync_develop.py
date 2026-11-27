#!/usr/bin/env python3
"""PostToolUse(Bash): sau `gh pr merge` ⇒ kéo `develop` local lên khớp `origin/develop` (nhà máy agent).

Không phụ thuộc trí nhớ của phiên: merge xong là develop ở checkout chính tự fast-forward, worktree/phiên
mới rẽ từ develop mới. Logic + test ở `tools/dev/sync_develop.py` (chỉ fast-forward, không stash/reset; không
cập nhật được thì báo lý do). Kết quả trả về Claude qua `additionalContext` — Claude phải nói lại cho user khi
FAIL. Không bao giờ chặn (PostToolUse); lỗi nội bộ ⇒ im lặng thoát 0.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MERGE = re.compile(r"(?<![\w-])gh\s+pr\s+merge(?![\w-])")

try:
    payload = json.load(sys.stdin)
    cmd = str(payload.get("tool_input", {}).get("command", ""))
except Exception:
    sys.exit(0)
if not MERGE.search(cmd):
    sys.exit(0)

root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")
script = root / "tools" / "dev" / "sync_develop.py"
if not script.exists():
    sys.exit(0)
try:
    r = subprocess.run([sys.executable, str(script), "--repo", str(root)], capture_output=True, text=True,
                       timeout=60)
    msg = (r.stdout or r.stderr).strip() or f"SYNC-DEVELOP FAIL: rc={r.returncode}"
except Exception as e:  # timeout, …
    msg = f"SYNC-DEVELOP FAIL: {e}"
note = "" if msg.startswith("SYNC-DEVELOP OK") else " — báo user, KHÔNG stash/reset hộ."
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": f"[post-merge] {msg}{note}"}}, ensure_ascii=False))
sys.exit(0)
