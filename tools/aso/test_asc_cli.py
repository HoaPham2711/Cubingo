"""Test wrapper asc_cli.py bằng một `asc` giả (script Python trong thư mục tạm)."""
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401 — thư mục trạng thái + cấu hình giả
import asc_cli  # noqa: E402
import policy  # noqa: E402

FAKE = """#!/usr/bin/env python3
import json, os, sys
marker = os.environ.get("FAKE_MARKER")
if sys.argv[1:] == ["version"]:
    venv = os.environ.get("FAKE_VERSION_ENV")
    if venv:
        keep = {k: v for k, v in os.environ.items() if k.startswith("ASC_") or k == "DO_NOT_TRACK"}
        open(venv, "w").write(json.dumps(keep))
    print(os.environ.get("FAKE_VERSION", "5.17.1"))
    sys.exit(0)
if marker:
    open(marker, "a").write("called\\n")
if os.environ.get("FAKE_FAIL"):
    sys.stderr.write("loi doc key " + os.environ["FAKE_FAIL"] + " hong\\n")
    sys.exit(1)
env = {k: v for k, v in os.environ.items() if k.startswith("ASC_")}
print(json.dumps({"argv": sys.argv[1:], "env": env, "cwd": os.getcwd()}))
"""


class AscCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wrapper cli "))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fake = self.tmp / "asc"
        self.fake.write_text(FAKE)
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IXUSR)
        self.key = self.tmp / "AuthKey_KID123.p8"
        self.key.write_text("FAKE-KEY")
        cfg = self.tmp / "cfg.json"
        cfg.write_text(json.dumps({"key_id": "KID123", "issuer_id": "ISS456"}))
        self.marker = self.tmp / "marker"
        env = {"ASO_CONFIG": str(cfg), "ASC_KEY_FILE": str(self.key),
               "FAKE_MARKER": str(self.marker), "ASC_STALE": "x"}
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        # Binary giả không khớp SHA ghim thật — mặc định bỏ ghim; test về ghim tự patch lại.
        pin = mock.patch.object(asc_cli, "ASC_SHA256", "")
        pin.start()
        self.addCleanup(pin.stop)
        asc_cli._VERSION_OK.clear()

    def test_read_sets_read_only_and_telemetry_off(self):
        out = asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)
        env = out["env"]
        self.assertEqual(env["ASC_READ_ONLY"], "1")
        self.assertEqual(env["ASC_TELEMETRY_DISABLED"], "1")
        self.assertEqual(env["ASC_APP_ID"], _testenv.FAKE_APP_ID)
        self.assertEqual(env["ASC_BYPASS_KEYCHAIN"], "1")
        self.assertEqual(env["ASC_KEY_ID"], "KID123")
        self.assertNotIn("ASC_STALE", env)
        self.assertEqual(out["argv"][-2:], ["--output", "json"])

    def test_runs_in_state_dir_cwd(self):
        import store
        out = asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)
        want = (store.state_dir() / "asc-cwd").resolve()
        self.assertEqual(Path(out["cwd"]).resolve(), want)
        self.assertTrue(want.is_dir())

    def test_write_drops_read_only(self):
        out = asc_cli.run(["metadata", "push", "--app", "1", "--version", "1", "--dir", "d"], write=True, bin=self.fake)
        self.assertNotIn("ASC_READ_ONLY", out["env"])

    def test_version_mismatch_refuses(self):
        with mock.patch.dict(os.environ, {"FAKE_VERSION": "5.18.0"}):
            with self.assertRaises(asc_cli.AscError):
                asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)

    def test_version_substring_not_accepted(self):
        with mock.patch.dict(os.environ, {"FAKE_VERSION": "15.17.10"}):
            with self.assertRaises(asc_cli.AscError):
                asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)

    def test_policy_enforced(self):
        with self.assertRaises(policy.PolicyError):
            asc_cli.run(["submit", "create"], write=True, bin=self.fake)
        self.assertFalse(self.marker.exists())

    def test_stderr_redacts_key_path(self):
        with mock.patch.dict(os.environ, {"FAKE_FAIL": str(self.key)}):
            with self.assertRaises(asc_cli.AscError) as cm:
                asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)
        self.assertNotIn(str(self.key), cm.exception.stderr)
        self.assertIn("<redacted>", cm.exception.stderr)
        self.assertEqual(cm.exception.returncode, 1)

    def test_version_check_uses_sanitized_env(self):
        venv = self.tmp / "venv.json"
        with mock.patch.dict(os.environ, {"FAKE_VERSION_ENV": str(venv), "ASC_KEY_ID": "LEAK"}):
            asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)
        env = json.loads(venv.read_text())
        self.assertEqual(env, {"ASC_TELEMETRY_DISABLED": "1", "DO_NOT_TRACK": "1"})

    def _sha(self):
        import hashlib
        return hashlib.sha256(self.fake.read_bytes()).hexdigest()

    def test_sha_pin_mismatch_refuses_without_running(self):
        venv = self.tmp / "venv.json"
        with mock.patch.object(asc_cli, "ASC_SHA256", "0" * 64), \
                mock.patch.dict(os.environ, {"FAKE_VERSION_ENV": str(venv)}):
            with self.assertRaises(asc_cli.AscError) as cm:
                asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)
        self.assertIn("SHA-256", str(cm.exception))
        self.assertFalse(venv.exists())          # binary lạ không được chạy, kể cả `version`
        self.assertFalse(self.marker.exists())

    def test_sha_pin_match_runs_and_is_cached(self):
        calls = []
        real = asc_cli._sha256_file

        def counting(path):
            calls.append(path)
            return real(path)
        with mock.patch.object(asc_cli, "ASC_SHA256", self._sha().upper()), \
                mock.patch.object(asc_cli, "_sha256_file", counting):
            asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)
            asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)
        self.assertEqual(len(calls), 1)
        self.assertTrue(self.marker.exists())

    def test_empty_sha_pin_skips_hash(self):
        with mock.patch.object(asc_cli, "ASC_SHA256", ""), \
                mock.patch.object(asc_cli, "_sha256_file", side_effect=AssertionError("không được hash")):
            asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)

    def test_sha_pin_file_exists_and_is_hex_or_empty(self):
        pin = (Path(asc_cli.__file__).parent / "ASC_SHA256").read_text().strip()
        self.assertRegex(pin, r"^([0-9a-fA-F]{64})?$")

    def test_install_script_sanitizes_and_checks_pin(self):
        text = (Path(asc_cli.__file__).parent / "install_asc.sh").read_text()
        self.assertIn("ASC_SHA256", text)
        self.assertIn("ASC_TELEMETRY_DISABLED=1", text)
        self.assertIn("DO_NOT_TRACK=1", text)
        self.assertIn("ghi giá trị này vào tools/aso/ASC_SHA256 sau khi user xác nhận", text)
        last = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")][-1]
        self.assertNotRegex(last, r'^"\$DEST_DIR/asc" version$')   # không chạy version với env thô

    def test_output_flag_not_duplicated(self):
        out = asc_cli.run(["metadata", "pull", "--output", "json"], bin=self.fake)
        self.assertEqual(out["argv"].count("--output"), 1)

    # --- định danh từ app.config.toml ---

    def test_khong_co_app_store_id_thi_tu_choi_co_huong_dan(self):
        _testenv.use_config(self, _testenv.cfg(**{"apple.app_store_id": ""}))
        venv = self.tmp / "venv.json"
        with mock.patch.dict(os.environ, {"FAKE_VERSION_ENV": str(venv)}):
            with self.assertRaises(asc_cli.NoAppRecord) as cm:
                asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)
        self.assertIn("apple.app_store_id", str(cm.exception))
        self.assertIn("app.config.toml", str(cm.exception))
        self.assertFalse(venv.exists(), "không chạy binary lần nào, kể cả `version`")
        self.assertFalse(self.marker.exists())
        with self.assertRaises(asc_cli.NoAppRecord):
            asc_cli.app_id()

    def test_binary_va_cau_hinh_khoa_theo_thu_muc_chung_va_slug(self):
        self.assertEqual(asc_cli.asc_bin(),
                         Path(os.environ["IOS_APP_FACTORY_BIN"]) / "asc" / asc_cli.ASC_VERSION / "asc")
        a = asc_cli.default_config(_testenv.cfg(**{"app.slug": "app-mot"}))
        b = asc_cli.default_config(_testenv.cfg(**{"app.slug": "app-hai"}))
        self.assertEqual(a, Path(os.environ["IOS_APP_FACTORY_CONFIG"]) / "app-mot" / "asc-listing.json")
        self.assertNotEqual(a.parent, b.parent)

    def test_khong_co_aso_config_thi_doc_cau_hinh_theo_slug(self):
        cfg_path = asc_cli.default_config()
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps({"key_id": "KID789", "issuer_id": "ISS000"}))
        self.addCleanup(cfg_path.unlink)
        with mock.patch.dict(os.environ, {}):
            del os.environ["ASO_CONFIG"]
            out = asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)
        self.assertEqual(out["env"]["ASC_KEY_ID"], "KID789")

    def test_thieu_cau_hinh_khoa_mot_dong_khong_lo_duong_dan(self):
        with mock.patch.dict(os.environ, {"ASO_CONFIG": str(self.tmp / "khong-co.json")}):
            with self.assertRaises(asc_cli.AscError) as cm:
                asc_cli.run(["metadata", "pull", "--dir", "d"], bin=self.fake)
        self.assertNotIn("\n", str(cm.exception))
        self.assertNotIn(str(self.tmp), str(cm.exception))
        self.assertFalse(self.marker.exists())


class OfflineFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fixture offline "))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_khoa_chuan_hoa_bo_app_id_va_duong_dan(self):
        k1 = asc_cli.fixture_key(["metadata", "pull", "--app", "111", "--version", "0.1.0", "--dir", "/tmp/a b/x"])
        k2 = asc_cli.fixture_key(["metadata", "pull", "--app", "999", "--version", "0.1.0",
                                  "--dir", str(self.tmp / "khac")])
        self.assertEqual(k1, k2)
        self.assertEqual(k1, "metadata_pull_--app_APP_--version_0.1.0_--dir_DIR")
        self.assertEqual(asc_cli.fixture_key(["builds", "upload", "--ipa", "/x/y.ipa"]), "builds_upload_--ipa_IPA")
        self.assertEqual(asc_cli.fixture_key(["versions", "view", "--note", "a b/c"]), "versions_view_--note_a-b-c")

    def test_doc_phan_hoi_va_ghi_file_vao_dir(self):
        key = "metadata_pull_--app_APP_--version_1.0.0_--dir_DIR"
        (self.tmp / f"{key}.json").write_text(json.dumps(
            {"response": {"ok": True}, "files": {"app-info/en-US.json": {"name": "Thu"}}}))
        run = asc_cli.offline_runner(self.tmp)
        dest = self.tmp / "dich den"
        out = run(["metadata", "pull", "--app", "1", "--version", "1.0.0", "--dir", str(dest)])
        self.assertEqual(out, {"ok": True})
        self.assertEqual(json.loads((dest / "app-info" / "en-US.json").read_text()), {"name": "Thu"})

    def test_thieu_fixture_loi_ro_ten_khoa(self):
        run = asc_cli.offline_runner(self.tmp)
        with self.assertRaises(asc_cli.AscError) as cm:
            run(["versions", "view", "--app", "1", "--version", "9.9.9", "--include", "build"])
        self.assertIn("versions_view_--app_APP_--version_9.9.9_--include_build", str(cm.exception))

    def test_fixture_tu_choi_lenh_ghi_va_lenh_ngoai_allowlist(self):
        run = asc_cli.offline_runner(self.tmp)
        with self.assertRaises(asc_cli.AscError):
            run(["metadata", "push", "--app", "1", "--version", "1", "--dir", "d"], write=True)
        with self.assertRaises(policy.PolicyError):
            run(["metadata", "push", "--app", "1", "--version", "1", "--dir", "d"])

    def test_fixture_khong_ghi_ra_ngoai_dir(self):
        key = "metadata_pull_--dir_DIR"
        (self.tmp / f"{key}.json").write_text(json.dumps({"response": None, "files": {"../thoat.json": {}}}))
        with self.assertRaises(asc_cli.AscError):
            asc_cli.offline_runner(self.tmp)(["metadata", "pull", "--dir", str(self.tmp / "d")])
        self.assertFalse((self.tmp / "thoat.json").exists())


if __name__ == "__main__":
    unittest.main()
