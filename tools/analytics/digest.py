#!/usr/bin/env python3
"""Gộp số đã kéo (ga4_pull / asc_pull / crash_pull / subs_pull / web_pull) thành `insights.json` + `report.md`.

Chạy:
    python3 tools/analytics/digest.py                    # 28 ngày gần nhất
    python3 tools/analytics/digest.py --since 2026-11-01

Đọc lần kéo MỚI NHẤT của từng nguồn ở `<gốc>/<nguồn>/<YYYY-MM-DD>/` (gốc = `$ANALYTICS_OUT` hoặc
`<repo>/.temp/analytics`), ghi `<gốc>/insights.json` và `<gốc>/report.md`. Không gọi mạng, không cần phụ thuộc ngoài.
Nguồn thiếu ⇒ ghi chú trong `notes`, không lỗi. Lần kéo có báo cáo lỗi (`_run.json` `errors`) ⇒ status
`partial` + một ghi chú cho mỗi báo cáo lỗi. Không nguồn nào ⇒ vẫn ghi file (metrics rỗng), rc 0.

Schema insights.json:
    {"generated_at": ISO, "sources": {<nguồn>: {"status": ok|partial|missing|stale, "run": YYYY-MM-DD|null,
                                                "path": str|null}},
     "metrics": [{"name", "value", "unit", "source", "period"}], "notes": [str]}
`period` = "<từ>..<tới>" (ngày ISO). Tỉ lệ (retention) có unit "ratio" (0..1).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shared  # noqa: E402
import crash_watch  # noqa: E402
import retention  # noqa: E402

SOURCES = {"ga4": "ga4_pull.py", "asc": "asc_pull.py", "crash": "crash_pull.py", "subs": "subs_pull.py",
           "web": "web_pull.py"}
# Nguồn qua API admin của web: một file JSON, trạng thái nằm trong chính file (`missing` khi thiếu token/host).
API_FILES = {"subs": "subs.json", "web": "web.json"}
DEFAULT_DAYS = 28


def load(d: Path, name: str):
    p = d / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []


def iso(yyyymmdd: str) -> str:
    return crash_watch.iso(yyyymmdd)


def latest(source: str, root: Path) -> Path | None:
    base = root / source
    dirs = sorted(p for p in base.iterdir() if p.is_dir() and _is_date(p.name)) if base.is_dir() else []
    return dirs[-1] if dirs else None


def latest_valid(source: str, root: Path) -> Path | None:
    """Như `latest` nhưng cho nguồn API admin: bỏ qua thư mục không có JSON hợp lệ (lần kéo lỗi để lại thư mục rỗng),
    lấy thư mục mới nhất có file đọc được. Không có ⇒ None (nguồn `missing`)."""
    base = root / source
    dirs = sorted((p for p in base.iterdir() if p.is_dir() and _is_date(p.name)), reverse=True) if base.is_dir() else []
    return next((p for p in dirs if api_data(p, source)), None)


def _is_date(s: str) -> bool:
    try:
        dt.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join("" if c is None else str(c) for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def metric(name, value, unit, source, period):
    return {"name": name, "value": value, "unit": unit, "source": source, "period": period}


def _period(since: str, dates) -> str:
    dates = sorted(dates)
    return f"{since}..{dates[-1]}" if dates else f"{since}..{since}"


# ---------- GA4 ----------

def ga4_metrics(d: Path, since: str):
    daily = [r for r in load(d, "daily") if iso(r["date"]) >= since]
    period = _period(since, [iso(r["date"]) for r in daily])
    out = []
    if daily:
        out += [metric("ga4.new_users", sum(int(r.get("newUsers", 0)) for r in daily), "users", "ga4", period),
                metric("ga4.sessions", sum(int(r.get("sessions", 0)) for r in daily), "sessions", "ga4", period),
                metric("ga4.events", sum(int(r.get("eventCount", 0)) for r in daily), "events", "ga4", period),
                metric("ga4.active_users_daily_avg",
                       round(sum(int(r.get("activeUsers", 0)) for r in daily) / len(daily), 1),
                       "users/day", "ga4", period)]
    crash_daily = [r for r in load(d, "crash_daily") if iso(r["date"]) >= since]
    if (d / "crash_daily.json").is_file():
        out.append(metric("ga4.app_exception", sum(int(r.get("eventCount", 0)) for r in crash_daily), "events", "ga4",
                          _period(since, [iso(r["date"]) for r in crash_daily])))
    return out


def retention_rows(ga4, asc, today):
    """→ (cohorts, pooled {n: (quay lại, cỡ, tỉ lệ)}, bảng [ngày, người mới cohort, người mới GA4, tải ASC, D1.., D7..])
    hoặc None khi chưa có `retention_daily`."""
    if not ga4 or not (ga4 / "retention_daily.json").is_file():
        return None
    cohorts = retention.matrix(load(ga4, "retention_daily"), today - dt.timedelta(days=1))
    since = min((c["date"] for c in cohorts), default=today.isoformat())
    by = {c["date"]: c for c in cohorts}
    rows = []
    for d, app, alln, first in retention.new_users_daily(
            cohorts, load(ga4, "daily"), retention.asc_first_by_day(asc / "sales.tsv" if asc else None), since):
        if d >= today.isoformat():
            continue  # hôm nay chưa trọn ngày (chỉ có khi ga4_pull --today)
        c = by.get(d)
        rows.append([d, app, alln, first] + [c["active"][n] if c else None for n in retention.DAYS])
    return cohorts, {n: retention.pooled(cohorts, n) for n in retention.DAYS}, rows


def retention_metrics(ga4: Path, since: str, today: dt.date):
    got = retention_rows(ga4, None, today)
    if not got:
        return [], []
    cohorts = [c for c in got[0] if c["date"] >= since]
    out, notes = [], []
    period = _period(since, [c["date"] for c in cohorts])
    for n in retention.DAYS:
        back, size, rate = retention.pooled(cohorts, n)
        if rate is None:
            notes.append(f"retention D{n}: chưa có cohort nào từ {since} đủ {n} ngày")
            continue
        out.append(metric(f"retention.d{n}", round(rate, 4), "ratio", "ga4", period))
    return out, notes


# ---------- App Store Connect ----------

def asc_metrics(d: Path, since: str):
    p = d / "sales.tsv"
    if not p.is_file():
        return [], ["asc: lần kéo không có sales.tsv (chưa có giao dịch hoặc key thiếu quyền Sales and Reports)"]
    first, iap, dates = 0.0, 0.0, set()
    with p.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            day = r.get("report_date", "")
            if day < since:
                continue
            dates.add(day)
            kind, units = r.get("Product Type Identifier") or "", float(r.get("Units") or 0)
            if kind.startswith("1"):
                first += units
            elif kind.startswith("IA"):
                iap += units
    period = _period(since, dates)
    return [metric("asc.first_downloads", int(first), "downloads", "asc", period),
            metric("asc.in_app_purchases", int(iap), "purchases", "asc", period)], []


# ---------- Crash ----------

def crash_data(d: Path | None):
    p = d / "crashes.json" if d else None
    return json.loads(p.read_text(encoding="utf-8")) if p and p.is_file() else {}


def crash_metrics(d: Path, since: str):
    data = crash_data(d)
    crashes = [c for c in data.get("crashes", []) if str(c.get("reported_at", ""))[:10] >= since]
    records = data.get("records")
    out = [metric("crash.app_exception_users", len({c["u"] for c in crashes if str(c["fatal"]) == "1"}), "users",
                  "crash", _period(since, [c["reported_at"][:10] for c in crashes]))]
    notes = []
    if records is None:
        notes.append("crash: chưa có bản ghi Crashlytics trên BigQuery (chưa bật export hoặc chưa có bảng)")
    else:
        rs = [r for r in records if r["at"][:10] >= since]
        period = _period(since, [r["at"][:10] for r in rs])
        out += [metric("crash.fatal", sum(1 for r in rs if r["fatal"]), "crashes", "crash", period),
                metric("crash.nonfatal", sum(1 for r in rs if not r["fatal"]), "errors", "crash", period)]
    return out, notes


def crash_digest(d, ga4, today=None, watch=None):
    """Phần Markdown về crash: cảnh báo theo dõi, crash theo ngày × máy (GA4), từng lần app_exception, issue, bản ghi."""
    by_ver = [r for r in (load(ga4, "events_by_version") if ga4 else []) if r.get("eventName") == "app_exception"]
    data = crash_data(d)
    crashes, records = data.get("crashes", []), data.get("records") or []
    daily = load(ga4, "crash_daily") if ga4 else []
    if not by_ver and not crashes and not records and not daily:
        return ""
    today = today or dt.date.today()
    if watch is None:
        watch, reviewed, days = crash_watch.load_watch()
    else:
        reviewed, days = [], crash_watch.RECENT_DAYS
    fatal = [c for c in crashes if str(c["fatal"]) == "1"]
    recent = crash_watch.recent_table(daily, today, days)
    out = ["## Crash (Crashlytics → `app_exception`)\n",
           f"### Theo dõi ({days} ngày gần nhất)\n",
           "\n".join({"alert": "- ⚠ ", "new": "- 🆕 ", "info": "- "}[a["level"]] + a["text"]
                     for a in crash_watch.alerts(records, daily, watch, today, reviewed, days)) or "- Không có cảnh báo.",
           "\n### Crash theo ngày × máy (GA4 `app_exception`)\n",
           table(["ngày", "máy", "iOS", "bản", "nước", "lượt"], recent) if recent else "(không có crash trong cửa sổ)\n",
           f"**{len(fatal)} crash thật** / {len({c['u'] for c in fatal})} người (BigQuery `fatal=1`)"
           + (f" · ⚠ {len(crashes) - len(fatal)} app_exception có `fatal≠1`" if len(crashes) > len(fatal) else "")
           + f" · {sum(not r['fatal'] for r in records)} lỗi non-fatal (Crashlytics).\n"]
    if by_ver:
        out += ["### app_exception theo version (GA4)\n",
                table(["version", "lượt", "người"], [[r["appVersion"], r["eventCount"], r["totalUsers"]] for r in by_ver])]
    if crashes:
        out.append("### Từng lần app_exception (BigQuery) — event ngay trước\n")
        for c in crashes:
            seq = " → ".join(b["n"] + (f"[{b['screen']}]" if b.get("screen") else "") for b in c["before"])
            kind = f"**CRASH {c['reported_at']}**" if str(c["fatal"]) == "1" else f"non-fatal {c['reported_at']}"
            out.append(f"- {kind} · bản {c['v']} · {c['model']} · {c['os']} · {c['country']} · "
                       f"store_env={c.get('env')}  \n  trước đó: {seq or '(không có)'}")
    if isinstance(data.get("issues"), list) and data["issues"]:
        out.append("\n### Issue Crashlytics (crash thật trước)\n")
        out.append(table(["loại", "issue", "chi tiết", "lượt", "người", "version", "lần cuối"],
                         [["crash" if i["fatal"] else "non-fatal", i["title"], i["subtitle"], i["n"], i["users"],
                           ", ".join(i["versions"] or []), i["last"]] for i in data["issues"]]))
    if records:
        out.append(f"\n### Bản ghi Crashlytics — {len(records)} bản, mới nhất {records[-1]['at']} (UTC)\n")
        out.append(table(["lúc (UTC)", "loại", "mã", "bản", "máy · iOS", "4 breadcrumb cuối"],
                         [[r["at"], "crash" if r["fatal"] else "non-fatal",
                           r["keys"].get("code") or r["issue_subtitle"], r["v"], f"{r['model']} · {r['os']}",
                           " → ".join(r["crumbs"][-4:]) or (r["blame"] if r["fatal"] else "")]
                          for r in records[-20:]]))
    return "\n".join(out)


# ---------- Subs / Web (API admin của web) ----------

def api_data(d: Path | None, src: str) -> dict:
    p = d / API_FILES[src] if d else None
    try:
        data = json.loads(p.read_text(encoding="utf-8")) if p and p.is_file() else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def subs_metrics(d: Path, since: str):
    data = api_data(d, "subs")
    period = f"{max(data.get('since') or since, since)}..{d.name}"
    by_type = data.get("events_by_type") or {}
    active = data.get("active_estimate_by_product") or {}
    out = [metric("subs.events", sum(by_type.values()), "events", "subs", period),
           metric("subs.renewals", data.get("renewals", 0), "events", "subs", period),
           metric("subs.cancellations", data.get("cancellations", 0), "events", "subs", period),
           metric("subs.refunds", data.get("refunds", 0), "events", "subs", period),
           metric("subs.active_estimate", sum(active.values()), "subscriptions", "subs", period)]
    out += [metric(f"subs.active_estimate.{p}", n, "subscriptions", "subs", period) for p, n in sorted(active.items())]
    return out, []


def web_metrics(d: Path, since: str):
    data = api_data(d, "web")
    days = int(data.get("days") or 30)
    start = (dt.date.fromisoformat(d.name) - dt.timedelta(days=days - 1)).isoformat()
    period = f"{max(start, since)}..{d.name}"
    out = [metric("web.pageviews", sum(int(p.get("views", 0)) for p in data.get("pages") or []), "views", "web", period)]
    if data.get("feedback_open") is not None:
        out.append(metric("web.feedback_open", data["feedback_open"], "items", "web", period))
        if data.get("feedback_open_capped"):
            out.append(metric("web.feedback_open_capped", True, "bool", "web", period))
    return out, []


def api_digest(subs: Path | None, web: Path | None) -> str:
    """Phần Markdown của subs/web: sự kiện gói theo loại, trang/nguồn/nước/thiết bị hàng đầu."""
    out = []
    s = api_data(subs, "subs")
    if s.get("events_by_type"):
        out += [f"## Gói đăng ký (App Store Server Notifications, {s.get('days', '?')} ngày)\n",
                table(["loại sự kiện", "lượt"], list(s["events_by_type"].items())),
                table(["sản phẩm", "gói còn hiệu lực (ước lượng trong cửa sổ)"],
                      list((s.get("active_estimate_by_product") or {}).items()))]
    w = api_data(web, "web")
    if w.get("pages"):
        out += [f"## Web ({w.get('days', '?')} ngày)\n",
                table(["trang", "lượt xem"], [[p["page"], p["views"]] for p in w["pages"][:10]])]
        for title, key, col in (("Nguồn giới thiệu", "referrers", "domain"), ("Nước", "countries", "country"),
                                ("Thiết bị", "devices", "device")):
            if w.get(key):
                out += [f"### {title}\n", table([col, "lượt"], [[r[col], r["n"]] for r in w[key][:10]])]
        if w.get("feedback_open") is not None:
            more = " (đầy trang, có thể nhiều hơn)" if w.get("feedback_open_capped") else ""
            out.append(f"Feedback đang mở: **{w['feedback_open']}**{more}\n")
    return "\n".join(out)


# ---------- Gộp ----------

def run_errors(d: Path) -> dict:
    """Báo cáo lỗi của lần kéo (`_run.json` → `errors` {tên: {status, body}}); không có file ⇒ {}."""
    p = d / "_run.json"
    if not p.is_file():
        return {}
    try:
        errors = json.loads(p.read_text(encoding="utf-8")).get("errors") or {}
    except (ValueError, AttributeError):
        return {"_run.json": {"status": "JSON hỏng"}}
    return errors if isinstance(errors, dict) else {}


def build(root: Path, since: str, today: dt.date):
    """→ (insights dict, report markdown). Hàm thuần trên thư mục đầu ra."""
    sources, metrics, notes, dirs = {}, [], [], {}
    for src, tool in SOURCES.items():
        d = latest_valid(src, root) if src in API_FILES else latest(src, root)
        dirs[src] = d
        if d is None:
            sources[src] = {"status": "missing", "run": None, "path": None}
            notes.append(f"{src}: chưa có dữ liệu — chạy python3 tools/analytics/{tool}")
            continue
        stale = d.name < since
        failed = run_errors(d)
        status = "stale" if stale else ("partial" if failed else "ok")
        if src in API_FILES:
            file_status = api_data(d, src).get("status")
            if file_status == "missing":
                sources[src] = {"status": "missing", "run": d.name, "path": f"{src}/{d.name}"}
                notes.append(f"{src}: chưa có dữ liệu — {api_data(d, src).get('reason', 'thiếu cấu hình')}; "
                             f"chạy python3 tools/analytics/{tool}")
                dirs[src] = None
                continue
            if file_status == "partial" and not stale:
                status = "partial"
                notes.append(f"{src}: lần kéo chỉ lấy được một phần — chỉ số thiếu, kéo lại bằng "
                             f"python3 tools/analytics/{tool}")
        sources[src] = {"status": status, "run": d.name, "path": f"{src}/{d.name}"}
        if stale:
            notes.append(f"{src}: lần kéo mới nhất ({d.name}) cũ hơn --since {since} — kéo lại")
        for name, err in sorted(failed.items()):
            notes.append(f"{src}: báo cáo {name} lỗi lúc kéo (HTTP {err.get('status', '?')}) — "
                         f"chỉ số dựa trên nó bị thiếu, kéo lại bằng python3 tools/analytics/{tool}")
    if dirs["ga4"]:
        metrics += ga4_metrics(dirs["ga4"], since)
        m, n = retention_metrics(dirs["ga4"], since, dt.date.fromisoformat(dirs["ga4"].name))
        metrics += m
        notes += n
    if dirs["asc"]:
        m, n = asc_metrics(dirs["asc"], since)
        metrics += m
        notes += n
    if dirs["crash"]:
        m, n = crash_metrics(dirs["crash"], since)
        metrics += m
        notes += n
    if dirs["subs"]:
        m, n = subs_metrics(dirs["subs"], since)
        metrics += m
        notes += n
    if dirs["web"]:
        m, n = web_metrics(dirs["web"], since)
        metrics += m
        notes += n
    insights = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "sources": sources,
                "metrics": metrics, "notes": notes}
    return insights, report_md(insights, dirs, since, today)


def report_md(insights, dirs, since, today):
    out = [f"# Báo cáo số liệu từ {since}\n",
           f"Tạo lúc {insights['generated_at']}. Nguồn: "
           + ", ".join(f"{k} {v['status']}" + (f" ({v['run']})" if v["run"] else "")
                       for k, v in insights["sources"].items()) + ".\n"]
    if insights["metrics"]:
        out += ["## Chỉ số\n", table(["chỉ số", "giá trị", "đơn vị", "nguồn", "kỳ"],
                                     [[m["name"], m["value"], m["unit"], m["source"], m["period"]]
                                      for m in insights["metrics"]])]
    if insights["notes"]:
        out += ["## Ghi chú\n", "\n".join(f"- {n}" for n in insights["notes"]) + "\n"]
    ga4 = dirs.get("ga4")
    if ga4:
        events = load(ga4, "events")[:15]
        if events:
            out += ["## Event nhiều nhất (cả cửa sổ lần kéo GA4)\n",
                    table(["event", "lượt", "người"], [[r["eventName"], r["eventCount"], r["totalUsers"]] for r in events])]
    crash = crash_digest(dirs.get("crash"), ga4, today)
    if crash:
        out.append(crash)
    api = api_digest(dirs.get("subs"), dirs.get("web"))
    if api:
        out.append(api)
    return "\n".join(out)


def _main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", help=f"ngày bắt đầu (YYYY-MM-DD), mặc định {DEFAULT_DAYS} ngày trước")
    args = ap.parse_args(argv)
    today = dt.date.today()
    if args.since:
        try:
            since = dt.date.fromisoformat(args.since).isoformat()
        except ValueError:
            raise _shared.Refuse(f"FAIL: --since phải là YYYY-MM-DD: {args.since!r}") from None
    else:
        since = (today - dt.timedelta(days=DEFAULT_DAYS)).isoformat()
    root = _shared.out_root()
    root.mkdir(parents=True, exist_ok=True)
    insights, md = build(root, since, today)
    _shared.write_json(root / "insights.json", insights)
    (root / "report.md").write_text(md, encoding="utf-8")
    print(f"  ok   {len(insights['metrics'])} chỉ số, {len(insights['notes'])} ghi chú → "
          f"{_shared.show(root / 'insights.json')}, {_shared.show(root / 'report.md')}")
    return 0


def main(argv=None) -> int:
    return _shared.run_main(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
