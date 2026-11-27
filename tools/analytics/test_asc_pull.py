#!/usr/bin/env python3
"""Test asc_pull.py bằng fetch giả: Sales report TSV gzip, cấu hình asc.json, bundle id từ app.config.toml.

Chạy: `python3 -m unittest discover -s tools/analytics -p "test_*.py"`.
"""
import _testenv  # noqa: F401  (đầu tiên)

import contextlib
import datetime as dt
import gzip
import io
import json
import unittest

import asc_pull
from _testenv import FAKE_BUNDLE, FIXTURES, Resp

TODAY = dt.date(2026, 11, 3)
CREDS = {"key_id": "KEY" "TEST01", "issuer_id": "00000000-thu-nghiem", "vendor_number": "8" "0000001"}


def sales_fetch(calls, gz=True):
    """Sales có báo cáo ngày 02/11 (gzip), mọi ngày/loại khác 404."""
    body = (FIXTURES / "sales_report.tsv").read_bytes()

    def fetch(method, url, params=None, **kw):
        calls.append((method, url, params, kw))
        if (url.endswith("/v1/salesReports") and params["filter[reportType]"] == "SALES"
                and params["filter[reportDate]"] == "2026-11-02"):
            return Resp(content=gzip.compress(body) if gz else body)
        return Resp(404, json_body={"errors": []})
    return fetch


class BaoCaoSales(unittest.TestCase):
    def test_phan_tich_tsv_gzip_cua_sales_report(self):
        out = _testenv.tmpdir(self)
        calls = []
        with contextlib.redirect_stdout(io.StringIO()):
            ok = asc_pull.pull_daily(asc_pull.Client(sales_fetch(calls)), CREDS["vendor_number"], out, 3, today=TODAY)
        self.assertTrue(ok)
        lines = (out / "sales.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0].split("\t")[:2], ["report_date", "Provider"])
        self.assertEqual(len(lines), 4)  # header + 3 dòng của ngày 02/11
        self.assertTrue(all(line.startswith("2026-11-02\t") for line in lines[1:]))
        self.assertIn("\t1F\t3\t", lines[1])
        sales = [c for c in calls if c[2] and c[2]["filter[reportType]"] == "SALES"]
        self.assertTrue(all(c[2]["filter[vendorNumber]"] == CREDS["vendor_number"] for c in sales))
        self.assertTrue(all(c[3]["headers"]["Accept"] == "application/a-gzip" for c in sales))
        self.assertFalse((out / "subscriptions.tsv").exists())  # toàn 404 ⇒ không ghi file rỗng

    def test_bao_cao_khong_nen_van_doc_duoc(self):
        out = _testenv.tmpdir(self)
        with contextlib.redirect_stdout(io.StringIO()):
            asc_pull.pull_daily(asc_pull.Client(sales_fetch([], gz=False)), "1", out, 2, today=TODAY)
        self.assertEqual(len((out / "sales.tsv").read_text(encoding="utf-8").splitlines()), 4)


def by_day_fetch(bodies):
    """Sales trả `bodies[ngày]` (bytes) với 200; ngày khác / loại khác 404."""
    def fetch(method, url, params=None, **kw):
        if params and params.get("filter[reportType]") == "SALES" and params["filter[reportDate]"] in bodies:
            return Resp(content=bodies[params["filter[reportDate]"]])
        return Resp(404, json_body={"errors": []})
    return fetch


class ThanBaoCaoBatThuong(unittest.TestCase):
    def pull(self, bodies, days=3):
        out = _testenv.tmpdir(self)
        with contextlib.redirect_stdout(io.StringIO()):
            asc_pull.pull_daily(asc_pull.Client(by_day_fetch(bodies)), "1", out, days, today=TODAY)
        return out

    def test_ngay_200_than_rong_khong_lam_header_rong(self):
        real = (FIXTURES / "sales_report.tsv").read_bytes()
        # 02/11 (kéo trước) trả 200 rỗng, 01/11 có số thật ⇒ header phải là header thật
        out = self.pull({"2026-11-02": gzip.compress(b""), "2026-11-01": gzip.compress(real)})
        lines = (out / "sales.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0].split("\t")[:2], ["report_date", "Provider"])
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(line.startswith("2026-11-01\t") for line in lines[1:]))

    def test_chi_rong_moi_ngay_khong_ghi_file(self):
        out = self.pull({"2026-11-02": b"", "2026-11-01": gzip.compress(b"\n\n")})
        self.assertFalse((out / "sales.tsv").exists())

    def test_chi_co_header_ghi_file_mot_dong(self):
        header = (FIXTURES / "sales_report.tsv").read_text(encoding="utf-8").splitlines()[0]
        out = self.pull({"2026-11-02": gzip.compress((header + "\n").encode())})
        self.assertEqual((out / "sales.tsv").read_text(encoding="utf-8"), "report_date\t" + header + "\n")

    def test_tieu_de_ung_dung_khong_ascii(self):
        row = "APPLE\tthu.app\tỨng Dụng Thử — 测试 ✓\t1.2.3\t1F\t2\t0\tVN\tUSD\n"
        header = (FIXTURES / "sales_report.tsv").read_text(encoding="utf-8").splitlines()[0]
        out = self.pull({"2026-11-02": gzip.compress((header + "\n" + row).encode("utf-8"))})
        self.assertIn("Ứng Dụng Thử — 测试 ✓", (out / "sales.tsv").read_bytes().decode("utf-8"))


class CauHinhAsc(unittest.TestCase):
    def test_thieu_vendor_number_huong_dan(self):
        conf, _ = _testenv.isolate(self)
        (conf / "asc.json").write_text(encoding="utf-8", data=json.dumps({"key_id": "K", "issuer_id": "I"}))
        rc, so, se = _testenv.run(asc_pull.main, [], fetch=lambda *a, **k: self.fail("không được gọi mạng"))
        self.assertEqual(rc, 2)
        self.assertEqual(se.count("\n"), 1)
        self.assertIn('thiếu "vendor_number"', se)
        self.assertIn("Payments and Financial Reports", se)
        self.assertIn(str(conf / "asc.json"), se)

    def test_thieu_file_cau_hinh_neu_duong_dan_mong_doi(self):
        conf, _ = _testenv.isolate(self)
        rc, so, se = _testenv.run(asc_pull.main, [], fetch=lambda *a, **k: self.fail("không được gọi mạng"))
        self.assertEqual(rc, 2)
        self.assertIn(str(conf / "asc.json"), se)
        self.assertNotIn("Traceback", se)

    def test_bien_asc_config_thang_thu_muc_cau_hinh(self):
        conf, _ = _testenv.isolate(self)
        other = _testenv.tmpdir(self) / "asc khac.json"
        other.write_text(encoding="utf-8", data=json.dumps({"key_id": "K", "issuer_id": "I"}))
        _testenv.set_env(self, ASC_CONFIG=str(other))
        rc, so, se = _testenv.run(asc_pull.main, [], fetch=lambda *a, **k: self.fail("không được gọi mạng"))
        self.assertEqual(rc, 2)
        self.assertIn(str(other), se)

    def test_main_tra_app_bang_bundle_cua_cau_hinh_va_ghi_vao_goc_dau_ra(self):
        conf, out = _testenv.isolate(self)
        (conf / "asc.json").write_text(encoding="utf-8", data=json.dumps(CREDS))
        calls = []
        sales = sales_fetch(calls)

        def fetch(method, url, params=None, **kw):
            if url.endswith("/v1/apps"):
                calls.append((method, url, params, kw))
                return Resp(json_body={"data": [{"id": "999", "attributes": {"bundleId": FAKE_BUNDLE}}]})
            if url.endswith("/v1/apps/999/analyticsReportRequests"):
                return Resp(json_body={"data": []})
            return sales(method, url, params, **kw)

        rc, so, se = _testenv.run(asc_pull.main, ["--days", "2"], fetch=fetch)
        self.assertEqual(rc, 0, se)
        apps = [c for c in calls if c[1].endswith("/v1/apps")]
        self.assertEqual(apps[0][2]["filter[bundleId]"], FAKE_BUNDLE)
        self.assertIn("chưa có report request ONGOING", so)
        self.assertEqual(len(list(out.glob("asc/*/"))), 1)
        self.assertTrue(all(c[0] == "GET" for c in calls))  # không tạo report request khi thiếu cờ


if __name__ == "__main__":
    unittest.main()
