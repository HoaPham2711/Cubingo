"""Test bảng cho stamp_whats_new.py (tiện ích thay chữ, không parser — chốt thật là `#if INTERNAL` của Swift).

Chạy: python3 -m unittest tools/release/test_stamp_whats_new.py
"""
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stamp_whats_new.py")


class StampTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cat = os.path.join(self.tmp.name, "WhatsNewCatalog.swift")

    def write(self, text):
        with open(self.cat, "w", encoding="utf-8") as f:
            f.write(text)

    def read(self):
        with open(self.cat, encoding="utf-8") as f:
            return f.read()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, "--catalog", self.cat, *args], capture_output=True, text=True)

    # --- --check / --count -----------------------------------------------------------------------------------
    def test_check_count_bang(self):
        cases = [
            ("sạch", 'WhatsNewCard(id: "a", version: .released("1.12.0"))\n', 0, 0),
            ("một thẻ", 'WhatsNewCard(id: "a", version: .unreleased)\n', 1, 1),
            ("hai thẻ", 'X(version: .unreleased)\nY(version: CardVersion.unreleased)\n', 1, 2),
            ("chỉ trong comment", '// thẻ mới viết .unreleased\nX(version: .released("1.0.0"))\n', 1, 1),
            ("trong chuỗi", 'let s = "unreleased"\n', 1, 1),
            ("dính chữ khác", 'let isUnreleasedX = 1 // preunreleasedpost\n', 1, 1),
        ]
        for name, text, check_rc, count in cases:
            with self.subTest(name):
                self.write(text)
                self.assertEqual(self.run_cli("--check").returncode, check_rc)
                r = self.run_cli("--count")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.strip(), str(count))

    def test_thieu_catalog_exit_0(self):
        for args in (["--check"], ["--version", "1.2.3"], ["--version", "1.2.3", "--dry-run"]):
            with self.subTest(args):
                self.assertEqual(self.run_cli(*args).returncode, 0)
        r = self.run_cli("--count")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "0"))
        self.assertFalse(os.path.exists(self.cat))

    # --- --version: thay được -----------------------------------------------------------------------------------
    def test_version_thay_mau_chuan(self):
        cases = [
            ("một thẻ", 'X(id: "a", version: .unreleased, priority: 1)\n',
             'X(id: "a", version: .released("1.15.0"), priority: 1)\n'),
            ("nhiều thẻ + dạng CardVersion.",
             'A(version: .unreleased)\nB(version: CardVersion.unreleased)\nC(version: .released("1.2.0"))\n',
             'A(version: .released("1.15.0"))\nB(version: .released("1.15.0"))\nC(version: .released("1.2.0"))\n'),
            ("khoảng trắng lạ quanh dấu hai chấm", 'A(version :.unreleased)\nB(version\t:\n   .unreleased)\n',
             'A(version :.released("1.15.0"))\nB(version\t:\n   .released("1.15.0"))\n'),
        ]
        for name, before, after in cases:
            with self.subTest(name):
                self.write(before)
                r = self.run_cli("--version", "1.15.0")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.read(), after)
                self.assertEqual(self.run_cli("--check").returncode, 0)
                # idempotent
                self.assertEqual(self.run_cli("--version", "1.15.0").returncode, 0)
                self.assertEqual(self.read(), after)

    def test_dry_run_khong_ghi(self):
        before = 'A(version: .unreleased)\n'
        self.write(before)
        r = self.run_cli("--version", "1.15.0", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read(), before)

    # --- --version: không thay được ⇒ 3, không ghi ------------------------------------------------------------------
    def test_dang_la_exit_3_khong_ghi(self):
        cases = [
            ("hằng", 'let dev: CardVersion = .unreleased\nA(version: dev)\n'),
            ("backtick", 'A(version: .`unreleased`)\n'),
            ("comment còn chữ", '// nhớ .unreleased\nA(version: .unreleased)\n'),
            ("hằng + mẫu chuẩn", 'A(version: .unreleased)\nlet x = CardVersion.unreleased\n'),
            ("CardVersion xuống dòng trước dấu chấm", 'A(version: CardVersion\n  .unreleased)\n'),
        ]
        for name, text in cases:
            for extra in ([], ["--dry-run"]):
                with self.subTest(name, extra=extra):
                    self.write(text)
                    r = self.run_cli("--version", "1.15.0", *extra)
                    self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
                    self.assertEqual(self.read(), text)

    def test_version_hong_exit_2_khong_ghi(self):
        text = 'A(version: .unreleased)\n'
        for bad in ("1.15", "1.15.0.1", "v1.15.0", "1.x.0", "", "1.15.0\n", "١.٢.٣", "1.１5.0"):
            with self.subTest(bad):
                self.write(text)
                r = self.run_cli("--version", bad)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertEqual(self.read(), text)

    def test_doi_so_sai_exit_2(self):
        self.write("x\n")
        for args in ([], ["--check", "--count"], ["--check", "--dry-run"]):
            with self.subTest(args):
                self.assertEqual(self.run_cli(*args).returncode, 2)


if __name__ == "__main__":
    unittest.main()
