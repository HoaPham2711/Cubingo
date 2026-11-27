#!/usr/bin/env python3
"""Kéo các lần crash (event `app_exception` do Crashlytics ghi vào Analytics) từ BigQuery export của GA4,
kèm ngữ cảnh: máy, bản, nước, môi trường cài, và các event NGAY TRƯỚC lần crash của chính người đó; cộng
MỌI bản ghi Crashlytics (fatal lẫn non-fatal) từ BigQuery export của Crashlytics.

Chạy:
    python3 tools/analytics/crash_pull.py            # → .temp/analytics/crash/<ngày>/crashes.json

Cấu hình: project BigQuery `$GA4_BQ_PROJECT` hoặc `[analytics] bq_project`; dataset `$GA4_BQ_DATASET` hoặc
`analytics_<ga4_property>`; vùng `$GA4_BQ_LOCATION` (tuỳ chọn, mặc định để BigQuery tự chọn). Thiếu project/
property ⇒ từ chối một dòng, rc 2. Xác thực bằng service account của ga4_pull.py (thêm role BigQuery Job User +
Data Viewer). Không in key.

Lưu ý:
- Crashlytics ghi `app_exception` khi app MỞ LẠI sau crash ⇒ "ngữ cảnh" = các event trước mốc đó.
- BigQuery export trễ ~1 ngày ⇒ crash hôm nay chưa có ở đây; đếm sơ bộ xem `crash_daily` của ga4_pull.py.
- Lỗi non-fatal app tự ghi KHÔNG sinh `app_exception` ⇒ `app_exception` ≈ crash thật; non-fatal chỉ đọc được ở
  `records` (dataset `firebase_crashlytics`, chỉ có từ ngày bật export).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shared  # noqa: E402
from _shared import Refuse  # noqa: E402

BQ = "https://bigquery.googleapis.com/bigquery/v2/projects/"
SCOPES = ["https://www.googleapis.com/auth/bigquery"]
CONTEXT_EVENTS = 8  # số event trước crash giữ lại
SKIP = ("user_engagement", "screen_view", "session_start", "firebase_campaign")
CRUMBS = 12  # số breadcrumb cuối giữ lại (mới → cũ trong SQL, đảo lại cũ → mới ở Python)

# `store_env` / `internal_device` là user property do Core/Telemetry gắn; `firebase_screen` / `fatal` là chuẩn.
CRASHES = """
WITH ev AS (  -- events_* gồm cả events_intraday_* ⇒ khử trùng
  SELECT DISTINCT user_pseudo_id u, event_timestamp ts, event_name n, event_date d,
    app_info.version v, device.mobile_model_name model,
    device.operating_system_version os, geo.country country,
    (SELECT value.string_value FROM UNNEST(user_properties) WHERE key='store_env') env,
    (SELECT value.string_value FROM UNNEST(user_properties) WHERE key='internal_device') internal,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key='firebase_screen') screen,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key='fatal') fatal
  FROM `{table}`
),
crash AS (SELECT * FROM ev WHERE n = 'app_exception'),
ctx AS (  -- BigQuery không cho subquery tương quan qua bảng ⇒ JOIN + đánh số
  SELECT c.u, c.ts cts, p.ts, p.n, p.screen,
    ROW_NUMBER() OVER (PARTITION BY c.u, c.ts ORDER BY p.ts DESC) k
  FROM crash c JOIN ev p ON p.u = c.u AND p.ts < c.ts AND p.n NOT IN {skip}
)
SELECT c.d, FORMAT_TIMESTAMP('%Y-%m-%d %H:%M', TIMESTAMP_MICROS(c.ts)) reported_at, c.u, c.v, c.model, c.os,
  c.country, c.env, c.internal, c.fatal,
  ARRAY_AGG(IF(y.x_ts IS NULL, NULL, STRUCT(FORMAT_TIMESTAMP('%H:%M:%S', TIMESTAMP_MICROS(y.x_ts)) AS t,
            y.x_n AS n, y.x_screen AS screen)) IGNORE NULLS ORDER BY y.x_ts) before
FROM crash c LEFT JOIN (SELECT u, cts, ts x_ts, n x_n, screen x_screen FROM ctx WHERE k <= {context}) y
  ON y.u = c.u AND y.cts = c.ts
GROUP BY c.d, c.ts, c.u, c.v, c.model, c.os, c.country, c.env, c.internal, c.fatal
ORDER BY c.ts
"""

# Giờ UTC (mọi app, mọi múi giờ) — đọc cùng cột `received` để biết độ trễ batch.
RECORDS = """SELECT FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', event_timestamp) `at`,
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M', received_timestamp) received, is_fatal fatal, error_type,
  issue_id, issue_title, issue_subtitle, blame_frame.symbol blame, application.display_version v, device.model model,
  operating_system.display_version os, installation_uuid install, process_state,
  ARRAY(SELECT AS STRUCT key, value FROM UNNEST(custom_keys) ORDER BY key) keys,
  ARRAY(SELECT message FROM UNNEST(logs) ORDER BY timestamp DESC LIMIT {n}) crumbs
FROM `{table}` ORDER BY event_timestamp"""


def bq_target(cfg: dict) -> tuple[str, str]:
    """(project, dataset) — env thắng cấu hình; thiếu ⇒ Refuse một dòng."""
    project = _shared.env_or("GA4_BQ_PROJECT", str(_shared.appconfig.opt(cfg, "analytics.bq_project", "") or ""))
    if not project:
        raise Refuse("FAIL: chưa có project BigQuery — đặt [analytics] bq_project trong app.config.toml "
                     "(hoặc biến GA4_BQ_PROJECT)")
    dataset = os.environ.get("GA4_BQ_DATASET", "")
    if not dataset:
        prop = str(_shared.appconfig.opt(cfg, "analytics.ga4_property", "") or "")
        prop = _shared.env_or("GA4_PROPERTY_ID", prop)
        if not prop:
            raise Refuse("FAIL: chưa biết dataset GA4 export — đặt [analytics] ga4_property "
                         "(dataset = analytics_<property>) hoặc biến GA4_BQ_DATASET")
        dataset = f"analytics_{prop}"
    check_ident("project BigQuery", project)
    check_ident("dataset BigQuery", dataset)
    location = os.environ.get("GA4_BQ_LOCATION", "")
    if location:
        check_ident("GA4_BQ_LOCATION", location)
    return project, dataset


_RE_IDENT = re.compile(r"[A-Za-z0-9_.-]+")


def check_ident(label: str, value: str) -> None:
    """Project/dataset/vùng được ghép thẳng vào SQL và URL ⇒ chỉ cho chữ, số, '_', '.', '-'."""
    if not _RE_IDENT.fullmatch(value):
        raise Refuse(f"FAIL: {label} sai dạng (chỉ chữ, số, '_', '.', '-'): {value!r}")


def crashes_sql(project, dataset):
    return CRASHES.format(table=f"{project}.{dataset}.events_*", skip=SKIP, context=CONTEXT_EVENTS)


def query(fetch, project, sql):
    body = {"query": sql, "useLegacySql": False, "timeoutMs": 90000}
    loc = os.environ.get("GA4_BQ_LOCATION", "")
    if loc:
        body["location"] = loc
    r = fetch("POST", f"{BQ}{project}/queries", json=body)
    try:
        doc = r.json()
    except ValueError:
        doc = {}
    if r.status_code != 200 or "error" in doc:
        raise RuntimeError(doc.get("error", {}).get("message", f"HTTP {r.status_code}"))
    return [_row(doc["schema"]["fields"], row) for row in doc.get("rows", [])]


def _row(fields, row):
    """BigQuery REST {f:[{v}]} → dict, đệ quy cho RECORD/REPEATED."""
    out = {}
    for f, cell in zip(fields, row["f"]):
        v = cell["v"]
        if f["type"] == "RECORD":
            v = [_row(f["fields"], x["v"]) for x in v] if f.get("mode") == "REPEATED" else _row(f["fields"], v)
        out[f["name"]] = v
    return out


def group_issues(records):
    """Gộp bản ghi Crashlytics theo issue_id → [{issue_id, title, subtitle, fatal, n, users, versions, first, last}],
    crash thật trước, rồi theo số lượt giảm dần. Hàm thuần."""
    by = {}
    for r in records:
        g = by.setdefault(r["issue_id"], {"issue_id": r["issue_id"], "title": r["issue_title"],
                                         "subtitle": r["issue_subtitle"], "fatal": r["fatal"], "n": 0,
                                         "users": set(), "versions": set(), "first": r["at"], "last": r["at"]})
        g["n"] += 1
        g["users"].add(r["install"])
        g["versions"].add(r["v"])
        g["first"], g["last"] = min(g["first"], r["at"]), max(g["last"], r["at"])
    out = [dict(g, users=len(g["users"]), versions=sorted(g["versions"])) for g in by.values()]
    return sorted(out, key=lambda g: (not g["fatal"], -g["n"], g["issue_id"]))


def normalize_record(r):
    """Hàng BigQuery (chuỗi) → kiểu dùng được: fatal bool, keys dict, crumbs cũ → mới.
    Mảng chuỗi qua REST về dạng [{"v": "..."}] (xem `_row`)."""
    crumbs = [c["v"] if isinstance(c, dict) else c for c in r["crumbs"] or []]
    return dict(r, fatal=r["fatal"] in (True, "true"), keys={k["key"]: k["value"] for k in r["keys"] or []},
                crumbs=list(reversed(crumbs)))


def crashlytics_records(fetch, project):
    """Mọi bản ghi Crashlytics nếu đã bật Crashlytics → BigQuery export; chưa bật ⇒ None; bật mà chưa có bảng ⇒
    "pending"."""
    ds = [d["datasetReference"]["datasetId"]
          for d in fetch("GET", f"{BQ}{project}/datasets", timeout=30).json().get("datasets", [])]
    if "firebase_crashlytics" not in ds:
        return None
    tables = fetch("GET", f"{BQ}{project}/datasets/firebase_crashlytics/tables", timeout=30).json().get("tables", [])
    if not tables:
        return "pending"
    return [normalize_record(r) for r in query(fetch, project, RECORDS.format(
        n=CRUMBS, table=f"{project}.firebase_crashlytics.*"))]


def _main(argv, fetch):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=None, help="thư mục đầu ra (mặc định <gốc>/crash/<ngày>)")
    args = ap.parse_args(argv)

    cfg = _shared.load_cfg()
    project, dataset = bq_target(cfg)
    if fetch is None:
        fetch = _shared.session_fetch(_shared.google_session(_shared.ga4_key_file(cfg), SCOPES))
    try:
        crashes = query(fetch, project, crashes_sql(project, dataset))
    except RuntimeError as e:
        print(f"  LỖI  BigQuery {project}.{dataset}: {e}", file=sys.stderr)
        return 1
    for c in crashes:
        c["before"] = c["before"] or []
    try:
        records = crashlytics_records(fetch, project)
    except RuntimeError as e:
        print(f"  cảnh báo: không đọc được firebase_crashlytics ({e})", file=sys.stderr)
        records = "error"
    if records == "error":
        records, note = None, " — LỖI đọc firebase_crashlytics (xem cảnh báo)"
    elif records == "pending":
        records, note = None, " — Crashlytics→BigQuery ĐÃ BẬT nhưng chưa có bảng (chờ ~24 h)"
    elif records is None:
        note = " — chưa bật Crashlytics→BigQuery nên chưa có stack trace"
    else:
        fatal = sum(r["fatal"] for r in records)
        note = f" — Crashlytics: {fatal} crash thật + {len(records) - fatal} non-fatal"
    issues = group_issues(records) if records is not None else None
    out = _shared.run_dir("crash", args.out)
    _shared.write_json(out / "crashes.json", {"crashes": crashes, "issues": issues, "records": records,
                                              "pulled_at": dt.datetime.now().isoformat(timespec="seconds")})
    users = {c["u"] for c in crashes}
    fatal = sum(str(c["fatal"]) == "1" for c in crashes)
    print(f"  ok   crash: {len(crashes)} lần app_exception ({fatal} fatal) / {len(users)} người "
          f"(BigQuery, trễ ~1 ngày){note} → {_shared.show(out / 'crashes.json')}")
    return 0


def main(argv=None, *, fetch=None) -> int:
    """`fetch(method, url, **kw) -> response kiểu requests` tiêm được (test); None ⇒ HTTP thật (service account)."""
    return _shared.run_main(_main, argv, fetch)


if __name__ == "__main__":
    sys.exit(main())
