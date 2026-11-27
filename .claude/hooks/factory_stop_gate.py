#!/usr/bin/env python3
"""Stop: phiên giám đốc của một mission autopilot chưa đạt DoD ⇒ chặn dừng, nhắc task kế tiếp.

"Khi nào xong thì thôi" — nhưng không bao giờ kẹt vòng: cho dừng khi mission có cổng chờ user,
mission blocked, hoặc đã chặn 3 lần liên tiếp mà ledger không đổi.
Chỉ áp cho phiên mà transcript có nhắc mã mission (= phiên đã chạy mission.py cho mission đó).
Logic + test: tools/factory/hooks_logic.py, tools/factory/test_hooks.py. Lỗi ⇒ cho dừng (exit 0).
"""
import json
import os
import sys
from pathlib import Path

root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
try:
    payload = json.load(sys.stdin)
    sys.path.insert(0, str(root / "tools" / "factory"))
    import hooks_logic  # noqa: E402
    res = hooks_logic.stop_decision(payload)
except Exception:
    sys.exit(0)
if res:
    print(json.dumps(res, ensure_ascii=False))
sys.exit(0)
