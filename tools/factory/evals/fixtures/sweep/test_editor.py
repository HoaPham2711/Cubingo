"""Fixture eval (quét cạn): test chỉ phủ một lối vào (crop)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from editor import Editor  # noqa: E402


class EditorTests(unittest.TestCase):
    def test_crop_ap_xoay_dang_xem_truoc(self):
        e = Editor()
        e.rotate_preview(90)
        e.crop((0, 0, 1, 1))
        self.assertEqual(e.save(), [("rotate", 90), ("crop", (0, 0, 1, 1))])


if __name__ == "__main__":
    unittest.main()
