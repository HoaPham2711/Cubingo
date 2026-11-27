"""Test cho release.py — plan release, mã ổn định, roundtrip qua planner.load_plan, render."""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401
import asc_cli  # noqa: E402
import confirm  # noqa: E402
import planner  # noqa: E402
import release  # noqa: E402


def _fake_run(version_attrs=None, builds=(), version="1.12.0"):
    calls = []

    def run(args, **kw):
        calls.append(args)
        if args[:2] == ["versions", "view"]:
            return {"data": {"attributes": {}, "relationships": {"build": {"data": None}}}}
        if args[0] == "versions":
            if version_attrs is None:
                return {"data": []}
            items = version_attrs if isinstance(version_attrs, list) else [version_attrs]
            return {"data": [{"attributes": {"versionString": version, **a}} for a in items]}
        return {"data": [{"attributes": {"version": b}} for b in builds]}
    run.calls = calls
    return run


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="aso thu "))
        self.ipa = self.d / "a.ipa"
        self.ipa.write_bytes(b"ipa-bytes")
        self.sha = hashlib.sha256(b"ipa-bytes").hexdigest()
        self.bj = self.d / "build.json"
        self._write()

    def _write(self, **over):
        b = {"version": "1.12.0", "build": "42", "commit": "abc1234", "ipa": str(self.ipa),
             "ipa_sha256": self.sha,
             "gates": {"verify_release_clean": "ok", "verify_catalog": "ok"}, "created": "x"}
        b.update(over)
        self.bj.write_text(json.dumps(b))

    def ops(self, **kw):
        return [o.action for o in release.make_release_plan(self.bj, **kw).ops]

    def test_release_plan_new_version(self):
        self.assertEqual(self.ops(run=_fake_run()), ["upload_build", "create_version", "attach_build"])

    def test_release_plan_skips_create_when_version_exists(self):
        run = _fake_run({"appVersionState": "PREPARE_FOR_SUBMISSION"})
        self.assertEqual(self.ops(run=run), ["upload_build", "attach_build"])
        for c in run.calls:
            self.assertIn(c[:2], (["versions", "list"], ["builds", "list"],
                                  ["versions", "view"]))  # chỉ lệnh đọc

    def test_release_plan_rejects_non_editable_version(self):
        for attrs in ({"appVersionState": "READY_FOR_DISTRIBUTION"}, {"appStoreState": "READY_FOR_SALE"}):
            with self.assertRaises(ValueError):
                release.make_release_plan(self.bj, run=_fake_run(attrs))

    def test_release_plan_rejects_existing_build_not_valid(self):
        # build đã có nhưng không có processingState VALID ⇒ không plan tiếp
        with self.assertRaises(ValueError) as cm:
            release.make_release_plan(self.bj, run=_fake_run(None, builds=["41", "42"]))
        self.assertIn("42", str(cm.exception))

    def test_release_plan_rejects_ipa_sha_mismatch(self):
        self._write(ipa_sha256="0" * 64)
        with self.assertRaises(ValueError):
            release.make_release_plan(self.bj, run=_fake_run())

    def test_release_plan_rejects_failed_gate(self):
        self._write(gates={"verify_release_clean": "ok", "verify_catalog": "fail"})
        with self.assertRaises(ValueError):
            release.make_release_plan(self.bj, run=_fake_run())

    def test_release_plan_id_stable_and_roundtrip(self):
        p = release.make_release_plan(self.bj, run=_fake_run())
        path = self.d / "plan.json"
        release.save(p, path)
        data = json.loads(path.read_text())
        self.assertEqual(data["kind"], "release")
        self.assertEqual(len(data["ops"]), 3)
        q = planner.load_plan(path)
        self.assertIsInstance(q, release.ReleasePlan)
        self.assertEqual(q.plan_id, p.plan_id)
        self._write(build="43")
        p2 = release.make_release_plan(self.bj, run=_fake_run())
        self.assertNotEqual(p.plan_id, p2.plan_id)
        self._write(commit="zzz")
        self.assertNotEqual(p.plan_id, release.make_release_plan(self.bj, run=_fake_run()).plan_id)

    def _saved(self):
        p = release.make_release_plan(self.bj, run=_fake_run())
        path = self.d / "plan.json"
        release.save(p, path)
        return p, path, json.loads(path.read_text())

    def _load_bad(self, mutate):
        _, path, data = self._saved()
        mutate(data)
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            planner.load_plan(path)

    def test_picks_matching_version_string(self):
        run = _fake_run([{"versionString": "1.11.0", "appVersionState": "PREPARE_FOR_SUBMISSION"},
                         {"appVersionState": "READY_FOR_SALE"}])
        with self.assertRaises(ValueError):  # 1.12.0 đang bán, 1.11.0 sửa được không được lẫn
            release.make_release_plan(self.bj, run=run)

    def test_two_matches_rejected(self):
        run = _fake_run([{"appVersionState": "PREPARE_FOR_SUBMISSION"}, {"appVersionState": "REJECTED"}])
        with self.assertRaises(ValueError):
            release.make_release_plan(self.bj, run=run)

    def test_other_version_only_means_absent(self):
        run = _fake_run([{"versionString": "1.11.0", "appVersionState": "READY_FOR_SALE"}])
        self.assertEqual(self.ops(run=run), ["upload_build", "create_version", "attach_build"])

    def test_matching_item_without_state_rejected(self):
        with self.assertRaises(ValueError) as cm:
            release.make_release_plan(self.bj, run=_fake_run({}))
        self.assertIn("không đọc được trạng thái", str(cm.exception))

    def test_unknown_kind_rejected(self):
        self._load_bad(lambda d: d.update(kind="relase"))

    def test_bad_action_order_gate_keys_rejected(self):
        self._load_bad(lambda d: d["ops"].__setitem__(0, {"action": "submit_review"}))
        self._load_bad(lambda d: d["ops"].reverse())
        self._load_bad(lambda d: d["gates"].update(verify_catalog="fail"))
        self._load_bad(lambda d: d.update(extra=1))
        self._load_bad(lambda d: d["ops"][0].update(x=1))
        self._load_bad(lambda d: d.update(gates={}))

    def test_tamper_changes_plan_id(self):
        muts = {
            "version": lambda d: d.update(version="9.9"), "build": lambda d: d.update(build="99"),
            "commit": lambda d: d.update(commit="zz"), "ipa": lambda d: d.update(ipa="/x.ipa"),
            "ipa_sha256": lambda d: d.update(ipa_sha256="1" * 64),
            "gates": lambda d: d["gates"].update(extra_gate="ok"),
            "remote_fingerprint": lambda d: d.update(remote_fingerprint="0" * 64),
            "ops": lambda d: d["ops"].pop(1),
        }
        for name, m in muts.items():
            with self.subTest(name):
                p, path, data = self._saved()
                m(data)
                path.write_text(json.dumps(data))
                self.assertNotEqual(planner.load_plan(path).plan_id, p.plan_id)

    def test_missing_or_empty_gates_message(self):
        for over in ({"gates": {}}, {"gates": None}):
            self._write(**over)
            with self.assertRaises(ValueError) as cm:
                release.make_release_plan(self.bj, run=_fake_run())
            self.assertIn("build.json không có gates", str(cm.exception))

    def test_load_plan_without_kind_is_metadata_plan(self):
        path = self.d / "m.json"
        planner.save(planner.Plan("1.0", "fp", [], "t"), path)
        self.assertIsInstance(planner.load_plan(path), planner.Plan)

    def test_render_release_plan(self):
        p = release.make_release_plan(self.bj, run=_fake_run())
        text = confirm.render(p)
        for s in ("1.12.0", "42", "abc1234", "Không xoá gì", "verify_release_clean", "verify_catalog"):
            self.assertIn(s, text)
        for a in p.ops:
            self.assertIn(release.STEP_LABELS[a.action], text)
        self.assertTrue(text.rstrip().endswith(f"Mã plan: {p.plan_id}"))


class FakeAsc:
    """asc giả cho apply_release: ghi (argv, write); trạng thái ASC đổi theo lệnh ghi như thật."""

    def __init__(self, *, version_state=None, wait_state="VALID", view_build=None,
                 view_state="PREPARE_FOR_SUBMISSION", fail=None, version="1.12.0",
                 existing_build=None, attached=None):
        self.calls = []
        self.version = version
        self.version_state = version_state     # None = chưa có version trên ASC
        # build đã có trên ASC: {số: processingState}
        self.builds = {} if existing_build is None else {"42": existing_build}
        self.attached = attached               # số build đang gắn vào version (None = chưa gắn)
        self.wait_state = wait_state
        self.view_build = view_build
        self.view_state = view_state
        self.fail = fail                       # tiền tố argv (2 từ) sẽ ném lỗi

    def __call__(self, args, *, write=False):
        args = list(args)
        self.calls.append((args, write))
        if self.fail and tuple(args[:2]) == self.fail:
            raise RuntimeError(f"giả lỗi {' '.join(self.fail)}")
        head = tuple(args[:2])
        if head == ("versions", "list"):
            if self.version_state is None:
                return {"data": []}
            return {"data": [{"attributes": {"versionString": self.version,
                                             "appVersionState": self.version_state}}]}
        if head == ("builds", "list"):
            return {"data": [{"attributes": {"version": b, **({"processingState": ps} if ps else {})}}
                             for b, ps in self.builds.items()]}
        if head == ("builds", "upload"):
            self.builds["42"] = "PROCESSING"
            return {"data": {"id": "upload-1"}}
        if head == ("builds", "wait"):
            attrs = {} if self.wait_state is None else {"processingState": self.wait_state}
            return {"data": {"id": "build-1", "attributes": {"version": "42", **attrs}}}
        if head == ("versions", "create"):
            self.version_state = "PREPARE_FOR_SUBMISSION"
            return {"data": {"id": "ver-1"}}
        if head == ("versions", "attach-build"):
            self.attached = "42"
            return {"data": {"id": "ver-1"}}
        if head == ("versions", "view"):
            shown = self.view_build if (self.view_build and self.attached) else self.attached
            state = self.view_state if self.attached and any(w for a, w in self.calls) else self.version_state
            rel = None if shown is None else {"type": "builds", "id": "build-1"}
            inc = [] if shown is None else [{"type": "builds", "id": "build-1", "attributes": {"version": shown}}]
            return {"data": {"id": "ver-1", "type": "appStoreVersions",
                             "attributes": {"versionString": self.version, "appVersionState": state},
                             "relationships": {"build": {"data": rel}}},
                    "included": inc}
        raise AssertionError(args)

    def writes(self):
        return [a[:2] for a, w in self.calls if w]


class ApplyReleaseTests(unittest.TestCase):
    def setUp(self):
        self.state = _testenv.isolate(self)
        self.d = Path(tempfile.mkdtemp(prefix="aso thu "))
        self.ipa = self.d / "a.ipa"
        self.ipa.write_bytes(b"ipa-bytes")
        self.bj = self.d / "build.json"
        self.bj.write_text(json.dumps({
            "version": "1.12.0", "build": "42", "commit": "abc1234", "ipa": str(self.ipa),
            "ipa_sha256": hashlib.sha256(b"ipa-bytes").hexdigest(),
            "gates": {"verify_release_clean": "ok", "verify_catalog": "ok"}, "created": "x"}))

    def _plan(self, asc):
        return release.make_release_plan(self.bj, run=asc)

    def _ledger(self):
        import applier
        p = applier.ledger_path()
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def test_apply_release_full_order(self):
        asc = FakeAsc()
        plan = self._plan(asc)
        asc.calls.clear()
        res = release.apply_release(plan, run=asc)
        A = _testenv.FAKE_APP_ID
        self.assertEqual([c for c in asc.calls if c[0][:2] not in (["versions", "list"], ["builds", "list"])], [
            (["builds", "upload", "--app", A, "--ipa", str(self.ipa)], True),
            (["builds", "wait", "--app", A, "--build-number", "42", "--version", "1.12.0", "--platform", "IOS",
              "--timeout", "45m"], False),
            (["versions", "create", "--app", A, "--version", "1.12.0", "--platform", "IOS",
              "--release-type", "MANUAL"], True),
            (["versions", "attach-build", "--app", A, "--version", "1.12.0", "--build-number", "42"], True),
            (["versions", "view", "--app", A, "--version", "1.12.0", "--include", "build"], False),
        ])
        # remote_state (chỉ đọc) chạy TRƯỚC mọi lệnh ghi.
        self.assertEqual([c[0][:2] for c in asc.calls[:2]], [["versions", "list"], ["builds", "list"]])
        self.assertFalse(any(c[1] for c in asc.calls[:2]))
        for args, _w in asc.calls:
            self.assertNotIn("--confirm", args)
            self.assertNotIn("submit", " ".join(args))
            asc_cli.policy.check_asc_args(args, write=_w)  # mọi argv phải qua allowlist
        self.assertEqual((res["build"], res["version"], res["state"]), ("42", "1.12.0", "PREPARE_FOR_SUBMISSION"))
        led = self._ledger()
        self.assertEqual(len(led), 1)
        self.assertEqual({k: led[0][k] for k in ("plan_id", "kind", "version", "build", "status")},
                         {"plan_id": plan.plan_id, "kind": "release", "version": "1.12.0", "build": "42",
                          "status": "ok"})

    def test_apply_release_existing_version_skips_create(self):
        asc = FakeAsc(version_state="PREPARE_FOR_SUBMISSION")
        plan = self._plan(asc)
        release.apply_release(plan, run=asc)
        self.assertEqual(asc.writes(), [["builds", "upload"], ["versions", "attach-build"]])

    def test_apply_release_rejects_changed_ipa(self):
        asc = FakeAsc()
        plan = self._plan(asc)
        self.ipa.write_bytes(b"ipa-byteZ")
        with self.assertRaises(RuntimeError):
            release.apply_release(plan, run=asc)
        self.assertEqual(asc.writes(), [])

    def test_apply_release_stops_on_invalid_build(self):
        for ws in ("INVALID", "PROCESSING", None):
            with self.subTest(ws):
                asc = FakeAsc(wait_state=ws)
                plan = self._plan(asc)
                with self.assertRaises(RuntimeError) as cm:
                    release.apply_release(plan, run=asc)
                self.assertIn(str(ws) if ws else "processingState", str(cm.exception))
                self.assertEqual(asc.writes(), [["builds", "upload"]])
                led = self._ledger()[-1]
                self.assertEqual(led["status"], "build_invalid")
                self.assertEqual(led["completed"], ["upload_build"])
                self.assertIn("upload_build", str(cm.exception).split("Chưa làm")[0])

    def test_apply_release_stops_when_remote_changed(self):
        asc = FakeAsc()
        plan = self._plan(asc)
        asc.version_state = "PREPARE_FOR_SUBMISSION"   # version xuất hiện giữa plan và apply
        with self.assertRaises(RuntimeError) as cm:
            release.apply_release(plan, run=asc)
        self.assertIn("ASC đã đổi", str(cm.exception))
        self.assertEqual(asc.writes(), [])

    def test_apply_release_verify_mismatch(self):
        for over in ({"view_build": "41"}, {"view_state": "WAITING_FOR_REVIEW"}):
            with self.subTest(over):
                asc = FakeAsc(**over)
                plan = self._plan(asc)
                with self.assertRaises(RuntimeError):
                    release.apply_release(plan, run=asc)
                self.assertEqual(self._ledger()[-1]["status"], "verify_failed")

    def test_apply_release_write_failure_statuses(self):
        cases = {("builds", "upload"): ("upload_failed", []),
                 ("builds", "wait"): ("wait_failed", ["upload_build"]),
                 ("versions", "create"): ("create_failed", ["upload_build"]),
                 ("versions", "attach-build"): ("attach_failed", ["upload_build", "create_version"])}
        for prefix, (status, done) in cases.items():
            with self.subTest(prefix):
                asc = FakeAsc(fail=prefix)
                plan = self._plan(asc)
                with self.assertRaises(RuntimeError) as cm:
                    release.apply_release(plan, run=asc)
                led = self._ledger()[-1]
                self.assertEqual(led["status"], status)
                self.assertEqual(led["completed"], done)
                self.assertIn("release-plan", str(cm.exception))
                self.assertIsNotNone(cm.exception.__cause__)
                # Không lệnh ghi nào sau bước hỏng.
                last_write = ["builds", "upload"] if prefix == ("builds", "wait") else list(prefix)
                self.assertEqual(asc.writes()[-1], last_write)
                if prefix == ("builds", "upload"):
                    self.assertIn("CÓ THỂ", str(cm.exception))

    # ---- Ruling 5: build đã có ⇒ plan tiếp phần còn lại (resume) ----

    def test_resume_plan_shapes(self):
        cases = [
            (dict(existing_build="VALID"), ["create_version", "attach_build"]),
            (dict(existing_build="VALID", version_state="PREPARE_FOR_SUBMISSION"), ["attach_build"]),
        ]
        for kw, ops in cases:
            with self.subTest(kw):
                p = release.make_release_plan(self.bj, run=FakeAsc(**kw))
                self.assertEqual([o.action for o in p.ops], ops)
                self.assertTrue(p.resume)
                self.assertEqual(p.ipa_sha256, hashlib.sha256(b"ipa-bytes").hexdigest())
        fresh = release.make_release_plan(self.bj, run=FakeAsc())
        self.assertFalse(fresh.resume)

    def test_resume_plan_rejections(self):
        cases = [
            (dict(existing_build="PROCESSING"), "PROCESSING"),
            (dict(existing_build="VALID", version_state="PREPARE_FOR_SUBMISSION", attached="42"),
             "không còn gì để làm"),
            (dict(existing_build="VALID", version_state="PREPARE_FOR_SUBMISSION", attached="41"), "41"),
            (dict(existing_build="VALID", version_state="READY_FOR_SALE"), "READY_FOR_SALE"),
        ]
        for kw, msg in cases:
            with self.subTest(kw):
                with self.assertRaises(ValueError) as cm:
                    release.make_release_plan(self.bj, run=FakeAsc(**kw))
                self.assertIn(msg, str(cm.exception))

    def test_resume_flag_in_hash_and_orders_tied_to_resume(self):
        p = release.make_release_plan(self.bj, run=FakeAsc(existing_build="VALID"))
        path = self.d / "r.json"
        release.save(p, path)
        data = json.loads(path.read_text())
        self.assertIs(data["resume"], True)
        self.assertEqual(planner.load_plan(path).plan_id, p.plan_id)
        q = release.ReleasePlan(**{**p.__dict__, "resume": False})
        self.assertNotEqual(q.plan_id, p.plan_id)
        bad = [
            dict(resume=False),                                                 # [create, attach] cần resume
            dict(resume=True, ops=[{"action": "upload_build"}, {"action": "attach_build"}]),
            dict(resume="yes"),
        ]
        for over in bad:
            with self.subTest(over):
                path.write_text(json.dumps({**data, **over}))
                with self.assertRaises(ValueError):
                    planner.load_plan(path)

    def test_apply_resume_plan_no_upload_and_skips_ipa_sha(self):
        asc = FakeAsc(existing_build="VALID", version_state="PREPARE_FOR_SUBMISSION")
        plan = release.make_release_plan(self.bj, run=asc)
        self.ipa.write_bytes(b"khac")      # resume không upload ⇒ không kiểm .ipa
        res = release.apply_release(plan, run=asc)
        self.assertEqual(asc.writes(), [["versions", "attach-build"]])
        self.assertEqual(res["build"], "42")
        self.assertEqual(self._ledger()[-1]["status"], "ok")

    def test_apply_resume_rejects_if_attached_changed(self):
        asc = FakeAsc(existing_build="VALID", version_state="PREPARE_FOR_SUBMISSION")
        plan = release.make_release_plan(self.bj, run=asc)
        asc.attached = "41"                # ai đó gắn build khác giữa plan và apply
        with self.assertRaises(RuntimeError):
            release.apply_release(plan, run=asc)
        self.assertEqual(asc.writes(), [])

    def test_attached_build_parsing(self):
        two = {"data": {"attributes": {}, "relationships": {"build": {"data": {"type": "builds", "id": "b2"}}}},
               "included": [{"type": "builds", "id": "b1", "attributes": {"version": "41"}},
                            {"type": "builds", "id": "b2", "attributes": {"version": "42"}}]}
        self.assertEqual(release._attached_build(two), ("42", "b2"))
        null = {"data": {"attributes": {}, "relationships": {"build": {"data": None}}},
                "included": [{"type": "builds", "id": "b1", "attributes": {"version": "41"}}]}
        self.assertEqual(release._attached_build(null), (None, None))
        no_rel_two = {"data": {"attributes": {}}, "included": two["included"]}
        for bad in (no_rel_two, {"data": []}, None,
                    {"data": {"relationships": {"build": {"data": {"id": "zz"}}}}, "included": two["included"]}):
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    release._attached_build(bad)

    def test_non_resume_rejects_version_with_attached_build(self):
        asc = FakeAsc(version_state="PREPARE_FOR_SUBMISSION", attached="41")
        with self.assertRaises(ValueError) as cm:
            release.make_release_plan(self.bj, run=asc)
        self.assertIn("đang gắn build 41", str(cm.exception))
        self.assertIn("tool không thay build", str(cm.exception))
        self.assertEqual(asc.writes(), [])

    def test_apply_rejects_build_attached_after_plan(self):
        asc = FakeAsc(version_state="PREPARE_FOR_SUBMISSION")
        plan = release.make_release_plan(self.bj, run=asc)
        self.assertEqual([o.action for o in plan.ops], ["upload_build", "attach_build"])
        asc.attached = "41"                # build khác được gắn giữa plan và apply
        with self.assertRaises(RuntimeError) as cm:
            release.apply_release(plan, run=asc)
        self.assertIn("ASC đã đổi", str(cm.exception))
        self.assertEqual(asc.writes(), [])

    def test_attached_build_relationship_without_data_key_rejected(self):
        for view in ({"data": {"relationships": {"build": {}}}, "included": []},
                     {"data": {"relationships": {"build": {"links": {"self": "x"}}}}, "included": []},
                     {"data": {"relationships": {"build": None}}, "included": []}):
            with self.subTest(view):
                with self.assertRaises(ValueError):
                    release._attached_build(view)

    def test_render_resume_plan(self):
        p = release.make_release_plan(self.bj, run=FakeAsc(existing_build="VALID",
                                                             version_state="PREPARE_FOR_SUBMISSION"))
        text = confirm.render(p)
        self.assertIn("Tiếp tục bản dở: build 42 đã có trên ASC (không upload lại)", text)
        self.assertIn("1. Gắn build 42 (đã có trên ASC)", text)
        self.assertNotIn(release.STEP_LABELS["upload_build"], text)
        fresh = confirm.render(release.make_release_plan(self.bj, run=FakeAsc()))
        self.assertNotIn("Tiếp tục bản dở", fresh)
        self.assertIn(release.STEP_LABELS["attach_build"], fresh)

    # ---- vòng review cuối ----

    def test_builds_list_sees_all_processing_states(self):
        asc = FakeAsc()
        release.remote_state("1.12.0", "42", run=asc)
        bl = [a for a, _w in asc.calls if a[:2] == ["builds", "list"]]
        self.assertEqual(len(bl), 1)
        i = bl[0].index("--processing-state")
        self.assertEqual(bl[0][i + 1], "all")
        asc_cli.policy.check_asc_args(bl[0], write=False)
        # vẫn lọc số build trong code: build 41 FAILED không làm build 42 "đã có"
        asc = FakeAsc()
        asc.builds = {"41": "FAILED"}
        self.assertFalse(release.remote_state("1.12.0", "42", run=asc)["build_exists"])
        asc.builds = {"42": "FAILED"}
        st = release.remote_state("1.12.0", "42", run=asc)
        self.assertEqual((st["build_exists"], st["build_state"]), (True, "FAILED"))

    def test_resume_plan_without_ipa(self):
        self.ipa.unlink()
        p = release.make_release_plan(self.bj, run=FakeAsc(existing_build="VALID"))
        self.assertTrue(p.resume)
        self.assertEqual(p.ipa, str(self.ipa))
        self.assertEqual(p.ipa_sha256, hashlib.sha256(b"ipa-bytes").hexdigest())
        self.assertIn("không upload lại", confirm.render(p))
        with self.assertRaises(ValueError) as cm:
            release.make_release_plan(self.bj, run=FakeAsc())
        self.assertIn(".ipa", str(cm.exception))

    def test_render_shows_observed_asc_state(self):
        fresh = confirm.render(release.make_release_plan(self.bj, run=FakeAsc()))
        self.assertIn("version 1.12.0 chưa có — sẽ tạo (release type MANUAL: Apple duyệt xong bạn tự bấm "
                      "phát hành)", fresh)
        have = confirm.render(release.make_release_plan(self.bj, run=FakeAsc(version_state="REJECTED")))
        self.assertIn("version 1.12.0 đã có, REJECTED", have)
        self.assertNotIn("chưa có — sẽ tạo", have)
        res = confirm.render(release.make_release_plan(self.bj, run=FakeAsc(existing_build="VALID")))
        self.assertIn("build 42 trên ASC: VALID", res)
        self.assertNotIn("trên ASC: VALID", fresh)

    def test_observed_state_in_plan_id_and_roundtrip(self):
        p = release.make_release_plan(self.bj, run=FakeAsc(version_state="REJECTED"))
        path = self.d / "o.json"
        release.save(p, path)
        data = json.loads(path.read_text())
        self.assertEqual(data["observed"], {"version_state": "REJECTED", "build_state": None})
        self.assertEqual(planner.load_plan(path).plan_id, p.plan_id)
        for over in ({"observed": {"version_state": "PREPARE_FOR_SUBMISSION", "build_state": None}},):
            path.write_text(json.dumps({**data, **over}))
            self.assertNotEqual(planner.load_plan(path).plan_id, p.plan_id)
        for bad in ({"observed": None}, {"observed": {"version_state": 1, "build_state": None}},
                    {"observed": {"version_state": None}}, {"observed": {**data["observed"], "x": 1}}):
            with self.subTest(bad):
                path.write_text(json.dumps({**data, **bad}))
                with self.assertRaises(ValueError):
                    planner.load_plan(path)

    def test_other_editable_version_blocks_create(self):
        class Other(FakeAsc):
            other = ("1.11.0", "PREPARE_FOR_SUBMISSION")

            def __call__(self, args, *, write=False):
                if list(args[:2]) == ["versions", "list"]:
                    self.calls.append((list(args), write))
                    out = super().__call__(args, write=write)
                    self.calls.pop()
                    out["data"].append({"attributes": {"versionString": self.other[0], "platform": "IOS",
                                                       "appVersionState": self.other[1]}})
                    return out
                return super().__call__(args, write=write)
        for kw in ({}, {"existing_build": "VALID"}):
            with self.subTest(kw):
                asc = Other(**kw)
                with self.assertRaises(ValueError) as cm:
                    release.make_release_plan(self.bj, run=asc)
                self.assertIn("bản 1.11.0 đang ở PREPARE_FOR_SUBMISSION — ASC không cho tạo version mới",
                              str(cm.exception))
                self.assertEqual(asc.writes(), [])
        # version 1.12.0 đã có (không tạo) ⇒ bản khác đang sửa được không cản
        asc = Other(version_state="PREPARE_FOR_SUBMISSION")
        self.assertEqual([o.action for o in release.make_release_plan(self.bj, run=asc).ops],
                         ["upload_build", "attach_build"])
        # bản khác KHÔNG sửa được (đang bán) ⇒ không cản; bản khác nền tảng khác ⇒ không cản
        asc = Other()
        asc.other = ("1.11.0", "READY_FOR_SALE")
        self.assertIn("create_version", [o.action for o in release.make_release_plan(self.bj, run=asc).ops])
        # lệnh versions list xem mọi version IOS (không lọc --version) để thấy bản khác
        vl = [a for a, _w in asc.calls if a[:2] == ["versions", "list"]][0]
        self.assertNotIn("--version", vl)
        self.assertIn("IOS", vl)
        asc_cli.policy.check_asc_args(vl, write=False)

    def test_attached_build_relationships_not_dict_rejected(self):
        for rels in (["build"], "build", 1):
            with self.subTest(rels):
                with self.assertRaises(ValueError):
                    release._attached_build({"data": {"relationships": rels}, "included": []})

    def test_applier_dispatches_release_plan(self):
        import applier
        asc = FakeAsc()
        plan = self._plan(asc)
        path = self.d / "plan.json"
        release.save(plan, path)
        called = []

        def nope(*a, **k):
            called.append(a)
            raise AssertionError("không được gọi đường metadata")
        res = applier.apply(path, plan.plan_id, pull=nope, push=nope, take_snapshot=nope, editable=nope,
                            run=asc)
        self.assertEqual(called, [])
        self.assertEqual(res["build"], "42")
        with self.assertRaises(ValueError):
            applier.apply(path, "deadbeef", pull=nope, push=nope, take_snapshot=nope, editable=nope, run=asc)

    def _cli(self, fn, argv, run):
        import aso
        args = aso.build_parser()[0].parse_args(argv)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = fn(args, run=run)
        return code, out.getvalue(), err.getvalue()

    def test_cli_release_plan_prints_contract(self):
        import aso
        asc = FakeAsc()
        code, out, _ = self._cli(aso.cmd_release_plan, ["release-plan", "--build-json", str(self.bj)], asc)
        self.assertEqual(code, 0)
        last = out.rstrip().splitlines()[-1]
        self.assertTrue(last.startswith("Plan: "))
        path = Path(last[len("Plan: "):])
        self.assertTrue(path.is_absolute())
        self.assertEqual(path.parent, self.state / "plans")
        plan = planner.load_plan(path)
        self.assertIn(confirm.render(plan), out)
        self.assertEqual(path.name, f"{plan.plan_id}.json")
        self.assertEqual(asc.writes(), [])

    def test_cli_release_plan_value_error_exit_2(self):
        import aso
        asc = FakeAsc()
        asc.builds["42"] = "PROCESSING"   # build đã có nhưng chưa VALID ⇒ make_release_plan ValueError
        code, out, err = self._cli(aso.cmd_release_plan, ["release-plan", "--build-json", str(self.bj)], asc)
        self.assertEqual(code, 2)
        self.assertIn("42", err)
        self.assertNotIn("Plan:", out)

    def test_cli_apply_release_output(self):
        import aso
        asc = FakeAsc()
        plan = self._plan(asc)
        path = self.d / "plan.json"
        release.save(plan, path)
        code, out, err = self._cli(aso.cmd_apply, ["apply", "--plan", str(path), "--expect", plan.plan_id], asc)
        self.assertEqual(code, 0, err)
        for s in ("42", "1.12.0", "PREPARE_FOR_SUBMISSION", aso.asc_link(),
                  "Bạn tự xem lại trên App Store Connect và tự bấm nộp review — tool không nộp."):
            self.assertIn(s, out)
        self.assertNotIn("Snapshot", out)


if __name__ == "__main__":
    unittest.main()
