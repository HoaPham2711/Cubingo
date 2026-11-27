"""Fixture eval: test KHÔNG gác biên trên (vẫn xanh với lỗi cài sẵn)."""
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


if __name__ == "__main__":
    unittest.main()
