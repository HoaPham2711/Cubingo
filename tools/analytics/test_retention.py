#!/usr/bin/env python3
"""Test retention.py (người mới theo ngày + giữ chân D1/D3/D7) và digest.retention_rows.

Chạy: `python3 -m unittest discover -s tools/analytics -p "test_*.py"`.
"""
import _testenv  # noqa: F401  (đầu tiên)

import datetime as dt
import json
import unittest

import digest
import retention


def row(cohort, n, active, total):
    return {"cohort": cohort, "cohortNthDay": f"{n:04d}", "cohortActiveUsers": active, "cohortTotalUsers": total}


ROWS = [row("2026-10-19", 0, 3, 3), row("2026-10-19", 1, 1, 3),
        row("2026-10-23", 0, 4, 4), row("2026-10-23", 1, 1, 4), row("2026-10-23", 3, 1, 4),
        row("2026-10-25", 0, 4, 4)]
LAST = dt.date(2026, 10, 26)  # ngày cuối đã chốt


class MaTran(unittest.TestCase):
    def test_ngay_tron_la_0_chua_tron_la_none(self):
        m = {c["date"]: c for c in retention.matrix(ROWS, LAST)}
        self.assertEqual(list(m), ["2026-10-25", "2026-10-23", "2026-10-19"])  # mới trước
        # 19/10: D7 = 26/10 đã trọn ⇒ 0, không phải None
        self.assertEqual((m["2026-10-19"]["active"][1], m["2026-10-19"]["active"][7]), (1, 0))
        # 23/10: D3 = 26/10 trọn; D7 = 30/10 chưa tới ⇒ None
        self.assertEqual((m["2026-10-23"]["active"][3], m["2026-10-23"]["active"][7]), (1, None))
        # 25/10: D1 = 26/10 trọn, không ai quay lại ⇒ 0
        self.assertEqual(m["2026-10-25"]["active"][1], 0)

    def test_gop_theo_nguoi_chi_cohort_da_tron(self):
        m = retention.matrix(ROWS, LAST)
        self.assertEqual(retention.pooled(m, 1), (2, 11, 2 / 11))   # 1+1+0 / 3+4+4
        self.assertEqual(retention.pooled(m, 7)[:2], (0, 3))        # chỉ 19/10 đủ 7 ngày
        self.assertEqual(retention.pooled([], 1), (0, 0, None))


class NguoiMoiTheoNgay(unittest.TestCase):
    def test_gop_cac_nguon(self):
        m = retention.matrix(ROWS, LAST)
        ga4 = [{"date": "20261019", "newUsers": 5}, {"date": "20261020", "newUsers": 2}]
        rows = retention.new_users_daily(m, ga4, {"2026-10-19": 4.0}, "2026-10-19")
        self.assertEqual(rows[-2:], [["2026-10-20", 0, 2, None], ["2026-10-19", 3, 5, 4]])

    def test_asc_chi_dem_tai_lan_dau(self):
        p = _testenv.tmpdir(self) / "sales.tsv"
        p.write_text(encoding="utf-8", data="report_date\tProduct Type Identifier\tUnits\n2026-10-19\t1F\t2\n2026-10-19\t1F\t1\n"
                     "2026-10-19\t3F\t5\n2026-10-20\tIA1\t1\n")
        self.assertEqual(retention.asc_first_by_day(p), {"2026-10-19": 3.0})
        self.assertEqual(retention.asc_first_by_day(None), {})


class DongRetention(unittest.TestCase):
    def test_bo_dong_hom_nay_va_dn_thang_hang(self):
        ga4 = _testenv.tmpdir(self)
        (ga4 / "retention_daily.json").write_text(encoding="utf-8", data=json.dumps(ROWS))
        (ga4 / "daily.json").write_text(encoding="utf-8", data=json.dumps([{"date": "20261027", "newUsers": 1}]))
        _, pool, rows = digest.retention_rows(ga4, None, dt.date(2026, 10, 27))
        self.assertNotIn("2026-10-27", [r[0] for r in rows])
        r23 = next(r for r in rows if r[0] == "2026-10-23")
        self.assertEqual(r23[4:], [1, 1, None])  # D1, D3, D7
        self.assertEqual(pool[1][:2], (2, 11))
        self.assertIsNone(digest.retention_rows(None, None, dt.date(2026, 10, 27)))


if __name__ == "__main__":
    unittest.main()
