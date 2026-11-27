"""Fixture eval: test gác cả hai biên."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calc import clamp  # noqa: E402


class ClampTests(unittest.TestCase):
    def test_giua_khoang(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_bien_duoi(self):
        self.assertEqual(clamp(-3, 0, 10), 0)

    def test_bien_tren(self):
        self.assertEqual(clamp(42, 0, 10), 10)

    def test_dung_bien(self):
        self.assertEqual(clamp(0, 0, 10), 0)
        self.assertEqual(clamp(10, 0, 10), 10)


if __name__ == "__main__":
    unittest.main()
