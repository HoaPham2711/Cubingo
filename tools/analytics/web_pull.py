#!/usr/bin/env python3
"""Kéo số liệu web (lượt xem, nguồn giới thiệu, nước, thiết bị) và số feedback đang mở từ API admin về `web.json`.

Chạy:
    python3 tools/analytics/web_pull.py                 # 30 ngày gần nhất → <gốc>/web/<ngày>/web.json
    python3 tools/analytics/web_pull.py --days 90 --out <thư mục>

Nguồn: `GET https://<web.host_prod>/api/v1/admin/stats?days=N` và `/admin/feedback?status=open&limit=200`
(Bearer ADMIN_TOKEN). Token: file `$WEB_ADMIN_TOKEN_FILE` hoặc `<config_dir>/web-admin-token` (ngoài repo, không
bao giờ in). `features.web_api` tắt (không có API) hoặc thiếu host/token ⇒ ghi `{"status": "missing"}` + lý do, rc 0, không gọi mạng. HTTP 401/429 ⇒ rc 2, một dòng hướng dẫn.

`feedback_open` = số mục đang mở (tối đa 200 một trang; đầy trang ⇒ `feedback_open_capped` true, số thật có thể lớn hơn). Feedback lỗi (không phải 401/429) ⇒
`status "partial"`, `feedback_open` null, số web vẫn giữ. Không ghi nội dung/e-mail feedback — chỉ đếm.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shared  # noqa: E402

DEFAULT_DAYS = 30
FEEDBACK_LIMIT = 200  # trần của admin.ts (FEEDBACK_LIST_MAX)


def _main(argv, fetch):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=_shared.retained_days, default=DEFAULT_DAYS)
    ap.add_argument("--out", type=Path, default=None, help="thư mục đầu ra (mặc định <gốc>/web/<ngày>)")
    args = ap.parse_args(argv)

    cfg = _shared.load_cfg()
    host, token, token_file = _shared.web_admin(cfg)
    def out_dir():  # tạo thư mục CHỈ khi sắp ghi — lần kéo lỗi không để lại thư mục rỗng
        return _shared.run_dir("web", args.out)

    if not _shared.web_api_on(cfg) or not host or not token:
        # web_api tắt ⇒ app không có API (Ruling 11) — không có gì để kéo, không gọi mạng.
        why = ("features.web_api tắt (không có API)" if not _shared.web_api_on(cfg)
               else "chưa đặt web.host_prod trong app.config.toml" if not host
               else f"thiếu token admin — đặt ADMIN_TOKEN vào {token_file}")
        _shared.write_json(out_dir() / "web.json", {"status": "missing", "reason": why})
        print(f"  --   web: {why} (bỏ qua nguồn này)")
        return 0
    fetch = fetch or _shared.http_fetch
    try:
        stats = _shared.admin_get(fetch, host, token, token_file, "stats", {"days": args.days})
    except _shared.AdminError as e:
        raise _shared.Refuse(f"FAIL: API web trả {e} ở /admin/stats — kiểm lại deploy") from None
    feedback_open, capped, status = None, False, "ok"
    try:
        items = _shared.admin_get(fetch, host, token, token_file, "feedback",
                                  {"status": "open", "limit": FEEDBACK_LIMIT}).get("items") or []
        feedback_open, capped = len(items), len(items) >= FEEDBACK_LIMIT
    except _shared.AdminError as e:
        status = "partial"
        print(f"  LỖI  feedback: {e} (giữ số web, feedback_open = null)")
    data = {"status": status, "days": args.days, "pulled_at": dt.datetime.now().isoformat(timespec="seconds"),
            "pages": stats.get("pages", []), "referrers": stats.get("referrers", []),
            "countries": stats.get("countries", []), "devices": stats.get("devices", []),
            "feedback_open": feedback_open, "feedback_open_capped": capped}
    _shared.write_json(out_dir() / "web.json", data)
    print(f"  ok   web: {len(data['pages'])} trang, feedback mở {feedback_open}{'+' if capped else ''} → {_shared.show(out_dir() / 'web.json')}")
    return 0


def main(argv=None, *, fetch=None) -> int:
    """`fetch(method, url, **kw)` tiêm được (test); None ⇒ HTTP thật."""
    return _shared.run_main(_main, argv, fetch)


if __name__ == "__main__":
    sys.exit(main())
