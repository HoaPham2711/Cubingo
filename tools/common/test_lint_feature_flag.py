"""Test cho lint_feature_flag.py — chạy bằng subprocess trên cây tạm, không đụng repo thật."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LINT = Path(__file__).resolve().parent / "lint_feature_flag.py"
KHOI = "CoreOptional/WebAPI/WebAPIFeedbackTransport.swift"
APP = "AppHost/AppHost/AppHostApp.swift"
REPO = Path(__file__).resolve().parents[2]
KHOI_SRC = "final class WebAPIFeedbackTransport {}\nenum AppCheckTokenSource {}\nprotocol GiaoThuc {}\n"


class FeatureFlagLintTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)

    def write(self, rel: str, content: str):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def run_lint(self):
        return subprocess.run([sys.executable, str(LINT), "--root", str(self.root)], capture_output=True, text=True)

    def test_cay_sach_rc0(self):
        self.write("Core/Bootstrap/A.swift", "struct A {}\n")
        self.write(KHOI, KHOI_SRC)
        self.write(APP, "#if FEATURE_WEB_API\nlet x = WebAPIFeedbackTransport.self\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_co_feature_web_api_trong_core_rc1(self):
        # Ca (g): gieo chuỗi cờ vào Core/ ⇒ rc 1 và nêu đúng file:dòng.
        self.write("Core/Support/X.swift", "struct X {}\n#if FEATURE_WEB_API\nlet y = 1\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Core/Support/X.swift:2", r.stdout)
        self.assertIn("FEATURE_WEB_API", r.stdout)

    def test_co_feature_trong_khoi_tuy_chon_va_thu_muc_test_rc1(self):
        for rel in (KHOI, "CoreTests/Support/T.swift", "CoreOptionalTests/WebAPI/T.swift"):
            with self.subTest(rel=rel):
                self.write(rel, "// nhánh theo FEATURE_WEB_API\n")
                r = self.run_lint()
                self.assertEqual(r.returncode, 1, rel)
                self.assertIn(rel + ":1", r.stdout)
                (self.root / rel).unlink()

    def test_cac_co_feature_khac_cung_bi_bat(self):
        # Quy tắc chung: mọi cờ FEATURE_* chỉ sống ở AppHost/, không riêng web api.
        self.write("Core/X.swift", "#if FEATURE_PAYWALL\n#endif\n")
        self.assertEqual(self.run_lint().returncode, 1)

    def test_co_o_apphost_duoc_phep(self):
        self.write("Core/X.swift", "struct X {}\n")
        self.write(APP, "#if FEATURE_WEB_API\n#endif\n")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_core_nhac_kieu_cua_khoi_tuy_chon_rc1(self):
        # Target CoreOnly biên dịch Core/ một mình: tham chiếu kiểu tuỳ chọn sẽ đỏ ở đó — lint bắt sớm.
        self.write(KHOI, KHOI_SRC)
        self.write("Core/Support/Y.swift", "let t = WebAPIFeedbackTransport.self\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Core/Support/Y.swift:1", r.stdout)
        self.assertIn("WebAPIFeedbackTransport", r.stdout)

    def test_core_tests_nhac_kieu_cua_khoi_tuy_chon_rc1(self):
        # CoreTests/ biên dịch ở mọi tổ hợp (kể cả web_api = false) nên cũng không được dùng kiểu tuỳ chọn.
        self.write(KHOI, KHOI_SRC)
        self.write("CoreTests/Support/T.swift", "final class T { let a = AppCheckTokenSource.self }\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1)
        self.assertIn("CoreTests/Support/T.swift:1", r.stdout)

    def test_core_nhac_ten_thu_muc_khoi_rc1(self):
        self.write("Core/X.swift", "// xem CoreOptional/WebAPI\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Core/X.swift:1", r.stdout)

    def test_ten_gan_giong_khong_bi_bat(self):
        # Khớp nguyên từ: `AppCheckTokenSourceX` không phải `AppCheckTokenSource`.
        self.write(KHOI, KHOI_SRC)
        self.write("Core/X.swift", "struct AppCheckTokenSourceX {}\n")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_khoi_tuy_chon_dung_kieu_cua_core_duoc_phep(self):
        self.write(KHOI, KHOI_SRC + "let f = FeedbackDraft.self\n")
        self.write("Core/Support/FeedbackDraft.swift", "struct FeedbackDraft {}\n")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_khong_co_khoi_tuy_chon_van_chay(self):
        self.write("Core/X.swift", "struct X {}\n")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_khong_co_thu_muc_nguon_la_loi_khong_traceback(self):
        r = self.run_lint()
        self.assertEqual(r.returncode, 2)
        self.assertIn("FAIL:", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    # --- luật (c): AppHost/ chỉ nhắc kiểu của khối tuỳ chọn trong #if <cờ của khối> ---
    def test_kieu_khoi_tuy_chon_ngoai_if_bi_bat(self):
        self.write(KHOI, KHOI_SRC)
        self.write("AppHost/AppHost/Foo.swift", "struct Foo {}\nlet t = AppCheckTokenSource.self\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("AppHost/AppHost/Foo.swift:2", r.stdout)
        self.assertIn("AppCheckTokenSource", r.stdout)

    def test_trong_if_dung_co_thi_qua(self):
        self.write(KHOI, KHOI_SRC)
        for i, src in enumerate((
            "#if FEATURE_WEB_API\nlet t = AppCheckTokenSource.self\n#endif\n",
            "#if FEATURE_WEB_API && DEBUG\nlet t = AppCheckTokenSource.self\n#endif\n",
            "#if DEBUG\n#if FEATURE_WEB_API\nlet t = AppCheckTokenSource.self\n#endif\n#endif\n",
            "#if !FEATURE_WEB_API\nlet a = 1\n#else\nlet t = AppCheckTokenSource.self\n#endif\n",
            "#if X\nlet a = 1\n#elseif FEATURE_WEB_API\nlet t = AppCheckTokenSource.self\n#endif\n",
        )):
            with self.subTest(i=i):
                self.write(APP, src)
                r = self.run_lint()
                self.assertEqual(r.returncode, 0, r.stdout)

    def test_nhanh_else_khong_duoc_nhac_kieu(self):
        self.write(KHOI, KHOI_SRC)
        for i, src in enumerate((
            "#if FEATURE_WEB_API\nlet a = 1\n#else\nlet t = AppCheckTokenSource.self\n#endif\n",
            "#if !FEATURE_WEB_API\nlet t = AppCheckTokenSource.self\n#endif\n",
            "#if FEATURE_WEB_API\nlet a = 1\n#endif\nlet t = AppCheckTokenSource.self\n",
            "#if FEATURE_WEB_API || DEBUG\nlet t = AppCheckTokenSource.self\n#endif\n",
            "#if FEATURE_WEB_API\n#if DEBUG\n#endif\nlet a = 1\n#endif\nlet t = AppCheckTokenSource.self\n",
        )):
            with self.subTest(i=i):
                self.write(APP, src)
                r = self.run_lint()
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("AppCheckTokenSource", r.stdout)

    def test_comment_nhac_ten_thi_qua(self):
        self.write(KHOI, KHOI_SRC)
        self.write("AppHost/AppHost/Foo.swift",
                   "// xem AppCheckTokenSource và CoreOptional/\n"
                   "let a = 1 // WebAPIFeedbackTransport\n"
                   "/* AppCheckTokenSource\n   WebAPIFeedbackTransport */ let b = 2\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_feature_ngoai_apphostapp_bi_bat(self):
        self.write("Core/X.swift", "struct X {}\n")
        for rel in ("AppHost/AppHost/Foo.swift", "AppHost/AppHostTests/T.swift"):
            with self.subTest(rel=rel):
                self.write(rel, "#if FEATURE_WEB_API\n#endif\n")
                r = self.run_lint()
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(rel + ":1", r.stdout)
                (self.root / rel).unlink()

    def test_cay_that_sach(self):
        # Cây thật của repo (chỉ đọc): phải sạch — gồm AppHostApp.swift:17 nhắc `CoreOptional/` trong comment.
        r = subprocess.run([sys.executable, str(LINT), "--root", str(REPO)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
