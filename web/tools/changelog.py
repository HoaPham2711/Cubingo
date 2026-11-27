#!/usr/bin/env python3
"""Trang `/changelog/` của site + cổng "website không cũ hơn App Store".

Nguồn duy nhất: `web/site/releases.json` — danh sách, MỚI NHẤT TRƯỚC, mỗi mục
`{"version": "X.Y.Z", "date": "YYYY-MM-DD", "notes": ["đoạn What's New", …]}` (chép What's New đã nộp App Store).
Tool chỉ ghi VÙNG SINH giữa hai dòng `<!-- releases:begin -->` / `<!-- releases:end -->` của
`web/site/public/changelog/index.html`; phần còn lại của trang (đầu, chân, style) thuộc app, sửa tay được.

Chỉ đưa lên trang các bản ≤ bản đang bán trên App Store (iTunes Lookup theo `bundle.store`), nên thêm bản sắp nộp vào
releases.json sớm cũng không lộ trước ngày Apple duyệt. Lookup trả `resultCount: 0` (app chưa lên Store) ⇒ bỏ vế
"bản đang bán": không lỗi, trang chưa liệt kê bản nào.

    python3 web/tools/changelog.py [--root DIR]            # sinh lại vùng (+ lastmod của /changelog/ trong sitemap)
    python3 web/tools/changelog.py --check [--root DIR]    # cổng deploy prod — lệch thì rc 1
    python3 web/tools/changelog.py --live 1.2.0 …          # bỏ qua iTunes Lookup (offline)

`--check` báo lỗi khi: releases.json sai dạng / không xếp mới nhất trước; bản đang bán chưa có trong releases.json;
vùng sinh của trang chưa khớp releases.json. Lỗi mạng khi gọi Lookup ⇒ rc 1 (chặn deploy, kèm lý do).
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[1]
sys.path.insert(0, str(DEFAULT_ROOT / "tools" / "common"))
import appconfig  # noqa: E402

RELEASES = Path("web/site/releases.json")
PUBLIC = Path("web/site/public")
PAGE = PUBLIC / "changelog" / "index.html"
SITEMAP = PUBLIC / "sitemap.xml"
LOOKUP = "https://itunes.apple.com/lookup"
BEGIN = "<!-- releases:begin -->"
END = "<!-- releases:end -->"
EMPTY = '<p class="empty">No releases yet.</p>'
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

Fetch = Callable[[str], dict]


class ChangelogError(Exception):
    pass


def default_fetch(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)


def lookup_url(bundle: str, now: float) -> str:
    # URL trơn dính cache CDN của Apple hàng giờ sau khi bản mới lên — thêm tham số đổi theo giây.
    return f"{LOOKUP}?{urllib.parse.urlencode({'bundleId': bundle, 'country': 'us', 't': int(now)})}"


def live_version(bundle: str, fetch: Fetch) -> str | None:
    """Bản đang bán; None khi Lookup trả `resultCount: 0` (chưa lên Store). Lỗi mạng/JSON ⇒ ngoại lệ."""
    data = fetch(lookup_url(bundle, datetime.datetime.now().timestamp()))
    results = data.get("results") or []
    if not data.get("resultCount") or not results:
        return None
    v = results[0].get("version")
    if not isinstance(v, str):
        raise ChangelogError(f"iTunes Lookup trả version lạ: {v!r}")
    return v


def vtuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def short(v: str) -> str:
    """1.10.0 → 1.10, 1.8.1 → 1.8.1 (cách App Store gọi bản)."""
    return v[:-2] if v.endswith(".0") else v


def load_releases(root: Path) -> list[dict]:
    try:
        data = json.loads((root / RELEASES).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ChangelogError(f"thiếu {RELEASES}")
    except json.JSONDecodeError as e:
        raise ChangelogError(f"{RELEASES} không phải JSON hợp lệ: {e}")
    if not isinstance(data, list):
        raise ChangelogError(f"{RELEASES} phải là một danh sách")
    for i, r in enumerate(data):
        ok = (isinstance(r, dict) and isinstance(r.get("version"), str) and VERSION_RE.fullmatch(r["version"])
              and isinstance(r.get("date"), str) and isinstance(r.get("notes"), list)
              and all(isinstance(n, str) and n.strip() for n in r["notes"]))
        if not ok:
            raise ChangelogError(f"{RELEASES} mục {i}: cần version X.Y.Z, date YYYY-MM-DD, notes = danh sách chuỗi")
        try:
            datetime.date.fromisoformat(r["date"])
        except ValueError:
            raise ChangelogError(f"{RELEASES} mục {i}: date sai dạng YYYY-MM-DD: {r['date']!r}")
    return data


def paragraph(text: str) -> str:
    # "Export: …" → nhãn đậm. Chỉ khi nhãn ngắn, để câu thường có dấu ":" không bị bôi đậm.
    m = re.match(r"([^:.]{2,40}):\s+(.*)", text)
    if m:
        return f"<p><strong>{html.escape(m.group(1))}:</strong> {html.escape(m.group(2))}</p>"
    return f"<p>{html.escape(text)}</p>"


def render_region(releases: list[dict], live: str | None) -> str:
    shown = [r for r in releases if live is not None and vtuple(r["version"]) <= vtuple(live)]
    if not shown:
        return EMPTY
    blocks = []
    for r in shown:
        v = r["version"]
        d = datetime.date.fromisoformat(r["date"])
        body = "\n".join(paragraph(p) for p in r["notes"])
        blocks.append(f'<section class="release" id="v{v.replace(".", "-")}">\n<h2>Version {short(v)}</h2>\n'
                      f'<p class="updated"><time datetime="{d.isoformat()}">{d.day} {d:%B %Y}</time></p>\n'
                      f"{body}\n</section>")
    return "\n\n".join(blocks)


def splice(page: str, region: str) -> str:
    """Trang với vùng sinh thay bằng `region`; thiếu/lặp dấu ⇒ ChangelogError."""
    lines = page.split("\n")
    starts = [i for i, ln in enumerate(lines) if ln.strip() == BEGIN]
    ends = [i for i, ln in enumerate(lines) if ln.strip() == END]
    if len(starts) != 1 or len(ends) != 1 or starts[0] > ends[0]:
        raise ChangelogError(f"{PAGE} phải có đúng một cặp dòng {BEGIN} … {END}")
    return "\n".join(lines[: starts[0] + 1] + region.split("\n") + lines[ends[0]:])


def bumped_sitemap(root: Path, host: str, today: str) -> str:
    """Nội dung sitemap với `<lastmod>` của `/changelog/` = `today` — CHỈ tính, không ghi (trang và sitemap cùng được
    kiểm trước khi ghi file nào). Thiếu host / thiếu đúng một `<url>` của trang ⇒ ChangelogError."""
    if not host:
        raise ChangelogError("web.host_prod rỗng — không xác định được <url> của /changelog/ trong sitemap")
    path = root / SITEMAP
    if not path.is_file():
        raise ChangelogError(f"thiếu {SITEMAP}")
    xml = path.read_text(encoding="utf-8")
    loc = re.escape(f"https://{host}/changelog/")
    new, n = re.subn(rf"(<loc>\s*{loc}\s*</loc>\s*<lastmod>)[^<]*", rf"\g<1>{today}", xml)
    if n != 1:
        raise ChangelogError(f"{SITEMAP} chưa có đúng một <url> cho https://{host}/changelog/")
    return new


def run(root: Path, *, check: bool, live: str | None, use_lookup: bool, fetch: Fetch,
        today: str) -> tuple[int, list[str]]:
    cfg = appconfig.load(root)
    releases = load_releases(root)
    if use_lookup:
        try:
            live = live_version(appconfig.get(cfg, "bundle.store"), fetch)
        except ChangelogError:
            raise
        except Exception as e:  # noqa: BLE001 — mạng/JSON hỏng đều phải chặn, kèm lý do
            raise ChangelogError(f"không đọc được bản đang bán trên App Store ({e}). Offline thì dùng --live X.Y.Z.")
    errors = []
    versions = [r["version"] for r in releases]
    if versions != sorted(versions, key=vtuple, reverse=True):
        errors.append(f"{RELEASES} phải xếp mới nhất trước")
    if live is not None and live not in versions:
        errors.append(f"App Store đang bán {live} nhưng {RELEASES} chưa có — chép What's New của bản đó vào rồi chạy "
                      "lại không --check")
    if errors:
        return 1, errors
    page_path = root / PAGE
    if not page_path.is_file():
        return 1, [f"thiếu {PAGE}"]
    current = page_path.read_text(encoding="utf-8")
    want = splice(current, render_region(releases, live))
    label = f"bản đang bán {live}" if live else "app chưa có trên App Store"
    if check:
        if want != current:
            return 1, [f"{PAGE} chưa sinh lại — chạy python3 web/tools/changelog.py"]
        return 0, [f"changelog OK ({label})."]
    if want == current:
        return 0, [f"changelog: không đổi ({label})."]
    # Tính đủ cả hai rồi mới ghi: sitemap hỏng thì không file nào bị đổi (chạy lại vẫn thấy trang lệch).
    sitemap = bumped_sitemap(root, appconfig.opt(cfg, "web.host_prod", ""), today)
    page_path.write_text(want, encoding="utf-8")
    (root / SITEMAP).write_text(sitemap, encoding="utf-8")
    return 0, [f"changelog: đã sinh lại {PAGE} ({label}) + lastmod sitemap."]


def main(argv: list[str] | None = None, fetch: Fetch | None = None, today: str | None = None) -> int:
    ap = argparse.ArgumentParser(description="Trang /changelog/ + cổng website khớp App Store")
    ap.add_argument("--check", action="store_true", help="chỉ kiểm, lệch thì rc 1")
    ap.add_argument("--live", help="bản đang bán X.Y.Z (bỏ qua iTunes Lookup)")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="gốc repo (mặc định: repo chứa file này)")
    args = ap.parse_args(argv)
    if args.live is not None and not VERSION_RE.fullmatch(args.live):
        print(f"changelog: --live phải dạng X.Y.Z: {args.live!r}", file=sys.stderr)
        return 1
    try:
        rc, lines = run(Path(args.root), check=args.check, live=args.live, use_lookup=args.live is None,
                        fetch=fetch or default_fetch, today=today or datetime.date.today().isoformat())
    except (ChangelogError, appconfig.ConfigError) as e:
        print(f"changelog: {e}", file=sys.stderr)
        return 1
    if rc:
        print("Website lệch App Store:", file=sys.stderr)
        for e in lines:
            print(f"  - {e}", file=sys.stderr)
        return rc
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
