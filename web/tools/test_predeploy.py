"""Test cho web/scripts/predeploy.mjs — chặn deploy khi cấu hình Cloudflare/Firebase còn thiếu.

Script đọc hai `wrangler.jsonc` SINH (Ruling 4: bỏ dòng `//` đầu, JSON); fixture dựng bằng chính
`appconfig.render_wrangler_api/site` để test bám đúng định dạng file sinh thật. Chạy `node` chỉ khi máy có (không mạng,
không wrangler). Thư mục tạm: bản chép `web/scripts/predeploy.mjs` + `web/api|site/wrangler.jsonc`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPT = REPO / "web" / "scripts" / "predeploy.mjs"
sys.path.insert(0, str(REPO / "tools" / "common"))
import appconfig  # noqa: E402

BASE_CFG = {
    "app": {"slug": "demo", "display_name": "Demo", "display_name_internal": "Demo Dev"},
    "bundle": {"store": "com.example.app", "internal": "com.example.app.internal"},
    "apple": {"team_id": "TEAMID0000"},
    "version": {"marketing": "1.0.0", "build": "1"},
    "web": {"host_prod": "demo-site.net", "host_dev": "dev.demo-site.net", "app_paths": []},
    "features": {"paywall": False, "web_api": True, "apple_ads": False},
    "cloudflare": {"d1_prod": "11111111-1111-1111-1111-111111111111", "d1_dev": "22222222-2222-2222-2222-222222222222"},
    "firebase": {"app_check_prod": "test-proj:123456", "app_check_dev": "test-proj:123456"},
}


def cfg_with(**changes) -> dict:
    cfg = json.loads(json.dumps(BASE_CFG))
    for dotted, value in changes.items():
        sec, key = dotted.split("__")
        cfg[sec][key] = value
    return cfg


class _WebDir:
    """Thư mục `web/` tạm: bản chép predeploy.mjs + hai wrangler.jsonc dựng bằng renderer thật."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.web = Path(tmp.name) / "web co dau cach"
        (self.web / "scripts").mkdir(parents=True)
        shutil.copy2(SCRIPT, self.web / "scripts" / "predeploy.mjs")

    def write(self, cfg: dict, api_edit=None, site_edit=None):
        for rel, text, edit in (("api/wrangler.jsonc", appconfig.render_wrangler_api(cfg), api_edit),
                                ("site/wrangler.jsonc", appconfig.render_wrangler_site(cfg), site_edit)):
            if edit is not None:
                header, body = text.split("\n", 1)
                data = json.loads(body)
                edit(data)
                text = header + "\n" + json.dumps(data, indent=2) + "\n"
            p = self.web / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

    def run_env(self, env: str):
        return subprocess.run(["node", str(self.web / "scripts" / "predeploy.mjs"), env], capture_output=True,
                              text=True, cwd=self.web.parent)

    def assert_ok(self, r):
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def assert_refused(self, r, needle):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(needle, r.stderr)


@unittest.skipUnless(shutil.which("node"), "cần node")
class PredeployTests(_WebDir, unittest.TestCase):

    def test_cau_hinh_du_thi_qua_ca_hai_moi_truong(self):
        self.write(BASE_CFG)
        self.assert_ok(self.run_env("dev"))
        self.assert_ok(self.run_env("prod"))

    def test_predeploy_tu_choi_d1_rong(self):
        self.write(cfg_with(cloudflare__d1_dev=""))
        self.assert_refused(self.run_env("dev"), "cloudflare.d1_dev")
        self.assert_ok(self.run_env("prod"))
        self.write(cfg_with(cloudflare__d1_prod=""))
        self.assert_refused(self.run_env("prod"), "cloudflare.d1_prod")
        self.assert_ok(self.run_env("dev"))

    def test_app_check_rong_khi_co_api_thi_tu_choi(self):
        # Dev: APP_CHECK_REQUIRED "0" ⇒ App Check không có tác dụng ⇒ chỉ CẢNH BÁO, vẫn deploy được.
        self.write(cfg_with(firebase__app_check_dev=""))
        r = self.run_env("dev")
        self.assert_ok(r)
        self.assertIn("CẢNH BÁO", r.stderr)
        self.assertIn("firebase.app_check_dev", r.stderr)
        self.write(cfg_with(firebase__app_check_prod=""))
        self.assert_refused(self.run_env("prod"), "firebase.app_check_prod")

    def test_khong_co_api_thi_chi_kiem_site(self):
        # Ruling 11: web_api tắt ⇒ site không có binding API ⇒ không có API: D1 id, App Check, ASSN đều không cần.
        cfg = cfg_with(features__web_api=False, firebase__app_check_dev="", firebase__app_check_prod="",
                       cloudflare__d1_dev="", cloudflare__d1_prod="")
        def empty(d):
            d["vars"]["ASSN_ENVIRONMENTS"] = ""
            d["env"]["dev"]["vars"]["ASSN_ENVIRONMENTS"] = ""
        self.write(cfg, api_edit=empty)
        for env in ("dev", "prod"):
            r = self.run_env(env)
            self.assert_ok(r)
            self.assertIn("chỉ site", r.stdout)
        # File api hỏng hay vắng cũng không chặn (không dùng); biến chỉ-test trong file api vẫn bị từ chối.
        (self.web / "api" / "wrangler.jsonc").unlink()
        self.assert_ok(self.run_env("dev"))
        self.write(cfg, api_edit=lambda d: d["vars"].__setitem__("APP_CHECK_JWKS", "{}"))
        self.assert_refused(self.run_env("prod"), "APP_CHECK_JWKS")

    def test_prod_tu_choi_host_giu_cho(self):
        # Host dành riêng (example.com, *.test, *.invalid, localhost) không bao giờ là site thật ⇒ prod từ chối.
        for host in ("example.com", "app.test", "shop.invalid", "localhost"):
            self.write(cfg_with(web__host_prod=host, web__host_dev=f"dev.{host}"))
            self.assert_refused(self.run_env("prod"), host)
            self.assert_ok(self.run_env("dev"))

    def test_bien_chi_cho_test_app_check_jwks_bi_tu_choi_moi_moi_truong(self):
        def put_dev(d):
            d["env"]["dev"]["vars"]["APP_CHECK_JWKS"] = "{}"
        self.write(BASE_CFG, api_edit=put_dev)
        # Biến chỉ-test nằm ở BẤT KỲ env nào của file api ⇒ cả dev lẫn prod đều từ chối.
        self.assert_refused(self.run_env("prod"), "APP_CHECK_JWKS")
        self.assert_refused(self.run_env("dev"), "APP_CHECK_JWKS")

    def test_assn_environments_rong_thi_tu_choi(self):
        def empty(d):
            d["vars"]["ASSN_ENVIRONMENTS"] = ""
        self.write(BASE_CFG, api_edit=empty)
        self.assert_refused(self.run_env("prod"), "ASSN_ENVIRONMENTS")
        self.assert_ok(self.run_env("dev"))

    def test_thieu_file_sinh_thi_tu_choi(self):
        self.write(BASE_CFG)
        (self.web / "site" / "wrangler.jsonc").unlink()
        self.assert_refused(self.run_env("dev"), "appconfig.py render")

    def test_file_hong_thi_tu_choi(self):
        self.write(BASE_CFG)
        (self.web / "api" / "wrangler.jsonc").write_text("// đầu\n{ hỏng\n", encoding="utf-8")
        self.assert_refused(self.run_env("dev"), "api/wrangler.jsonc")

    def test_tham_so_sai_rc2(self):
        self.write(BASE_CFG)
        for args in ([], ["staging"], ["dev", "prod"]):
            r = subprocess.run(["node", str(self.web / "scripts" / "predeploy.mjs"), *args], capture_output=True,
                               text=True)
            self.assertEqual(r.returncode, 2, f"{args}: {r.stdout}{r.stderr}")


@unittest.skipUnless(shutil.which("node"), "cần node")
class DeployModeTests(_WebDir, unittest.TestCase):
    """`--deploy`: thứ tự lệnh thật với `npm`/`python3` GIẢ trên PATH (ghi lời gọi; không wrangler, không mạng)."""

    def deploy(self, env, fail_on=None):
        bindir = self.web.parent / "bin gia"
        bindir.mkdir(exist_ok=True)
        calls = self.web.parent / "calls.txt"
        if calls.exists():
            calls.unlink()
        for name in ("npm", "python3"):
            rc = f'case "$*" in *"{fail_on}"*) exit 1 ;; esac\n' if fail_on else ""
            (bindir / name).write_text(f'#!/bin/bash\necho "{name} $*" >> "{calls}"\n{rc}exit 0\n')
            (bindir / name).chmod(0o755)
        env_vars = {"PATH": f"{bindir}:/usr/bin:/bin"}
        r = subprocess.run([shutil.which("node"), str(self.web / "scripts" / "predeploy.mjs"), env, "--deploy"],
                           capture_output=True, text=True, env=env_vars)
        return r, (calls.read_text().splitlines() if calls.exists() else [])

    def test_deploy_dev_co_api_thi_api_truoc_site(self):
        self.write(BASE_CFG)
        r, calls = self.deploy("dev")
        self.assert_ok(r)
        self.assertEqual(calls, ["npm run deploy:dev -w api", "npm run deploy:dev -w site"])

    def test_deploy_prod_qua_cong_site_truoc_moi_wrangler(self):
        self.write(BASE_CFG)
        r, calls = self.deploy("prod")
        self.assert_ok(r)
        self.assertEqual(calls, ["python3 tools/check_sitemap.py", "python3 tools/changelog.py --check",
                                 "python3 tools/check_site.py --release", "npm run deploy:prod -w api",
                                 "npm run deploy:prod -w site"])

    def test_deploy_khong_co_api_thi_chi_site(self):
        self.write(cfg_with(features__web_api=False, cloudflare__d1_dev="", cloudflare__d1_prod=""))
        for env, want in (("dev", ["npm run deploy:dev -w site"]),
                          ("prod", ["python3 tools/check_sitemap.py", "python3 tools/changelog.py --check",
                                    "python3 tools/check_site.py --release", "npm run deploy:prod -w site"])):
            r, calls = self.deploy(env)
            self.assert_ok(r)
            self.assertEqual(calls, want, env)

    def test_deploy_dung_o_loi_dau_tien(self):
        self.write(BASE_CFG)
        r, calls = self.deploy("prod", fail_on="check_site.py")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(calls[-1], "python3 tools/check_site.py --release")
        self.assertFalse(any(c.startswith("npm") for c in calls), calls)

    def test_kiem_do_thi_khong_goi_lenh_nao(self):
        self.write(cfg_with(cloudflare__d1_dev=""))
        r, calls = self.deploy("dev")
        self.assert_refused(r, "cloudflare.d1_dev")
        self.assertEqual(calls, [])


class PackageScriptsTests(unittest.TestCase):
    """`web/package.json`: deploy chỉ qua predeploy --deploy (thứ tự + API có điều kiện nằm trong script)."""

    def test_deploy_qua_predeploy(self):
        scripts = json.loads((REPO / "web" / "package.json").read_text(encoding="utf-8"))["scripts"]
        self.assertEqual(scripts["deploy:dev"], "node scripts/predeploy.mjs dev --deploy")
        self.assertEqual(scripts["deploy:prod"], "node scripts/predeploy.mjs prod --deploy")


if __name__ == "__main__":
    unittest.main()
