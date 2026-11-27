"""Test roadmap.py debt trên fixture nhỏ."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roadmap as R  # noqa: E402

FIXTURE = """**Đây là doc trạng thái — đọc trước.**

## 2026-11-04 — Màn trợ giúp đợt 1 (nhánh `x`, chưa merge, CHƯA device)

- **Còn chờ:** đo trên máy thật.

## 2026-10-27 — Xuất tệp (MERGED develop, chưa push; user nghiệm thu device)

## 2026-10-20 — Gửi phản hồi (merged)

- **Còn chờ:** áp migration rồi deploy; chưa deploy prod.

## 2026-10-10 — Bộ lọc mới (mặc định TẮT, CHỜ DEVICE)

## 2026-09-01 — Xong hết (device OK)

- **Còn lại:** đợt cũ từng ghi chưa device, nay đã thử xong.

## 2026-10-04 — Định dạng gói A (nhánh `x`, chưa merge, CHƯA nghiệm thu device)

## 2026-09-20 — Màn cài đặt (merged, đã nghiệm thu device đợt 1, chưa device iPad)

## Ghi chú chung
- Còn chờ: không thuộc mục nào
"""


class DebtTests(unittest.TestCase):
    def setUp(self):
        self.entries = R.parse(FIXTURE)
        self.by = {e["title"].split(" (")[0]: e for e in self.entries}

    def test_phan_loai_tieu_de(self):
        self.assertEqual(self.by["Màn trợ giúp đợt 1"]["kinds"], ["device", "merge"])
        self.assertEqual(self.by["Bộ lọc mới"]["kinds"], ["device", "off"])

    def test_da_nghiem_thu_khong_tinh_no_device(self):
        self.assertEqual(self.by["Xuất tệp"]["kinds"], ["push"])
        self.assertEqual(self.by["Xong hết"]["kinds"], [])

    def test_chua_nghiem_thu_khong_bi_coi_la_da_nghiem_thu(self):
        # lỗi từng gặp: lookahead `nghiệm thu device(?! .*chưa)` chỉ nhìn phía SAU
        self.assertEqual(self.by["Định dạng gói A"]["kinds"], ["device", "merge"])

    def test_tieu_de_con_cum_no_device_thi_giu_no(self):
        self.assertIn("device", self.by["Màn cài đặt"]["kinds"])

    def test_from_body_tach_no_do_than(self):
        self.assertEqual(self.by["Gửi phản hồi"]["from_body"], ["deploy"])
        self.assertEqual(self.by["Màn trợ giúp đợt 1"]["from_body"], [])

    def test_no_deploy_tu_dong_con_cho(self):
        self.assertEqual(self.by["Gửi phản hồi"]["kinds"], ["deploy"])

    def test_muc_khong_ngay_khong_bi_gop(self):
        self.assertNotIn("Ghi chú chung", self.by)
        self.assertEqual(len(self.by["Bộ lọc mới"]["pending"]), 0)

    def test_loc_kind_since_va_thu_tu(self):
        rows = R.debt(self.entries, kind="device")
        self.assertEqual([r["date"] for r in rows], ["2026-11-04", "2026-10-10", "2026-10-04", "2026-09-20"])
        rows = R.debt(self.entries, since="2026-10-15")
        self.assertEqual([r["date"] for r in rows], ["2026-11-04", "2026-10-27", "2026-10-20"])


if __name__ == "__main__":
    unittest.main()
