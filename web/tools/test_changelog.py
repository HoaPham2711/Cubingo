"""Test cho web/tools/changelog.py — repo tạm, iTunes Lookup giả (không mạng)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import changelog  # noqa: E402
from webtest_kit import clean_env, make_repo, sitemap  # noqa: E402

PUB = "web/site/public/"
SHELL = ("<!doctype html>\n<html lang=\"en\">\n<body>\n<h1>What's new</h1>\n<!-- releases:begin -->\n"
         "<p class=\"empty\">No releases yet.</p>\n<!-- releases:end -->\n</body>\n</html>\n")
RELEASES = [
    {"version": "1.1.0", "date": "2030-02-01", "notes": ["Faster export: files are ready sooner.", "Small fixes."]},
    {"version": "1.0.0", "date": "2030-01-01", "notes": ["First release."]},
]


def lookup(*versions):
    seen = []

    def fetch(url):
        seen.append(url)
        return {"resultCount": len(versions), "results": [{"version": v} for v in versions]}
    return fetch, seen


class ChangelogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict("os.environ", clean_env(), clear=True)
        p.start()
        self.addCleanup(p.stop)
        self.root = make_repo(Path(self._tmp.name), {
            PUB + "changelog/index.html": SHELL,
            PUB + "sitemap.xml": sitemap("example.com", {"/": "2030-01-01", "/changelog/": "2030-01-01"}),
            "web/site/releases.json": json.dumps(RELEASES, indent=2) + "\n",
        })
        self.page = self.root / PUB / "changelog/index.html"

    def run_tool(self, *args, fetch):
        return changelog.main(["--root", str(self.root), *args], fetch=fetch, today="2030-03-01")

    def test_sinh_trang_chi_ban_dang_ban_va_doi_lastmod(self):
        fetch, seen = lookup("1.0.0")
        self.assertEqual(self.run_tool(fetch=fetch), 0)
        html = self.page.read_text(encoding="utf-8")
        self.assertIn("Version 1.0", html)
        self.assertNotIn("Version 1.1", html, "bản chưa bán không được lộ")
        self.assertIn("<h1>What's new</h1>", html, "phần ngoài vùng sinh giữ nguyên")
        self.assertIn("bundleId=com.example.app", seen[0])
        sm = (self.root / PUB / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("<loc>https://example.com/changelog/</loc>\n    <lastmod>2030-03-01</lastmod>", sm)
        self.assertIn("<loc>https://example.com/</loc>\n    <lastmod>2030-01-01</lastmod>", sm)
        self.assertEqual(self.run_tool("--check", fetch=fetch), 0)

    def test_nhan_ngan_in_dam_va_html_duoc_thoat(self):
        rel = [{"version": "1.0.0", "date": "2030-01-01", "notes": ["Export: <b> & more", "plain text"]}]
        (self.root / "web/site/releases.json").write_text(json.dumps(rel), encoding="utf-8")
        self.assertEqual(self.run_tool(fetch=lookup("1.0.0")[0]), 0)
        html = self.page.read_text(encoding="utf-8")
        self.assertIn("<p><strong>Export:</strong> &lt;b&gt; &amp; more</p>", html)

    def test_changelog_lookup_rong_khong_loi(self):
        empty = lambda url: {"resultCount": 0, "results": []}  # noqa: E731 — app chưa lên Store
        self.assertEqual(self.run_tool("--check", fetch=empty), 0)
        self.assertEqual(self.run_tool(fetch=empty), 0)
        self.assertIn("No releases yet.", self.page.read_text(encoding="utf-8"))

    def test_changelog_check_lech_releases(self):
        fetch = lookup("1.1.0")[0]
        # Trang còn trống trong khi Store đang bán 1.1.0 ⇒ trang chưa sinh lại.
        self.assertEqual(self.run_tool("--check", fetch=fetch), 1)
        self.assertEqual(self.run_tool(fetch=fetch), 0)
        self.assertEqual(self.run_tool("--check", fetch=fetch), 0)
        # Store bán bản releases.json chưa có ⇒ lỗi.
        self.assertEqual(self.run_tool("--check", fetch=lookup("1.2.0")[0]), 1)

    def test_releases_phai_moi_nhat_truoc(self):
        (self.root / "web/site/releases.json").write_text(json.dumps(list(reversed(RELEASES))), encoding="utf-8")
        self.assertEqual(self.run_tool("--check", fetch=lookup("1.0.0")[0]), 1)

    def test_loi_mang_chan(self):
        def boom(url):
            raise OSError("mất mạng")
        self.assertEqual(self.run_tool("--check", fetch=boom), 1)
        self.assertEqual(self.run_tool("--check", "--live", "1.0.0", fetch=boom), 1, "--live bỏ qua mạng nhưng trang"
                         " vẫn trống")
        self.assertEqual(self.run_tool("--live", "1.0.0", fetch=boom), 0)

    def test_sitemap_thieu_url_changelog_khong_ghi_gi(self):
        sm = self.root / PUB / "sitemap.xml"
        sm.write_text(sitemap("example.com", {"/": "2030-01-01"}), encoding="utf-8")
        before = (self.page.read_text(encoding="utf-8"), sm.read_text(encoding="utf-8"))
        self.assertEqual(self.run_tool(fetch=lookup("1.0.0")[0]), 1)
        self.assertEqual((self.page.read_text(encoding="utf-8"), sm.read_text(encoding="utf-8")), before)

    def test_trang_thieu_dau_vung_sinh_bao_loi(self):
        self.page.write_text("<html></html>\n", encoding="utf-8")
        self.assertEqual(self.run_tool(fetch=lookup("1.0.0")[0]), 1)


if __name__ == "__main__":
    unittest.main()
