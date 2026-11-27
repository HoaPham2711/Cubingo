#!/usr/bin/env python3
"""Kéo số liệu Firebase Analytics (GA4 Data API) về JSON — chỉ các báo cáo TĨNH, chung cho mọi app.

Chạy:
    python3 tools/analytics/ga4_pull.py                 # 90 ngày gần nhất
    python3 tools/analytics/ga4_pull.py --days 28
    python3 tools/analytics/ga4_pull.py --dry-run       # chỉ in request, không gọi API, không cần khoá
    python3 tools/analytics/ga4_pull.py --today         # lấy cả số hôm nay (tạm tính)

Kết quả: .temp/analytics/ga4/<ngày chạy>/<tên report>.json (hoặc `$ANALYTICS_OUT/ga4/<ngày>/`, hoặc `--out`).

Báo cáo chỉ dùng dimension/metric chuẩn của GA4 (eventName, appVersion, country, deviceModel, date, cohort…),
KHÔNG custom dimension — app muốn lát cắt theo tham số riêng thì viết báo cáo riêng.

Property: `$GA4_PROPERTY_ID` hoặc `[analytics] ga4_property` trong app.config.toml (rỗng ⇒ từ chối, rc 2).
Xác thực: service account role Viewer trên property; file `$GA4_KEY_FILE` hoặc `<config_dir>/analytics-reader.json`.
Script KHÔNG BAO GIỜ in nội dung key. Cần gói ở requirements.txt (google-auth, requests).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shared  # noqa: E402

API_BASE = "https://analyticsdata.googleapis.com/v1beta/properties/"
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

COHORT_WEEKS = 8  # số cohort tuần cho retention_weekly
RETENTION_COHORT_DAYS = 28  # số cohort NGÀY cài cho retention_daily (D0..D7)


def api_url(prop: str) -> str:
    return API_BASE + prop


def report(dimensions, metrics, days, order_metric=None, limit=10000, end_date="yesterday"):
    body = {
        "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": end_date}],
        "dimensions": [{"name": d} for d in dimensions],
        "metrics": [{"name": m} for m in metrics],
        "limit": limit,
    }
    if order_metric:
        body["orderBys"] = [{"metric": {"metricName": order_metric}, "desc": True}]
    elif "date" in dimensions:
        body["orderBys"] = [{"dimension": {"dimensionName": "date"}}]
    return body


def static_reports(days, end_date="yesterday"):
    """Báo cáo theo eventName / version / nước / máy — chỉ trường chuẩn của GA4."""
    def r(dims, mets, order=None):
        return report(dims, mets, days, order, end_date=end_date)
    users = ["activeUsers", "newUsers"]
    ev = ["eventCount", "totalUsers"]
    return {
        "daily": r(["date"], users + ["sessions", "engagedSessions", "userEngagementDuration", "eventCount"]),
        "events": r(["eventName"], ev + ["eventCountPerUser"], "eventCount"),
        "events_daily": r(["date", "eventName"], ev),
        "events_by_version": r(["appVersion", "eventName"], ev, "eventCount"),
        "events_by_country": r(["country", "eventName"], ev, "eventCount"),
        "events_by_device": r(["deviceModel", "eventName"], ev, "eventCount"),
        "versions": r(["appVersion"], users + ["sessions", "userEngagementDuration"], "activeUsers"),
        "countries": r(["country"], users + ["userEngagementDuration"], "activeUsers"),
        "devices": r(["deviceModel"], users, "activeUsers"),
        "os_versions": r(["operatingSystemVersion"], users, "activeUsers"),
        "languages": r(["language"], users, "activeUsers"),
        "screens": r(["unifiedScreenName"], ["screenPageViews", "totalUsers", "userEngagementDuration"],
                     "screenPageViews"),
        "new_vs_returning": r(["newVsReturning"], ["activeUsers", "sessions", "userEngagementDuration"]),
        # Crash theo ngày × máy (`app_exception` do Crashlytics ghi) — crash_watch.py đọc.
        "crash_daily": r(["date", "deviceModel", "operatingSystemVersion", "appVersion", "country"], ev)
        | {"dimensionFilter": {"filter": {"fieldName": "eventName",
                                          "stringFilter": {"matchType": "EXACT", "value": "app_exception"}}}},
    }


def cohort_weekly(today=None):
    """Retention theo tuần: cohort = tuần mở app lần đầu (Chủ nhật–thứ Bảy) đã kết thúc, đo tuần 0..N."""
    today = today or dt.date.today()
    this_sunday = today - dt.timedelta(days=(today.weekday() + 1) % 7)
    cohorts = []
    for i in range(COHORT_WEEKS, 0, -1):
        start = this_sunday - dt.timedelta(weeks=i)
        cohorts.append({"name": start.isoformat(), "dimension": "firstSessionDate",
                        "dateRange": {"startDate": start.isoformat(),
                                      "endDate": (start + dt.timedelta(days=6)).isoformat()}})
    return {
        "dimensions": [{"name": "cohort"}, {"name": "cohortNthWeek"}],
        "metrics": [{"name": "cohortActiveUsers"}],
        "cohortSpec": {"cohorts": cohorts, "cohortsRange": {"granularity": "WEEKLY", "endOffset": COHORT_WEEKS}},
        "limit": 10000,
    }


def cohort_daily(today=None):
    """Retention theo NGÀY mở app lần đầu: mỗi ngày trong RETENTION_COHORT_DAYS ngày gần nhất (tới hôm qua) là
    một cohort, đo `cohortNthDay` 0..7. Mọi bản cài (không lọc theo user property). Đọc ở retention.py."""
    today = today or dt.date.today()
    days = [today - dt.timedelta(days=i) for i in range(RETENTION_COHORT_DAYS, 0, -1)]
    return {
        "dimensions": [{"name": "cohort"}, {"name": "cohortNthDay"}],
        "metrics": [{"name": "cohortActiveUsers"}, {"name": "cohortTotalUsers"}],
        "cohortSpec": {
            "cohorts": [{"name": d.isoformat(), "dimension": "firstSessionDate",
                         "dateRange": {"startDate": d.isoformat(), "endDate": d.isoformat()}} for d in days],
            "cohortsRange": {"granularity": "DAILY", "endOffset": 7},
        },
        "limit": 10000,
    }


def all_reports(days, end_date="yesterday", today=None):
    return static_reports(days, end_date) | {"retention_weekly": cohort_weekly(today),
                                             "retention_daily": cohort_daily(today)}


def flatten(resp):
    """Response của runReport → list dict {tên cột: giá trị}."""
    dims = [h["name"] for h in resp.get("dimensionHeaders", [])]
    mets = [h["name"] for h in resp.get("metricHeaders", [])]
    rows = []
    for r in resp.get("rows", []):
        row = {k: v["value"] for k, v in zip(dims, r.get("dimensionValues", []))}
        for k, v in zip(mets, r.get("metricValues", [])):
            raw = v["value"]
            try:
                row[k] = float(raw) if "." in raw else int(raw)
            except ValueError:
                row[k] = raw
        rows.append(row)
    return rows


def _main(argv, fetch):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--dry-run", action="store_true", help="in request, không gọi API")
    ap.add_argument("--out", type=Path, default=None, help="thư mục đầu ra (mặc định <gốc>/ga4/<ngày>)")
    ap.add_argument("--today", action="store_true", help="lấy cả số của hôm nay (tạm tính, GA4 chưa xử lý xong)")
    args = ap.parse_args(argv)

    cfg = _shared.load_cfg()
    prop = _shared.ga4_property(cfg)
    bodies = all_reports(args.days, "today" if args.today else "yesterday")
    if args.dry_run:
        print(json.dumps({"property": prop, "reports": bodies}, indent=2))
        return 0

    if fetch is None:
        fetch = _shared.session_fetch(_shared.google_session(_shared.ga4_key_file(cfg), SCOPES))
    out = _shared.run_dir("ga4", args.out)
    api = api_url(prop)

    errors = {}
    for name, body in bodies.items():
        resp = fetch("POST", f"{api}:runReport", json=body)
        if resp.status_code != 200:
            # Lỗi hay gặp: service account chưa được thêm Viewer vào property, hoặc API chưa bật.
            errors[name] = {"status": resp.status_code, "body": resp.text[:1000]}
            print(f"  LỖI  {name}: HTTP {resp.status_code}")
            continue
        rows = flatten(resp.json())
        _shared.write_json(out / f"{name}.json", rows)
        print(f"  ok   {name}: {len(rows)} dòng")

    _shared.write_json(out / "_run.json", {
        "property": prop, "days": args.days,
        "pulled_at": dt.datetime.now().isoformat(timespec="seconds"), "errors": errors,
    })
    print(f"\nĐã ghi vào {_shared.show(out)} — {len(bodies) - len(errors)}/{len(bodies)} report, {len(errors)} lỗi")
    return 1 if errors and len(errors) == len(bodies) else 0


def main(argv=None, *, fetch=None) -> int:
    """`fetch(method, url, **kw) -> response kiểu requests` tiêm được (test); None ⇒ HTTP thật (service account)."""
    return _shared.run_main(_main, argv, fetch)


if __name__ == "__main__":
    sys.exit(main())
