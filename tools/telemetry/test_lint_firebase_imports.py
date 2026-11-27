"""Test cho lint_firebase_imports.py — chạy bằng subprocess trên cây tạm, không đụng repo thật."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LINT = Path(__file__).resolve().parent / "lint_firebase_imports.py"


class FirebaseLintTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)

    def write(self, rel: str, content: str):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def run_lint(self):
        return subprocess.run([sys.executable, str(LINT), "--root", str(self.root)],
                              capture_output=True, text=True)

    def test_import_firebase_ngoai_sink_bi_bat(self):
        self.write("AppHost/AppHost/Home.swift", "import FirebaseAnalytics\n")
        self.assertEqual(self.run_lint().returncode, 1)

    def test_import_trong_sink_duoc_phep(self):
        self.write("Core/Telemetry/FirebaseSink.swift", "import FirebaseCore\n")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_import_firebase_trong_core_ngoai_sink_bi_bat(self):
        self.write("Core/Telemetry/Other.swift", "import FirebaseCore\n")
        self.assertEqual(self.run_lint().returncode, 1)

    def test_vi_pham_trong_core_chi_bao_mot_lan(self):
        # SRC_ROOTS chứa `Core/` ⇒ lint không được quét Core/ hai lần (báo trùng dòng).
        self.write("Core/Telemetry/Other.swift", "import FirebaseCore\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.count("Core/Telemetry/Other.swift:1"), 1, r.stdout)

    def test_sink_chi_duoc_import_ba_module(self):
        # FirebaseAuth không vào template; App Check chỉ ở khối tuỳ chọn WebAPI — kể cả trong sink cũng bị bắt.
        for mod in ("FirebaseCore", "FirebaseAnalytics", "FirebaseCrashlytics"):
            self.write("Core/Telemetry/FirebaseSink.swift", f"import {mod}\n")
            self.assertEqual(self.run_lint().returncode, 0, mod)
        for mod in ("FirebaseAuth", "FirebaseAppCheck", "FirebaseFirestore"):
            self.write("Core/Telemetry/FirebaseSink.swift", f"import {mod}\n")
            r = self.run_lint()
            self.assertEqual(r.returncode, 1, mod)
            self.assertIn(mod, r.stdout)

    def test_app_check_chi_o_dung_mot_file_cua_webapi(self):
        # Danh sách cho phép gọi tên ĐÚNG file (AppCheckTokenSource), không mở cả thư mục WebAPI/.
        f = "CoreOptional/WebAPI/AppCheckTokenSource.swift"
        for mods in (("FirebaseAppCheck",), ("FirebaseAppCheck", "FirebaseCore")):
            self.write(f, "".join(f"import {m}\n" for m in mods))
            self.assertEqual(self.run_lint().returncode, 0, mods)
        for mod in ("FirebaseAuth", "FirebaseAnalytics"):
            self.write(f, f"import {mod}\n")
            self.assertEqual(self.run_lint().returncode, 1, mod)

    def test_file_khac_trong_webapi_khong_duoc_import_firebase(self):
        self.write("CoreOptional/WebAPI/AppCheckTokenSource.swift", "import FirebaseAppCheck\n")
        for mod in ("FirebaseAppCheck", "FirebaseCore"):
            self.write("CoreOptional/WebAPI/WebAPIFeedbackTransport.swift", f"import {mod}\n")
            r = self.run_lint()
            self.assertEqual(r.returncode, 1, mod)
            self.assertIn("CoreOptional/WebAPI/WebAPIFeedbackTransport.swift:1", r.stdout)

    def test_core_optional_ngoai_webapi_bi_bat(self):
        self.write("Core/Telemetry/FirebaseSink.swift", "import FirebaseCore\n")
        self.write("CoreOptional/Khac/X.swift", "import FirebaseAppCheck\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1)
        self.assertIn("CoreOptional/Khac/X.swift:1", r.stdout)

    def test_bon_dang_import_lach_deu_bi_bat(self):
        # Mẫu cũ chỉ khớp dòng `import FirebaseX` trần ⇒ bốn dạng này lọt.
        cac_dang = {
            "comment_duoi_dong": "import FirebaseAnalytics // ghi chú\n",
            "exported": "@_exported import FirebaseAuth\n",
            "testable": "@testable import FirebaseCore\n",
            "import_symbol": "import struct FirebaseCore.FirebaseOptions\n",
        }
        for ten, dong in cac_dang.items():
            with self.subTest(ten):
                self.write("AppHost/AppHost/Home.swift", "import SwiftUI\n" + dong)
                r = self.run_lint()
                self.assertEqual(r.returncode, 1, (ten, r.stdout))
                self.assertIn("AppHost/AppHost/Home.swift:2", r.stdout)

    def test_thuoc_tinh_co_tham_so_va_measurement_bi_bat(self):
        for dong in ("@_spi(Internal) @preconcurrency import FirebaseCore\n", "import GoogleAppMeasurementX\n"):
            with self.subTest(dong):
                self.write("AppHost/AppHost/Home.swift", dong)
                self.assertEqual(self.run_lint().returncode, 1, dong)

    def test_comment_va_chuoi_chi_nhac_toi_khong_bi_bat(self):
        self.write("AppHost/AppHost/Home.swift", "\n".join([
            "import SwiftUI",
            "// import FirebaseAnalytics",
            "/*",
            "import FirebaseCore",
            "*/",
            'let a = "import FirebaseAuth"',
            'let b = """',
            "import FirebaseCrashlytics",
            '"""',
            'let c = #"import FirebaseAuth"#',
        ]) + "\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_import_sau_dau_cham_phay_bi_bat(self):
        for dong in ("let a = 1; import FirebaseCore\n", "import Foundation; import FirebaseCore\n"):
            with self.subTest(dong):
                self.write("AppHost/AppHost/Home.swift", "import SwiftUI\n" + dong)
                r = self.run_lint()
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("Home.swift:2", r.stdout)

    def test_import_va_ten_module_tren_hai_dong_bao_dung_dong_import(self):
        self.write("AppHost/AppHost/Home.swift", "import SwiftUI\nimport\n    FirebaseAnalytics\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("Home.swift:2", r.stdout)

    def test_thang_nhay_trong_regex_literal_khong_nuot_ca_file(self):
        # `#"` không có `"#` đóng trên cùng dòng ⇒ không phải chuỗi thô; import thật ở dòng sau vẫn bị bắt.
        self.write("AppHost/AppHost/Home.swift", 'let r = /#"/\nimport FirebaseCore\n')
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("Home.swift:2", r.stdout)
        # Chuỗi nhiều dòng không đóng cũng chỉ xoá tới hết dòng mở.
        self.write("AppHost/AppHost/Home.swift", 'let s = """\nimport FirebaseCore\n')
        self.assertIn("Home.swift:2", self.run_lint().stdout)

    def test_chuoi_tho_that_co_dong_va_chuoi_nhieu_dong_van_bi_bo(self):
        self.write("AppHost/AppHost/Home.swift", "\n".join([
            'let a = #"x \\"; import FirebaseCore"#',
            'let b = #"""',
            "import FirebaseCore",
            '"""#',
            "let c = 1; // import FirebaseCore",
        ]) + "\n")
        self.assertEqual(self.run_lint().returncode, 0, self.run_lint().stdout)

    def test_ten_module_co_ranh_gioi_tu(self):
        # `FirebaseX` là tiền tố của tên module, không phải của một từ bất kỳ: `MyFirebaseCore` không phải Firebase.
        self.write("AppHost/AppHost/Home.swift", "import MyFirebaseCore\nimport FirebaseCoreHelpers_\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Home.swift:1", r.stdout)
        self.assertIn("Home.swift:2", r.stdout)

    def test_khong_co_thu_muc_nguon_la_loi_khong_traceback(self):
        r = self.run_lint()
        self.assertEqual(r.returncode, 2)
        self.assertIn("FAIL:", r.stdout)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
