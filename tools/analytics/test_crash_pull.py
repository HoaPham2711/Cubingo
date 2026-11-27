#!/usr/bin/env python3
"""Test crash_pull.py (hàm thuần + lệnh với fetch giả), crash_watch.py và phần crash của digest.

Chạy: `python3 -m unittest discover -s tools/analytics -p "test_*.py"`.
"""
import _testenv  # noqa: F401  (đầu tiên: thư mục tạm + cấu hình giả)

import datetime as dt
import json
import os
import unittest
from unittest import mock

import crash_pull
import crash_watch
import digest
from _testenv import FAKE_BQ, FAKE_PROPERTY, FIXTURES, Resp


def rec(at, issue, fatal, install="a", v="1.2.0", code="luu_loi", crumbs=()):
    return {"at": at, "fatal": fatal, "issue_id": issue, "issue_title": "t-" + issue, "issue_subtitle": "thu.module",
            "install": install, "v": v, "model": "iPhone18,1", "os": "26.5.1", "blame": "f()",
            "keys": {"code": code}, "crumbs": list(crumbs)}


class ChuanHoaBanGhi(unittest.TestCase):
    def test_chuoi_bigquery_thanh_kieu(self):
        r = crash_pull.normalize_record({"fatal": "false", "keys": [{"key": "code", "value": "luu_loi"}],
                                         "crumbs": [{"v": "luu.xong"}, {"v": "luu.bat_dau ranh=true"}]})
        self.assertIs(r["fatal"], False)
        self.assertEqual(r["keys"], {"code": "luu_loi"})
        # SQL trả mới → cũ; giữ cũ → mới để đọc theo thứ tự thời gian
        self.assertEqual(r["crumbs"], ["luu.bat_dau ranh=true", "luu.xong"])
        self.assertIs(crash_pull.normalize_record({"fatal": "true", "keys": None, "crumbs": None})["fatal"], True)


class GopIssue(unittest.TestCase):
    def test_crash_that_truoc_roi_theo_so_luot(self):
        g = crash_pull.group_issues([rec("2026-10-26 10:30:37", "nf", False, "a"),
                                     rec("2026-10-27 08:12:00", "nf", False, "a", v="1.2.0"),
                                     rec("2026-10-25 09:00:00", "nf", False, "b", v="1.1.0"),
                                     rec("2026-10-24 01:00:00", "crash", True, "c")])
        self.assertEqual([i["issue_id"] for i in g], ["crash", "nf"])
        nf = g[1]
        self.assertEqual((nf["n"], nf["users"], nf["versions"]), (3, 2, ["1.1.0", "1.2.0"]))
        self.assertEqual((nf["first"], nf["last"]), ("2026-10-25 09:00:00", "2026-10-27 08:12:00"))
        self.assertEqual(crash_pull.group_issues([]), [])


class TachFatal(unittest.TestCase):
    def setUp(self):
        self.tmp = _testenv.tmpdir(self)
        (self.tmp / "crash").mkdir()
        (self.tmp / "crash" / "crashes.json").write_text(encoding="utf-8", data=json.dumps({
            "crashes": [{"u": "x", "reported_at": "2026-10-20 10:45", "v": "1.1.0", "model": "iPhone 16 Pro",
                         "os": "iOS 26.6.2", "country": "United States", "env": "production", "fatal": "1",
                         "before": []},
                        {"u": "y", "reported_at": "2026-10-27 08:13", "v": "1.2.0", "model": "iPhone 17 Pro",
                         "os": "iOS 26.5.1", "country": "United States", "env": "production", "fatal": "0",
                         "before": [{"n": "mo_man", "screen": "Items"}]}],
            "issues": crash_pull.group_issues([rec("2026-10-27 08:12:00", "nf", False)]),
            "records": [rec("2026-10-26 10:30:37", "nf", False),
                        rec("2026-10-27 08:12:00", "nf", False, crumbs=["luu.bat_dau cho=3001ms ranh=false"])]}))

    def test_chi_so_dem_rieng_fatal_va_non_fatal(self):
        m = {x["name"]: x for x in digest.crash_metrics(self.tmp / "crash", "2026-10-01")[0]}
        # non-fatal đếm từ bản ghi Crashlytics, KHÔNG từ app_exception (non-fatal không sinh app_exception)
        self.assertEqual((m["crash.fatal"]["value"], m["crash.nonfatal"]["value"]), (0, 2))
        self.assertEqual(m["crash.app_exception_users"]["value"], 1)
        self.assertEqual(m["crash.nonfatal"]["period"], "2026-10-01..2026-10-27")

    def test_digest_gan_nhan_tung_loai(self):
        md = digest.crash_digest(self.tmp / "crash", None, dt.date(2026, 10, 28), watch=[])
        self.assertIn("**1 crash thật** / 1 người (BigQuery `fatal=1`) · ⚠ 1 app_exception có `fatal≠1` "
                      "· 2 lỗi non-fatal (Crashlytics)", md)
        self.assertIn("**CRASH 2026-10-20 10:45**", md)
        self.assertIn("non-fatal 2026-10-27 08:13", md)
        self.assertIn("cho=3001ms ranh=false", md)


class LenhKeoCrash(unittest.TestCase):
    def test_dataset_mac_dinh_theo_property_va_ghi_crashes(self):
        _, out = _testenv.isolate(self)
        calls = []

        def fetch(method, url, **kw):
            calls.append((method, url, kw))
            if url.endswith("/queries"):
                return Resp(json_body=json.loads((FIXTURES / "bq_crashes.json").read_text(encoding="utf-8")))
            return Resp(json_body={"datasets": []})  # chưa bật Crashlytics export

        rc, so, se = _testenv.run(crash_pull.main, [], fetch=fetch)
        self.assertEqual(rc, 0, se)
        sql = calls[0][2]["json"]["query"]
        self.assertIn(f"`{FAKE_BQ}.analytics_{FAKE_PROPERTY}.events_*`", sql)
        self.assertTrue(calls[0][1].endswith(f"/projects/{FAKE_BQ}/queries"))
        self.assertNotIn("location", calls[0][2]["json"])
        data = json.loads(next(out.glob("crash/*/crashes.json")).read_text(encoding="utf-8"))
        self.assertEqual(data["crashes"][0]["before"], [{"t": "09:14:58", "n": "mo_man", "screen": "Items"}])
        self.assertIsNone(data["records"])

    def test_dinh_danh_bigquery_sai_dang_tu_choi_mot_dong(self):
        _testenv.isolate(self)
        for env in ({"GA4_BQ_DATASET": "analytics_1`; DROP TABLE x; --"},
                    {"GA4_BQ_PROJECT": "proj x"},
                    {"GA4_BQ_LOCATION": "asia/../x"}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                rc, so, se = _testenv.run(crash_pull.main, [], fetch=lambda *a, **k: self.fail("không được gọi mạng"))
                self.assertEqual(rc, 2)
                self.assertEqual(se.count("\n"), 1)
                self.assertIn("sai dạng", se)
        with mock.patch.dict(os.environ, {"GA4_BQ_LOCATION": "asia-southeast1"}):
            self.assertEqual(crash_pull.bq_target(_testenv.FAKE_CFG)[0], FAKE_BQ)

    def test_thieu_project_tu_choi_mot_dong(self):
        _testenv.isolate(self)
        _testenv.use_config(self, _testenv.cfg(**{"analytics.bq_project": ""}))
        rc, so, se = _testenv.run(crash_pull.main, [], fetch=lambda *a, **k: self.fail("không được gọi mạng"))
        self.assertEqual(rc, 2)
        self.assertEqual(se.count("\n"), 1)
        self.assertIn("bq_project", se)


WATCH = [{"issue_id": "slam", "name": "Lỗi thử", "status": "watching",
          "known_devices": [{"model": "iPhone18,1", "os": "26.5.1"}]}]
TODAY = dt.date(2026, 10, 28)


def crash_rec(at, issue, model="iPhone18,1", os="26.5.1", fatal=True):
    return dict(rec(at, issue, fatal), model=model, os=os)


class TheoDoiCrash(unittest.TestCase):
    def test_chuan_hoa_ios_khop_ga4_va_crashlytics(self):
        self.assertEqual(crash_watch.norm_os("iOS 26.5.1"), "26.5.1")
        self.assertEqual(crash_watch.norm_os("26.3.0"), "26.3")
        self.assertEqual(crash_watch.norm_os("27.0"), "27.0")

    def test_chi_may_da_biet_la_info(self):
        a = crash_watch.alerts([crash_rec("2026-10-27 08:31:04", "slam", os="26.5.1.0")], [], WATCH, TODAY)
        self.assertEqual([x["level"] for x in a], ["info"])
        self.assertIn("CHỈ trên máy đã biết", a[0]["text"])

    def test_lan_sang_may_khac_la_canh_bao(self):
        a = crash_watch.alerts([crash_rec("2026-10-27 08:31:04", "slam"),
                                crash_rec("2026-10-28 09:00:00", "slam", model="iPhone17,1", os="27.0.1")],
                               [], WATCH, TODAY)
        self.assertEqual(a[0]["level"], "alert")
        self.assertIn("iPhone17,1 · iOS 27.0.1 (1 lần)", a[0]["text"])

    def test_cung_model_khac_ios_la_may_khac(self):
        a = crash_watch.alerts([crash_rec("2026-10-28 09:00:00", "slam", os="27.0.1")], [], WATCH, TODAY)
        self.assertEqual(a[0]["level"], "alert")

    def test_issue_fatal_moi_duoc_bao_non_fatal_va_cu_bo_qua(self):
        a = crash_watch.alerts([crash_rec("2026-10-27 10:00:00", "other", model="iPad13,1", os="27.0"),
                                crash_rec("2026-10-27 10:00:00", "nf", fatal=False),
                                crash_rec("2026-10-01 10:00:00", "old")], [], WATCH, TODAY)
        new = [x for x in a if x["level"] == "new"]
        self.assertEqual(len(new), 1)
        self.assertIn("other", new[0]["text"])

    def test_crash_ga4_tren_may_la_la_canh_bao(self):
        daily = [{"date": "20261027", "deviceModel": "iPhone18,1", "operatingSystemVersion": "26.5.1",
                  "appVersion": "1.2.0", "country": "United States", "eventCount": 6, "totalUsers": 1},
                 {"date": "20261028", "deviceModel": "iPhone19,2", "operatingSystemVersion": "iOS 27.0.1",
                  "appVersion": "1.2.0", "country": "Germany", "eventCount": 2, "totalUsers": 1},
                 {"date": "20261001", "deviceModel": "iPad1,1", "operatingSystemVersion": "18.0",
                  "appVersion": "1.0.0", "country": "France", "eventCount": 1, "totalUsers": 1}]
        a = crash_watch.alerts([], daily, WATCH, TODAY)
        alerts = [x["text"] for x in a if x["level"] == "alert"]
        self.assertEqual(len(alerts), 1)
        self.assertIn("iPhone19,2 · iOS 27.0.1", alerts[0])
        self.assertEqual([r[1] for r in crash_watch.recent_table(daily, TODAY)], ["iPhone19,2", "iPhone18,1"])
        # máy đã xem tới 27/10 ⇒ crash 28/10 vẫn báo; xem tới 28/10 ⇒ im
        seen = [{"model": "iPhone19,2", "os": "27.0.1", "through": "2026-10-27"}]
        self.assertEqual(len([x for x in crash_watch.alerts([], daily, WATCH, TODAY, seen)
                              if x["level"] == "alert"]), 1)
        seen[0]["through"] = "2026-10-28"
        self.assertEqual([x for x in crash_watch.alerts([], daily, WATCH, TODAY, seen) if x["level"] == "alert"], [])

    def test_issue_da_dong_bo_qua(self):
        w = [dict(WATCH[0], status="closed")]
        self.assertEqual(crash_watch.alerts([crash_rec("2026-10-28 09:00:00", "slam", model="iPhone17,1")],
                                            [], w, TODAY), [])

    def test_danh_sach_mac_dinh_chung_va_bien_moi_truong_ghi_de(self):
        issues, reviewed, days = crash_watch.load_watch(crash_watch.WATCH_FILE)
        self.assertEqual((issues, reviewed, days), ([], [], 7))  # lõi đồng bộ: không issue riêng của app nào
        f = _testenv.tmpdir(self) / "watch.json"
        f.write_text(encoding="utf-8", data=json.dumps({"recent_days": 3, "issues": WATCH}))
        _testenv.set_env(self, CRASH_WATCH_FILE=str(f))
        self.assertEqual(crash_watch.load_watch()[2], 3)
        self.assertEqual(crash_watch.load_watch()[0][0]["issue_id"], "slam")

    def test_danh_sach_rieng_cua_app_thang_mac_dinh_thua_bien_moi_truong(self):
        app = _testenv.tmpdir(self) / "tools" / "app" / "crash_watch.json"
        with mock.patch.object(crash_watch, "APP_WATCH_FILE", app):
            self.assertEqual(crash_watch.watch_path(), crash_watch.WATCH_FILE, "chưa có file của app ⇒ mặc định chung")
            app.parent.mkdir(parents=True)
            app.write_text(encoding="utf-8", data=json.dumps({"recent_days": 5, "issues": WATCH}))
            self.assertEqual(crash_watch.watch_path(), app)
            self.assertEqual(crash_watch.load_watch()[2], 5)
            env = _testenv.tmpdir(self) / "env.json"
            env.write_text(encoding="utf-8", data=json.dumps({"recent_days": 2}))
            _testenv.set_env(self, CRASH_WATCH_FILE=str(env))
            self.assertEqual(crash_watch.watch_path(), env)
            self.assertEqual(crash_watch.load_watch()[2], 2)
        # test chạy trong app có file riêng vẫn không đọc nó: _testenv thay đường dẫn bằng file không tồn tại
        self.assertEqual(crash_watch.APP_WATCH_FILE.name, "khong-co-app-watch.json", "_testenv phải chặn file của app")


if __name__ == "__main__":
    unittest.main()
