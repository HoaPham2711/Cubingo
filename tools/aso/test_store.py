"""Test cho store.py — đọc/ghi bố cục `asc metadata pull`."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402
from store import load, write  # noqa: E402


class StoreTests(unittest.TestCase):
    def _root(self):
        d = tempfile.TemporaryDirectory(prefix="kho metadata ")
        self.addCleanup(d.cleanup)
        return Path(d.name)

    def _put(self, root, rel, data):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data), encoding="utf-8")

    def test_load_tu_choi_null(self):
        r = self._root()
        self._put(r, "app-info/en-US.json", {"name": None})
        with self.assertRaises(ValueError):
            load(r, "1.0")

    def test_load_tu_choi_default_json(self):
        r = self._root()
        self._put(r, "version/1.0/default.json", {"description": "x"})
        with self.assertRaises(ValueError):
            load(r, "1.0")
        r2 = self._root()
        self._put(r2, "app-info/default.json", {"name": "x"})
        with self.assertRaises(ValueError):
            load(r2, "1.0")

    def test_version_va_versions_cung_luc_loi(self):
        r = self._root()
        self._put(r, "version/1.0/en-US.json", {"description": "a"})
        self._put(r, "versions/1.0/en-US.json", {"description": "a"})
        with self.assertRaises(ValueError):
            load(r, "1.0")
        app = self._root()          # cùng luật qua hàm theo gốc repo
        self._put(store.metadata_dir(app), "version/1.0/en-US.json", {"description": "a"})
        self._put(store.metadata_dir(app), "versions/1.0/en-US.json", {"description": "a"})
        with self.assertRaises(ValueError):
            store.load_version(app, "1.0", "en-US")
        with self.assertRaises(ValueError):
            store.locales_on_disk(app, "1.0")

    def test_load_tu_choi_khong_phai_chuoi(self):
        r = self._root()
        self._put(r, "app-info/en-US.json", {"name": 5})
        with self.assertRaises(ValueError):
            load(r, "1.0")

    def test_load_nhan_thu_muc_versions(self):
        r = self._root()
        self._put(r, "versions/1.0/vi.json", {"description": "Xin chào"})
        got = load(r, "1.0")
        self.assertEqual(got, {("version", "vi", "description"): "Xin chào"})
        self.assertEqual(got.vdir, "versions")

    def test_ghi_roi_doc_lai(self):
        r = self._root()
        values = {
            ("app-info", "en-US", "name"): "Tên thử",
            ("version", "en-US", "description"): "Dòng 1\nDòng 2",
            ("version", "vi", "keywords"): "a,b",
        }
        write(r, "1.0", values)
        self.assertEqual(dict(load(r, "1.0")), values)
        text = (r / "app-info/en-US.json").read_text(encoding="utf-8")
        self.assertTrue(text.endswith("}\n"))
        self.assertIn("Tên thử", text, "giữ UTF-8, không escape \\u")

    def test_ghi_tu_choi_default_va_khong_phai_chuoi(self):
        r = self._root()
        with self.assertRaises(ValueError):
            write(r, "1.0", {("version", "default", "description"): "x"})
        with self.assertRaises(ValueError):
            write(r, "1.0", {("version", "en-US", "description"): 3})

    def test_ham_theo_goc_repo(self):
        app = self._root()
        meta = store.metadata_dir(app)
        self.assertEqual(meta, app / "store" / "metadata")
        self._put(meta, "app-info/en-US.json", {"name": "A", "subtitle": ""})
        self._put(meta, "app-info/vi.json", {"name": "B"})
        self._put(meta, "version/2.0/en-US.json", {"description": "d"})
        self._put(meta, "version/2.0/ja.json", {"description": "e"})
        self.assertEqual(store.load_app_info(app, "en-US"), {"name": "A", "subtitle": ""})
        self.assertEqual(store.load_app_info(app, "fr"), {})
        self.assertEqual(store.load_version(app, "2.0", "ja"), {"description": "e"})
        self.assertEqual(store.load_version(app, "9.9", "ja"), {})
        self.assertEqual(store.locales_on_disk(app, "2.0"), ["en-US", "ja", "vi"])
        self.assertEqual(store.locales_on_disk(app, "9.9"), ["en-US", "vi"])

    def test_ham_theo_goc_repo_tu_choi_default_va_null(self):
        app = self._root()
        meta = store.metadata_dir(app)
        self._put(meta, "version/2.0/default.json", {"description": "x"})
        with self.assertRaises(ValueError):
            store.locales_on_disk(app, "2.0")
        with self.assertRaises(ValueError):
            store.load_version(app, "2.0", "default")
        self._put(meta, "app-info/en-US.json", {"name": None})
        with self.assertRaises(ValueError):
            store.load_app_info(app, "en-US")

    def test_goc_repo_la_hai_cap_tren_thu_muc_cong_cu(self):
        self.assertEqual(store.REPO, Path(__file__).resolve().parents[1].parent)


if __name__ == "__main__":
    unittest.main()
