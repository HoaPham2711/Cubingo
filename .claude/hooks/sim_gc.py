#!/usr/bin/env python3
"""SessionStart / WorktreeRemove: dọn simulator `factory-*` của worktree đã xoá, sim không dùng > 24 giờ,
và tắt bớt sim nhàn ≥ 30 phút khi quá 4 sim đang boot. Giữ nguyên sim của worktree phiên này.

Chạy NỀN (tách tiến trình) để không làm chậm lúc mở phiên; lỗi bất kỳ ⇒ im lặng (exit 0). Không in gì vào
context. Logic + test: tools/dev/sim_pool.py, tools/dev/test_sim_pool.py.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    payload = json.load(sys.stdin)
except Exception:
    payload = {}
root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
script = root / "tools" / "dev" / "sim_pool.py"
if not script.exists():
    sys.exit(0)
keep = str(root)  # gốc worktree (sim_pool đặt tên theo gốc repo, không theo thư mục con của cwd)
try:
    subprocess.Popen([sys.executable, str(script), "gc", "--keep-repo", keep],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
except Exception:
    pass
sys.exit(0)
