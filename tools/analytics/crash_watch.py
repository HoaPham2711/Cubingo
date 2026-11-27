#!/usr/bin/env python3
"""Theo dõi crash hằng ngày: một issue đã biết có lan sang máy khác không, có issue crash mới không.

Không gọi API — chỉ đọc output của crash_pull.py (bản ghi Crashlytics, có issue, trễ ~1 ngày) và report
`crash_daily` của ga4_pull.py (`app_exception` theo ngày × máy, KHÔNG có issue), rồi so với danh sách theo dõi.

Danh sách theo dõi (thứ tự ưu tiên): `$CRASH_WATCH_FILE` nếu đặt; không thì `tools/app/crash_watch.json` của app nếu có
(file của app, không thuộc lớp đồng bộ — nơi app ghi issue nó theo dõi); không thì `crash_watch.json` cạnh file này
(mặc định chung của lõi: ngưỡng `recent_days`, chưa theo dõi issue nào — không ghi issue của app vào đây). Dạng: {"recent_days": 7, "issues": [{issue_id, name, status,
known_devices: [{model, os}]}], "reviewed": [{model, os, through}]}.

Máy = mã model + iOS (VD `iPhone18,1` · `26.5.1`). Hai khách cùng model + iOS bị coi là một máy — đủ để trả lời
"có lan sang máy khác không", không đủ để đếm người. digest.py gọi `alerts()`.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

WATCH_FILE = Path(__file__).resolve().parent / "crash_watch.json"
# Danh sách riêng của app (app-owned, ngoài lớp đồng bộ): <gốc repo>/tools/app/crash_watch.json.
APP_WATCH_FILE = Path(__file__).resolve().parents[2] / "tools" / "app" / "crash_watch.json"
RECENT_DAYS = 7  # cửa sổ "gần đây" mặc định (crash_watch.json `recent_days` ghi đè)


def norm_os(v):
    """'iOS 26.5.1' / '26.3.0' / '26.5.1' → '26.5.1' / '26.3' / '26.5.1' (GA4 và Crashlytics ghi khác nhau)."""
    v = (v or "").replace("iOS", "").strip()
    parts = v.split(".")
    while len(parts) > 2 and parts[-1] == "0":
        parts.pop()
    return ".".join(parts)


def device_key(model, os_version):
    return (model or "?", norm_os(os_version))


def watch_path() -> Path:
    """`$CRASH_WATCH_FILE` > `tools/app/crash_watch.json` (nếu có) > mặc định chung của lõi."""
    v = os.environ.get("CRASH_WATCH_FILE", "")
    if v:
        return Path(v).expanduser()
    return APP_WATCH_FILE if APP_WATCH_FILE.is_file() else WATCH_FILE


def load_watch(path=None):
    """→ (issues, reviewed, recent_days); thiếu file ⇒ ([], [], RECENT_DAYS)."""
    path = path or watch_path()
    d = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return d.get("issues", []), d.get("reviewed", []), int(d.get("recent_days", RECENT_DAYS))


def alerts(records, crash_daily, watch, today, reviewed=(), recent_days=RECENT_DAYS):
    """→ [{"level": "alert"|"new"|"info", "text": str}], cảnh báo trước. Hàm thuần.

    records: bản ghi Crashlytics đã chuẩn hoá (crash_pull.normalize_record) hoặc [] khi chưa có export.
    crash_daily: hàng GA4 {date YYYYMMDD, deviceModel, operatingSystemVersion, appVersion, country, eventCount}.
    reviewed: [{model, os, through}] — crash GA4 trên máy đó tới hết ngày `through` đã xem, không báo lại.
    """
    out = []
    since = (today - dt.timedelta(days=recent_days)).isoformat()
    known_all = {device_key(d["model"], d["os"]) for w in watch for d in w.get("known_devices", [])}
    watched_ids = {w["issue_id"] for w in watch}
    for w in watch:
        if w.get("status") == "closed":
            continue
        known = {device_key(d["model"], d["os"]) for d in w.get("known_devices", [])}
        rs = [r for r in records if r["issue_id"] == w["issue_id"]]
        if not rs:
            out.append({"level": "info", "text": f"{w['name']}: chưa có bản ghi Crashlytics nào trên BigQuery "
                                                 f"(export trễ ~1 ngày) — máy đã biết: {fmt_devices(known)}."})
            continue
        devices = {device_key(r["model"], r["os"]) for r in rs}
        spread = devices - known
        last = max(r["at"] for r in rs)
        versions = sorted({r["v"] for r in rs})
        if spread:
            n_new = sum(device_key(r["model"], r["os"]) in spread for r in rs)
            out.append({"level": "alert", "text": f"{w['name']} ĐÃ XUẤT HIỆN TRÊN MÁY KHÁC: {fmt_devices(spread)} "
                                                  f"({n_new} lần) — ngoài máy đã biết {fmt_devices(known)}. "
                                                  f"Tổng {len(rs)} lần, bản {', '.join(versions)}, lần cuối {last}."})
        else:
            out.append({"level": "info", "text": f"{w['name']}: {len(rs)} lần, CHỈ trên máy đã biết "
                                                 f"{fmt_devices(known)}, bản {', '.join(versions)}, lần cuối {last}."})
    fresh = {}
    for r in records:
        if r["fatal"] and r["issue_id"] not in watched_ids and r["at"][:10] >= since:
            fresh.setdefault(r["issue_id"], []).append(r)
    for iid, rs in sorted(fresh.items(), key=lambda kv: -len(kv[1])):
        devices = {device_key(r["model"], r["os"]) for r in rs}
        out.append({"level": "new", "text": f"Issue crash MỚI chưa theo dõi {iid[:8]} "
                                            f"({rs[0]['issue_subtitle'] or rs[0]['issue_title']}): "
                                            f"{len(rs)} lần trên {fmt_devices(devices)}, "
                                            f"bản {', '.join(sorted({r['v'] for r in rs}))}, "
                                            f"lần cuối {max(r['at'] for r in rs)} — xem stack trace rồi thêm vào "
                                            f"danh sách theo dõi."})
    seen_through = {device_key(v["model"], v["os"]): v["through"] for v in reviewed}
    recent = [r for r in crash_daily if iso(r["date"]) >= since]
    other = {}
    for r in recent:
        k = device_key(r["deviceModel"], r["operatingSystemVersion"])
        if k not in known_all and iso(r["date"]) > seen_through.get(k, ""):
            other.setdefault(k, []).append(r)
    for k, rs in sorted(other.items()):
        out.append({"level": "alert", "text": f"GA4: crash trên máy CHƯA GẶP {fmt_devices({k})} — "
                                              f"{sum(r['eventCount'] for r in rs)} lần, "
                                              f"ngày {', '.join(sorted({iso(r['date']) for r in rs}))}, "
                                              f"bản {', '.join(sorted({r['appVersion'] for r in rs}))}. "
                                              f"Chưa biết issue nào (chờ BigQuery Crashlytics hoặc xem Console)."})
    order = {"alert": 0, "new": 1, "info": 2}
    return sorted(out, key=lambda a: order[a["level"]])


def recent_table(crash_daily, today, recent_days=RECENT_DAYS):
    """Hàng GA4 trong `recent_days` ngày gần nhất, mới trước: [ngày, máy, iOS, bản, nước, lượt]."""
    since = (today - dt.timedelta(days=recent_days)).isoformat()
    rows = [[iso(r["date"]), r["deviceModel"], norm_os(r["operatingSystemVersion"]), r["appVersion"], r["country"],
             r["eventCount"]] for r in crash_daily if iso(r["date"]) >= since]
    return sorted(rows, key=lambda r: (r[0], r[5]), reverse=True)


def iso(yyyymmdd):
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}" if "-" not in yyyymmdd else yyyymmdd


def fmt_devices(keys):
    return ", ".join(f"{m} · iOS {o}" for m, o in sorted(keys)) or "(chưa có)"
