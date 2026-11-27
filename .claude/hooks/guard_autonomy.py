#!/usr/bin/env python3
"""PreToolUse(Bash): cổng con người của nhà máy agent — lệnh đẩy/đăng/deploy prod/upload/merge ⇒ "ask".

Không bao giờ chặn cứng (user luôn Allow được). Lỗi nội bộ (VD module hỏng) mà lệnh có từ khoá rủi ro
(push/deploy/merge/release/upload…) ⇒ vẫn "ask" kèm lý do "guard lỗi" — fail-closed về hỏi, không fail-open im
lặng (factory-review 2026-11-06). Lệnh không có từ khoá ⇒ cho qua. JSON stdin hỏng ⇒ cho qua.
Logic + test: tools/factory/hooks_logic.py, tools/factory/test_hooks.py.
"""
import json
import os
import sys
from pathlib import Path

FALLBACK_WORDS = ("push", "deploy", "merge", "release", "altool", "notarytool", "upload", "wrangler", "firebase",
                  "bump_version", "exportarchive")


def emit(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason}}, ensure_ascii=False))


try:
    payload = json.load(sys.stdin)
    cmd = str(payload.get("tool_input", {}).get("command", ""))
except Exception:
    sys.exit(0)

root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
try:
    sys.path.insert(0, str(root / "tools" / "factory"))
    import hooks_logic  # noqa: E402
    res = hooks_logic.autonomy_decision(cmd, payload.get("cwd"))
except Exception as e:  # noqa: BLE001
    if any(w in cmd.casefold() for w in FALLBACK_WORDS):
        emit(f"guard_autonomy lỗi nội bộ ({type(e).__name__}) — không phân tích được lệnh có từ khoá rủi ro; "
             "chỉ Allow nếu bạn đã đồng ý việc này.")
    sys.exit(0)
if res:
    emit(res[1])
sys.exit(0)
