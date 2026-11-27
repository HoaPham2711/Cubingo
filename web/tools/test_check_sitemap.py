"""Test cho web/tools/check_sitemap.py — repo git tạm, không đụng repo thật."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_sitemap  # noqa: E402
from webtest_kit import clean_env, commit_all, git, make_repo, page, sitemap, write  # noqa: E402

PUB = "web/site/public/"


class CheckSitemapTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict("os.environ", clean_env(), clear=True)
        p.start()
        self.addCleanup(p.stop)
        self.root = make_repo(Path(self._tmp.name), {PUB + "index.html": page(), PUB + "privacy/index.html": page(),
                                                     PUB + "404.html": page()})

    def test_sitemap_du_va_kip_qua(self):
        write(self.root, PUB + "sitemap.xml", sitemap("example.com", {"/": "2030-01-05", "/privacy/": "2030-01-05"}))
        commit_all(self.root, "trang", date="2030-01-05")
        self.assertEqual(check_sitemap.check(self.root), [])
        self.assertEqual(check_sitemap.main(["--root", str(self.root)]), 0)

    def test_sitemap_thieu_trang_bi_bao(self):
        write(self.root, PUB + "sitemap.xml", sitemap("example.com", {"/": "2030-01-05", "/cu/": "2030-01-05"}))
        commit_all(self.root, "trang", date="2030-01-05")
        errors = check_sitemap.check(self.root)
        self.assertIn("thiếu trong sitemap: https://example.com/privacy/", errors)
        self.assertIn("sitemap có nhưng không có trang: https://example.com/cu/", errors)
        self.assertEqual(check_sitemap.main(["--root", str(self.root)]), 1)

    def test_sitemap_dung_host_cua_cau_hinh(self):
        write(self.root, PUB + "sitemap.xml", sitemap("khac.example.org", {"/": "2030-01-05", "/privacy/": "2030-01-05"}))
        commit_all(self.root, "trang", date="2030-01-05")
        self.assertIn("thiếu trong sitemap: https://example.com/", check_sitemap.check(self.root))

    def test_sitemap_lastmod_cu_hon_commit_bi_bao(self):
        write(self.root, PUB + "sitemap.xml", sitemap("example.com", {"/": "2030-01-01", "/privacy/": "2030-01-05"}))
        commit_all(self.root, "trang", date="2030-01-05")
        errors = check_sitemap.check(self.root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("https://example.com/: lastmod 2030-01-01 < 2030-01-05", errors[0])

    def test_staged_trang_dang_commit_can_lastmod_hom_nay(self):
        write(self.root, PUB + "sitemap.xml", sitemap("example.com", {"/": "2030-01-05", "/privacy/": "2030-01-05"}))
        commit_all(self.root, "trang", date="2030-01-05")
        write(self.root, PUB + "privacy/index.html", page("moi"))
        git(self.root, "add", "-A")
        errors = check_sitemap.check(self.root, staged=True, today="2030-02-01")
        self.assertEqual(errors, ["https://example.com/privacy/: lastmod 2030-01-05 < 2030-02-01 — sửa <lastmod> "
                                  "thành 2030-02-01"])
        self.assertEqual(check_sitemap.check(self.root, staged=False, today="2030-02-01"), [])

    def test_commit_dau_tien_cua_repo_chua_co_commit_nao(self):
        # new_app commit lần đầu qua hook thật: repo chưa có commit ⇒ không có lịch sử để so, chỉ vế "trang đang
        # commit cần lastmod hôm nay" (đã gặp: hook từ chối commit khởi tạo vì `git log` lỗi trên HEAD chưa có).
        write(self.root, PUB + "sitemap.xml", sitemap("example.com", {"/": "2030-02-01", "/privacy/": "2030-02-01"}))
        git(self.root, "add", "-A")
        self.assertEqual(check_sitemap.check(self.root, staged=True, today="2030-02-01"), [])
        self.assertEqual(check_sitemap.check(self.root, staged=False, today="2030-02-01"), [])
        errors = check_sitemap.check(self.root, staged=True, today="2030-02-02")
        self.assertEqual(len(errors), 2, errors)

    def test_url_thieu_lastmod_bi_bao(self):
        write(self.root, PUB + "sitemap.xml", sitemap("example.com", {"/": "2030-01-05", "/privacy/": "2030-01-05"})
              .replace("<lastmod>2030-01-05</lastmod>", "", 1))
        commit_all(self.root, "trang", date="2030-01-05")
        self.assertTrue(any("<lastmod>" in e for e in check_sitemap.check(self.root)))

    def test_khong_phai_repo_git_rc_2_mot_dong(self):
        import io
        import shutil
        from contextlib import redirect_stderr
        write(self.root, PUB + "sitemap.xml", sitemap("example.com", {"/": "2030-01-05", "/privacy/": "2030-01-05"}))
        shutil.rmtree(self.root / ".git")
        err = io.StringIO()
        with mock.patch.dict("os.environ", {"GIT_CEILING_DIRECTORIES": str(self.root.parent)}), redirect_stderr(err):
            rc = check_sitemap.main(["--root", str(self.root)])
        self.assertEqual(rc, 2)
        self.assertEqual(len(err.getvalue().strip().splitlines()), 1, err.getvalue())
        self.assertIn("không phải repo git", err.getvalue())

    def test_khong_co_web_thi_bo_qua(self):
        base = Path(self._tmp.name) / "khac"
        base.mkdir()
        root = make_repo(base, {})                       # app không có web/site/public
        self.assertEqual(check_sitemap.main(["--root", str(root)]), 0)


if __name__ == "__main__":
    unittest.main()
