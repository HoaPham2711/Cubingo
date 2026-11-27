#!/usr/bin/env python3
"""Góc nhìn TÍNH RA từ docs/ROADMAP.md: mục nào còn nợ (chưa merge / chưa device / chưa deploy /
chưa push / mặc định tắt chờ quyết). Không phải doc thứ hai — ROADMAP vẫn là nguồn sự thật.

    python3 tools/factory/roadmap.py debt                # bảng gọn, mới nhất trước
    python3 tools/factory/roadmap.py debt --kind device  # chỉ một loại nợ
    python3 tools/factory/roadmap.py debt --json         # cho planner / workflow
    python3 tools/factory/roadmap.py debt --since 2026-10-01

Planner dùng lệnh này thay vì đọc cả ROADMAP (~3 000 dòng).

Heuristic (đọc TIÊU ĐỀ mục + dòng "Còn chờ/Còn lại/Nợ" trong thân):
- device: "chưa device", "CHỜ DEVICE", "chưa nghiệm thu", "chưa ghi nhận device", "chưa xem trên device"
  — trừ khi tiêu đề nói đã nghiệm thu/"device OK".
- merge:  "chưa merge"
- deploy: "chưa deploy"
- push:   "chưa push"
- off:    "mặc định TẮT" / "default OFF"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEAD = re.compile(r"^## (?P<date>\d{4}-\d{2}-\d{2})(?:→\d{2})?\s+—\s+(?P<rest>.+)$")

KINDS = {
    "device": [r"ch[ưu]a\s+(?:ghi nhận\s+|xem trên\s+)?device", r"chờ\s+device", r"ch[ưu]a\s+nghiệm thu",
               r"nợ device", r"nợ nghiệm thu"],
    "merge": [r"ch[ưu]a\s+merge"],
    "deploy": [r"ch[ưu]a\s+deploy"],
    "push": [r"ch[ưu]a\s+push"],
    "off": [r"mặc định\s+tắt", r"default\s+off"],
}
DONE_DEVICE = [r"device\s+ok", r"đã nghiệm thu", r"user nghiệm thu", r"(?<!a )(?<!ư )nghiệm thu device",
               r"device đã xác nhận", r"user thử device", r"user đã test device"]
PENDING_LINE = re.compile(r"^\s*[-*]?\s*\**\s*(còn chờ|còn lại|nợ|chưa làm|còn nợ)", re.I)


def _has(patterns, text):
    return any(re.search(p, text, re.I) for p in patterns)


def parse(text: str) -> list[dict]:
    entries, cur = [], None
    for i, line in enumerate(text.splitlines(), 1):
        mh = HEAD.match(line)
        if mh:
            cur = {"date": mh["date"], "title": mh["rest"].strip(), "line": i, "pending": []}
            entries.append(cur)
            continue
        if line.startswith("## "):
            cur = None
            continue
        if cur is not None and PENDING_LINE.match(line):
            cur["pending"].append(re.sub(r"\s+", " ", line.strip(" -*"))[:220])
    for e in entries:
        head = e["title"]
        body = " ".join(e["pending"])
        kinds = []
        for k, pats in KINDS.items():
            if _has(pats, head) or (k in ("device", "deploy") and _has(pats, body)):
                kinds.append(k)
        # Gỡ nợ device CHỈ khi tiêu đề nói đã xong VÀ tiêu đề không còn cụm nợ device nào
        # ("CHƯA nghiệm thu device" chứa "nghiệm thu device" — lỗi factory-critic bắt 2026-11-06).
        if "device" in kinds and _has(DONE_DEVICE, head) and not _has(KINDS["device"], head):
            kinds.remove("device")
        e["kinds"] = kinds
        # kind chỉ đến từ dòng "Còn nợ…" trong THÂN (tiêu đề không có cụm nợ đó) — sửa tiêu đề không gỡ được
        # trừ khi tiêu đề ghi đã xong cho MỌI ý (retro mission 2026-11-06-roadmap-debt-cleanup).
        e["from_body"] = [k for k in kinds if not _has(KINDS[k], head)]
    return entries


def debt(entries, kind=None, since=None):
    out = [e for e in entries if e["kinds"]]
    if kind:
        out = [e for e in out if kind in e["kinds"]]
    if since:
        out = [e for e in out if e["date"] >= since]
    return sorted(out, key=lambda e: (e["date"], -e["line"]), reverse=True)


def short_title(t: str, n: int = 90) -> str:
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t)  # bỏ ngoặc trạng thái cuối tiêu đề
    return t if len(t) <= n else t[: n - 1] + "…"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("debt")
    p.add_argument("--kind", choices=sorted(KINDS))
    p.add_argument("--since")
    p.add_argument("--json", action="store_true")
    p.add_argument("--file", default=str(ROOT / "docs" / "ROADMAP.md"))
    a = ap.parse_args(argv)
    entries = parse(Path(a.file).read_text(encoding="utf-8"))
    rows = debt(entries, a.kind, a.since)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    counts = {k: sum(k in e["kinds"] for e in rows) for k in KINDS}
    print(f"Nợ trong ROADMAP: {len(rows)} mục · " + " · ".join(f"{k}={v}" for k, v in counts.items() if v))
    print("(đọc theo TIÊU ĐỀ lúc viết mục — mục cũ có thể đã giải ở mục sau/memory; kiểm trước khi coi là nợ thật)")
    for e in rows:
        print(f"{e['date']}  [{','.join(e['kinds'])}]  {short_title(e['title'])}  (ROADMAP.md:{e['line']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
