#!/usr/bin/env python3
"""Cổng `web/site/public/sitemap.xml` — sitemap viết tay nên phải có máy canh.

Kiểm 2 điều:
  1. ĐỦ: mỗi trang `web/site/public/**/index.html` có đúng một <url> trong sitemap và ngược lại (không trang thừa,
     không trang thiếu). Địa chỉ trang = `https://<web.host_prod>/<thư mục>/` (host đọc từ app.config.toml).
  2. KỊP: `<lastmod>` của mỗi trang ≥ ngày commit gần nhất đụng file HTML đó. Với `--staged` (pre-commit), trang nào
     đang được commit thì `<lastmod>` phải ≥ HÔM NAY — sửa trang và sửa ngày trong sitemap đi cùng một commit.

Chạy ở: .githooks/pre-commit (khi commit đụng web/site/public/) và trước deploy prod. App không có web (không có
`web/site/public/` hoặc `web.host_prod` rỗng) ⇒ in SKIP, rc 0.

    python3 web/tools/check_sitemap.py [--staged] [--root DIR]     # rc 0 đúng · 1 lệch · 2 không phải repo git
"""
from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[1]
sys.path.insert(0, str(DEFAULT_ROOT / "tools" / "common"))
import appconfig  # noqa: E402

PUBLIC = Path("web/site/public")
ENTRY_RE = re.compile(r"<url>\s*<loc>\s*([^<\s]+)\s*</loc>\s*<lastmod>\s*([^<\s]+)\s*</lastmod>\s*</url>")


def git(root: Path, *args: str) -> str:
    # Môi trường giữ nguyên: trong hook, GIT_INDEX_FILE trỏ đúng index đang commit.
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def site_of(root: Path) -> str | None:
    host = appconfig.opt(appconfig.load(root), "web.host_prod", "")
    return f"https://{host}" if host else None


def url_of(site: str, public: Path, page: Path) -> str:
    rel = page.parent.relative_to(public).as_posix()
    return f"{site}/" if rel == "." else f"{site}/{rel}/"


def check(root: Path, staged: bool = False, today: str | None = None) -> list[str]:
    """Danh sách lỗi (rỗng = đúng). Gọi khi chắc có web/site/public và host."""
    root = Path(root)
    public = root / PUBLIC
    site = site_of(root)
    sitemap = public / "sitemap.xml"
    if not sitemap.is_file():
        return [f"thiếu {PUBLIC}/sitemap.xml"]
    xml = sitemap.read_text(encoding="utf-8")
    found = ENTRY_RE.findall(xml)
    if len(found) != xml.count("<url>"):
        return ["mỗi <url> phải có <loc> rồi <lastmod> liền sau"]
    entries = dict(found)
    errors: list[str] = []
    if len(entries) != len(found):
        errors.append("sitemap có <loc> lặp")
    pages = {url_of(site, public, p): p for p in sorted(public.rglob("index.html"))}
    errors += [f"thiếu trong sitemap: {u}" for u in sorted(pages.keys() - entries.keys())]
    errors += [f"sitemap có nhưng không có trang: {u}" for u in sorted(entries.keys() - pages.keys())]
    staged_set: set[Path] = set()
    if staged:
        top = Path(git(root, "rev-parse", "--show-toplevel"))
        staged_set = {(top / f).resolve() for f in
                      git(root, "-c", "core.quotePath=false", "diff", "--cached", "--name-only", "--diff-filter=ACMR")
                      .splitlines() if f}
    today = today or datetime.date.today().isoformat()
    # Repo chưa có commit nào (commit khởi tạo của new_app chạy qua hook này) ⇒ chưa có lịch sử để so; `git log` trên HEAD
    # chưa có thì lỗi. Vẫn là repo git (rev-parse --git-dir lỗi ⇒ CalledProcessError ⇒ rc 2 như cũ).
    git(root, "rev-parse", "--git-dir")
    has_head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD^{commit}"], cwd=root,
                              capture_output=True).returncode == 0
    for url, page in pages.items():
        lastmod = entries.get(url)
        if lastmod is None:
            continue
        committed = git(root, "log", "-1", "--format=%cs", "--", str(page.relative_to(root))) if has_head else ""
        need = max(filter(None, [committed, today if page.resolve() in staged_set else ""]), default="")
        if need and lastmod < need:
            errors.append(f"{url}: lastmod {lastmod} < {need} — sửa <lastmod> thành {need}")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cổng sitemap.xml của site tĩnh")
    ap.add_argument("--staged", action="store_true", help="trang đang commit phải có lastmod hôm nay")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="gốc repo (mặc định: repo chứa file này)")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not (root / PUBLIC).is_dir():
        print(f"sitemap: SKIP — không có {PUBLIC}/")
        return 0
    try:
        if site_of(root) is None:
            print("sitemap: SKIP — web.host_prod rỗng (app không có web)")
            return 0
        errors = check(root, staged=args.staged)
    except appconfig.ConfigError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    except (subprocess.CalledProcessError, OSError) as e:
        why = (getattr(e, "stderr", "") or str(e)).strip().splitlines()
        print(f"FAIL: {root} không phải repo git đọc được (cần git log để so lastmod): {why[0] if why else e}",
              file=sys.stderr)
        return 2
    if errors:
        print("sitemap.xml chưa đúng:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print(f"  (file: {PUBLIC}/sitemap.xml)", file=sys.stderr)
        return 1
    print("sitemap OK: đủ trang, lastmod kịp.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
