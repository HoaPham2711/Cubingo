"""Test sync_develop bằng repo git tạm (origin bare + clone + worktree). Chạy:
python3 -m unittest tools/dev/test_sync_develop.py"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_develop as S  # noqa: E402


def sh(cwd, *args):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


class SyncDevelopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.origin = t / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "develop", str(self.origin)], check=True)
        self.main = t / "main"          # checkout chính, đang ở develop
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.main)], check=True,
                       capture_output=True)
        for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
            sh(self.main, "config", k, v)
        sh(self.main, "checkout", "-q", "-b", "develop")
        self.commit(self.main, "a.txt", "1")
        sh(self.main, "push", "-q", "-u", "origin", "develop")
        self.other = t / "other"        # máy/phiên khác merge PR lên origin
        subprocess.run(["git", "clone", "-q", "-b", "develop", str(self.origin), str(self.other)], check=True,
                       capture_output=True)
        for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
            sh(self.other, "config", k, v)

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, repo, name, text):
        (Path(repo) / name).write_text(text)
        sh(repo, "add", name)
        sh(repo, "commit", "-q", "-m", f"{name}={text}")

    def remote_advances(self):
        self.commit(self.other, "b.txt", "merged")
        sh(self.other, "push", "-q", "origin", "develop")
        return sh(self.other, "rev-parse", "HEAD")

    def test_fastForwards_checkedOutDevelop_fromFeatureWorktree(self):
        wt = Path(self.tmp.name) / "feature"
        sh(self.main, "worktree", "add", "-q", "-b", "feat", str(wt))
        new = self.remote_advances()
        ok, msg = S.sync(wt)            # gọi từ worktree feature, develop ở checkout chính
        self.assertTrue(ok, msg)
        self.assertEqual(sh(self.main, "rev-parse", "HEAD"), new)
        self.assertTrue((self.main / "b.txt").exists())   # working tree cũng cập nhật, không chỉ ref

    def test_updatesRef_whenDevelopNotCheckedOut(self):
        sh(self.main, "checkout", "-q", "-b", "elsewhere")
        new = self.remote_advances()
        ok, msg = S.sync(self.main)
        self.assertTrue(ok, msg)
        self.assertEqual(sh(self.main, "rev-parse", "develop"), new)
        self.assertEqual(sh(self.main, "branch", "--show-current"), "elsewhere")

    def test_alreadyInSync_isOk(self):
        ok, msg = S.sync(self.main)
        self.assertTrue(ok, msg)
        self.assertIn("đã khớp", msg)

    def test_divergedLocal_refusesAndKeepsLocalCommit(self):
        self.commit(self.main, "local.txt", "x")
        mine = sh(self.main, "rev-parse", "HEAD")
        self.remote_advances()
        ok, msg = S.sync(self.main)
        self.assertFalse(ok)
        self.assertIn("lệch nhánh", msg)
        self.assertEqual(sh(self.main, "rev-parse", "HEAD"), mine)

    def test_dirtyOverlappingFile_refusesWithoutTouchingWork(self):
        self.commit(self.other, "a.txt", "remote")
        sh(self.other, "push", "-q", "origin", "develop")
        (self.main / "a.txt").write_text("đang sửa dở")
        before = sh(self.main, "rev-parse", "HEAD")
        ok, msg = S.sync(self.main)
        self.assertFalse(ok)
        self.assertEqual((self.main / "a.txt").read_text(), "đang sửa dở")
        self.assertEqual(sh(self.main, "rev-parse", "HEAD"), before)

    def test_dirtyUnrelatedFile_stillFastForwards(self):
        (self.main / "notes.txt").write_text("rác chưa track")
        new = self.remote_advances()
        ok, msg = S.sync(self.main)
        self.assertTrue(ok, msg)
        self.assertEqual(sh(self.main, "rev-parse", "HEAD"), new)
        self.assertTrue((self.main / "notes.txt").exists())


if __name__ == "__main__":
    unittest.main()
