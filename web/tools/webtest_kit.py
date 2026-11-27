"""Dụng cụ chung cho test của web/tools — repo git tạm có app.config.toml giả (giá trị trung tính) và web/site/public.

Không mạng, không đụng repo thật; mọi lệnh git chạy với môi trường đã gỡ GIT_* (test có thể chạy trong hook)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

CONFIG = """\
[app]
slug = "demo"
display_name = "Demo"
display_name_internal = "Demo Dev"

[bundle]
store = "com.example.app"
internal = "com.example.app.internal"

[apple]
team_id = "TEAMID0000"
app_store_id = ""

[version]
marketing = "1.0.0"
build = "1"

[web]
host_prod = "example.com"
host_dev = "dev.example.com"

[support]
email = "help@example.com"

[features]
paywall = true
web_api = true
apple_ads = true

[purchases]
product_ids = ["pro.monthly"]
"""
GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]


def clean_env(extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra or {})
    return env


def git(root: Path, *args: str, env: dict | None = None) -> str:
    r = subprocess.run(["git", *GIT_ID, *args], cwd=root, env=clean_env(env), capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout


def make_repo(base: Path, files: dict[str, str], config: str = CONFIG) -> Path:
    root = base / "repo co dau cach"
    root.mkdir()
    git(root, "init", "-q")
    write(root, "app.config.toml", config)
    for rel, text in files.items():
        write(root, rel, text)
    return root


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def commit_all(root: Path, msg: str, date: str | None = None) -> None:
    git(root, "add", "-A")
    env = {"GIT_COMMITTER_DATE": f"{date}T12:00:00", "GIT_AUTHOR_DATE": f"{date}T12:00:00"} if date else None
    git(root, "commit", "-q", "-m", msg, env=env)


def page(title: str = "x", body: str = "") -> str:
    return f"<!doctype html>\n<html lang=\"en\">\n<head><title>{title}</title></head>\n<body>\n{body}\n</body>\n</html>\n"


def sitemap(host: str, entries: dict[str, str]) -> str:
    urls = "".join(f"  <url>\n    <loc>https://{host}{path}</loc>\n    <lastmod>{day}</lastmod>\n  </url>\n"
                   for path, day in entries.items())
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
