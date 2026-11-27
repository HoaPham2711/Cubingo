"""Test mutate.py: phá → chạy → khôi phục đúng từng byte, kể cả khi bị kill / chạy song song."""
import contextlib
import io
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mutate  # noqa: E402

PY = sys.executable
SCRIPT = str(HERE / "mutate.py")


class MutateBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state"
        self._old_state = mutate.STATE_ROOT
        mutate.STATE_ROOT = self.state
        self.env = dict(os.environ, FACTORY_MUTATE_STATE=str(self.state))
        self.src = Path(self.tmp.name) / "calc.py"
        self.src.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        self.test = Path(self.tmp.name) / "t.py"
        self.test.write_text(
            "import sys; sys.path.insert(0, %r)\nimport calc\nassert calc.add(2, 3) == 5\n" % self.tmp.name,
            encoding="utf-8")
        self.orig = self.src.read_bytes()

    def tearDown(self):
        mutate.STATE_ROOT = self._old_state
        self.tmp.cleanup()

    def run_m(self, find, replace, cmd, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = mutate.main(["--file", str(self.src), "--find", find, "--replace", replace, *extra, "--"] + cmd)
        return rc, out.getvalue()

    def spawn(self, cmd):
        return subprocess.Popen([PY, SCRIPT, "--file", str(self.src), "--find", "a + b", "--replace", "a - b", "--"]
                                + cmd, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def wait_mutated(self, timeout=10):
        t0 = time.time()
        while self.src.read_bytes() == self.orig:
            if time.time() - t0 > timeout:
                self.fail("mutate không phá file trong thời hạn")
            time.sleep(0.05)


class VerdictTests(MutateBase):
    def test_killed_khi_test_gac(self):
        rc, out = self.run_m("a + b", "a - b", [PY, str(self.test)])
        self.assertEqual(rc, 0)
        self.assertIn("MUTATION KILLED", out)
        self.assertEqual(self.src.read_bytes(), self.orig)

    def test_survived_khi_test_khong_gac(self):
        rc, out = self.run_m("a + b", "a - b", [PY, "-c", "pass"])
        self.assertEqual(rc, 1)
        self.assertIn("MUTATION SURVIVED", out)
        self.assertEqual(self.src.read_bytes(), self.orig)

    def test_rc3_false_green_la_inconclusive(self):
        rc, out = self.run_m("a + b", "a - b", [PY, "-c", "import sys; sys.exit(3)"])
        self.assertEqual(rc, 4)
        self.assertIn("INCONCLUSIVE", out)

    def test_loi_cu_phap_la_inconclusive(self):
        rc, out = self.run_m("a + b", "a +* b", [PY, str(self.test)])
        self.assertEqual(rc, 4)
        self.assertEqual(self.src.read_bytes(), self.orig)

    def test_kill_pattern_khong_khop_la_inconclusive(self):
        rc, _ = self.run_m("a + b", "a - b", [PY, str(self.test)], "--kill-pattern", "FAILED \\(failures")
        self.assertEqual(rc, 4)
        rc, _ = self.run_m("a + b", "a - b", [PY, str(self.test)], "--kill-pattern", "AssertionError")
        self.assertEqual(rc, 0)

    def test_find_phai_duy_nhat(self):
        rc, _ = self.run_m("a", "z", [PY, "-c", "pass"])
        self.assertEqual(rc, 2)
        self.assertEqual(self.src.read_bytes(), self.orig)

    def test_khoi_phuc_ca_khi_lenh_khong_ton_tai(self):
        with self.assertRaises(FileNotFoundError):
            mutate.main(["--file", str(self.src), "--find", "a + b", "--replace", "a - b", "--",
                         "/khong/co/lenh-nay"])
        self.assertEqual(self.src.read_bytes(), self.orig)


class KillTests(MutateBase):
    def test_sigterm_van_khoi_phuc(self):
        p = self.spawn(["sleep", "30"])
        self.wait_mutated()
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=10)
        self.assertEqual(self.src.read_bytes(), self.orig)

    def test_sigkill_khoi_phuc_o_lan_sau(self):
        p = self.spawn(["sleep", "30"])
        self.wait_mutated()
        p.kill()
        p.wait(timeout=10)
        self.assertNotEqual(self.src.read_bytes(), self.orig)  # SIGKILL: không handler nào chạy được
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mutate.main(["--recover"]), 0)
        self.assertEqual(self.src.read_bytes(), self.orig)

    def test_chay_lai_sau_sigkill_khong_sap(self):
        # review vòng 2: restore_pending rmtree cả thư mục khoá ⇒ lần chạy sau văng FileNotFoundError rc=1
        p = self.spawn(["sleep", "30"])
        self.wait_mutated()
        p.kill()
        p.wait(timeout=10)
        rc, out = self.run_m("a + b", "a - b", [PY, str(self.test)])
        self.assertEqual(rc, 0, out)
        self.assertIn("MUTATION KILLED", out)
        self.assertEqual(self.src.read_bytes(), self.orig)

    def test_khong_khoi_phuc_de_len_sua_doi_that(self):
        # review vòng 2: sau kill -9, thợ sửa file; lần mutate sau KHÔNG được chép bản cũ đè lên
        p = self.spawn(["sleep", "30"])
        self.wait_mutated()
        p.kill()
        p.wait(timeout=10)
        self.src.write_text("def add(a, b):\n    return b + a  # thợ sửa thật\n", encoding="utf-8")
        edited = self.src.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mutate.main(["--recover"]), 2)
        self.assertEqual(self.src.read_bytes(), edited)

    def test_timeout_co_tac_dung(self):
        t0 = time.time()
        rc, out = self.run_m("a + b", "a - b", [PY, "-c", "import time; print('x', flush=True); time.sleep(20)"],
                             "--timeout", "2")
        self.assertLess(time.time() - t0, 10)
        self.assertEqual(rc, 4)
        self.assertIn("rc=124", out)
        self.assertEqual(self.src.read_bytes(), self.orig)

    def test_timeout_diet_ca_tien_trinh_chau(self):
        # review vòng 3: run_tests.py sinh xcodebuild làm CHÁU — hết hạn phải diệt cả nhóm, không chỉ con
        pidf = Path(self.tmp.name) / "grandchild.pid"
        prog = ("import subprocess; p = subprocess.Popen(['sleep', '60']); "
                "open(%r, 'w').write(str(p.pid)); p.wait()" % str(pidf))
        rc, _ = self.run_m("a + b", "a - b", [PY, "-c", prog], "--timeout", "2")
        self.assertEqual(rc, 4)
        pid = int(pidf.read_text())
        deadline = time.time() + 5
        alive = True
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except ProcessLookupError:
                alive = False
                break
        self.assertFalse(alive, "tiến trình cháu còn sống sau timeout")

    def test_song_song_cung_file_bi_tu_choi(self):
        p = self.spawn(["sleep", "3"])
        self.wait_mutated()
        # Không khoá: lần 2 sẽ "khôi phục" bản ghi dở của lần 1 (phá ngang lần 1) rồi chạy tiếp với chuỗi gốc.
        out = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(out):
            rc = mutate.main(["--file", str(self.src), "--find", "a + b", "--replace", "a * b", "--", PY, "-c", "pass"])
        self.assertEqual(rc, 2)
        self.assertIn("đang có mutate khác", out.getvalue())
        self.assertIn(b"a - b", self.src.read_bytes())  # lần 1 vẫn giữ nguyên phép phá của nó
        p.wait(timeout=15)
        self.assertEqual(self.src.read_bytes(), self.orig)


if __name__ == "__main__":
    unittest.main()
