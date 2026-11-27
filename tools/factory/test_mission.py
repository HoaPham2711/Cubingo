"""Test ledger nhà máy agent. Chạy: python3 -m unittest discover -s tools/factory -p 'test_*.py'"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission as M  # noqa: E402


class LedgerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("FACTORY_ROOT")
        os.environ["FACTORY_ROOT"] = self.tmp.name

    def tearDown(self):
        if self._old is None:
            os.environ.pop("FACTORY_ROOT", None)
        else:
            os.environ["FACTORY_ROOT"] = self._old
        self.tmp.cleanup()

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = M.main(list(args))
        return rc, out.getvalue(), err.getvalue()

    def mk(self, **kw):
        m = M.new_mission(kw.pop("goal", "Làm việc X"), kw.pop("playbook", "feature"), today="2026-11-05", **kw)
        M.save(m)
        return m


class NewMissionTests(LedgerTestCase):
    def test_slug_bo_dau_va_khong_trung(self):
        a = self.mk(goal="Thêm màn Trợ giúp đẹp")
        b = self.mk(goal="Thêm màn Trợ giúp đẹp")
        self.assertEqual(a["id"], "2026-11-05-them-man-tro-giup-dep")
        self.assertEqual(b["id"], "2026-11-05-them-man-tro-giup-dep-2")

    def test_playbook_sai_bi_tu_choi(self):
        with self.assertRaises(M.LedgerError):
            M.new_mission("x", "marketing-magic")

    def test_cli_new_in_ma_mission(self):
        rc, out, _ = self.cli("new", "--goal", "Báo cáo tuần", "--playbook", "analytics")
        self.assertEqual(rc, 0)
        self.assertIn("FACTORY-MISSION ", out)
        self.assertEqual(len(M.all_missions()), 1)


class TaskRuleTests(LedgerTestCase):
    def test_task_phai_co_tieu_chi(self):
        m = self.mk()
        with self.assertRaises(M.LedgerError):
            M.add_task(m, "t", "ios-engineer", accept=[])

    def test_phu_thuoc_phai_ton_tai(self):
        m = self.mk()
        with self.assertRaises(M.LedgerError):
            M.add_task(m, "t", "ios-engineer", accept=["a"], depends=["T9"])

    def test_verified_can_by_verifier(self):
        m = self.mk()
        M.add_task(m, "t", "ios-engineer", accept=["a"])
        with self.assertRaises(M.LedgerError):
            M.set_status(m, "T1", "verified", evidence=["run_tests OK"], by="ios-engineer")

    def test_verified_can_evidence(self):
        m = self.mk()
        M.add_task(m, "t", "ios-engineer", accept=["a"])
        with self.assertRaises(M.LedgerError):
            M.set_status(m, "T1", "verified", by="factory-verifier")
        M.set_status(m, "T1", "verified", evidence=["run_tests.py rc=0, 12 test"], by="factory-verifier")
        self.assertEqual(m["tasks"][0]["status"], "verified")

    def test_verified_khi_phu_thuoc_chua_xong_bi_chan(self):
        m = self.mk()
        M.add_task(m, "a", "ios-engineer", accept=["a"])
        M.add_task(m, "b", "ios-engineer", accept=["b"], depends=["T1"])
        with self.assertRaises(M.LedgerError):
            M.set_status(m, "T2", "verified", evidence=["x"], by="factory-verifier")

    def test_tran_fail_la_2(self):
        self.assertEqual(M.MAX_ATTEMPTS, 2)

    def test_fail_toi_tran_thanh_blocked(self):
        m = self.mk()
        M.add_task(m, "t", "ios-engineer", accept=["a"])
        for _ in range(M.MAX_ATTEMPTS - 1):
            M.set_status(m, "T1", "failed")
            self.assertEqual(m["tasks"][0]["status"], "failed")
        M.set_status(m, "T1", "failed")
        self.assertEqual(m["tasks"][0]["status"], "blocked")
        self.assertEqual(m["status"], "blocked")

    def test_cung_lop_fail_lan_2_thi_escalate(self):
        m = self.mk()
        M.add_task(m, "t", "ios-engineer", accept=["a"])
        M.set_status(m, "T1", "failed", fail_class=["preview-state"])
        self.assertNotIn("escalate", m["tasks"][0])
        M.set_status(m, "T1", "failed", fail_class=["preview-state", "preview-state"])
        self.assertEqual(m["tasks"][0]["escalate"], ["preview-state"])
        # trần 2 FAIL ⇒ đồng thời blocked; cờ escalate giữ lại để giám đốc biết lớp nào lặp
        self.assertEqual(m["tasks"][0]["status"], "blocked")
        self.assertIn("ESCALATE", M.summary(m))
        # sang trạng thái khác (giám đốc đổi cách) ⇒ cờ được gỡ
        M.set_status(m, "T1", "doing")
        self.assertNotIn("escalate", m["tasks"][0])

    def test_lop_khac_nhau_khong_escalate(self):
        m = self.mk()
        M.add_task(m, "t", "ios-engineer", accept=["a"])
        M.set_status(m, "T1", "failed", fail_class=["i18n"])
        M.set_status(m, "T1", "failed", fail_class=["layout"])
        self.assertNotIn("escalate", m["tasks"][0])

    def test_cli_failed_bat_buoc_fail_class(self):
        self.mk()
        rc, *_ = self.cli("add-task", "--title", "t", "--role", "ios-engineer", "--accept", "a")
        self.assertEqual(rc, 0)
        rc, _, err = self.cli("set", "T1", "--status", "failed")
        self.assertEqual(rc, 2)
        self.assertIn("--fail-class", err)
        self.cli("set", "T1", "--status", "failed", "--fail-class", "x")
        rc, out, _ = self.cli("set", "T1", "--status", "failed", "--fail-class", "x")
        self.assertEqual(rc, 0)
        self.assertIn("FACTORY-ESCALATE T1", out)

    def test_tick_bao_vuot_ngan_sach_dung_mot_lan(self):
        m = self.mk(budget=3)
        self.assertFalse(M.tick(m, 3))
        self.assertTrue(M.tick(m))
        self.assertFalse(M.tick(m))
        self.assertIn("5/3", M.budget_line(m))
        self.assertIn("VƯỢT", M.summary(m))

    def test_cli_tick(self):
        self.cli("new", "--goal", "g", "--playbook", "ops", "--budget", "1")
        rc, out, _ = self.cli("tick", "--what", "planner")
        self.assertEqual(rc, 0)
        self.assertIn("1/1", out)
        rc, out, _ = self.cli("tick", "2")
        self.assertIn("FACTORY-BUDGET", out)

    def test_budget_set_ghi_lich_su_va_bao_vuot_moc_moi(self):
        m = self.mk(budget=3)
        M.tick(m, 4)
        M.set_budget(m, 10, "plan thêm 3 task")
        self.assertEqual(m["budget"], 10)
        self.assertEqual(m["budget_history"][-1]["from"], 3)
        self.assertEqual(m["budget_history"][-1]["runs"], 4)
        self.assertNotIn("VƯỢT", M.budget_line(m))
        self.assertFalse(M.tick(m, 6))
        self.assertTrue(M.tick(m))
        with self.assertRaises(M.LedgerError):
            M.set_budget(m, 20, "  ")
        with self.assertRaises(M.LedgerError):
            M.set_budget(m, 0, "x")

    def test_cli_budget_va_thong_diep_khong_cat_viec(self):
        self.cli("new", "--goal", "g", "--playbook", "ops", "--budget", "1")
        rc, out, _ = self.cli("tick", "2")
        self.assertIn("budget --set", out)
        self.assertIn("KHÔNG cắt việc", out)
        rc, out, _ = self.cli("budget", "--set", "9", "--why", "phạm vi lớn")
        self.assertEqual(rc, 0)
        self.assertIn("2/9", out)
        with self.assertRaises(SystemExit):
            self.cli("budget", "--set", "9")

    def test_skipped_can_ly_do(self):
        m = self.mk()
        M.add_task(m, "t", "ios-engineer", accept=["a"])
        with self.assertRaises(M.LedgerError):
            M.set_status(m, "T1", "skipped")
        M.set_status(m, "T1", "skipped", note="trùng T0")
        self.assertEqual(m["tasks"][0]["status"], "skipped")

    def test_set_status_reset_stop_blocks(self):
        m = self.mk()
        M.add_task(m, "t", "ios-engineer", accept=["a"])
        m["stop_blocks"] = {"s": 2}
        M.set_status(m, "T1", "doing")
        self.assertEqual(m["stop_blocks"], {})

    def test_claim_in_dau_giam_doc(self):
        m = self.mk()
        rc, out, _ = self.cli("claim", "--mission", m["id"])
        self.assertEqual(rc, 0)
        self.assertIn(M.director_mark(m["id"]), out)
        self.assertNotIn(M.DIRECTOR_MARK, M.summary(M.load(m["id"])))


class ReadyAndCheckTests(LedgerTestCase):
    def test_ready_theo_phu_thuoc(self):
        m = self.mk()
        M.add_task(m, "a", "platform-engineer", accept=["a"])
        M.add_task(m, "b", "platform-engineer", accept=["b"], depends=["T1"])
        self.assertEqual([t["id"] for t in M.ready_tasks(m)], ["T1"])
        M.set_status(m, "T1", "verified", evidence=["ok"], by="factory-verifier")
        self.assertEqual([t["id"] for t in M.ready_tasks(m)], ["T2"])

    def test_check_va_close(self):
        m = self.mk()
        self.assertTrue(M.check(m))  # chưa có task
        M.add_task(m, "a", "platform-engineer", accept=["a"])
        with self.assertRaises(M.LedgerError):
            M.close(m)
        M.set_status(m, "T1", "verified", evidence=["ok"], by="factory-verifier")
        g = M.open_gate(m, "push", "Push develop?")
        self.assertTrue(any("cổng" in p for p in M.check(m)))
        M.resolve_gate(m, g["id"], approve=True)
        self.assertEqual(M.check(m), [])
        M.close(m)
        self.assertEqual(m["status"], "done")

    def test_abandon_can_ly_do(self):
        m = self.mk()
        with self.assertRaises(M.LedgerError):
            M.close(m, abandon=" ")
        M.close(m, abandon="user đổi hướng")
        self.assertEqual(m["status"], "abandoned")

    def test_cli_check_rc(self):
        m = self.mk()
        M.add_task(m, "a", "platform-engineer", accept=["a"])
        M.save(m)
        rc, out, _ = self.cli("check")
        self.assertEqual(rc, 1)
        self.assertIn("CHƯA xong", out)
        rc, _, err = self.cli("set", "T1", "--status", "verified", "--evidence", "ok")
        self.assertEqual(rc, 2)  # thiếu --by
        self.assertIn("verifier", err)
        rc, _, _ = self.cli("set", "T1", "--status", "verified", "--evidence", "ok", "--by", "factory-verifier")
        self.assertEqual(rc, 0)
        rc, out, _ = self.cli("check")
        self.assertEqual(rc, 0)


class AmendTests(LedgerTestCase):
    """Đổi DoD/tiêu chí giữa chừng phải để lại dấu vết (mission 2026-11-06: DoD chỉ đổi trong log ⇒ `show` sai)."""

    def test_sua_dod_can_ly_do_va_ghi_log(self):
        m = self.mk(dod=["MEMORY ≤ 100 dòng"])
        with self.assertRaises(M.LedgerError):
            M.amend(m, "dod", 1, "giảm ≥25 % byte", why=" ")
        M.amend(m, "dod", 1, "giảm ≥25 % byte", why="mâu thuẫn luật một-dòng-một-memory")
        self.assertEqual(m["dod"], ["giảm ≥25 % byte"])
        self.assertTrue(any("MEMORY ≤ 100 dòng" in l["msg"] and "mâu thuẫn" in l["msg"] for l in m["log"]))

    def test_sua_tieu_chi_task(self):
        m = self.mk()
        M.add_task(m, "t", "factory-scribe", accept=["a", "b"])
        M.amend(m, "accept", 2, "b mới", why="đo bằng byte", task="T1")
        self.assertEqual(m["tasks"][0]["acceptance"], ["a", "b mới"])

    def test_chi_so_ngoai_tam(self):
        m = self.mk(dod=["x"])
        with self.assertRaises(M.LedgerError):
            M.amend(m, "dod", 3, "y", why="z")

    def test_cli(self):
        m = self.mk(dod=["x"])
        rc, out, _ = self.cli("amend", "dod", "1", "--text", "y", "--why", "z", "--mission", m["id"])
        self.assertEqual(rc, 0)
        self.assertEqual(M.load(m["id"])["dod"], ["y"])


class MissionFlagPositionTests(LedgerTestCase):
    def test_mission_truoc_hoac_sau_lenh_con(self):
        a = self.mk(goal="a")
        self.mk(goal="b")  # 2 mission active ⇒ bắt buộc chỉ định
        rc, _, _ = self.cli("add-task", "--mission", a["id"], "--title", "x", "--role", "platform-engineer",
                            "--accept", "y")
        self.assertEqual(rc, 0)
        rc, out, _ = self.cli("--mission", a["id"], "show")
        self.assertEqual(rc, 0)
        self.assertIn("T1", out)
        rc, out, _ = self.cli("show", "--mission", a["id"])
        self.assertIn("T1", out)
        rc, _, err = self.cli("show")
        self.assertEqual(rc, 2)
        self.assertIn("nhiều mission active", err)


class ResolveTests(LedgerTestCase):
    def test_nhieu_mission_active_bat_chi_dinh(self):
        self.mk(goal="a")
        self.mk(goal="b")
        with self.assertRaises(M.LedgerError):
            M.resolve(None)

    def test_ghi_nguyen_tu_json_hop_le(self):
        m = self.mk()
        M.add_task(m, "a", "platform-engineer", accept=["a"])
        M.save(m)
        data = json.loads(M.mission_path(m["id"]).read_text(encoding="utf-8"))
        self.assertEqual(data["tasks"][0]["id"], "T1")
        leftovers = list(M.mission_path(m["id"]).parent.glob(".mission-*"))
        self.assertEqual(leftovers, [])

    def test_summary_co_ma_va_task_ke(self):
        m = self.mk(goal="Mục tiêu A")
        M.add_task(m, "làm a", "platform-engineer", accept=["a"])
        s = M.summary(m)
        self.assertIn(m["id"], s)
        self.assertIn("Kế tiếp: T1", s)


if __name__ == "__main__":
    unittest.main()


class CloseUntrackedTests(LedgerTestCase):
    """close phải nhắc commit hồ sơ mission (theo thiết kế nó thuộc git) — lỗ hổng 2026-11-07: 3 mission sót."""

    def git(self, *args):
        import subprocess
        subprocess.run(["git", "-C", self.tmp.name, *args], check=True, capture_output=True, env=self.env)

    def setUp(self):
        super().setUp()
        # Chạy trong hook git (pre-commit) thì GIT_DIR/GIT_INDEX_FILE trỏ repo THẬT — phải gỡ, nếu không `git init`
        # và `git config` ghi vào repo thật (sự cố 2026-11-07: core.bare=true + user t@t). Gỡ cả ở os.environ cho
        # mission.uncommitted_files, và kiểm chắc tmp là repo riêng trước khi làm gì.
        self._git_env = {k: v for k, v in os.environ.items() if k.startswith("GIT_")}
        for k in self._git_env:
            del os.environ[k]
        self.addCleanup(os.environ.update, self._git_env)
        self.env = dict(os.environ)
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        import subprocess
        top = subprocess.run(["git", "-C", self.tmp.name, "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, env=self.env).stdout.strip()
        assert Path(top).resolve() == Path(self.tmp.name).resolve(), f"git trỏ nhầm repo: {top}"
        Path(self.tmp.name, ".gitignore").write_text(".factory/missions/*/artifacts/\n", encoding="utf-8")

    def test_close_bao_untracked_roi_im_khi_da_commit(self):
        m = self.mk(goal="việc a")
        art = M.missions_dir() / m["id"] / "artifacts"
        art.mkdir()
        (art / "log.txt").write_text("lớn", encoding="utf-8")
        rc, out, _ = self.cli("close", "--mission", m["id"], "--abandon", "thử")
        self.assertEqual(rc, 0)
        self.assertIn("FACTORY-UNTRACKED", out)
        self.assertIn("mission.json", out)
        self.assertNotIn("artifacts", out.split("(")[1].split(")")[0])
        self.git("add", "-A")
        self.git("commit", "-qm", "x")
        self.assertEqual(M.uncommitted_files(m["id"]), [])

    def test_close_bao_ca_file_da_track_nhung_sua(self):
        m = self.mk(goal="việc b")
        self.git("add", "-A")
        self.git("commit", "-qm", "x")
        rc, out, _ = self.cli("close", "--mission", m["id"], "--abandon", "thử")
        self.assertIn("FACTORY-UNTRACKED", out)

    def test_ngoai_git_khong_vo(self):
        import shutil
        shutil.rmtree(Path(self.tmp.name, ".git"))
        m = self.mk(goal="việc c")
        rc, out, _ = self.cli("close", "--mission", m["id"], "--abandon", "thử")
        self.assertEqual(rc, 0)
        self.assertNotIn("FACTORY-UNTRACKED", out)
