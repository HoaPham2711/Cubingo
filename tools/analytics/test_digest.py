#!/usr/bin/env python3
"""Test digest.py: gộp đủ nguồn thành insights.json + report.md; nguồn thiếu ⇒ ghi chú chứ không lỗi.

Chạy: `python3 -m unittest discover -s tools/analytics -p "test_*.py"`.
"""
import _testenv  # noqa: F401  (đầu tiên)

import datetime as dt
import json
import unittest

import digest

RUN = (dt.date.today() - dt.timedelta(days=1)).isoformat()


def day(offset):
    return (dt.date.fromisoformat(RUN) - dt.timedelta(days=offset)).isoformat()


def ymd(iso):
    return iso.replace("-", "")


def seed_all(out):
    ga4 = out / "ga4" / RUN
    ga4.mkdir(parents=True)
    (ga4 / "daily.json").write_text(encoding="utf-8", data=json.dumps([
        {"date": ymd(day(3)), "activeUsers": 10, "newUsers": 4, "sessions": 12, "eventCount": 100},
        {"date": ymd(day(2)), "activeUsers": 6, "newUsers": 2, "sessions": 7, "eventCount": 50},
        {"date": ymd(day(40)), "activeUsers": 99, "newUsers": 99, "sessions": 99, "eventCount": 999}]))
    (ga4 / "events.json").write_text(encoding="utf-8", data=json.dumps([{"eventName": "mo_man", "eventCount": 150, "totalUsers": 9}]))
    (ga4 / "crash_daily.json").write_text(encoding="utf-8", data=json.dumps([
        {"date": ymd(day(2)), "deviceModel": "iPhone17,1", "operatingSystemVersion": "26.1", "appVersion": "1.2.3",
         "country": "Germany", "eventCount": 2, "totalUsers": 1}]))
    (ga4 / "retention_daily.json").write_text(encoding="utf-8", data=json.dumps([
        {"cohort": day(5), "cohortNthDay": "0000", "cohortActiveUsers": 4, "cohortTotalUsers": 4},
        {"cohort": day(5), "cohortNthDay": "0001", "cohortActiveUsers": 1, "cohortTotalUsers": 4}]))
    asc = out / "asc" / RUN
    asc.mkdir(parents=True)
    (asc / "sales.tsv").write_text(encoding="utf-8", data=
        "report_date\tProduct Type Identifier\tUnits\n"
        f"{day(2)}\t1F\t3\n{day(2)}\tIAY\t2\n{day(2)}\t3F\t5\n{day(40)}\t1F\t50\n")
    crash = out / "crash" / RUN
    crash.mkdir(parents=True)
    (crash / "crashes.json").write_text(encoding="utf-8", data=json.dumps({
        "crashes": [{"u": "a", "reported_at": f"{day(2)} 09:15", "v": "1.2.3", "model": "iPhone17,1", "os": "26.1",
                     "country": "Germany", "env": "production", "fatal": "1", "before": []}],
        "issues": [], "records": [
            {"at": f"{day(2)} 09:14:00", "fatal": True, "issue_id": "i1", "issue_title": "t", "issue_subtitle": "s",
             "install": "a", "v": "1.2.3", "model": "iPhone17,1", "os": "26.1", "blame": "f()", "keys": {},
             "crumbs": []}]}))
    seed_web(out)


def seed_web(out, subs_status="ok", web_status="ok"):
    """Lần kéo subs/web (API admin): số gộp, không có mã giao dịch thô."""
    subs = out / "subs" / RUN
    subs.mkdir(parents=True)
    (subs / "subs.json").write_text(encoding="utf-8", data=json.dumps({
        "status": subs_status, "days": 30, "since": day(30),
        "events_by_type": {"SUBSCRIBED": 4, "DID_RENEW": 2}, "renewals": 2, "cancellations": 1, "refunds": 1,
        "active_estimate_by_product": {"com.example.app.pro.monthly": 1, "com.example.app.pro.yearly": 2},
        "excluded": {"sandbox": 1, "test": 0}}))
    web = out / "web" / RUN
    web.mkdir(parents=True)
    (web / "web.json").write_text(encoding="utf-8", data=json.dumps({
        "status": web_status, "days": 30,
        "pages": [{"page": "/", "views": 120}, {"page": "/privacy/", "views": 15}],
        "referrers": [{"domain": "example.org", "n": 9}], "countries": [{"country": "US", "n": 80}],
        "devices": [{"device": "mobile", "n": 100}], "feedback_open": 200, "feedback_open_capped": True}))


class Digest(unittest.TestCase):
    def test_gop_du_nguon(self):
        _, out = _testenv.isolate(self)
        _testenv.set_env(self, CRASH_WATCH_FILE=str(out / "khong-co.json"))
        seed_all(out)
        since = day(10)
        rc, so, se = _testenv.run(digest.main, ["--since", since])
        self.assertEqual(rc, 0, se)
        ins = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        self.assertEqual(set(ins), {"generated_at", "sources", "metrics", "notes"})
        self.assertEqual({k: v["status"] for k, v in ins["sources"].items()}, {"ga4": "ok", "asc": "ok", "crash": "ok", "subs": "ok", "web": "ok"})
        m = {x["name"]: x for x in ins["metrics"]}
        for x in ins["metrics"]:
            self.assertEqual(set(x), {"name", "value", "unit", "source", "period"})
        self.assertEqual(m["ga4.new_users"]["value"], 6)  # ngày trước --since bị loại
        self.assertEqual(m["ga4.new_users"]["period"], f"{since}..{day(2)}")
        self.assertEqual(m["ga4.active_users_daily_avg"]["value"], 8.0)
        self.assertEqual(m["ga4.app_exception"]["value"], 2)
        self.assertEqual((m["retention.d1"]["value"], m["retention.d1"]["unit"]), (0.25, "ratio"))
        self.assertEqual((m["asc.first_downloads"]["value"], m["asc.in_app_purchases"]["value"]), (3, 2))
        self.assertEqual((m["crash.fatal"]["value"], m["crash.nonfatal"]["value"]), (1, 0))
        # cohort duy nhất chưa đủ 7 ngày ⇒ D7 là ghi chú, không phải chỉ số 0
        self.assertEqual(ins["notes"], [f"retention D7: chưa có cohort nào từ {since} đủ 7 ngày"])
        self.assertNotIn("retention.d7", m)
        md = (out / "report.md").read_text(encoding="utf-8")
        self.assertIn(f"# Báo cáo số liệu từ {since}", md)
        self.assertIn("| asc.first_downloads | 3 | downloads | asc |", md)
        self.assertIn("mo_man", md)
        self.assertIn("**1 crash thật**", md)

    def test_digest_gop_subs_va_web(self):
        _, out = _testenv.isolate(self)
        _testenv.set_env(self, CRASH_WATCH_FILE=str(out / "khong-co.json"))
        seed_web(out)
        rc, so, se = _testenv.run(digest.main, ["--since", day(40)])
        self.assertEqual(rc, 0, se)
        ins = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        self.assertEqual((ins["sources"]["subs"]["status"], ins["sources"]["web"]["status"]), ("ok", "ok"))
        m = {x["name"]: x for x in ins["metrics"]}
        for x in ins["metrics"]:
            self.assertEqual(set(x), {"name", "value", "unit", "source", "period"})
        self.assertEqual((m["subs.renewals"]["value"], m["subs.cancellations"]["value"], m["subs.refunds"]["value"]),
                         (2, 1, 1))
        self.assertEqual(m["subs.active_estimate"]["value"], 3)
        self.assertEqual(m["subs.active_estimate"]["source"], "subs")
        self.assertEqual(m["web.pageviews"]["value"], 135)
        self.assertEqual(m["web.feedback_open"]["value"], 200)
        self.assertIs(m["web.feedback_open_capped"]["value"], True)
        self.assertEqual(m["web.pageviews"]["source"], "web")
        md = (out / "report.md").read_text(encoding="utf-8")
        self.assertIn("/privacy/", md)
        self.assertIn("example.org", md)
        self.assertIn("DID_RENEW", md)

    def test_subs_web_missing_trong_file_la_missing_khong_ra_chi_so(self):
        _, out = _testenv.isolate(self)
        seed_web(out, subs_status="missing", web_status="missing")
        rc, so, se = _testenv.run(digest.main, ["--since", day(40)])
        ins = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        self.assertEqual((ins["sources"]["subs"]["status"], ins["sources"]["web"]["status"]), ("missing", "missing"))
        self.assertFalse([x for x in ins["metrics"] if x["source"] in ("subs", "web")])
        self.assertTrue([n for n in ins["notes"] if n.startswith("web: chưa có dữ liệu")])

    def test_thu_muc_rong_khong_phai_ok_va_dung_lan_keo_tot_cu(self):
        _, out = _testenv.isolate(self)
        seed_web(out)  # lần kéo tốt ở RUN
        for src in ("subs", "web"):
            (out / src / dt.date.today().isoformat()).mkdir()  # lần kéo lỗi sau đó để lại thư mục rỗng
        _testenv.run(digest.main, ["--since", day(40)])
        ins = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        for src in ("subs", "web"):
            self.assertEqual((ins["sources"][src]["status"], ins["sources"][src]["run"]), ("ok", RUN))
        self.assertIn("web.pageviews", [x["name"] for x in ins["metrics"]])
        # chỉ còn thư mục rỗng ⇒ missing, không phải ok
        for p in sorted((out / "web" / RUN).iterdir()):
            p.unlink()
        _testenv.run(digest.main, ["--since", day(40)])
        ins = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        self.assertEqual(ins["sources"]["web"]["status"], "missing")
        self.assertFalse([x for x in ins["metrics"] if x["source"] == "web"])

    def test_web_partial_trong_file_la_partial(self):
        _, out = _testenv.isolate(self)
        seed_web(out, web_status="partial")
        _testenv.run(digest.main, ["--since", day(40)])
        ins = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        self.assertEqual(ins["sources"]["web"]["status"], "partial")
        self.assertTrue([n for n in ins["notes"] if n.startswith("web: ") and "một phần" in n])

    def test_nguon_thieu_ghi_chu_chu_khong_loi(self):
        _, out = _testenv.isolate(self)
        rc, so, se = _testenv.run(digest.main, ["--since", "2026-11-01"])
        self.assertEqual(rc, 0, se)
        ins = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        self.assertEqual(ins["metrics"], [])
        self.assertEqual({k: v["status"] for k, v in ins["sources"].items()},
                         {"ga4": "missing", "asc": "missing", "crash": "missing", "subs": "missing",
                          "web": "missing"})
        self.assertIn("ga4: chưa có dữ liệu — chạy python3 tools/analytics/ga4_pull.py", ins["notes"])
        self.assertIn("subs: chưa có dữ liệu — chạy python3 tools/analytics/subs_pull.py", ins["notes"])
        self.assertIn("web: chưa có dữ liệu — chạy python3 tools/analytics/web_pull.py", ins["notes"])
        self.assertEqual(len(ins["notes"]), 5)
        self.assertTrue((out / "report.md").is_file())

    def test_mot_nguon_thieu_van_gop_nguon_con_lai(self):
        _, out = _testenv.isolate(self)
        seed_all(out)
        for p in sorted((out / "asc").rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
        rc, so, se = _testenv.run(digest.main, ["--since", day(10)])
        self.assertEqual(rc, 0, se)
        ins = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        self.assertEqual(ins["sources"]["asc"]["status"], "missing")
        self.assertIn("ga4.new_users", [x["name"] for x in ins["metrics"]])
        self.assertFalse([x for x in ins["metrics"] if x["source"] == "asc"])

    def test_bao_cao_ga4_loi_la_partial_va_ghi_chu_tung_bao_cao(self):
        _, out = _testenv.isolate(self)
        seed_all(out)
        ga4 = out / "ga4" / RUN
        (ga4 / "daily.json").unlink()  # báo cáo daily hỏng lúc kéo ⇒ không có file
        (ga4 / "_run.json").write_text(encoding="utf-8", data=json.dumps({"property": "1", "errors": {
            "daily": {"status": 403, "body": "x"}, "events": {"status": 500, "body": "y"}}}))
        rc, so, se = _testenv.run(digest.main, ["--since", day(10)])
        self.assertEqual(rc, 0, se)
        ins = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        self.assertEqual(ins["sources"]["ga4"]["status"], "partial")
        failed = [n for n in ins["notes"] if n.startswith("ga4: báo cáo ")]
        self.assertEqual(len(failed), 2)
        self.assertIn("ga4: báo cáo daily lỗi lúc kéo (HTTP 403)", failed[0])
        self.assertIn("ga4: báo cáo events lỗi lúc kéo (HTTP 500)", failed[1])
        self.assertNotIn("ga4.new_users", [x["name"] for x in ins["metrics"]])
        self.assertIn("ga4 partial", (out / "report.md").read_text(encoding="utf-8"))

    def test_run_json_khong_loi_van_ok(self):
        _, out = _testenv.isolate(self)
        seed_all(out)
        (out / "ga4" / RUN / "_run.json").write_text(encoding="utf-8", data=json.dumps({"errors": {}}))
        _testenv.run(digest.main, ["--since", day(10)])
        ins = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        self.assertEqual(ins["sources"]["ga4"]["status"], "ok")

    def test_ten_event_khong_ascii_vao_bao_cao(self):
        _, out = _testenv.isolate(self)
        seed_all(out)
        (out / "ga4" / RUN / "events.json").write_text(encoding="utf-8", data=json.dumps(
            [{"eventName": "mở_màn_ứng_dụng_测试", "eventCount": 3, "totalUsers": 1}], ensure_ascii=False))
        rc, so, se = _testenv.run(digest.main, ["--since", day(10)])
        self.assertEqual(rc, 0, se)
        self.assertIn("mở_màn_ứng_dụng_测试", (out / "report.md").read_bytes().decode("utf-8"))

    def test_lan_keo_cu_hon_since_la_stale(self):
        _, out = _testenv.isolate(self)
        seed_all(out)
        rc, so, se = _testenv.run(digest.main, ["--since", dt.date.today().isoformat()])
        self.assertEqual(rc, 0, se)
        ins = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        self.assertEqual(ins["sources"]["ga4"]["status"], "stale")

    def test_since_sai_dang_tu_choi(self):
        _testenv.isolate(self)
        rc, so, se = _testenv.run(digest.main, ["--since", "hom-qua"])
        self.assertEqual(rc, 2)
        self.assertEqual(se.count("\n"), 1)


if __name__ == "__main__":
    unittest.main()
