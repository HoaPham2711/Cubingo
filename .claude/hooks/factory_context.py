#!/usr/bin/env python3
"""SessionStart (startup|resume|compact): có mission đang mở ⇒ in tóm tắt ≤1500 ký tự vào context,
để phiên sau compact/resume không mất mạch (trạng thái thật nằm ở ledger .factory/missions).
Logic + test: tools/factory/hooks_logic.py. Lỗi ⇒ im lặng (exit 0).

Thêm: repo có `.githooks/` mà `git config core.hooksPath` khác `.githooks` ⇒ in MỘT dòng cảnh báo kèm lệnh đặt — khi
chưa đặt thì pre-commit (lint, cổng lệch lõi ở app) không chạy. Đặt rồi ⇒ im lặng. Không bao giờ làm hook thất bại.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def hooks_path_warning(repo: Path):
    """Dòng cảnh báo khi repo có `.githooks/pre-commit` mà core.hooksPath chưa trỏ `.githooks`; ngược lại None."""
    if not (repo / ".githooks" / "pre-commit").is_file():
        return None
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    base = ["git", "--no-optional-locks", "-C", str(repo)]
    top = subprocess.run(base + ["rev-parse", "--show-toplevel"], capture_output=True, text=True, env=env, timeout=10)
    if top.returncode != 0:
        return None
    r = subprocess.run(base + ["config", "--get", "core.hooksPath"], capture_output=True, text=True, env=env,
                       timeout=10)
    value = r.stdout.strip() if r.returncode == 0 else ""
    if value.rstrip("/") in (".githooks", str(repo / ".githooks")):
        return None
    now = f"'{value}'" if value else "chưa đặt"
    return (f"[hooks] core.hooksPath {now}, không phải .githooks — pre-commit (lint, cổng lệch lõi) KHÔNG chạy. "
            f"Nhờ người dùng chạy (agent không đặt được — hook chặn lệnh này): git config core.hooksPath .githooks")


warning = None
try:
    warning = hooks_path_warning(root)
except Exception:
    warning = None

text = None
try:
    payload = json.load(sys.stdin)
    sys.path.insert(0, str(root / "tools" / "factory"))
    import hooks_logic  # noqa: E402
    text = hooks_logic.session_context(payload)
except Exception:
    text = None
if warning:
    print(warning)
if text:
    print(text)
sys.exit(0)
