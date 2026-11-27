"""Test cho lint_preview_code.py: kiểu *PreviewSeed/*PreviewStore chỉ trong `#if targetEnvironment(simulator)`.

Mỗi test dựng một gốc tạm (AppHost/AppHost/…, Core/…) rồi chạy script thật với `--root`.
Chạy: python3 -m unittest tools/release/test_lint_preview_code.py
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "lint_preview_code.py"
REPO = HERE.parents[1]


class LintPreviewCodeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "gốc có dấu cách"
        (self.root / "Core").mkdir(parents=True)

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def run_lint(self, root=None):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root or self.root)],
                              capture_output=True, text=True)

    def assertFails(self, *names):
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        for n in names:
            self.assertIn(n, r.stderr)
        return r

    def assertPasses(self):
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)

    def test_khai_bao_seed_ngoai_if_simulator_bi_bat(self):
        self.write("AppHost/AppHost/Features/X/XPreviewSeed.swift", "import Foundation\n\nenum XPreviewSeed {}\n")
        r = self.assertFails("AppHost/AppHost/Features/X/XPreviewSeed.swift:3: XPreviewSeed")
        self.assertIn("FAIL", r.stderr)

    def test_store_ngoai_if_trong_core_bi_bat_kem_cac_tu_khoa(self):
        self.write("Core/A.swift", "@MainActor\nfinal class APreviewStore {}\nstruct BPreviewStore {}\n"
                                   "actor CPreviewSeed {}\nprivate struct DPreviewStore {}\n")
        self.assertFails("Core/A.swift:2: APreviewStore", "Core/A.swift:3: BPreviewStore",
                         "Core/A.swift:4: CPreviewSeed", "Core/A.swift:5: DPreviewStore")

    def test_trong_if_simulator_thi_qua(self):
        self.write("AppHost/AppHost/A.swift",
                   "#if targetEnvironment(simulator)\nenum APreviewSeed {\n    #if DEBUG\n"
                   "    struct InnerPreviewStore {}\n    #endif\n}\n#endif\n")
        self.write("Core/B.swift", "#if DEBUG && targetEnvironment( simulator )\nprivate struct BPreviewStore {}\n"
                                   "#endif\n#if (targetEnvironment(simulator))\nstruct CPreviewSeed {}\n#endif\n")
        self.assertPasses()

    def test_nhanh_else_khong_tinh(self):
        self.write("AppHost/AppHost/A.swift",
                   "#if targetEnvironment(simulator)\nenum OkPreviewSeed {}\n#else\nenum APreviewSeed {}\n#endif\n")
        self.assertFails("A.swift:4: APreviewSeed")

    def test_elseif_va_phu_dinh_va_hoac_khong_tinh(self):
        self.write("AppHost/AppHost/A.swift",
                   "#if DEBUG\n#elseif targetEnvironment(simulator)\nenum APreviewSeed {}\n#endif\n"
                   "#if !targetEnvironment(simulator)\n#else\nenum BPreviewSeed {}\n#endif\n"
                   "#if targetEnvironment(simulator) || DEBUG\nenum CPreviewStore {}\n#endif\n"
                   "#if DEBUG\nenum DPreviewStore {}\n#endif\n")
        self.assertFails("A.swift:3: APreviewSeed", "A.swift:7: BPreviewSeed", "A.swift:10: CPreviewStore",
                         "A.swift:13: DPreviewStore")

    def test_comment_chuoi_va_ten_khac_khong_bi_bat(self):
        self.write("AppHost/AppHost/A.swift",
                   "// enum APreviewSeed {}\nlet s = \"struct BPreviewStore {}\"\nenum PreviewSeedX {}\n"
                   "let x = CPreviewStore.self\nstruct NoCounterStore {}\n"
                   "/* #endif */\n#if targetEnvironment(simulator)\n/* #endif */ enum DPreviewSeed {}\n#endif\n")
        self.assertPasses()

    def test_thu_muc_test_khong_quet(self):
        self.write("AppHost/AppHostTests/T.swift", "enum TPreviewSeed {}\n")
        self.assertPasses()

    def test_goc_khong_ton_tai_rc2(self):
        r = self.run_lint(self.root / "khong-co")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("FAIL", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_tham_so_la_rc2(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--khong-co"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_cay_that_sach(self):
        r = self.run_lint(REPO)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
