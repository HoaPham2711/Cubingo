#!/usr/bin/env python3
"""Tiện ích đóng dấu thẻ What's New: `version: .unreleased` -> `version: .released("X.Y.Z")` (spec D12).

CHỐT CHÍNH không nằm ở đây: case `CardVersion.unreleased` chỉ tồn tại dưới `#if INTERNAL` (+ cờ riêng của verify_catalog.py) (WhatsNewCard.swift),
config Release không có cờ đó ⇒ archive App Store không biên dịch được nếu còn sót thẻ ở BẤT KỲ dạng nào. Script
này chỉ làm việc thay chữ cho tiện lúc bump, và cố ý KHÔNG parse Swift (5 vòng thử parser đều lọt ca hợp lệ):

  stamp_whats_new.py --check                     # exit 1 nếu text thô còn chuỗi con `unreleased` (kể cả comment)
  stamp_whats_new.py --count                     # in số lần xuất hiện chuỗi con `unreleased`
  stamp_whats_new.py --version X.Y.Z [--dry-run] # thay mẫu chuẩn; --dry-run: kiểm đủ nhưng KHÔNG ghi file

Mẫu thay được: `version<ws>:<ws>.unreleased` và `version<ws>:<ws>CardVersion.unreleased` (`<ws>` = khoảng trắng
tuỳ ý, kể cả xuống dòng). Sau khi thay mà text còn `unreleased` ở đâu đó (hằng, backtick, comment…) ⇒ exit 3,
KHÔNG ghi file — sửa tay rồi chạy lại.

Exit: 0 sạch/đã ghi · 1 còn (--check) · 2 sai đối số / version hỏng / không đọc được file · 3 còn chỗ không tự thay.
Catalog không tồn tại (hotfix từ `main` cũ chưa có tính năng) ⇒ exit 0 kèm ghi chú. Idempotent. Stdlib thuần.
"""
import argparse
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools", "common"))
import appconfig  # noqa: E402  (đường dẫn catalog là hằng số bố cục một nguồn)

DEFAULT_CATALOG = os.path.join(REPO_ROOT, appconfig.WHATS_NEW_CATALOG)

WORD = "unreleased"
VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")  # [0-9], không \d: \d khớp cả chữ số Ả Rập-Ấn (١.٢.٣)
STAMPABLE = re.compile(r"\bversion(\s*):(\s*)(?:CardVersion)?\.unreleased\b")


def stamp(text: str, version: str) -> tuple:
    """Trả (text mới, số chỗ đã thay). Giữ nguyên khoảng trắng quanh `:`."""
    return STAMPABLE.subn(lambda m: f'version{m.group(1)}:{m.group(2)}.released("{version}")', text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--count", action="store_true")
    mode.add_argument("--version")
    ap.add_argument("--dry-run", action="store_true", help="chỉ với --version: kiểm đủ, không ghi file")
    ap.add_argument("--catalog", default=DEFAULT_CATALOG)
    args = ap.parse_args(argv)

    if args.dry_run and not args.version:
        print("FAIL: --dry-run chỉ đi với --version", file=sys.stderr)
        return 2
    if args.version is not None and not VERSION_RE.fullmatch(args.version):
        print(f"FAIL: version '{args.version}' không phải dạng X.Y.Z", file=sys.stderr)
        return 2

    if not os.path.exists(args.catalog):
        if args.count:
            print(0)
        else:
            print(f"(không có {args.catalog} — bỏ qua What's New)", file=sys.stderr)
        return 0
    try:
        with open(args.catalog, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"FAIL: không đọc được {args.catalog}: {e}", file=sys.stderr)
        return 2

    n = text.count(WORD)
    if args.count:
        print(n)
        return 0
    if args.check:
        if n:
            print(f"còn {n} chỗ chứa '{WORD}' trong {args.catalog}", file=sys.stderr)
            return 1
        return 0

    new, replaced = stamp(text, args.version)
    left = new.count(WORD)
    if left:
        lines = [i + 1 for i, line in enumerate(new.splitlines()) if WORD in line]
        print(f"FAIL: sau khi thay {replaced} chỗ vẫn còn {left} chỗ '{WORD}' (dòng {lines}) không tự thay được —"
              f" sửa tay thành `version: .released(\"{args.version}\")` (hoặc xoá chữ khỏi comment). Chưa ghi file.",
              file=sys.stderr)
        return 3
    if args.dry_run:
        print(f"[dry-run] sẽ đóng dấu {replaced} thẻ thành {args.version}")
        return 0
    if replaced:
        with open(args.catalog, "w", encoding="utf-8") as f:
            f.write(new)
    print(f"đã đóng dấu {replaced} thẻ thành {args.version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
