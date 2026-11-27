#!/usr/bin/env python3
"""Test subs_pull.py bằng fetch giả đóng vai API admin: gom theo loại, phân trang `since` gồm mốc + khử trùng,
401/429, thiếu token/host, không ghi mã giao dịch thô, không ghi ngoài thư mục đầu ra.

Chạy: `python3 -m unittest discover -s tools/analytics -p "test_*.py"`.
"""
import _testenv  # noqa: F401  (đầu tiên)

import json
import unittest
import urllib.parse
from unittest import mock

import subs_pull
from _testenv import FIXTURES, Resp

HOST = "example.com"
TOKEN = "TOKEN-BI-MAT-" "7f3a"
NOW = 9_000_000_000 + 86_400_000


def doc(name):
    return json.loads((FIXTURES / "web" / name).read_text(encoding="utf-8"))


def san_sang(tc, token=TOKEN, host=HOST, web_api=True):
    app_conf, out = _testenv.isolate(tc)
    _testenv.use_config(tc, _testenv.cfg(**{"web.host_prod": host, "features.web_api": web_api}))
    if token is not None:
        (app_conf / "web-admin-token").write_text(token + "\n", encoding="utf-8")
    return app_conf, out


def may_chu(items, calls):
    """Giả API: lọc `signed_date >= since`, sắp (signed_date, uuid), cắt `limit` — đúng như admin.ts."""
    def fetch(method, url, **kw):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        calls.append((method, url, kw.get("headers", {}), q))
        since, limit = int(q["since"][0]), int(q["limit"][0])
        rows = sorted((i for i in items if i["signed_date"] >= since),
                      key=lambda i: (i["signed_date"], i["notification_uuid"]))
        return Resp(200, json_body={"items": rows[:limit]})
    return fetch


def chay(tc, fetch, *argv):
    out_dir = _testenv.tmpdir(tc, "subs out ")
    rc, so, se = _testenv.run(subs_pull.main, ["--out", str(out_dir), *argv], fetch=fetch, now_ms=NOW)
    return rc, so, se, out_dir


class GomTheoLoai(unittest.TestCase):
    def test_subs_pull_gom_theo_loai(self):
        san_sang(self)
        calls = []
        rc, so, se, out = chay(self, may_chu(doc("subscription_events.json")["items"], calls))
        self.assertEqual(rc, 0, se)
        d = json.loads((out / "subs.json").read_text(encoding="utf-8"))
        self.assertEqual(d["status"], "ok")
        self.assertEqual(d["events_by_type"], {"SUBSCRIBED": 4, "DID_RENEW": 2, "EXPIRED/VOLUNTARY": 1,
                                               "DID_CHANGE_RENEWAL_STATUS/AUTO_RENEW_DISABLED": 1, "REFUND": 1})
        self.assertEqual((d["renewals"], d["cancellations"], d["refunds"]), (2, 1, 1))
        # tx-aaa hết hạn, tx-ccc hoàn tiền ⇒ chỉ tx-bbb (yearly) và tx-ddd (monthly) còn hiệu lực
        self.assertEqual(d["active_estimate_by_product"],
                         {"com.example.app.pro.monthly": 1, "com.example.app.pro.yearly": 1})
        self.assertEqual(d["excluded"], {"sandbox": 1, "test": 1})
        m, url, headers, q = calls[0]
        self.assertEqual((m, headers["Authorization"]), ("GET", "Bearer " + TOKEN))
        self.assertTrue(url.startswith(f"https://{HOST}/api/v1/admin/subscription-events?"))

    def test_phan_trang_gom_moc_va_khu_trung(self):
        san_sang(self)
        base = {"type": "SUBSCRIBED", "subtype": None, "environment": "Production", "product_id": "p"}
        # e1, e2 trùng mốc; e3, e4, e5 trùng mốc kế; limit 3 ⇒ trang 1 = e1 e2 e3, trang 2 = e3 e4 e5 (e3 trùng)
        items = [dict(base, notification_uuid=f"e{n}", original_tx_id=f"t{n}", signed_date=T)
                 for n, T in ((1, NOW - 5), (2, NOW - 5), (3, NOW - 4), (4, NOW - 4), (5, NOW - 4))]
        calls = []
        with mock.patch.object(subs_pull, "PAGE_LIMIT", 3):
            rc, so, se, out = chay(self, may_chu(items, calls))
        self.assertEqual(rc, 0, se)
        d = json.loads((out / "subs.json").read_text(encoding="utf-8"))
        self.assertEqual(d["events_by_type"], {"SUBSCRIBED": 5})  # đủ 5, không trùng, không sót
        self.assertEqual(calls[1][3]["since"][0], str(NOW - 4))  # trang sau dùng đúng signed_date cuối, KHÔNG +1
        self.assertEqual(d["status"], "ok")

    def test_khong_ghi_ma_giao_dich_tho(self):
        san_sang(self)
        rc, so, se, out = chay(self, may_chu(doc("subscription_events.json")["items"], []))
        text = (out / "subs.json").read_text(encoding="utf-8") + so + se
        for tho in ("tx-aaa", "tx-bbb", "tx-ccc", "tx-ddd", "u-01", "u-11", "original_tx_id", "notification_uuid"):
            self.assertNotIn(tho, text)

    def test_khong_ghi_ngoai_thu_muc_out(self):
        app_conf, root = san_sang(self)
        truoc = sorted(app_conf.rglob("*"))
        rc, so, se, out = chay(self, may_chu(doc("subscription_events.json")["items"], []))
        self.assertEqual(rc, 0, se)
        self.assertEqual([p.name for p in out.iterdir()], ["subs.json"])
        self.assertEqual(list(root.rglob("*")), [])  # gốc ANALYTICS_OUT không bị đụng khi có --out
        self.assertEqual(sorted(app_conf.rglob("*")), truoc)  # thư mục cấu hình/khoá không bị ghi


class LoiVaThieu(unittest.TestCase):
    def test_khong_token_la_missing_rc0(self):
        san_sang(self, token=None)
        rc, so, se, out = chay(self, lambda *a, **k: self.fail("không được gọi mạng"))
        self.assertEqual(rc, 0, se)
        self.assertEqual(json.loads((out / "subs.json").read_text(encoding="utf-8"))["status"], "missing")

    def test_tat_web_api_la_missing_khong_goi_mang(self):
        # Ruling 11: web_api tắt ⇒ app không có API ⇒ không có gì để kéo, kể cả khi đủ host + token.
        san_sang(self, web_api=False)
        rc, so, se, out = chay(self, lambda *a, **k: self.fail("không được gọi mạng"))
        self.assertEqual(rc, 0, se)
        d = json.loads((out / "subs.json").read_text(encoding="utf-8"))
        self.assertEqual(d["status"], "missing")
        self.assertIn("features.web_api", d["reason"])
        self.assertEqual(len([ln for ln in so.splitlines() if "web_api" in ln]), 1, so)

    def test_khong_host_la_missing_rc0(self):
        san_sang(self, host="")
        rc, so, se, out = chay(self, lambda *a, **k: self.fail("không được gọi mạng"))
        self.assertEqual(rc, 0, se)
        self.assertEqual(json.loads((out / "subs.json").read_text(encoding="utf-8"))["status"], "missing")

    def test_401_rc2_mot_dong_khong_in_token(self):
        san_sang(self)
        rc, so, se, out = chay(self, lambda *a, **k: Resp(401, json_body={"error": "unauthorized"}))
        self.assertEqual(rc, 2)
        self.assertEqual(se.count("\n"), 1)
        self.assertIn("401", se)
        self.assertNotIn(TOKEN, so + se)
        self.assertFalse((out / "subs.json").exists())

    def test_loi_may_chu_500_rc2_mot_dong_khong_traceback(self):
        san_sang(self)
        rc, so, se, out = chay(self, lambda *a, **k: Resp(500, json_body={"error": "boom"}))
        self.assertEqual(rc, 2)
        self.assertEqual(se.count("\n"), 1)
        self.assertIn("500", se)
        self.assertFalse((out / "subs.json").exists())

    def test_trang_day_khong_them_gi_moi_thi_nhich_since_khong_ket(self):
        san_sang(self)
        base = {"type": "SUBSCRIBED", "subtype": None, "environment": "Production", "product_id": "p"}
        # đúng `limit` sự kiện ở mốc cuối: trang sau chỉ trả lại chính chúng ⇒ phải nhích 1 ms để kết thúc
        items = [dict(base, notification_uuid=f"e{n}", original_tx_id=f"t{n}", signed_date=NOW - 3) for n in range(3)]
        calls = []
        with mock.patch.object(subs_pull, "PAGE_LIMIT", 3):
            rc, so, se, out = chay(self, may_chu(items, calls))
        d = json.loads((out / "subs.json").read_text(encoding="utf-8"))
        self.assertEqual(d["events_by_type"], {"SUBSCRIBED": 3})
        self.assertLessEqual(len(calls), 3)

    def test_429_rc2_noi_ip_bi_khoa(self):
        san_sang(self)
        rc, so, se, out = chay(self, lambda *a, **k: Resp(429, json_body={"error": "locked"}))
        self.assertEqual(rc, 2)
        self.assertIn("429", se)
        self.assertNotIn(TOKEN, so + se)

    def test_token_file_theo_bien_moi_truong(self):
        san_sang(self, token=None)
        f = _testenv.tmpdir(self) / "tok"
        f.write_text(TOKEN, encoding="utf-8")
        _testenv.set_env(self, WEB_ADMIN_TOKEN_FILE=str(f))
        calls = []
        rc, so, se, out = chay(self, may_chu([], calls))
        self.assertEqual(rc, 0, se)
        self.assertEqual(calls[0][2]["Authorization"], "Bearer " + TOKEN)


if __name__ == "__main__":
    unittest.main()
