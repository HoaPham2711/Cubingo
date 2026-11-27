#!/usr/bin/env python3
"""Người mới theo ngày + giữ chân (retention) D1/D3/D7 theo ngày cài. Hàm thuần — test ở test_retention.py.

Nguồn (ga4_pull.py):
- `retention_daily`: cohort theo `firstSessionDate`, từng ngày trong RETENTION_COHORT_DAYS ngày gần nhất,
  `cohortNthDay` 0..7, mọi bản cài. Cỡ cohort (`cohortTotalUsers`) = người mở app lần đầu ngày đó.
- `daily`: `newUsers` theo ngày — để so.
- ASC `sales.tsv` (asc_pull.py): lượt tải lần đầu (Product Type Identifier bắt đầu bằng `1`) theo `report_date`.

Dn = có hoạt động đúng ngày thứ n sau ngày cài (không phải "trong n ngày"). Một ô chỉ tính khi ngày đó đã
TRỌN (≤ ngày cuối có dữ liệu chốt), nếu không để trống — tránh đọc ô dở dang thành 0 %.
"""
from __future__ import annotations

import csv
import datetime as dt

DAYS = (1, 3, 7)  # các mốc hiện ra trong báo cáo


def matrix(rows, last_complete):
    """rows GA4 {cohort, cohortNthDay '0003', cohortActiveUsers, cohortTotalUsers} → mới trước:
    [{"date", "size", "active": {n: người|None}}]. None = ngày đó chưa trọn; 0 = trọn mà không ai quay lại."""
    by = {}
    for r in rows:
        c = by.setdefault(r["cohort"], {"size": 0, "seen": {}})
        c["size"] = max(c["size"], int(r["cohortTotalUsers"]))
        c["seen"][int(r["cohortNthDay"])] = int(r["cohortActiveUsers"])
    out = []
    for date, c in by.items():
        if not c["size"]:
            continue
        d0 = dt.date.fromisoformat(date)
        active = {n: (c["seen"].get(n, 0) if d0 + dt.timedelta(days=n) <= last_complete else None)
                  for n in range(0, max(DAYS) + 1)}
        out.append({"date": date, "size": c["size"], "active": active})
    return sorted(out, key=lambda c: c["date"], reverse=True)


def pooled(cohorts, n):
    """Retention Dn gộp mọi cohort đã trọn ngày n: (quay lại, cỡ, tỉ lệ|None). Gộp theo NGƯỜI, không trung bình %."""
    ok = [c for c in cohorts if c["active"].get(n) is not None]
    back, size = sum(c["active"][n] for c in ok), sum(c["size"] for c in ok)
    return back, size, (back / size if size else None)


def asc_first_by_day(sales_tsv):
    """sales.tsv → {YYYY-MM-DD: lượt tải lần đầu}. Thiếu file ⇒ {}."""
    if not sales_tsv or not sales_tsv.is_file():
        return {}
    out = {}
    with sales_tsv.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if (r.get("Product Type Identifier") or "").startswith("1"):
                out[r["report_date"]] = out.get(r["report_date"], 0) + float(r.get("Units") or 0)
    return out


def new_users_daily(cohorts, ga4_daily, asc_first, since):
    """→ mới trước: [ngày, người mới (GA4 cohort), người mới (GA4 daily), tải lần đầu (ASC)|None]."""
    app = {c["date"]: c["size"] for c in cohorts}
    allnew = {f"{r['date'][:4]}-{r['date'][4:6]}-{r['date'][6:]}": int(r["newUsers"]) for r in ga4_daily}
    days = sorted({d for d in (*app, *allnew, *asc_first) if d >= since}, reverse=True)
    return [[d, app.get(d, 0), allnew.get(d, 0), int(asc_first[d]) if d in asc_first else None] for d in days]
