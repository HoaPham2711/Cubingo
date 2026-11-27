#!/usr/bin/env python3
"""Lint định danh: không file nào được mang literal định danh ngoài file cấu hình.

Hai luật, chạy trên các file text trong `git ls-files`:
  (a) cấm bốn từ của repo nguồn (không phân biệt hoa thường), trừ docs/superpowers/
      và docs/decisions/ (tài liệu thiết kế buộc phải nhắc app nguồn). Ở APP (repo không track
      tools/template/new_app.py), từ cấm nằm trong bundle.store/bundle.internal/apple.team_id của chính app được
      miễn — app cùng chủ tài khoản với repo nguồn dùng chung tiền tố bundle và team id; ở template không miễn;
  (b) giá trị bundle.store, bundle.internal, apple.team_id, app.display_name_internal
      không được xuất hiện ngoài các đường dẫn được phép (trong web/ chỉ mã bị quét — WEB_CODE_PREFIXES).
Mỗi vi phạm: `đường/dẫn:số_dòng: lý do`. CLI: rc 0 sạch, rc 1 có vi phạm.
Danh sách từ cấm viết dạng ghép chuỗi để chính file này không tự vi phạm.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appconfig  # noqa: E402

FORBIDDEN_WORDS = ("pura" + "cam", "vimind" + "tech", "LiDARTextured" + "Scanner", "Q73A5F75" + "B4")

# Luật (a) bỏ qua các thư mục này.
RULE_A_SKIP_PREFIXES = ("docs/superpowers/", "docs/decisions/")

# Luật (b) cho phép: đường dẫn chính xác, tiền tố thư mục, hoặc mẫu fnmatch.
RULE_B_ALLOWED_EXACT = ("app.config.toml", appconfig.XCCONFIG, "CHANGELOG.md")
RULE_B_ALLOWED_PREFIXES = ("store/", "web/", "docs/")
RULE_B_ALLOWED_GLOBS = ("tools/*/test_*.py", "tools/test_*.py")
# Trong web/ chỉ MÃ bị quét (kể cả test): file sinh (`web/*/wrangler.jsonc`) và nội dung gieo (`web/site/public/**`,
# `web/site/releases.json`) mang định danh do dựng từ cấu hình — miễn như store/ và Identity.xcconfig.
WEB_CODE_PREFIXES = ("web/api/src/", "web/api/test/", "web/site/src/", "web/site/test/", "web/tools/", "web/scripts/")

IDENTITY_KEYS = ("bundle.store", "bundle.internal", "apple.team_id", "app.display_name_internal")

# Dấu nhận diện DƯƠNG template (giống manifest.is_app): file này được track ⇒ template, mọi repo khác là app.
TEMPLATE_MARKER = "tools/template/new_app.py"
# Ở app, từ cấm (a) nằm trong các giá trị này của chính app thì được miễn.
OWN_IDENTITY_KEYS = ("bundle.store", "bundle.internal", "apple.team_id")


def _tracked_files(root: Path) -> list[str]:
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                       capture_output=True, text=True, check=True)
    return [p for p in r.stdout.split("\0") if p]


def _read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _rule_b_exempt(rel: str) -> bool:
    if rel.startswith(WEB_CODE_PREFIXES):
        return False
    return (rel in RULE_B_ALLOWED_EXACT
            or rel.startswith(RULE_B_ALLOWED_PREFIXES)
            or any(fnmatch.fnmatch(rel, g) for g in RULE_B_ALLOWED_GLOBS))


def find_violations(root: Path) -> list[str]:
    root = Path(root)
    cfg = appconfig.load(root)
    # Khớp theo ranh giới token: không dính chữ/số hai bên (tránh dãy số 0 dài, tiền tố của id dài hơn).
    # Hậu tố '.' vẫn tính là khớp: id store theo sau bởi ".internal" vẫn bị bắt.
    values = [(appconfig.get(cfg, k), re.compile(rf"(?<![A-Za-z0-9]){re.escape(appconfig.get(cfg, k))}(?![A-Za-z0-9])"))
              for k in IDENTITY_KEYS]
    tracked = _tracked_files(root)
    words = [w.lower() for w in FORBIDDEN_WORDS]
    if TEMPLATE_MARKER not in tracked:
        # Ở APP: từ cấm nằm trong định danh của CHÍNH app (vd cùng chủ tài khoản với repo nguồn: bundle chung tiền
        # tố tổ chức, cùng team id) không còn là "rò rỉ" — miễn. Từ cấm khác vẫn bị bắt. Ở template KHÔNG miễn gì:
        # cấu hình của template là giá trị giữ chỗ, và miễn theo cấu hình sẽ là lỗ tự-miễn.
        own = " ".join(appconfig.get(cfg, k) for k in OWN_IDENTITY_KEYS).lower()
        words = [w for w in words if w not in own]
    out: list[str] = []
    for rel in tracked:
        text = _read_text(root / rel)
        if text is None:
            continue
        check_a = not rel.startswith(RULE_A_SKIP_PREFIXES)
        check_b = not _rule_b_exempt(rel)
        if not (check_a or check_b):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if check_a:
                low = line.lower()
                if any(w in low for w in words):
                    out.append(f"{rel}:{n}: chứa từ cấm của repo nguồn")
            if check_b:
                for k, (v, rx) in zip(IDENTITY_KEYS, values):
                    if v and rx.search(line):
                        out.append(f"{rel}:{n}: literal định danh ({k}) — đọc qua appconfig")
    return out


def _main() -> int:
    try:
        violations = find_violations(appconfig.repo_root())
    except appconfig.ConfigError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    for v in violations:
        print(v)
    if violations:
        print(f"FAIL: {len(violations)} vi phạm định danh", file=sys.stderr)
        return 1
    print("OK: không có literal định danh ngoài cấu hình")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
