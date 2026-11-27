#!/usr/bin/env python3
"""Cổng nội dung site tĩnh `web/site/public/` của app.

Kiểm:
  1. Trang BẤT BIẾN có mặt: `index.html`, `privacy/index.html`, `terms/index.html`, `support/index.html` — app nướng cứng
     `/`, `/privacy/`, `/terms/`, `/support/` (Core/Bootstrap/AppConfig.swift), không được đổi.
  2. Chữ giữ chỗ `TEMPLATE-PLACEHOLDER` (phần app phải tự viết): LỖI với `--release` (trước deploy prod / ra bản),
     CẢNH BÁO khi không.
  3. Privacy: mỗi phần tử `data-feature="<x>"` ⇔ công tắc `<x>` bật (paywall, web_api, apple_ads, và `purchase_records` =
     paywall VÀ web_api: server lưu thông báo mua hàng) — bật mà trang thiếu phần đó, hoặc tắt mà trang còn, đều là lỗi;
     giá trị lạ là lỗi.
  4. `m.js` (beacon web analytics, gửi tới API) chỉ được nhắc trong trang khi `features.web_api` bật.
  5. Trang không còn dấu khối `feature:<x>:begin|end` hay biến gieo `$<tên>` chưa thay (trang gieo chưa dựng).
  6. CHỈ `--release`: `web.host_prod` / tên miền của `support.email` không phải host giữ chỗ (`example.com|net|org`, `*.test`,
     `*.invalid`, `localhost`… — `appconfig.is_reserved_host`); mọi `<link rel="canonical">` trỏ `web.host_prod` (hay `www.`
     của nó) và mọi `mailto:` là đúng `support.email` — đổi cấu hình mà quên trang thì bắt ở đây.
App không có `web/site/public/` ⇒ SKIP, rc 0.

    python3 web/tools/check_site.py [--release] [--root DIR]     # rc 0 đúng · 1 lỗi
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[1]
sys.path.insert(0, str(DEFAULT_ROOT / "tools" / "common"))
import appconfig  # noqa: E402

PUBLIC = Path("web/site/public")
INVARIANT_PAGES = ("index.html", "privacy/index.html", "terms/index.html", "support/index.html")
PRIVACY_PAGE = "privacy/index.html"
PLACEHOLDER = "TEMPLATE-PLACEHOLDER"
# Công tắc của phần privacy — `appconfig.web_seed_switches` là nguồn giá trị (cùng hàm cắt khối của trang gieo).
SWITCHES = ("paywall", "web_api", "purchase_records", "apple_ads")
TEXT_SUFFIXES = (".html", ".txt", ".xml", ".css", ".js", ".json", ".webmanifest")
PAGE_SUFFIXES = (".html", ".txt", ".xml")
DATA_FEATURE_RE = re.compile(r"""data-feature\s*=\s*["']([^"']*)["']""")
M_JS_RE = re.compile(r"""["'(/]m\.js\b""")
MARK_RE = re.compile(r"feature:[A-Za-z0-9_-]*:(?:begin|end)\b")
SEED_VAR_RE = re.compile(r"\$\{?([a-z_]+)\}?")
CANONICAL_RE = re.compile(r"""<link\b[^>]*\brel\s*=\s*["']canonical["'][^>]*>""", re.I)
HREF_RE = re.compile(r"""\bhref\s*=\s*["']([^"']*)["']""", re.I)
MAILTO_RE = re.compile(r"""mailto:([^"'?<>\s]+)""", re.I)


def _text_files(public: Path) -> list[tuple[str, str]]:
    out = []
    for p in sorted(public.rglob("*")):
        if p.is_file() and not p.is_symlink() and p.suffix in TEXT_SUFFIXES:
            try:
                out.append((p.relative_to(public).as_posix(), p.read_text(encoding="utf-8")))
            except UnicodeDecodeError:
                continue
    return out


def _release_identity(cfg: dict, files: list[tuple[str, str]]) -> list[str]:
    """Kiểm 6: host/e-mail thật và trang khớp cấu hình (chỉ khi ra bản)."""
    out: list[str] = []
    host = appconfig.opt(cfg, "web.host_prod", "") or ""
    email = appconfig.opt(cfg, "support.email", "") or ""
    if appconfig.is_reserved_host(host):
        out.append(f"web.host_prod = \"{host}\" là host giữ chỗ/dành riêng — điền tên miền thật của app rồi "
                   "appconfig.py render (và sửa link canonical, sitemap)")
    if email and appconfig.is_reserved_host(email.rpartition("@")[2]):
        out.append(f"support.email = \"{email}\" thuộc tên miền giữ chỗ — điền e-mail hỗ trợ thật")
    for rel, text in files:
        if not rel.endswith(".html"):
            continue
        for tag in CANONICAL_RE.findall(text):
            m = HREF_RE.search(tag)
            target = (urlsplit(m.group(1)).hostname or "") if m else ""
            if not host or not appconfig.same_site(target, host):
                out.append(f"{PUBLIC}/{rel}: link canonical trỏ \"{target or '?'}\" ≠ web.host_prod \"{host}\"")
        for addr in MAILTO_RE.findall(text):
            if addr.lower() != email.lower():
                out.append(f"{PUBLIC}/{rel}: mailto:{addr} ≠ support.email \"{email}\"")
    return out


def _why(switch: str) -> str:
    return "features.paywall + features.web_api" if switch == "purchase_records" else f"features.{switch}"


def check(root: Path, release: bool = False) -> tuple[list[str], list[str]]:
    """(lỗi, cảnh báo). Gọi khi chắc có web/site/public."""
    root = Path(root)
    cfg = appconfig.load(root)
    public = root / PUBLIC
    errors: list[str] = []
    warnings: list[str] = []
    for rel in INVARIANT_PAGES:
        if not (public / rel).is_file():
            errors.append(f"thiếu trang bất biến {PUBLIC}/{rel} (app nướng cứng đường dẫn này)")
    files = _text_files(public)
    for rel, text in files:
        n = text.count(PLACEHOLDER)
        if n:
            msg = f"{PUBLIC}/{rel}: còn {n} chỗ {PLACEHOLDER} — viết nội dung thật của app"
            (errors if release else warnings).append(msg)
        if not rel.endswith(PAGE_SUFFIXES):
            continue
        for no, line in enumerate(text.splitlines(), 1):
            if MARK_RE.search(line):
                errors.append(f"{PUBLIC}/{rel}:{no}: còn dấu khối feature: (trang gieo chưa cắt theo công tắc) — app lên từ "
                              "v0.5.0? `git reset --hard` rồi chạy sync_core.py CỦA TEMPLATE Ở TAG ĐÍCH (--root <app> "
                              "--adopt-new-seed), không phải bản cũ trong app")
            for m in SEED_VAR_RE.finditer(line):
                errors.append(f"{PUBLIC}/{rel}:{no}: biến gieo chưa thay ${m.group(1)}")
    seed_on = appconfig.web_seed_switches(cfg)
    on = {s: seed_on[s] for s in SWITCHES}
    privacy = public / PRIVACY_PAGE
    if privacy.is_file():
        found = set(DATA_FEATURE_RE.findall(privacy.read_text(encoding="utf-8")))
        for x in sorted(found - set(SWITCHES)):
            errors.append(f"{PUBLIC}/{PRIVACY_PAGE}: data-feature=\"{x}\" không phải công tắc (có: {', '.join(SWITCHES)})")
        for s in SWITCHES:
            if on[s] and s not in found:
                errors.append(f"{PUBLIC}/{PRIVACY_PAGE}: thiếu phần data-feature=\"{s}\" trong khi {_why(s)} bật")
            if not on[s] and s in found:
                errors.append(f"{PUBLIC}/{PRIVACY_PAGE}: còn phần data-feature=\"{s}\" trong khi {_why(s)} không bật")
    if release:
        errors += _release_identity(cfg, files)
    if not on["web_api"]:
        for rel, text in files:
            if rel.endswith(".html") and M_JS_RE.search(text):
                errors.append(f"{PUBLIC}/{rel}: nhắc m.js (beacon tới API) trong khi features.web_api = false")
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cổng nội dung site tĩnh")
    ap.add_argument("--release", action="store_true", help="chữ giữ chỗ là lỗi (trước deploy prod / ra bản)")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="gốc repo (mặc định: repo chứa file này)")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not (root / PUBLIC).is_dir():
        print(f"site: SKIP — không có {PUBLIC}/")
        return 0
    try:
        errors, warnings = check(root, release=args.release)
    except appconfig.ConfigError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"WARN: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print("site OK" + (f" ({len(warnings)} cảnh báo)" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
