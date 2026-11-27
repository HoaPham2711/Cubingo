#!/usr/bin/env python3
"""PreToolUse(Bash): chặn chạy test ở config/scheme của bản STORE.

Test chỉ được chạy ở Debug — không bao giờ ở Release hay scheme Store. Config Release và scheme Store
mang bundle id Store — app host của test khi đó trỏ vào app record THẬT trên App Store Connect,
StoreKit gọi sandbox thật và bật hộp thoại "Sign in to Apple Account" làm treo cả suite.

Chỉ chặn action TEST (`test`, `build-for-testing`, `test-without-building`); `build`/`archive`
Release vẫn hợp lệ (verify_catalog, archive App Store). Exit 2 = chặn, stderr trả về cho Claude.
Tên scheme Store lấy từ `appconfig.STORE_SCHEME`; nạp appconfig lỗi ⇒ dùng mẫu chung "<tên>-Store"
(vẫn chặn, không crash phiên).
"""
import json
import os
import re
import sys
from pathlib import Path

TEST_ACTION = re.compile(r"(?<![\w-])(test|build-for-testing|test-without-building)(?![\w-])")
RELEASE_CFG = re.compile(r"-configuration[\s=]+['\"]?Release\b")

root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
try:
    sys.path.insert(0, str(root / "tools" / "common"))
    import appconfig  # noqa: E402
    store_scheme, test_scheme = re.escape(appconfig.STORE_SCHEME), appconfig.SCHEME
except Exception:  # noqa: BLE001
    store_scheme, test_scheme = r"[\w.]+-Store", "scheme thường (không hậu tố -Store)"
STORE_SCHEME = re.compile(r"-scheme[\s=]+['\"]?" + store_scheme + r"(?![\w-])")

try:
    cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
except Exception:
    sys.exit(0)

# Tách theo toán tử shell để một lệnh build Release đứng cạnh một lệnh test Debug không bị bắt nhầm.
for part in re.split(r"&&|\|\||;|\n", cmd):
    if "xcodebuild" not in part or not TEST_ACTION.search(part):
        continue
    if RELEASE_CFG.search(part) or STORE_SCHEME.search(part):
        sys.stderr.write(
            "BLOCKED: không chạy test ở config Release / scheme Store (bundle id Store → StoreKit "
            "sandbox thật → hộp thoại đăng nhập treo test). Dùng " + test_scheme + " với "
            "-configuration Debug — chạy test bằng tools/dev/run_tests.py.\n")
        sys.exit(2)
sys.exit(0)
