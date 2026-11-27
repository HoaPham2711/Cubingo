"""Test CLI aso.py bằng runner giả (offline): import/plan/lint/pull-version, app record, fixture offline, read-only."""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402 — thư mục trạng thái + cấu hình giả
import asc_cli  # noqa: E402
import aso  # noqa: E402
import lint as lint_mod  # noqa: E402
import store  # noqa: E402
from test_snapshot import fake_pull  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURE_APP_MOI = HERE / "fixtures" / "app-moi"


def make_run(state):
    pull = fake_pull()

    def run(args, **kw):
        if args[:2] == ["versions", "view"]:
            return {"data": {"attributes": {"appVersionState": state}}}
        return pull(args, **kw)
    return run


def capture(fn, *a, **k):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(*a, **k)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aso cli thu "))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = _testenv.isolate(self)
        # Repo giả: <tmp>/repo/store/metadata (+ store/lint.toml cạnh nó).
        p = mock.patch.object(store, "STORE", self.tmp / "repo" / "store" / "metadata")
        p.start()
        self.addCleanup(p.stop)

    def _call(self, fn, argv, run):
        args = aso.build_parser()[0].parse_args(argv)
        return capture(fn, args, run=run)

    def test_build_errors_exit_2_without_traceback(self):
        for exc in (RuntimeError("lệnh lỗi (exit 65): xcodebuild archive"), ValueError("phải build từ nhánh main")):
            with self.subTest(exc):
                def boom(*a, **k):
                    raise exc
                with mock.patch.object(aso.build_mod, "build", boom):
                    code, _out, err = capture(aso.main, ["build", "--version", "1.2.3"])
                self.assertEqual(code, 2)
                self.assertIn(f"Lỗi: {exc}", err)
                self.assertNotIn("Traceback", err)

    def test_abbrev_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            aso.build_parser()[0].parse_args(["pull", "--vers", "1"])

    def test_import_then_plan_zero_changes_then_refuse_reimport(self):
        run = make_run("PREPARE_FOR_SUBMISSION")
        code, _, _ = self._call(aso.cmd_import, ["import", "--version", "1.2.3"], run)
        self.assertEqual(code, 0)
        code, out, _ = self._call(aso.cmd_plan, ["plan", "--version", "1.2.3"], run)
        self.assertEqual(code, 0)
        self.assertIn("Không có thay đổi", out)
        self.assertIn("Plan: ", out)
        self.assertTrue(list((self.state / "plans").glob("*.json")))
        plan_line = [l for l in out.splitlines() if l.startswith("Plan: ")][-1]
        plan_path = Path(plan_line.split("Plan: ", 1)[1])
        self.assertTrue(plan_path.is_absolute())
        self.assertEqual(plan_path.parent, self.state / "plans")
        code, _, err = self._call(aso.cmd_import, ["import", "--version", "1.2.3"], run)
        self.assertEqual(code, 2)
        self.assertIn("từ chối", err)

    def _khung(self):
        store.write(store.STORE, "1.2.3", {
            ("app-info", "en-US", "name"): "Thu App",
            ("version", "en-US", "description"): lint_mod.PLACEHOLDER + " — describe",
            ("version", "en-US", "keywords"): lint_mod.PLACEHOLDER,
            ("version", "en-US", "whatsNew"): lint_mod.PLACEHOLDER + " — what"})

    def test_import_force_over_skeleton_thay_khung(self):
        self._khung()
        run = make_run("PREPARE_FOR_SUBMISSION")
        code, _, err = self._call(aso.cmd_import, ["import", "--version", "1.2.3"], run)
        self.assertEqual(code, 2, "không cờ ⇒ vẫn từ chối")
        self.assertIn("--force-over-skeleton", err)
        code, _, err = self._call(aso.cmd_import, ["import", "--version", "1.2.3", "--force-over-skeleton"], run)
        self.assertEqual(code, 0, err)
        got = store.load(store.STORE, "1.2.3")
        self.assertEqual(dict(got), {("app-info", "en-US", "name"): "Thu App", ("version", "en-US", "whatsNew"): "x"})

    def test_import_force_over_skeleton_tu_choi_khi_da_viet_that(self):
        self._khung()
        p = store.STORE / "version" / "1.2.3" / "en-US.json"
        data = json.loads(p.read_text())
        data["keywords"] = "memo,jot"          # một ô đã viết thật
        p.write_text(json.dumps(data))
        before = p.read_bytes()
        code, _, err = self._call(aso.cmd_import, ["import", "--version", "1.2.3", "--force-over-skeleton"],
                                  make_run("PREPARE_FOR_SUBMISSION"))
        self.assertEqual(code, 2)
        self.assertIn("chữ viết thật", err)
        self.assertEqual(p.read_bytes(), before)

    def test_import_force_pull_loi_khong_xoa_khung(self):
        self._khung()
        before = sorted(x.relative_to(store.STORE) for x in store.STORE.rglob("*"))

        def boom(args, **kw):
            raise asc_cli.AscError("mạng rớt")
        with self.assertRaises(asc_cli.AscError):
            self._call(aso.cmd_import, ["import", "--version", "1.2.3", "--force-over-skeleton"], boom)
        self.assertEqual(sorted(x.relative_to(store.STORE) for x in store.STORE.rglob("*")), before)

    def test_lint_local_issue_exit_1(self):
        store.write(store.STORE, "1", {("app-info", "en-US", "name"): "x" * 40})
        calls = []

        def run(args, **kw):
            calls.append(args)
            return {"findings": []}
        code, out, _ = self._call(aso.cmd_lint, ["lint", "--version", "1"], run)
        self.assertEqual(code, 1)
        self.assertIn("en-US/name:", out)
        self.assertNotIn("--dir", calls[0])
        self.assertEqual(calls[0][:3], ["metadata", "keywords", "audit"])
        self.assertEqual(calls[0][calls[0].index("--app") + 1], _testenv.FAKE_APP_ID)

    def test_lint_clean_audit_failure_warns_exit_0(self):
        store.write(store.STORE, "1", {("app-info", "en-US", "name"): "Thu App"})

        def run(args, **kw):
            raise RuntimeError("hỏng")
        code, out, _ = self._call(aso.cmd_lint, ["lint", "--version", "1"], run)
        self.assertEqual(code, 0)
        self.assertIn("CẢNH BÁO: keywords audit không chạy được: hỏng", out)

    def test_lint_canh_bao_khong_lam_do_va_chu_cam_cua_app(self):
        store.write(store.STORE, "1", {("version", "en-US", "marketingUrl"): "https://nguoi" "-la.app/x"})
        code, out, _ = self._call(aso.cmd_lint, ["lint", "--version", "1"], lambda a, **k: None)
        self.assertEqual(code, 0)
        self.assertIn("cảnh báo:", out)
        (store.STORE.parent / "lint.toml").write_text('banned = ["nguoi-la"]\n', encoding="utf-8")
        code, out, _ = self._call(aso.cmd_lint, ["lint", "--version", "1"], lambda a, **k: None)
        self.assertEqual(code, 1)
        self.assertIn("chữ cấm", out)

    def test_lint_toml_sai_dang_thi_fail_rc2_khong_traceback(self):
        store.write(store.STORE, "1", {("app-info", "en-US", "name"): "Thu App"})
        (store.STORE.parent / "lint.toml").write_text('banned = "x"\n', encoding="utf-8")
        code, out, err = capture(aso.main, ["lint", "--version", "1"])
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("FAIL: "), err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", out + err)

    def test_lint_khong_app_store_id_van_chay_bo_audit(self):
        _testenv.use_config(self, _testenv.cfg(**{"apple.app_store_id": ""}))
        store.write(store.STORE, "1", {("app-info", "en-US", "name"): "Thu App"})
        calls = []
        code, out, _ = self._call(aso.cmd_lint, ["lint", "--version", "1"], lambda a, **k: calls.append(a))
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn("apple.app_store_id rỗng", out)

    def test_plan_value_error_exit_2(self):
        run = make_run("PREPARE_FOR_SUBMISSION")
        self._call(aso.cmd_import, ["import", "--version", "1.2.3"], run)
        (store.STORE / "app-info" / "en-US.json").unlink()
        code, _, err = self._call(aso.cmd_plan, ["plan", "--version", "1.2.3"], run)
        self.assertEqual(code, 2)
        self.assertIn("thiếu locale", err)

    def test_version_mac_dinh_lay_tu_app_config(self):
        args = aso.build_parser()[0].parse_args(["lint"])
        self.assertIsNone(args.version)
        seen = {}

        def fake_lint(a, **k):
            seen["v"] = a.version
            return 0
        with mock.patch.object(aso, "cmd_lint", fake_lint):
            code, _, _ = capture(aso.main, ["lint"])
        self.assertEqual((code, seen["v"]), (0, "1.2.3"))

    # --- app record ---

    def test_khong_co_app_store_id_thi_tu_choi_co_huong_dan(self):
        _testenv.use_config(self, _testenv.cfg(**{"apple.app_store_id": ""}))
        for argv in (["pull"], ["import"], ["plan"], ["pull-version"], ["snapshot"],
                     ["apply", "--plan", "p.json", "--expect", "abcd1234"], ["restore", "--snapshot", "x"],
                     ["release-plan", "--build-json", "b.json"]):
            with self.subTest(argv=argv):
                with mock.patch.object(asc_cli, "run", side_effect=AssertionError("không được gọi asc")):
                    code, out, err = capture(aso.main, argv)
                self.assertEqual(code, 2)
                lines = err.strip().splitlines()
                self.assertEqual(len(lines), 1, err)
                self.assertIn("apple.app_store_id", lines[0])
                self.assertIn("app.config.toml", lines[0])
                self.assertNotIn("Traceback", out + err)

    def test_hai_app_khong_chung_thu_muc_trang_thai(self):
        a = store.state_dir(_testenv.cfg(**{"app.slug": "app-mot"}))
        b = store.state_dir(_testenv.cfg(**{"app.slug": "app-hai"}))
        self.assertNotEqual(a, b)
        self.assertEqual(a.name, "aso")
        self.assertEqual(a.parent.name, "app-mot")
        self.assertEqual(b.parent.name, "app-hai")
        self.assertEqual(a.parent.parent, b.parent.parent)
        # plan lưu theo slug của app đang chạy
        _testenv.use_config(self, _testenv.cfg(**{"app.slug": "app-mot"}))
        self.assertEqual(aso.plans_dir(), a / "plans")

    # --- fixture offline ---

    def test_offline_fixture_khong_dung_duoc_voi_apply(self):
        plan = self.tmp / "plan.json"
        plan.write_text("{}")
        with mock.patch.object(asc_cli, "offline_runner", side_effect=AssertionError("không được dựng runner")):
            code, _out, err = capture(aso.main, ["--offline-fixture", str(FIXTURE_APP_MOI), "apply",
                                                 "--plan", str(plan), "--expect", "abcd1234"])
        self.assertEqual(code, 2)
        self.assertIn("--offline-fixture", err)
        self.assertFalse(applied_ledger(self.state))

    def test_offline_fixture_an_khoi_help(self):
        code, out, _ = capture(lambda: _help())
        self.assertNotIn("offline", out)

    def test_offline_fixture_app_moi_lint_va_plan(self):
        _testenv.use_config(self, _testenv.cfg(**{"version.marketing": "0.1.0",
                                                  "web.host_prod": "example.com",
                                                  "web.host_dev": "dev.example.com"}))
        # Khung như new_app sinh với host giữ chỗ của template: chữ giữ chỗ + URL example.com (ASC chưa có URL nào).
        fx = json.loads((FIXTURE_APP_MOI / "metadata_pull_--app_APP_--version_0.1.0_--dir_DIR.json").read_text())
        urls = {"app-info/en-US.json": {"privacyPolicyUrl": "https://{h}/privacy/"},
                "version/0.1.0/en-US.json": {"marketingUrl": "https://{h}/", "supportUrl": "https://{h}/support/"}}

        def write_local(host):
            for rel, obj in fx["files"].items():
                p = store.STORE / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                old = json.loads(p.read_text()) if p.exists() else obj
                old.update({k: v.format(h=host) for k, v in urls[rel].items()})
                p.write_text(json.dumps(old, ensure_ascii=False))
        write_local("example.com")
        argv = ["--offline-fixture", str(FIXTURE_APP_MOI)]
        code, out, _ = capture(aso.main, argv + ["lint"])
        self.assertEqual(code, 1, "khung còn chữ giữ chỗ ⇒ lint đỏ")
        self.assertIn("0 finding", out)
        self.assertIn("host giữ chỗ/dành riêng (example.com)", out)
        # viết chữ thật nhưng giữ host của template ⇒ lint vẫn đỏ, plan từ chối (URL sẽ lên ASC)
        vfile = store.STORE / "version" / "0.1.0" / "en-US.json"
        data = json.loads(vfile.read_text())
        data.update(description="Write notes fast.", keywords="memo,jot", promotionalText="Fresh.",
                    whatsNew="First release.")
        vfile.write_text(json.dumps(data))
        code, out, _ = capture(aso.main, argv + ["lint"])
        self.assertEqual(code, 1, out)
        code, out, err = capture(aso.main, argv + ["plan"])
        self.assertEqual(code, 2, out)
        self.assertIn("host giữ chỗ/dành riêng", err)
        # đặt host thật trong app.config.toml + sửa URL ⇒ lint xanh, plan ra thay đổi mang app id
        host = "ghi-chu" "-thu.app"
        _testenv.use_config(self, _testenv.cfg(**{"version.marketing": "0.1.0", "web.host_prod": host,
                                                  "web.host_dev": "dev." + host}))
        write_local(host)
        code, out, _ = capture(aso.main, argv + ["lint"])
        self.assertEqual(code, 0, out)
        code, out, err = capture(aso.main, argv + ["plan"])
        self.assertEqual(code, 0, err)
        self.assertIn("Tổng: 7 thao tác", out)
        self.assertIn("App (apple.app_store_id): " + _testenv.FAKE_APP_ID, out)

    def test_lint_thieu_thu_muc_version_dang_soi_la_loi(self):
        store.write(store.STORE, "1.0.0", {("app-info", "en-US", "name"): "Thu App",
                                           ("version", "en-US", "description"): "Notes."})
        code, out, _ = self._call(aso.cmd_lint, ["lint", "--version", "1.0.0"], lambda a, **k: None)
        self.assertEqual(code, 0, out)
        # sau bump_version: version mới chưa có thư mục ⇒ đỏ, chỉ đường pull-version
        code, out, _ = self._call(aso.cmd_lint, ["lint", "--version", "1.1.0"], lambda a, **k: None)
        self.assertEqual(code, 1, out)
        self.assertIn("thiếu thư mục version 1.1.0", out)
        self.assertIn("store/metadata/version/1.1.0/<locale>.json", out)
        # bố cục `versions/` (asc ghi kiểu đó) ⇒ gợi ý đúng `versions/`
        shutil.rmtree(store.STORE / "version")
        store.write(store.STORE, "1.0.0", {("version", "en-US", "description"): "Notes."}, vdir="versions")
        code, out, _ = self._call(aso.cmd_lint, ["lint", "--version", "1.1.0"], lambda a, **k: None)
        self.assertEqual(code, 1, out)
        self.assertIn("store/metadata/versions/1.1.0/<locale>.json", out)
        self.assertIn("pull-version --version 1.1.0", out)

    def test_lint_chua_co_thu_muc_version_nao_chi_canh_bao(self):
        # store/metadata trống chờ import: không có gì để soi ⇒ cảnh báo, rc 0
        code, out, _ = self._call(aso.cmd_lint, ["lint", "--version", "1.0.0"], lambda a, **k: None)
        self.assertEqual(code, 0, out)
        self.assertIn("không có metadata nào", out)

    def test_lint_notes_apple_review_con_giu_cho_la_loi(self):
        store.write(store.STORE, "1.0.0", {("app-info", "en-US", "name"): "Thu App"})
        notes = store.STORE.parent / "review" / "notes.txt"
        notes.parent.mkdir(parents=True)
        notes.write_text(lint_mod.PLACEHOLDER + " — write the notes here.", encoding="utf-8")
        code, out, _ = self._call(aso.cmd_lint, ["lint", "--version", "1.0.0"], lambda a, **k: None)
        self.assertEqual(code, 1, out)
        self.assertIn("review/notes.txt", out)
        notes.write_text("Open the app and tap New.", encoding="utf-8")
        code, out, _ = self._call(aso.cmd_lint, ["lint", "--version", "1.0.0"], lambda a, **k: None)
        self.assertEqual(code, 0, out)

    def test_offline_fixture_thieu_lenh_bao_ro(self):
        code, _out, err = capture(aso.main, ["--offline-fixture", str(FIXTURE_APP_MOI), "snapshot",
                                             "--version", "9.9.9"])
        self.assertEqual(code, 1)
        self.assertIn("metadata_pull_--app_APP_--version_9.9.9_--dir_DIR", err)

    # --- read-only ---

    def test_lenh_doc_luon_read_only(self):
        """Mọi lệnh không phải apply chỉ gọi asc ở chế độ đọc (write=False ⇒ ASC_READ_ONLY=1), và asc_cli đặt
        ASC_READ_ONLY=1 cho mọi lệnh đọc trong allowlist."""
        calls = []
        real = asc_cli.offline_runner

        def recording(d):
            inner = real(d)

            def run(args, **kw):
                calls.append((list(args), kw.get("write", False)))
                return inner(args, **kw)
            return run
        _testenv.use_config(self, _testenv.cfg(**{"version.marketing": "0.1.0"}))
        snap = self.tmp / "snap"
        store.write(snap / "metadata", "0.1.0", {("app-info", "en-US", "name"): "Sample",
                                                 ("version", "en-US", "keywords"): lint_mod.PLACEHOLDER})
        argv = ["--offline-fixture", str(FIXTURE_APP_MOI)]
        with mock.patch.object(asc_cli, "offline_runner", recording):
            for cmd in (["lint"], ["plan"], ["pull", "--dir", str(self.tmp / "p")], ["snapshot"],
                        ["restore", "--snapshot", str(snap)]):
                capture(aso.main, argv + cmd)
        self.assertEqual(len(calls), 7, calls)
        self.assertEqual([c for c in calls if c[1]], [], "lệnh đọc gọi asc với write=True")
        # tầng env: write=False ⇒ ASC_READ_ONLY=1; chỉ lối ghi bỏ nó
        self.assertEqual(asc_cli._build_env(False, "k", "i", Path("/x"), "1").get("ASC_READ_ONLY"), "1")
        self.assertNotIn("ASC_READ_ONLY", asc_cli._build_env(True, "k", "i", Path("/x"), "1"))

    # --- pull-version ---
    def _pv(self, run, version="1.2.3"):
        return self._call(aso.cmd_pull_version, ["pull-version", "--version", version], run)

    def test_pull_version_refuses_existing_dir(self):
        for d in ("version", "versions"):
            with self.subTest(d=d):
                (store.STORE / d / "1.2.3").mkdir(parents=True, exist_ok=True)
                code, _, err = self._pv(make_run("PREPARE_FOR_SUBMISSION"))
                self.assertEqual(code, 2)
                self.assertIn("từ chối", err)
                shutil.rmtree(store.STORE / d)

    def test_pull_version_refuses_app_info_drift(self):
        store.write(store.STORE, "1.2.2", {("app-info", "en-US", "name"): "Khác"})
        code, out, err = self._pv(make_run("PREPARE_FOR_SUBMISSION"))
        self.assertEqual(code, 2)
        self.assertIn("app-info en-US name", out + err)
        self.assertFalse((store.STORE / "version" / "1.2.3").exists())

    def test_pull_version_copies_only_version_dir(self):
        store.write(store.STORE, "1.2.2", {("app-info", "en-US", "name"): "Thu App",
                                            ("version", "en-US", "whatsNew"): "cũ"})
        info = store.STORE / "app-info" / "en-US.json"
        before = info.read_bytes()
        mtime = info.stat().st_mtime_ns
        code, out, _ = self._pv(make_run("PREPARE_FOR_SUBMISSION"))
        self.assertEqual(code, 0)
        self.assertEqual(info.read_bytes(), before)
        self.assertEqual(info.stat().st_mtime_ns, mtime)
        self.assertEqual(store.load(store.STORE, "1.2.3")[("version", "en-US", "whatsNew")], "x")
        self.assertEqual(store.load(store.STORE, "1.2.2")[("version", "en-US", "whatsNew")], "cũ")
        self.assertIn("en-US", out)
        for f in ("description", "keywords", "promotionalText"):
            self.assertIn(f, out)
        self.assertEqual(sorted(p.name for p in (store.STORE / "version" / "1.2.3").iterdir()), ["en-US.json"])

    def test_pull_version_keeps_pulled_vdir_name(self):
        pull = fake_pull(vdir="versions")
        store.write(store.STORE, "1.2.2", {("app-info", "en-US", "name"): "Thu App"})
        code, _, _ = self._pv(lambda a, **k: pull(a, **k))
        self.assertEqual(code, 0)
        self.assertTrue((store.STORE / "versions" / "1.2.3" / "en-US.json").is_file())
        self.assertFalse((store.STORE / "version" / "1.2.3").exists())


def applied_ledger(state: Path) -> bool:
    return (state / "applied.jsonl").exists()


def _help():
    parser = aso.build_parser()[0]
    print(parser.format_help())
    return 0


if __name__ == "__main__":
    unittest.main()
