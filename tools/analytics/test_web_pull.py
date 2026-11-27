#!/usr/bin/env python3
"""Test web_pull.py bằng fetch giả đóng vai API admin: số liệu web + feedback mở, thiếu token ⇒ missing,
401 ⇒ rc 2 không in token, feedback lỗi ⇒ partial.

Chạy: `python3 -m unittest discover -s tools/analytics -p "test_*.py"`.
"""
import _testenv  # noqa: F401  (đầu tiên)

import json
import unittest
import urllib.parse

import web_pull
from _testenv import Resp
from test_subs_pull import HOST, TOKEN, doc, san_sang


def may_chu(calls, feedback=None, feedback_status=200):
    def fetch(method, url, **kw):
        p = urllib.parse.urlparse(url)
        calls.append((method, url, kw.get("headers", {}), urllib.parse.parse_qs(p.query)))
        if p.path.endswith("/admin/stats"):
            return Resp(200, json_body=doc("stats.json"))
        if p.path.endswith("/admin/feedback"):
            return Resp(feedback_status, json_body=feedback if feedback is not None else doc("feedback_open.json"))
        return Resp(404, json_body={})
    return fetch


def chay(tc, fetch, *argv):
    out = _testenv.tmpdir(tc, "web out ")
    rc, so, se = _testenv.run(web_pull.main, ["--out", str(out), *argv], fetch=fetch)
    return rc, so, se, out


def doc_out(out):
    return json.loads((out / "web.json").read_text(encoding="utf-8"))


class KeoSoWeb(unittest.TestCase):
    def test_web_pull_ghi_so_web_va_feedback_mo(self):
        san_sang(self)
        calls = []
        rc, so, se, out = chay(self, may_chu(calls), "--days", "14")
        self.assertEqual(rc, 0, se)
        d = doc_out(out)
        self.assertEqual(d["status"], "ok")
        self.assertEqual(d["days"], 14)
        self.assertEqual(d["pages"][0], {"page": "/", "views": 120})
        self.assertEqual(d["referrers"], [{"domain": "example.org", "n": 9}])
        self.assertEqual(len(d["countries"]), 2)
        self.assertEqual(len(d["devices"]), 2)
        self.assertEqual((d["feedback_open"], d["feedback_open_capped"]), (3, False))
        stats = [c for c in calls if c[1].split("?")[0].endswith("/admin/stats")][0]
        self.assertEqual(stats[3]["days"], ["14"])
        self.assertEqual(stats[2]["Authorization"], "Bearer " + TOKEN)
        fb = [c for c in calls if c[1].split("?")[0].endswith("/admin/feedback")][0]
        self.assertEqual((fb[3]["status"], fb[3]["limit"]), (["open"], ["200"]))
        self.assertTrue(fb[1].startswith(f"https://{HOST}/api/v1/admin/feedback?"))

    def test_feedback_day_trang_la_200_cong(self):
        san_sang(self)
        full = {"items": [{"id": f"f{i}", "status": "open"} for i in range(200)]}
        rc, so, se, out = chay(self, may_chu([], feedback=full))
        d = doc_out(out)
        self.assertEqual((d["feedback_open"], d["feedback_open_capped"]), (200, True))

    def test_feedback_loi_la_partial_van_giu_so_web(self):
        san_sang(self)
        rc, so, se, out = chay(self, may_chu([], feedback_status=500))
        self.assertEqual(rc, 0, se)
        d = doc_out(out)
        self.assertEqual(d["status"], "partial")
        self.assertIsNone(d["feedback_open"])
        self.assertEqual(d["pages"][0]["views"], 120)

    def test_web_pull_khong_token_la_missing(self):
        san_sang(self, token=None)
        rc, so, se, out = chay(self, lambda *a, **k: self.fail("không được gọi mạng"))
        self.assertEqual(rc, 0, se)
        self.assertEqual(doc_out(out)["status"], "missing")

    def test_web_pull_tat_web_api_la_missing_khong_goi_mang(self):
        san_sang(self, web_api=False)
        rc, so, se, out = chay(self, lambda *a, **k: self.fail("không được gọi mạng"))
        self.assertEqual(rc, 0, se)
        d = doc_out(out)
        self.assertEqual(d["status"], "missing")
        self.assertIn("features.web_api", d["reason"])

    def test_web_pull_401_rc2_khong_in_token(self):
        san_sang(self)
        rc, so, se, out = chay(self, lambda *a, **k: Resp(401, json_body={"error": "unauthorized"}))
        self.assertEqual(rc, 2)
        self.assertEqual(se.count("\n"), 1)
        self.assertNotIn(TOKEN, so + se)
        self.assertFalse((out / "web.json").exists())

    def test_lan_keo_loi_khong_de_thu_muc_rong_va_days_phai_duong(self):
        san_sang(self)
        root = _testenv.tmpdir(self, "goc ")
        _testenv.set_env(self, ANALYTICS_OUT=str(root))
        for main, name in ((web_pull.main, "web"),):
            rc, so, se = _testenv.run(main, [], fetch=lambda *a, **k: Resp(401, json_body={}))
            self.assertEqual(rc, 2)
            self.assertEqual(list(root.rglob("*")), [])  # không thư mục ngày rỗng
        import subs_pull
        rc, so, se = _testenv.run(subs_pull.main, [], fetch=lambda *a, **k: Resp(500, json_body={}))
        self.assertEqual((rc, list(root.rglob("*"))), (2, []))
        for main in (web_pull.main, subs_pull.main):
            # Server chỉ giữ 400 ngày (cron) và kẹp /admin/stats ở 400 ⇒ --days > 400 là lỗi, không ghi "999 ngày" sai.
            for bad in ("0", "-3", "401", "999"):
                with self.assertRaises(SystemExit) as cm:
                    _testenv.run(main, ["--days", bad], fetch=lambda *a, **k: self.fail("không gọi mạng"))
                self.assertEqual(cm.exception.code, 2)

    def test_khong_ghi_ngoai_thu_muc_out(self):
        app_conf, root = san_sang(self)
        truoc = sorted(app_conf.rglob("*"))
        rc, so, se, out = chay(self, may_chu([]))
        self.assertEqual([p.name for p in out.iterdir()], ["web.json"])
        self.assertEqual(list(root.rglob("*")), [])
        self.assertEqual(sorted(app_conf.rglob("*")), truoc)


class KhongTheoChuyenHuong(unittest.TestCase):
    """http_fetch THẬT với hai máy chủ cục bộ (127.0.0.1, không mạng ngoài): 3xx ⇒ Refuse một dòng, KHÔNG gửi lại
    Authorization tới đích chuyển hướng (host_prod cấu hình sai — apex → www, trang đỗ tên miền — làm lộ token admin)."""

    def test_http_fetch_khong_theo_redirect_va_khong_lo_token(self):
        import http.server
        import threading
        import _shared
        hits = []

        class Dich(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *a):
                pass

        dich = http.server.HTTPServer(("127.0.0.1", 0), Dich)

        class Nguon(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{dich.server_port}/x")
                self.end_headers()

            def log_message(self, *a):
                pass

        nguon = http.server.HTTPServer(("127.0.0.1", 0), Nguon)
        for s in (dich, nguon):
            threading.Thread(target=s.serve_forever, daemon=True).start()
            self.addCleanup(s.server_close)
            self.addCleanup(s.shutdown)
        with self.assertRaises(_shared.Refuse) as cm:
            _shared.http_fetch("GET", f"http://127.0.0.1:{nguon.server_port}/api/v1/admin/stats",
                               headers={"Authorization": f"Bearer {TOKEN}"}, timeout=10)
        msg = str(cm.exception)
        self.assertIn("302", msg)
        self.assertNotIn(TOKEN, msg)
        self.assertEqual(msg.count("\n"), 0)
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
