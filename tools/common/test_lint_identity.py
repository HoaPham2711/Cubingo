"""Test cho lint_identity — repo git tạm, không đụng repo thật."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import appconfig  # noqa: E402
import lint_identity  # noqa: E402

SAMPLE_CONFIG = """\
[app]
slug = "sample"
display_name = "Sample"
display_name_internal = "Sample Dev"

[bundle]
store = "com.example.sample"
internal = "com.example.sample.internal"

[apple]
team_id = "0000000000"
app_store_id = ""

[version]
marketing = "0.1.0"
build = "1"

[web]
host_prod = ""
host_dev = ""
"""
GIT = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com"]


class LintIdentityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        (self.root / "app.config.toml").write_text(SAMPLE_CONFIG, encoding="utf-8")
        appconfig.write_xcconfig(self.root, appconfig.load(self.root))
        self.commit_file("README.md", "template\n")
        subprocess.run(["git", "add", "app.config.toml", appconfig.XCCONFIG], cwd=self.root, check=True)
        subprocess.run(GIT + ["commit", "-q", "-m", "base"], cwd=self.root, check=True)

    def commit_file(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", rel], cwd=self.root, check=True)
        subprocess.run(GIT + ["commit", "-q", "-m", f"add {rel}"], cwd=self.root, check=True)

    def test_tu_cam_cua_repo_nguon_bi_bat(self):
        self.commit_file("tools/x.py", "NAME = 'Pura" + "cam'\n")
        self.assertTrue(any("tools/x.py:1" in v for v in lint_identity.find_violations(self.root)))

    def test_dinh_danh_literal_ngoai_cau_hinh_bi_bat(self):
        self.commit_file("tools/y.sh", 'BID="com.example.sample"\n')
        self.assertTrue(any("tools/y.sh:1" in v for v in lint_identity.find_violations(self.root)))

    def test_cau_hinh_va_xcconfig_duoc_phep(self):
        self.assertEqual(lint_identity.find_violations(self.root), [])

    def hits(self, rel):
        return [v for v in lint_identity.find_violations(self.root) if v.startswith(rel + ":")]

    def test_uuid_toan_so_khong_va_chuoi_khong_dai_khong_bi_bat(self):
        self.commit_file("tools/u.txt", "ID=00000000-0000-0000-0000-000000000000\nN=000000000000000\n")
        self.assertEqual(self.hits("tools/u.txt"), [])

    def test_team_id_dung_ranh_gioi_van_bi_bat(self):
        self.commit_file("tools/t.txt", 'TEAM="0000000000"\nT2=0000000000\nT3 = 0000000000 x\n')
        self.assertEqual(len(self.hits("tools/t.txt")), 3)

    def test_bundle_id_la_tien_to_cua_chuoi_dai_hon_khong_bi_bat(self):
        self.commit_file("tools/p.txt", "com.example.sampleapp\ncom.example.sample2\n")
        self.assertEqual(self.hits("tools/p.txt"), [])

    def test_bundle_id_dung_ranh_gioi_bi_bat(self):
        self.commit_file("tools/b.txt", 'a="com.example.sample"\nb: com.example.sample \nc=com.example.sample')
        self.assertEqual(len(self.hits("tools/b.txt")), 3)

    def test_bundle_internal_van_bi_bat_khi_co_hau_to_cham(self):
        self.commit_file("tools/i.txt", "ID=com.example.sample.internal\n")
        self.assertTrue(self.hits("tools/i.txt"))

    def test_web_chi_quet_ma_khong_quet_file_sinh_va_trang_gieo(self):
        line = 'APP = "com.example.sample"\n'
        for rel in ("web/api/src/x.ts", "web/api/test/x.test.ts", "web/site/src/worker.ts", "web/site/test/a.test.ts",
                    "web/tools/check_x.py", "web/tools/test_x.py", "web/scripts/predeploy.mjs"):
            self.commit_file(rel, line)
            self.assertTrue(self.hits(rel), rel)
        for rel in ("web/api/wrangler.jsonc", "web/site/wrangler.jsonc", "web/site/public/privacy/index.html",
                    "web/site/releases.json", "web/README.md"):
            self.commit_file(rel, line)
            self.assertEqual(self.hits(rel), [], rel)

    def test_tai_lieu_thiet_ke_duoc_nhac_ten_app_nguon(self):
        content = "Nguồn: vimind" + "tech\n"
        self.commit_file("docs/superpowers/specs/s.md", content)
        self.commit_file("docs/decisions/d.md", content)
        self.assertEqual(lint_identity.find_violations(self.root), [])
        self.commit_file("tools/z.md", content)
        self.assertTrue(any("tools/z.md:1" in v for v in lint_identity.find_violations(self.root)))

    # Từ cấm (a) ghép chuỗi để file này không tự vi phạm.
    ORG = "vimind" + "tech"
    TEAM = "Q73A5F75" + "B4"

    def use_own_identity(self):
        """Cấu hình app mang định danh cùng chủ tài khoản với repo nguồn (tiền tố bundle + team id)."""
        text = (SAMPLE_CONFIG.replace("com.example.sample", f"com.{self.ORG}.cubes")
                .replace('team_id = "0000000000"', f'team_id = "{self.TEAM}"'))
        (self.root / "app.config.toml").write_text(text, encoding="utf-8")
        appconfig.write_xcconfig(self.root, appconfig.load(self.root))
        subprocess.run(["git", "add", "app.config.toml", appconfig.XCCONFIG], cwd=self.root, check=True)
        subprocess.run(GIT + ["commit", "-q", "-m", "own identity"], cwd=self.root, check=True)

    def test_app_duoc_mien_tu_cam_nam_trong_dinh_danh_cua_chinh_app(self):
        self.use_own_identity()
        self.commit_file("docs/CHECKLIST.md", f"Bundle com.{self.ORG}.cubes, team {self.TEAM}\n")
        self.assertEqual(lint_identity.find_violations(self.root), [])

    def test_app_van_bi_bat_tu_cam_khong_thuoc_dinh_danh_cua_app(self):
        self.use_own_identity()
        self.commit_file("tools/x.py", "NAME = 'Pura" + "cam'\n")
        self.assertTrue(any("tools/x.py:1" in v for v in lint_identity.find_violations(self.root)))

    def test_template_khong_mien_du_cau_hinh_mang_tu_cam(self):
        self.use_own_identity()
        self.commit_file(lint_identity.TEMPLATE_MARKER, "# chỉ template\n")
        found = lint_identity.find_violations(self.root)
        self.assertTrue(any(v.startswith("app.config.toml:") for v in found), found)


if __name__ == "__main__":
    unittest.main()
