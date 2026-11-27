"""Test build.py — chỉ dựng argv/kiểm tiền điều kiện; xcodebuild/git là hàm giả tiêm vào, không chạy gì thật."""
import _testenv  # noqa: F401 — thư mục trạng thái + cấu hình giả trước mọi import khác
import hashlib
import json
import plistlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import appconfig  # noqa: E402
import build  # noqa: E402
import store  # noqa: E402

VERSION, NUMBER = "1.2.3", "7"   # = [version] của _testenv.FAKE_CFG


def make_repo(tc, cfg=None) -> Path:
    """Repo tạm có file sinh từ cấu hình (Identity.xcconfig, Features.generated.yml) khớp `cfg`."""
    repo = Path(tempfile.mkdtemp(prefix="aso repo ")).resolve()
    tc.addCleanup(shutil.rmtree, repo, True)
    appconfig.write_generated(repo, cfg or _testenv.cfg())
    return repo


def fake_git(branch="main", status="", tag="v" + VERSION, sha="abc123"):
    def git(argv):
        if argv[:2] == ["rev-parse", "--abbrev-ref"]:
            return branch + "\n"
        if argv[0] == "status":
            return status
        if argv[0] == "describe":
            if tag is None:
                raise RuntimeError("no tag")
            return tag + "\n"
        if argv[:2] == ["rev-parse", "HEAD"]:
            return sha + "\n"
        raise AssertionError(argv)
    return git


class Runner:
    """run_cmd giả: ghi lại lệnh; tạo .app khi archive, .ipa khi exportArchive; fail_on = chuỗi trong argv ⇒ exit 1."""

    def __init__(self, fail_on=None, ipa=b"ipa-bytes", ipas=1, app_vb=(VERSION, NUMBER)):
        self.calls, self.fail_on, self.ipa, self.ipas, self.app_vb = [], fail_on, ipa, ipas, app_vb

    def __call__(self, argv, cwd):
        self.calls.append((list(argv), cwd))
        if self.fail_on and any(self.fail_on in a for a in argv):
            return 1, "boom\n" * 50
        if argv[:2] == ["xcodebuild", "archive"]:
            app = Path(argv[argv.index("-archivePath") + 1]) / "Products" / "Applications" / "P.app"
            app.mkdir(parents=True)
            (app / "Info.plist").write_bytes(plistlib.dumps(
                {"CFBundleShortVersionString": self.app_vb[0], "CFBundleVersion": self.app_vb[1]}))
        if "-exportArchive" in argv:
            exp = Path(argv[argv.index("-exportPath") + 1])
            exp.mkdir(parents=True, exist_ok=True)
            for i in range(self.ipas):
                (exp / f"Ban{i}.ipa").write_bytes(self.ipa)
        return 0, "ok"


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.state = _testenv.isolate(self)
        self.repo = make_repo(self)

    def test_build_refuses_wrong_checkout(self):
        cases = [fake_git(branch="develop"), fake_git(status=" M x.py\n"), fake_git(tag="v1.2.2"),
                 fake_git(tag=None)]
        for g in cases:
            r = Runner()
            with self.assertRaises(ValueError):
                build.build(self.repo, VERSION, run_cmd=r, git=g)
            self.assertEqual(r.calls, [])

    def test_build_doc_version_tu_app_config(self):
        # --version khác [version] marketing ⇒ từ chối trước mọi lệnh
        r = Runner()
        with self.assertRaises(ValueError) as cm:
            build.build(self.repo, "9.9.9", run_cmd=r, git=fake_git(tag="v9.9.9"))
        self.assertIn("version.marketing", str(cm.exception))
        self.assertEqual(r.calls, [])
        # số build + thư mục theo [version] build của cấu hình (không đọc Info.plist literal)
        cfg = _testenv.cfg(**{"version.build": "42"})
        _testenv.use_config(self, cfg)
        repo = make_repo(self, cfg)
        path = build.build(repo, VERSION, run_cmd=Runner(app_vb=(VERSION, "42")), git=fake_git())
        b = json.loads(path.read_text())
        self.assertEqual((b["version"], b["build"]), (VERSION, "42"))
        self.assertEqual(path.parent, store.state_dir() / "builds" / f"{VERSION}-42")

    def test_file_sinh_ra_lech_cau_hinh_thi_tu_choi(self):
        (self.repo / appconfig.XCCONFIG).write_text("// lệch\n", encoding="utf-8")
        r = Runner()
        with self.assertRaises(ValueError) as cm:
            build.build(self.repo, VERSION, run_cmd=r, git=fake_git())
        self.assertIn(appconfig.XCCONFIG, str(cm.exception))
        self.assertEqual(r.calls, [])

    def test_build_runs_steps_in_order(self):
        r = Runner()
        build.build(self.repo, VERSION, run_cmd=r, git=fake_git())
        argvs = [c[0] for c in r.calls]
        self.assertEqual(argvs[0], ["xcodegen", "generate"])
        self.assertEqual(r.calls[0][1], self.repo / appconfig.PROJ_DIR)
        self.assertEqual(argvs[1][:2], ["xcodebuild", "archive"])
        self.assertEqual(argvs[1][argvs[1].index("-scheme") + 1], appconfig.STORE_SCHEME)
        self.assertEqual(argvs[1][argvs[1].index("-project") + 1], appconfig.PROJECT)
        self.assertEqual(argvs[1][argvs[1].index("-configuration") + 1], "Release")
        self.assertIn("-exportArchive", argvs[2])
        self.assertTrue(argvs[3][0].endswith("verify_release_clean.sh"))
        self.assertTrue(argvs[3][1].endswith(f"{appconfig.APP_TARGET}.xcarchive"))
        self.assertEqual(argvs[4], ["python3", "tools/i18n/verify_catalog.py", "--check"])
        self.assertEqual(len(argvs), 5)
        flat = " ".join(" ".join(a) for a in argvs)
        self.assertNotIn("Debug", flat)
        self.assertNotIn("Internal", flat)
        self.assertNotIn(" test", flat)

    def test_build_gate_failure_writes_no_build_json(self):
        r = Runner(fail_on="verify_release_clean.sh")
        with self.assertRaises(RuntimeError) as cm:
            build.build(self.repo, VERSION, run_cmd=r, git=fake_git())
        self.assertEqual(str(cm.exception).count("boom"), 40)
        self.assertEqual(list(self.state.glob("builds/*/build.json")), [])

    def test_build_json_has_sha_of_ipa(self):
        path = build.build(self.repo, VERSION, run_cmd=Runner(ipa=b"hello"), git=fake_git())
        b = json.loads(path.read_text())
        self.assertEqual(b["ipa_sha256"], hashlib.sha256(b"hello").hexdigest())
        self.assertEqual((b["version"], b["build"], b["commit"]), (VERSION, NUMBER, "abc123"))
        self.assertEqual(b["gates"], {"verify_release_clean": "ok", "verify_catalog": "ok"})
        self.assertTrue(Path(b["ipa"]).is_absolute() and Path(b["ipa"]).exists())
        self.assertEqual(path.parent, store.state_dir() / "builds" / f"{VERSION}-{NUMBER}")
        self.assertIn("created", b)

    def test_archive_app_plist_mismatch_aborts(self):
        with self.assertRaises(RuntimeError):
            build.build(self.repo, VERSION, run_cmd=Runner(app_vb=(VERSION, "6")), git=fake_git())
        self.assertEqual(list(self.state.glob("builds/*/build.json")), [])

    def test_failure_leaves_no_final_dir_and_retry_works(self):
        final = self.state / "builds" / f"{VERSION}-{NUMBER}"
        with self.assertRaises(RuntimeError):
            build.build(self.repo, VERSION, run_cmd=Runner(fail_on="verify_catalog.py"), git=fake_git())
        self.assertFalse(final.exists())
        path = build.build(self.repo, VERSION, run_cmd=Runner(), git=fake_git())
        self.assertEqual(path, final / "build.json")
        b = json.loads(path.read_text())
        self.assertTrue(b["ipa"].startswith(str(path.parent / "export")))
        self.assertTrue(Path(b["ipa"]).exists())
        self.assertFalse(final.with_name(final.name + ".partial").exists())

    def test_build_ipa_count_must_be_one(self):
        for n in (0, 2):
            with self.assertRaises(RuntimeError):
                build.build(self.repo, VERSION, run_cmd=Runner(ipas=n), git=fake_git())
            shutil.rmtree(store.state_dir() / "builds")

    def test_build_refuses_existing_dir(self):
        (store.state_dir() / "builds" / f"{VERSION}-{NUMBER}").mkdir(parents=True)
        r = Runner()
        with self.assertRaises(ValueError):
            build.build(self.repo, VERSION, run_cmd=r, git=fake_git())
        self.assertEqual(r.calls, [])

    def test_export_options_values(self):
        d = Path(tempfile.mkdtemp(prefix="aso export "))
        self.addCleanup(shutil.rmtree, d, True)
        p = d / "E.plist"
        build.export_options(p, _testenv.FAKE_TEAM)
        self.assertEqual(plistlib.loads(p.read_bytes()), {
            "method": "app-store-connect", "teamID": _testenv.FAKE_TEAM, "signingStyle": "automatic",
            "uploadSymbols": True, "destination": "export"})

    def test_team_trong_export_options_doc_tu_cau_hinh(self):
        seen, runner = {}, Runner()

        def run_cmd(argv, cwd):
            if "-exportArchive" in argv:
                seen["opts"] = plistlib.loads(Path(argv[argv.index("-exportOptionsPlist") + 1]).read_bytes())
            return runner(argv, cwd)
        build.build(self.repo, VERSION, run_cmd=run_cmd, git=fake_git())
        self.assertEqual(seen["opts"]["teamID"], _testenv.FAKE_TEAM)


if __name__ == "__main__":
    unittest.main()
