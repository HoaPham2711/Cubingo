#!/usr/bin/env python3
"""Kéo sự kiện gói (App Store Server Notifications V2) từ API admin của web về `subs.json` — gom số, không mã thô.

Chạy:
    python3 tools/analytics/subs_pull.py                # 30 ngày gần nhất → <gốc>/subs/<ngày>/subs.json
    python3 tools/analytics/subs_pull.py --days 90 --out <thư mục>

Nguồn: `GET https://<web.host_prod>/api/v1/admin/subscription-events?since=<ms>&limit=500` (Bearer ADMIN_TOKEN).
Token: file `$WEB_ADMIN_TOKEN_FILE` hoặc `<config_dir>/web-admin-token` (ngoài repo, không bao giờ in).
`features.web_api` tắt (không có API) hoặc thiếu host/token ⇒ ghi `{"status": "missing"}` + lý do, rc 0, không gọi mạng. HTTP 401/429 ⇒ rc 2, một dòng hướng dẫn.

Phân trang: `since` GỒM mốc (>=). Trang sau dùng `since` = `signed_date` cuối (không +1), khử trùng theo
`notification_uuid`, dừng khi trang ít hơn `limit`. Trang đầy mà không thêm gì mới (≥ limit sự kiện trùng một mốc ms)
thì nhích `since` thêm 1 ms để không kẹt vòng lặp.

Đầu ra CHỈ gồm số gộp: `events_by_type` ("TYPE" hoặc "TYPE/SUBTYPE" → đếm, chỉ môi trường Production, không tính TEST),
`renewals` (DID_RENEW), `cancellations` (tắt gia hạn), `refunds` (REFUND), `active_estimate_by_product` (số gói còn
hiệu lực theo sản phẩm, ước lượng từ chính các sự kiện trong cửa sổ — gói bắt đầu trước cửa sổ và không có sự kiện nào
trong đó thì không được đếm), `excluded` (Sandbox / TEST). `original_tx_id` và `notification_uuid` CHỈ dùng trong bộ nhớ
(ước lượng + khử trùng), không ghi ra file hay in.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shared  # noqa: E402

PAGE_LIMIT = 500  # trần của admin.ts (SUB_EVENTS_MAX)
MAX_PAGES = 1000  # chặn vòng lặp vô hạn nếu server trả bất thường
DEFAULT_DAYS = 30
DAY_MS = 86_400_000
_ENDING = {"EXPIRED", "REVOKE", "REFUND", "GRACE_PERIOD_EXPIRED"}
_STARTING = {"SUBSCRIBED", "DID_RENEW"}


def fetch_events(fetch, host, token, token_file, since_ms):
    """Mọi sự kiện có `signed_date >= since_ms`, khử trùng theo `notification_uuid`. → (items, truncated)."""
    seen, items, since = set(), [], since_ms
    for _ in range(MAX_PAGES):
        page = _shared.admin_get(fetch, host, token, token_file, "subscription-events",
                                 {"since": since, "limit": PAGE_LIMIT}).get("items") or []
        new = [i for i in page if i.get("notification_uuid") not in seen]
        seen.update(i.get("notification_uuid") for i in new)
        items += new
        if len(page) < PAGE_LIMIT:
            return items, False
        last = max(int(i.get("signed_date") or 0) for i in page)
        since = last + 1 if not new else last
    return items, True


def summarize(items) -> dict:
    """Gom sự kiện thành số — hàm thuần. Chỉ Production (khác TEST) vào số khách; Sandbox/TEST đếm riêng."""
    by_type, excluded, state = {}, {"sandbox": 0, "test": 0}, {}
    renewals = cancellations = refunds = 0
    for e in sorted(items, key=lambda i: (int(i.get("signed_date") or 0), str(i.get("notification_uuid")))):
        t, sub = e.get("type"), e.get("subtype")
        if t == "TEST":
            excluded["test"] += 1
            continue
        if e.get("environment") != "Production":
            excluded["sandbox"] += 1
            continue
        key = f"{t}/{sub}" if sub else str(t)
        by_type[key] = by_type.get(key, 0) + 1
        renewals += t == "DID_RENEW"
        refunds += t == "REFUND"
        cancellations += (t, sub) == ("DID_CHANGE_RENEWAL_STATUS", "AUTO_RENEW_DISABLED")
        tx = e.get("original_tx_id")
        if tx and (t in _STARTING or t in _ENDING):
            st = state.setdefault(tx, {"active": False, "product": None})
            st["active"] = t in _STARTING
            st["product"] = e.get("product_id") or st["product"]
    active: dict[str, int] = {}
    for st in state.values():
        if st["active"]:
            p = st["product"] or "unknown"
            active[p] = active.get(p, 0) + 1
    return {"events_by_type": dict(sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0]))),
            "active_estimate_by_product": dict(sorted(active.items())),
            "renewals": renewals, "cancellations": cancellations, "refunds": refunds, "excluded": excluded}


def _main(argv, fetch, now_ms):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=_shared.retained_days, default=DEFAULT_DAYS)
    ap.add_argument("--out", type=Path, default=None, help="thư mục đầu ra (mặc định <gốc>/subs/<ngày>)")
    args = ap.parse_args(argv)

    cfg = _shared.load_cfg()
    host, token, token_file = _shared.web_admin(cfg)
    def out_dir():  # tạo thư mục CHỈ khi sắp ghi — lần kéo lỗi không để lại thư mục rỗng
        return _shared.run_dir("subs", args.out)

    if not _shared.web_api_on(cfg) or not host or not token:
        # web_api tắt ⇒ app không có API (Ruling 11) — không có gì để kéo, không gọi mạng.
        why = ("features.web_api tắt (không có API)" if not _shared.web_api_on(cfg)
               else "chưa đặt web.host_prod trong app.config.toml" if not host
               else f"thiếu token admin — đặt ADMIN_TOKEN vào {token_file}")
        _shared.write_json(out_dir() / "subs.json", {"status": "missing", "reason": why})
        print(f"  --   subs: {why} (bỏ qua nguồn này)")
        return 0
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    since_ms = now_ms - args.days * DAY_MS
    try:
        items, truncated = fetch_events(fetch or _shared.http_fetch, host, token, token_file, since_ms)
    except _shared.AdminError as e:
        raise _shared.Refuse(f"FAIL: API web trả {e} ở /admin/subscription-events — kiểm lại deploy") from None
    data = {"status": "partial" if truncated else "ok", "days": args.days,
            "since": dt.datetime.fromtimestamp(since_ms / 1000, dt.timezone.utc).date().isoformat(),
            "pulled_at": dt.datetime.now().isoformat(timespec="seconds")} | summarize(items)
    _shared.write_json(out_dir() / "subs.json", data)
    print(f"  ok   subs: {len(items)} sự kiện / {args.days} ngày → {_shared.show(out_dir() / 'subs.json')}")
    return 0


def main(argv=None, *, fetch=None, now_ms=None) -> int:
    """`fetch(method, url, **kw)` và `now_ms` tiêm được (test); None ⇒ HTTP thật / đồng hồ thật."""
    return _shared.run_main(_main, argv, fetch, now_ms)


if __name__ == "__main__":
    sys.exit(main())
