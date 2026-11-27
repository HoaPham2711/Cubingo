#!/usr/bin/env python3
"""Test ga4_pull.py: request báo cáo tĩnh đúng property của cấu hình, không custom dimension.

Chạy: `python3 -m unittest discover -s tools/analytics -p "test_*.py"`.
"""
import _testenv  # noqa: F401  (đầu tiên)

import json
import unittest

import ga4_pull
from _testenv import FAKE_PROPERTY, FIXTURES, Resp


def report_fetch(calls):
    body = json.loads((FIXTURES / "ga4_run_report.json").read_text(encoding="utf-8"))

    def fetch(method, url, **kw):
        calls.append((method, url, kw))
        return Resp(json_body=body)
    return fetch


class BaoCaoTinh(unittest.TestCase):
    def test_dung_request_bao_cao_tinh_dung_property_khong_custom_dimension(self):
        _, out = _testenv.isolate(self)
        calls = []
        rc, so, se = _testenv.run(ga4_pull.main, ["--days", "7"], fetch=report_fetch(calls))
        self.assertEqual(rc, 0, se)
        self.assertTrue(calls)
        for method, url, kw in calls:
            self.assertEqual((method, url),
                             ("POST", f"https://analyticsdata.googleapis.com/v1beta/properties/{FAKE_PROPERTY}:runReport"))
            self.assertNotIn("custom", json.dumps(kw["json"]))  # chỉ dimension/metric chuẩn
        names = {p.stem for p in out.glob("ga4/*/*.json")}
        self.assertTrue({"daily", "events", "events_by_version", "events_by_country", "events_by_device",
                         "crash_daily", "retention_daily", "_run"} <= names, names)
        daily = json.loads(next(out.glob("ga4/*/daily.json")).read_text(encoding="utf-8"))
        self.assertEqual(daily[0], {"date": "20261101", "activeUsers": 12, "newUsers": 5,
                                    "userEngagementDuration": 340.5})
        self.assertEqual(json.loads(next(out.glob("ga4/*/_run.json")).read_text(encoding="utf-8"))["property"], FAKE_PROPERTY)

    def test_bien_moi_truong_thang_cau_hinh(self):
        _testenv.isolate(self)
        _testenv.set_env(self, GA4_PROPERTY_ID="4242")
        calls = []
        _testenv.run(ga4_pull.main, [], fetch=report_fetch(calls))
        self.assertTrue(all("/properties/4242:" in c[1] for c in calls))

    def test_property_rong_tu_choi_mot_dong(self):
        _testenv.isolate(self)
        _testenv.use_config(self, _testenv.cfg(**{"analytics.ga4_property": ""}))
        rc, so, se = _testenv.run(ga4_pull.main, [], fetch=lambda *a, **k: self.fail("không được gọi mạng"))
        self.assertEqual(rc, 2)
        self.assertEqual(se.count("\n"), 1)
        self.assertIn("[analytics] ga4_property", se)

    def test_dry_run_khong_can_khoa_khong_goi_mang(self):
        _testenv.isolate(self)
        rc, so, se = _testenv.run(ga4_pull.main, ["--dry-run"])
        self.assertEqual(rc, 0, se)
        self.assertEqual(json.loads(so)["property"], FAKE_PROPERTY)

    def test_moi_bao_cao_chi_dung_truong_chuan(self):
        for name, body in ga4_pull.all_reports(28).items():
            fields = [d["name"] for d in body.get("dimensions", [])] + [m["name"] for m in body.get("metrics", [])]
            self.assertFalse([f for f in fields if ":" in f], name)  # customEvent:/customUser: có dấu ':'


if __name__ == "__main__":
    unittest.main()
