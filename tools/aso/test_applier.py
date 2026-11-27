"""Test applier.apply + lệnh apply/restore của aso.py bằng pull/push/snapshot giả (offline, không spawn)."""
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
import _testenv  # noqa: E402,F401 — thư mục trạng thái + cấu hình giả
import applier  # noqa: E402
import asc_cli  # noqa: E402
import aso  # noqa: E402
import planner  # noqa: E402
import store  # noqa: E402

V = "1.0"
REMOTE = {
    ("app-info", "en-US", "name"): "Thu App",
    ("app-info", "en-US", "subtitle"): "Quick notes",
    ("app-info", "ja", "name"): "Thu App JP",
    ("version", "en-US", "promotionalText"): "old promo",
    ("version", "en-US", "description"): "old desc",
    ("version", "ja", "description"): "ja desc",
}


class Harness:
    """Pull/push/snapshot/editable giả; ghi thứ tự gọi và nội dung thư mục push."""

    def __init__(self, tmp: Path, pulls, *, editable=True, vdir="version"):
        self.tmp = tmp
        self.vdir = vdir          # tên thư mục version mà `metadata pull` giả "đã ghi"
        self.pulls = list(pulls)
        self.calls = []
        self.pushed = []        # (dir, version, nội dung đọc lại bằng store.load)
        self.editable_value = editable
        self.snapshot_fp = None   # đặt ⇒ fingerprint.txt của snapshot giả lệch plan
        self.last_pull = None

    def pull(self, version):
        self.calls.append("pull")
        nxt = self.pulls.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        self.last_pull = dict(nxt)
        return nxt if self.vdir is None else store.Metadata(nxt, self.vdir)

    def push(self, d, version):
        self.calls.append("push")
        self.pushed.append((Path(d), version, store.load(Path(d), version)))
        self.pushed_files = sorted(str(f.relative_to(d)) for f in Path(d).rglob("*") if f.is_file())
        self.pushed_texts = {str(f.relative_to(d)): f.read_text() for f in Path(d).rglob("*") if f.is_file()}

    def take_snapshot(self, version):
        self.calls.append("snapshot")
        snap = self.tmp / "snaps" / "20261029T000000Z"
        snap.mkdir(parents=True, exist_ok=True)
        fp = self.snapshot_fp or planner.fingerprint(self.last_pull)
        (snap / "fingerprint.txt").write_text(fp + "\n")
        return snap

    def editable(self, version):
        self.calls.append("editable")
        return self.editable_value

    def kwargs(self):
        return dict(pull=self.pull, push=self.push, take_snapshot=self.take_snapshot, editable=self.editable)


def applied(remote, plan):
    out = dict(remote)
    for o in plan.ops:
        out[(o.scope, o.locale, o.field)] = o.new
    return out


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aso thu "))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = _testenv.isolate(self)

    def _plan(self, changes, *, remote=REMOTE):
        local = dict(remote)
        local.update(changes)
        plan = planner.make_plan(local, remote, V, editable=True, app_id=_testenv.FAKE_APP_ID)
        path = self.tmp / "plan.json"
        planner.save(plan, path)
        return plan, path

    def test_apply_release_plan_skips_metadata_path(self):
        import release
        rp = release.ReleasePlan("1.0", "5", "abc", "/x.ipa", "a" * 64,
                                 {"verify_release_clean": "ok"}, "fp",
                                 [release.Step("upload_build"), release.Step("attach_build")], "t")
        path = self.tmp / "rel.json"
        release.save(rp, path)
        h = Harness(self.tmp, [REMOTE])
        with mock.patch.object(release, "apply_release", return_value={"build": "5"}) as ar:
            res = applier.apply(path, rp.plan_id, run=lambda *a, **k: None, **h.kwargs())
        self.assertEqual(res, {"build": "5"})
        self.assertEqual(ar.call_count, 1)
        self.assertEqual(h.calls, [])  # không pull/snapshot/push metadata

    def test_apply_rejects_tampered_plan(self):
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        data = json.loads(path.read_text())
        data["ops"][0]["new"] = "chữ khác thứ đã duyệt"
        path.write_text(json.dumps(data))
        h = Harness(self.tmp, [REMOTE])
        with self.assertRaises(ValueError) as cm:
            applier.apply(path, plan.plan_id, **h.kwargs())
        self.assertIn("plan đã đổi", str(cm.exception))
        self.assertEqual(h.calls, [])
        self.assertFalse(applier.ledger_path().exists())

    def test_apply_stops_when_remote_changed(self):
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        changed = dict(REMOTE)
        changed[("version", "ja", "description")] = "ai đó sửa trên ASC"
        h = Harness(self.tmp, [changed])
        with self.assertRaises(RuntimeError) as cm:
            applier.apply(path, plan.plan_id, **h.kwargs())
        self.assertIn("ASC đã đổi", str(cm.exception))
        self.assertEqual(h.calls, ["pull"])

    def test_apply_snapshot_before_push(self):
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        h = Harness(self.tmp, [REMOTE, applied(REMOTE, plan)])
        res = applier.apply(path, plan.plan_id, **h.kwargs())
        self.assertEqual(h.calls, ["pull", "snapshot", "push", "pull"])
        self.assertEqual(res.plan_id, plan.plan_id)
        self.assertEqual(res.changed, 1)
        self.assertEqual(res.snapshot, self.tmp / "snaps" / "20261029T000000Z")
        line = json.loads(applier.ledger_path().read_text().strip())
        self.assertEqual(line["plan_id"], plan.plan_id)
        self.assertEqual(line["version"], V)
        self.assertEqual(line["ops"], 1)
        self.assertEqual(line["snapshot"], str(res.snapshot))
        self.assertEqual(line["status"], "ok")
        self.assertIn("time", line)
        # Thư mục push tạm phải được dọn.
        self.assertFalse(h.pushed[0][0].exists())

    def test_apply_pushes_only_planned_ops(self):
        plan, path = self._plan({("version", "en-US", "description"): "new desc"})
        # store/ giả có thêm thay đổi ngoài plan — applier không được đọc nó.
        fake_store = self.tmp / "store" / "metadata"
        extra = dict(REMOTE)
        extra[("version", "en-US", "description")] = "new desc"
        extra[("app-info", "en-US", "name")] = "Tên chưa duyệt"
        extra[("version", "de-DE", "description")] = "locale chưa duyệt"
        store.write(fake_store, V, extra)
        h = Harness(self.tmp, [REMOTE, applied(REMOTE, plan)])
        with mock.patch.object(store, "STORE", fake_store):
            applier.apply(path, plan.plan_id, **h.kwargs())
        _d, version, pushed = h.pushed[0]
        self.assertEqual(version, V)
        # Chỉ đúng field của plan khác ASC — không gì từ store/ giả (locale khác chỉ mang giá trị y hệt ASC).
        changed = {k: v for k, v in pushed.items() if REMOTE.get(k) != v}
        self.assertEqual(changed, {("version", "en-US", "description"): "new desc"})
        self.assertNotIn(("app-info", "en-US", "name"), pushed)
        self.assertNotIn(("version", "de-DE", "description"), pushed)

    def test_apply_verifies_after_push(self):
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        h = Harness(self.tmp, [REMOTE, REMOTE])  # sau push ASC vẫn giữ giá trị cũ
        with self.assertRaises(RuntimeError) as cm:
            applier.apply(path, plan.plan_id, **h.kwargs())
        msg = str(cm.exception)
        snap = str(self.tmp / "snaps" / "20261029T000000Z")
        self.assertIn(snap, msg)
        self.assertIn(applier.restore_hint(Path(snap)), msg)
        self.assertIn("aso.py restore --snapshot '", msg)   # đường dẫn có dấu cách ⇒ nháy
        self.assertEqual(json.loads(applier.ledger_path().read_text())["status"], "mismatch")

    def test_apply_verify_pull_error_is_recoverable(self):
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        h = Harness(self.tmp, [REMOTE, ConnectionError("mạng rớt")])
        with self.assertRaises(RuntimeError) as cm:
            applier.apply(path, plan.plan_id, **h.kwargs())
        snap = str(self.tmp / "snaps" / "20261029T000000Z")
        self.assertIn(snap, str(cm.exception))
        self.assertIn(applier.restore_hint(Path(snap)), str(cm.exception))
        self.assertEqual(h.calls, ["pull", "snapshot", "push", "pull"])
        line = json.loads(applier.ledger_path().read_text())
        self.assertEqual((line["status"], line["snapshot"]), ("unverified", snap))

    def test_apply_detects_collateral_change(self):
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        after = applied(REMOTE, plan)
        after[("version", "en-US", "description")] = ""          # field ngoài plan bị xoá trắng
        after[("version", "de-DE", "description")] = "thừa"      # khoá thừa
        h = Harness(self.tmp, [REMOTE, after])
        with self.assertRaises(RuntimeError) as cm:
            applier.apply(path, plan.plan_id, **h.kwargs())
        msg = str(cm.exception)
        self.assertIn("version en-US description", msg)
        self.assertIn("version de-DE description", msg)
        self.assertNotIn("promotionalText", msg)
        self.assertIn(str(self.tmp / "snaps" / "20261029T000000Z"), msg)
        self.assertEqual(json.loads(applier.ledger_path().read_text())["status"], "mismatch")

    def test_apply_push_failure_logged(self):
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        h = Harness(self.tmp, [REMOTE])

        def bad_push(d, v):
            h.calls.append("push")
            raise OSError("asc chết giữa chừng")
        kw = h.kwargs()
        kw["push"] = bad_push
        with self.assertRaises(RuntimeError) as cm:
            applier.apply(path, plan.plan_id, **kw)
        self.assertIn("restore --snapshot", str(cm.exception))
        self.assertEqual(json.loads(applier.ledger_path().read_text())["status"], "push_failed")

    def _break_ledger(self):
        """State dir là một FILE ⇒ mọi lần ghi ledger lỗi OSError."""
        bad = self.tmp / "state-is-a-file"
        bad.write_text("x")
        p = mock.patch.dict("os.environ", {"IOS_APP_FACTORY_STATE": str(bad)})
        p.start()
        self.addCleanup(p.stop)

    def test_ledger_failure_keeps_original_recovery_error(self):
        self._break_ledger()
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        cases = {
            "push_failed": [REMOTE],
            "unverified": [REMOTE, ConnectionError("mạng rớt")],
            "mismatch": [REMOTE, REMOTE],
        }
        for status, pulls in cases.items():
            h = Harness(self.tmp, pulls)
            kw = h.kwargs()
            if status == "push_failed":
                def bad_push(d, v):
                    raise OSError("asc chết giữa chừng")
                kw["push"] = bad_push
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(RuntimeError) as cm:
                applier.apply(path, plan.plan_id, **kw)
            msg = str(cm.exception)
            self.assertIn("restore --snapshot", msg, status)
            self.assertIn(str(self.tmp / "snaps" / "20261029T000000Z"), msg, status)
            self.assertIn("ledger", err.getvalue(), status)
            self.assertIn(status, err.getvalue())

    def test_ledger_failure_on_ok_still_succeeds(self):
        self._break_ledger()
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        h = Harness(self.tmp, [REMOTE, applied(REMOTE, plan)])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            res = applier.apply(path, plan.plan_id, **h.kwargs())
        self.assertEqual(res.changed, 1)
        self.assertIn("CẢNH BÁO", err.getvalue())
        self.assertIn("ledger", err.getvalue())

    def test_apply_stops_when_snapshot_fingerprint_differs(self):
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        h = Harness(self.tmp, [REMOTE])
        h.snapshot_fp = "0" * 64
        with self.assertRaises(RuntimeError) as cm:
            applier.apply(path, plan.plan_id, **h.kwargs())
        self.assertIn("ASC đổi trong lúc chụp snapshot", str(cm.exception))
        self.assertEqual(h.calls, ["pull", "snapshot"])
        self.assertFalse(applier.ledger_path().exists())

    def test_apply_rechecks_editable_for_non_promo_ops(self):
        plan, path = self._plan({("version", "en-US", "description"): "new desc"})
        h = Harness(self.tmp, [REMOTE, applied(REMOTE, plan)], editable=False)
        with self.assertRaises(RuntimeError):
            applier.apply(path, plan.plan_id, **h.kwargs())
        self.assertEqual(h.calls, ["pull", "editable"])
        # Chỉ promotionalText ⇒ không cần version sửa được.
        plan2, path2 = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        h2 = Harness(self.tmp, [REMOTE, applied(REMOTE, plan2)], editable=False)
        applier.apply(path2, plan2.plan_id, **h2.kwargs())
        self.assertNotIn("editable", h2.calls)
        self.assertIn("push", h2.calls)

    def test_apply_push_dir_has_only_op_fields(self):
        # asc PATCH mọi field có trong file locale; version đang bán từ chối field khác promotionalText
        # (gặp thật 2026-10-29) ⇒ thư mục push chỉ chứa đúng field plan đổi; field vắng = giữ nguyên trên ASC.
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        h = Harness(self.tmp, [REMOTE, applied(REMOTE, plan)])
        applier.apply(path, plan.plan_id, **h.kwargs())
        d, _v, pushed = h.pushed[0]
        # Locale có op: chỉ field của op. Thư mục scope có mặt ⇒ asc quản MỌI locale của scope (locale vắng = xoá,
        # `{}` bị từ chối — cả hai gặp thật) ⇒ locale không op mang đúng một field y hệt ASC (asc không PATCH vì
        # không khác). Scope không op (app-info): bỏ hẳn.
        self.assertEqual(pushed, {("version", "en-US", "promotionalText"): "new promo",
                                  ("version", "ja", "description"): "ja desc"})
        self.assertEqual(h.pushed_files, [f"version/{V}/en-US.json", f"version/{V}/ja.json"])
        for k, v in pushed.items():
            if k != ("version", "en-US", "promotionalText"):
                self.assertEqual(v, REMOTE[k], k)

    def test_apply_push_dir_keeps_pulled_version_dirname(self):
        for vdir in ("version", "versions"):
            plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
            h = Harness(self.tmp, [REMOTE, applied(REMOTE, plan)], vdir=vdir)
            applier.apply(path, plan.plan_id, **h.kwargs())
            self.assertEqual(h.pushed_files, [f"{vdir}/{V}/en-US.json", f"{vdir}/{V}/ja.json"], vdir)

    def test_apply_refuses_pull_without_vdir(self):
        plan, path = self._plan({("version", "en-US", "promotionalText"): "new promo"})
        h = Harness(self.tmp, [REMOTE], vdir=None)    # pull trả dict trơn: không biết bố cục
        with self.assertRaises(RuntimeError):
            applier.apply(path, plan.plan_id, **h.kwargs())
        self.assertNotIn("snapshot", h.calls)
        self.assertNotIn("push", h.calls)

    def test_apply_rejects_empty_plan(self):
        plan, path = self._plan({})
        h = Harness(self.tmp, [REMOTE])
        with self.assertRaises(ValueError):
            applier.apply(path, plan.plan_id, **h.kwargs())
        self.assertNotIn("push", h.calls)

    def test_apply_rejects_handmade_wipe_op(self):
        # Plan viết tay (make_plan không bao giờ ra op này) xoá trắng field ⇒ dừng trước snapshot/push.
        key = ("version", "en-US", "description")
        plan = planner.Plan(V, planner.fingerprint(REMOTE),
                            [planner.Op("update", *key, REMOTE[key], "  ")], "x", app_id=_testenv.FAKE_APP_ID)
        path = self.tmp / "wipe.json"
        planner.save(plan, path)
        h = Harness(self.tmp, [REMOTE])
        with self.assertRaises(RuntimeError) as cm:
            applier.apply(path, plan.plan_id, **h.kwargs())
        self.assertIn("xoá nội dung field bị cấm", str(cm.exception))
        self.assertEqual(h.calls, ["pull", "editable"])

    def test_apply_tu_choi_plan_cua_app_khac_hoac_khong_ghi_app(self):
        # Plan mang App Store id của app khác (hoặc không ghi) ⇒ dừng TRƯỚC mọi lệnh ASC, kể cả khi ASC trùng vân tay.
        key = ("version", "en-US", "promotionalText")
        for app_id in ("98765" "43210", ""):
            with self.subTest(app_id=app_id):
                plan = planner.make_plan({**REMOTE, key: "new promo"}, REMOTE, V, editable=True, app_id=app_id)
                path = self.tmp / "khac.json"
                planner.save(plan, path)
                h = Harness(self.tmp, [REMOTE])
                with self.assertRaises(ValueError) as cm:
                    applier.apply(path, plan.plan_id, **h.kwargs())
                self.assertIn("app hiện tại là " + _testenv.FAKE_APP_ID, str(cm.exception))
                self.assertEqual(h.calls, [])

    def test_restore_hint_quotes_space_path(self):
        snap = Path("/Users/x/Library/Application Support/app/aso/snapshots/20261029T000000Z")
        self.assertEqual(applier.restore_hint(snap),
                         f"python3 tools/aso/aso.py restore --snapshot '{snap}'")

    def test_push_argv_is_exact(self):
        calls = []
        push = applier.make_push(lambda args, **kw: calls.append((args, kw)))
        push(Path("/x/y"), "1.2.3")
        self.assertEqual(calls, [(["metadata", "push", "--app", _testenv.FAKE_APP_ID, "--version", "1.2.3",
                                   "--dir", "/x/y"], {"write": True})])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aso thu "))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = _testenv.isolate(self)
        p = mock.patch.object(store, "STORE", self.tmp / "repo" / "store" / "metadata")
        p.start()
        self.addCleanup(p.stop)

    def _call(self, fn, argv, run):
        args = aso.build_parser()[0].parse_args(argv)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = fn(args, run=run)
        return code, out.getvalue(), err.getvalue()

    def test_cli_apply_rejects_extra_options(self):
        parser = aso.build_parser()[0]
        args = parser.parse_args(["apply", "--plan", "p.json", "--expect", "abcd1234"])
        self.assertEqual((args.plan, args.expect), ("p.json", "abcd1234"))
        for extra in (["--version", "1.0"], ["--force"], ["--dir", "x"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser.parse_args(["apply", "--plan", "p.json", "--expect", "abcd1234", *extra])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["apply", "--plan", "p.json"])

    def _remote_run(self, remote_values, state="PREPARE_FOR_SUBMISSION"):
        calls = []

        def run(args, **kw):
            calls.append((list(args), kw))
            if args[:2] == ["versions", "view"]:
                return {"data": {"attributes": {"appVersionState": state}}}
            if args[:2] == ["metadata", "pull"]:
                store.write(Path(args[args.index("--dir") + 1]), args[args.index("--version") + 1],
                            remote_values)
                return None
            raise AssertionError(args)
        return run, calls

    def test_restore_plans_back_to_snapshot(self):
        key = ("version", "en-US", "promotionalText")
        snap = self.tmp / "snap"
        snap_values = dict(REMOTE)
        snap_values[key] = "A"
        store.write(snap / "metadata", V, snap_values)
        now = dict(REMOTE)
        now[key] = "B"
        run, calls = self._remote_run(now)
        code, out, err = self._call(aso.cmd_restore, ["restore", "--snapshot", str(snap)], run)
        self.assertEqual(code, 0, err)
        self.assertIn("Plan: ", out)
        plan = planner.load_plan(Path(out.strip().splitlines()[-1].split("Plan: ", 1)[1]))
        self.assertEqual(plan.version, V)
        self.assertEqual([(o.scope, o.locale, o.field, o.old, o.new) for o in plan.ops],
                         [(*key, "B", "A")])
        self.assertTrue(all(not kw.get("write") for _a, kw in calls))
        self.assertFalse(any(a[:2] == ["metadata", "push"] for a, _kw in calls))

    def test_cli_apply_end_to_end_with_fake_run(self):
        import snapshot
        key = ("version", "en-US", "promotionalText")
        state = {"remote": dict(REMOTE)}
        calls = []

        def run(args, **kw):
            calls.append((list(args), kw))
            if args[:2] == ["metadata", "pull"]:
                store.write(Path(args[args.index("--dir") + 1]), V, state["remote"])
                return None
            if args[:2] == ["metadata", "push"]:
                # Như asc thật: field có trong file thì ghi, field vắng giữ nguyên.
                state["remote"] = {**state["remote"], **store.load(Path(args[args.index("--dir") + 1]), V)}
                return None
            raise AssertionError(args)

        local = dict(REMOTE)
        local[key] = "new promo"
        plan = planner.make_plan(local, REMOTE, V, editable=True, app_id=_testenv.FAKE_APP_ID)
        path = self.tmp / "plan.json"
        planner.save(plan, path)
        with mock.patch.dict("os.environ", {"IOS_APP_FACTORY_STATE": str(self.tmp / "state1")}):
            code, out, err = self._call(aso.cmd_apply, ["apply", "--plan", str(path), "--expect", plan.plan_id],
                                        run)
        self.assertEqual(code, 0, err)
        self.assertEqual(state["remote"][key], "new promo")
        writes = [(a, kw) for a, kw in calls if kw.get("write")]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0][:2], ["metadata", "push"])
        self.assertIn(aso.asc_link(), out)
        self.assertIn("tool không nộp", out)
        # Sai mã ⇒ exit 2, không ghi thêm.
        with mock.patch.dict("os.environ", {"IOS_APP_FACTORY_STATE": str(self.tmp / "state2")}):
            code, _out, err = self._call(aso.cmd_apply, ["apply", "--plan", str(path), "--expect", "deadbeef"], run)
        self.assertEqual(code, 2)
        self.assertIn("plan đã đổi", err)
        self.assertEqual(len([1 for _a, kw in calls if kw.get("write")]), 1)

    def test_restore_ambiguous_version_exit_2(self):
        snap = self.tmp / "snap"
        store.write(snap / "metadata", "1.0", REMOTE)
        store.write(snap / "metadata", "2.0", REMOTE)
        run, calls = self._remote_run(REMOTE)
        code, _out, err = self._call(aso.cmd_restore, ["restore", "--snapshot", str(snap)], run)
        self.assertEqual(code, 2)
        self.assertEqual(calls, [])

    def test_restore_new_remote_locale_listed_not_deleted(self):
        key = ("version", "en-US", "promotionalText")
        snap = self.tmp / "snap"
        snap_values = dict(REMOTE)
        snap_values[key] = "A"
        store.write(snap / "metadata", V, snap_values)
        now = dict(REMOTE)
        now[key] = "B"
        now[("version", "de-DE", "description")] = "neu"   # locale thêm trên ASC sau snapshot
        run, _calls = self._remote_run(now)
        code, out, err = self._call(aso.cmd_restore, ["restore", "--snapshot", str(snap)], run)
        self.assertEqual(code, 0, err)
        head, _sep, rest = out.partition("Không khôi phục được (cấm xoá) — tự xử lý trên ASC:")
        self.assertEqual(head, "")
        self.assertIn("version de-DE description", rest.splitlines()[1])
        self.assertNotIn("store/", out + err)
        plan = planner.load_plan(Path(out.strip().splitlines()[-1].split("Plan: ", 1)[1]))
        self.assertEqual([(o.scope, o.locale, o.field, o.old, o.new) for o in plan.ops],
                         [(*key, "B", "A")])

    def test_restore_blank_snapshot_value_listed_not_wiped(self):
        key = ("version", "en-US", "promotionalText")
        desc = ("version", "en-US", "description")
        snap = self.tmp / "snap"
        snap_values = dict(REMOTE)
        snap_values[key] = ""          # snapshot lúc promo còn rỗng
        snap_values[desc] = "A"
        store.write(snap / "metadata", V, snap_values)
        now = dict(REMOTE)
        now[key] = "promo mới"
        now[desc] = "B"
        run, _calls = self._remote_run(now)
        code, out, err = self._call(aso.cmd_restore, ["restore", "--snapshot", str(snap)], run)
        self.assertEqual(code, 0, err)
        head, _sep, rest = out.partition("Không khôi phục được (cấm xoá) — tự xử lý trên ASC:")
        self.assertEqual(head, "")
        self.assertIn("version en-US promotionalText", rest.split("\n\n", 1)[0])
        plan = planner.load_plan(Path(out.strip().splitlines()[-1].split("Plan: ", 1)[1]))
        self.assertEqual([(o.field, o.old, o.new) for o in plan.ops], [("description", "B", "A")])

    def test_restore_live_version_untouched_lint_issue_is_warning(self):
        key = ("version", "en-US", "promotionalText")
        kw = ("version", "en-US", "keywords")
        snap = self.tmp / "snap"
        snap_values = dict(REMOTE)
        snap_values[key] = "A"
        snap_values[kw] = "note, memo"
        store.write(snap / "metadata", V, snap_values)
        now = dict(snap_values)
        now[key] = "B"
        run, _calls = self._remote_run(now, state="READY_FOR_SALE")
        code, out, err = self._call(aso.cmd_restore, ["restore", "--snapshot", str(snap)], run)
        self.assertEqual(code, 0, err)
        self.assertIn("## Cảnh báo (field không đổi)", out)


if __name__ == "__main__":
    unittest.main()
