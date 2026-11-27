"""Test cho .githooks/pre-commit khối (1): hook phải kiểm NỘI DUNG SẼ ĐƯỢC COMMIT, không phải working tree.

Mỗi test dựng một repo git tạm có hook thật (chép từ repo) + appconfig/lint_identity thật, rồi commit thật.
Mọi biến GIT_* bị gỡ khỏi env (docs/lessons-learned/test-git-trong-hook-dung-repo-that.md).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import appconfig  # noqa: E402

CONFIG = """\
[app]
slug = "sample"
display_name = "Sample"
display_name_internal = "Sample Dev"

[bundle]
store = "com.example.sample"
internal = "com.example.sample.internal"

[apple]
team_id = "0000000000"

[version]
marketing = "0.1.0"
build = "1"
"""
TEMPLATE_MARKER = "tools/template/new_app.py"
GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    return env


class PreCommitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo có dấu cách"
        self.root.mkdir()
        self.env = clean_env()
        self.git("init", "-q", "-b", "main")
        top = self.git("rev-parse", "--show-toplevel").stdout.strip()
        self.assertEqual(Path(top).resolve(), self.root.resolve(), "repo tạm phải là gốc, không phải repo thật")
        # Repo thật bỏ qua __pycache__ bằng .gitignore; repo tạm không có ⇒ chạy tool trong đó ghi bytecode rồi `git add -A`
        # kéo cả .pyc vào index. Loại cục bộ (không track) để repo tạm xử lý bytecode như repo thật.
        (self.root / ".git/info/exclude").write_text("__pycache__/\n", encoding="utf-8")
        for rel in (".githooks/pre-commit", "tools/common/appconfig.py", "tools/common/lint_identity.py",
                    "tools/release/check_storekit.py"):
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)
        self.write(appconfig.CONFIG_FILE, CONFIG)
        appconfig.write_generated(self.root, appconfig.load(self.root))
        # Repo tạm mô phỏng TEMPLATE: dấu nhận diện dương là tools/template/new_app.py được track (không có ⇒ là app,
        # khối 0 đòi core.lock). Lớp mô phỏng app gỡ file này.
        self.write(TEMPLATE_MARKER, "")
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "base")
        self.git("config", "core.hooksPath", ".githooks")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, env=self.env, capture_output=True, text=True)

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def commit(self):
        return self.git(*GIT_ID, "commit", "-q", "-m", "thử")

    def head(self):
        return self.git("rev-parse", "HEAD").stdout.strip()

    def render(self):
        r = subprocess.run([sys.executable, "tools/common/appconfig.py", "render"], cwd=self.root, env=self.env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_stage_mot_nua_bi_tu_choi(self):
        # Tái hiện review: sửa config, render, chỉ stage app.config.toml ⇒ commit mang build=7 mà xcconfig build=1.
        self.write(appconfig.CONFIG_FILE, CONFIG.replace('build = "1"', 'build = "7"'))
        self.render()
        self.git("add", appconfig.CONFIG_FILE)
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, "hook cho qua commit stage một nửa:\n" + r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("chưa stage", r.stderr)

    def test_xcconfig_cu_trong_index_bi_tu_choi_va_goi_y_render(self):
        self.write(appconfig.CONFIG_FILE, CONFIG.replace('build = "1"', 'build = "8"'))
        self.git("add", appconfig.CONFIG_FILE)
        r = self.commit()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("appconfig.py render", r.stderr)

    def test_cau_hinh_hong_khong_goi_y_render(self):
        self.write(appconfig.CONFIG_FILE, CONFIG.replace('team_id = "0000000000"\n', ""))
        self.git("add", appconfig.CONFIG_FILE)
        r = self.commit()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("apple.team_id", r.stderr)
        self.assertIn("xem lỗi ở trên", r.stderr)
        self.assertNotIn("appconfig.py render", r.stderr)

    def with_privacy_template(self):
        tpl = self.root / appconfig.PRIVACY_TEMPLATE
        tpl.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / appconfig.PRIVACY_TEMPLATE, tpl)
        self.render()
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "thêm mẫu privacy")
        self.assertTrue((self.root / appconfig.PRIVACY_MANIFEST).exists())

    def test_privacy_manifest_sua_tay_bi_tu_choi(self):
        self.with_privacy_template()
        m = self.root / appconfig.PRIVACY_MANIFEST
        m.write_text(m.read_text(encoding="utf-8").replace("<false/>", "<true/>", 1), encoding="utf-8")
        self.git("add", appconfig.PRIVACY_MANIFEST)
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn(appconfig.PRIVACY_MANIFEST, r.stderr)

    def test_privacy_manifest_chua_stage_sau_khi_sua_mau_bi_tu_choi(self):
        self.with_privacy_template()
        tpl = self.root / appconfig.PRIVACY_TEMPLATE
        tpl.write_text(tpl.read_text(encoding="utf-8").replace("CA92.1", "C617.1"), encoding="utf-8")
        self.render()
        self.git("add", appconfig.PRIVACY_TEMPLATE)
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("chưa stage", r.stderr)
        self.git("add", appconfig.PRIVACY_MANIFEST)
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_features_yml_chua_add_bi_tu_choi(self):
        # File sinh ra mới tinh chưa từng `git add` ⇒ `check` (đọc working tree) xanh nhưng commit thiếu file.
        (self.root / appconfig.FEATURES_YML).unlink()
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "gỡ file sinh ra")
        self.render()
        self.write("ghi-chu.txt", "x\n")
        self.git("add", "ghi-chu.txt")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn(appconfig.FEATURES_YML, r.stderr)

    def test_stage_du_ca_hai_thi_qua(self):
        # Đối chứng dương: cùng thay đổi, stage đủ ⇒ commit qua.
        self.write(appconfig.CONFIG_FILE, CONFIG.replace('build = "1"', 'build = "7"'))
        self.render()
        self.git("add", appconfig.CONFIG_FILE, appconfig.XCCONFIG)
        before = self.head()
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(self.head(), before)


PAYWALL = """
[web]
host_prod = "example.com"
host_dev = "dev.example.com"

[features]
paywall = true

[purchases]
product_ids = ["a.monthly", "a.lifetime"]
"""


def storekit_json(*ids):
    import json
    return json.dumps({"products": [{"productID": i, "type": "NonConsumable"} for i in ids],
                       "subscriptionGroups": [], "nonRenewingSubscriptions": []})


class PreCommitStoreKitTests(PreCommitTests):
    """Khối (1b): id trong file .storekit phải khớp [purchases] product_ids khi commit đụng một trong hai."""

    # Không chạy lại các test của lớp cha trong lớp con.
    test_stage_mot_nua_bi_tu_choi = None
    test_xcconfig_cu_trong_index_bi_tu_choi_va_goi_y_render = None
    test_cau_hinh_hong_khong_goi_y_render = None
    test_features_yml_chua_add_bi_tu_choi = None
    test_stage_du_ca_hai_thi_qua = None

    def bat_paywall(self, *storekit_ids):
        self.write(appconfig.CONFIG_FILE, CONFIG + PAYWALL)
        self.render()
        self.write(appconfig.STOREKIT_CONFIG, storekit_json(*storekit_ids))
        self.git("add", "-A")

    def test_khop_thi_qua(self):
        self.bat_paywall("a.monthly", "a.lifetime")
        before = self.head()
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(self.head(), before)

    def test_lech_id_bi_tu_choi_neu_ten_id(self):
        self.bat_paywall("a.monthly")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("a.lifetime", r.stderr)

    def test_storekit_stage_mot_nua_bi_tu_choi(self):
        # Index có file khớp, working tree đã sửa lệch: lint đọc working tree ⇒ phải đòi stage trước.
        self.bat_paywall("a.monthly", "a.lifetime")
        self.assertEqual(self.commit().returncode, 0)
        self.write(appconfig.STOREKIT_CONFIG, storekit_json("a.monthly", "a.lifetime", "a.yearly"))
        self.git("add", appconfig.STOREKIT_CONFIG)
        self.write(appconfig.STOREKIT_CONFIG, storekit_json("a.monthly", "a.lifetime"))
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, "hook cho qua .storekit stage một nửa:\n" + r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("chưa stage", r.stderr)

    def test_khong_dung_hai_file_thi_khong_chay(self):
        # Paywall bật, .storekit lệch đã nằm sẵn trong repo; commit một file khác ⇒ khối (1b) không chạy.
        self.bat_paywall("a.monthly")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "lệch sẵn")
        self.write("ghi-chu.txt", "x\n")
        self.git("add", "ghi-chu.txt")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


WEB_CONFIG = CONFIG + '\n[web]\nhost_prod = "example.com"\nhost_dev = "dev.example.com"\n'
WEB_PAGE = "<!doctype html>\n<html lang=\"en\">\n<body>\n{body}\n</body>\n</html>\n"
WEB_PUBLIC = "web/site/public/"


def web_sitemap(day):
    urls = "".join(f"  <url>\n    <loc>https://example.com{p}</loc>\n    <lastmod>{day}</lastmod>\n  </url>\n"
                   for p in ("/", "/privacy/", "/terms/", "/support/"))
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset>\n{urls}</urlset>\n'


class PreCommitWebSiteTests(PreCommitTests):
    """Khối (1e): commit đụng web/site/public/ (hoặc app.config.toml) ⇒ check_sitemap --staged + check_site; repo không
    có web/tools ⇒ không làm gì."""

    test_stage_mot_nua_bi_tu_choi = None
    test_xcconfig_cu_trong_index_bi_tu_choi_va_goi_y_render = None
    test_cau_hinh_hong_khong_goi_y_render = None
    test_features_yml_chua_add_bi_tu_choi = None
    test_stage_du_ca_hai_thi_qua = None

    def setUp(self):
        super().setUp()
        for rel in ("web/tools/check_site.py", "web/tools/check_sitemap.py"):
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)
        self.write(appconfig.CONFIG_FILE, WEB_CONFIG)
        self.render()
        for rel in ("index.html", "privacy/index.html", "terms/index.html", "support/index.html"):
            self.write(WEB_PUBLIC + rel, WEB_PAGE.format(body="<p>x</p>"))
        self.write(WEB_PUBLIC + "sitemap.xml", web_sitemap("2000-01-01"))
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "site")

    def today(self):
        import datetime
        return datetime.date.today().isoformat()

    def test_sua_trang_ma_khong_sua_lastmod_bi_chan(self):
        self.write(WEB_PUBLIC + "terms/index.html", WEB_PAGE.format(body="<p>moi</p>"))
        self.git("add", "-A")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("https://example.com/terms/", r.stderr)
        self.write(WEB_PUBLIC + "sitemap.xml", web_sitemap(self.today()))
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_privacy_lech_cong_tac_bi_chan(self):
        self.write(WEB_PUBLIC + "privacy/index.html", WEB_PAGE.format(body='<p data-feature="paywall">mua</p>'))
        self.write(WEB_PUBLIC + "sitemap.xml", web_sitemap(self.today()))
        self.git("add", "-A")
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("paywall", r.stderr)

    def test_trang_chua_stage_bi_tu_choi(self):
        self.write(WEB_PUBLIC + "sitemap.xml", web_sitemap(self.today()))
        self.git("add", "-A")
        self.write(WEB_PUBLIC + "support/index.html", WEB_PAGE.format(body="<p>chua stage</p>"))
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("chưa stage", r.stderr)

    def test_khong_co_web_tools_thi_khong_chay(self):
        shutil.rmtree(self.root / "web/tools")
        self.git("add", "-A")
        self.write(WEB_PUBLIC + "privacy/index.html", WEB_PAGE.format(body='<p data-feature="paywall">mua</p>'))
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class PreCommitSwiftLintTests(PreCommitTests):
    """Khối (2): commit đụng .swift ⇒ lint cờ FEATURE_* / biên khối tuỳ chọn chạy và chặn thật."""

    # Không chạy lại các test của lớp cha trong lớp con.
    test_stage_mot_nua_bi_tu_choi = None
    test_xcconfig_cu_trong_index_bi_tu_choi_va_goi_y_render = None
    test_cau_hinh_hong_khong_goi_y_render = None
    test_features_yml_chua_add_bi_tu_choi = None
    test_stage_du_ca_hai_thi_qua = None

    def setUp(self):
        super().setUp()
        for rel in ("tools/i18n/lint_localizable.py", "tools/telemetry/lint_firebase_imports.py",
                    "tools/common/lint_feature_flag.py", "tools/release/lint_debug_symbols.py",
                    "tools/release/lint_preview_code.py", "tools/template/remove_sample.py",
                    "tools/template/blocks.py"):
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)
        self.write("tools/release/debug_symbols.txt", "")
        # remove_sample.py --check đòi gốc template: app.config.toml (lớp cha đã có) + AppHost/project.yml.
        self.write("AppHost/project.yml", "name: AppHost\n")
        self.write("Core/Bootstrap/A.swift", "struct A {}\n")
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "thêm lõi mẫu")

    def test_swift_sach_thi_qua(self):
        self.write("Core/Bootstrap/B.swift", "struct B {}\n")
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_co_feature_trong_core_bi_chan(self):
        self.write("Core/Bootstrap/B.swift", "#if FEATURE_WEB_API\nstruct B {}\n#endif\n")
        self.git("add", "-A")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("Core/Bootstrap/B.swift:1", r.stdout + r.stderr)
        self.assertIn("FEATURE_*", r.stderr)

    def test_symbol_mau_ngoai_khoi_bi_chan(self):
        self.write("AppHost/AppHost/Features/Sample/SampleX.swift", "struct SampleX {}\n")
        self.write("AppHost/AppHost/App.swift", "let s = SampleX()\n")
        self.git("add", "-A")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("AppHost/AppHost/App.swift:1", r.stdout + r.stderr)
        self.assertIn("biên tính năng mẫu", r.stderr)

    def test_doi_ten_thuan_file_swift_van_chay_lint(self):
        # File lỗi lọt vào repo (--no-verify); đổi tên THUẦN nó (status R) vẫn phải qua remove_sample --check.
        self.write("AppHost/AppHost/Features/Sample/SampleX.swift", "struct SampleX {}\n")
        self.write("AppHost/AppHost/Old.swift", "let s = SampleX()\n")
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "lỗi sẵn")
        self.git("mv", "AppHost/AppHost/Old.swift", "AppHost/AppHost/New.swift")
        names = self.git("diff", "--cached", "--name-status").stdout
        self.assertTrue(names.startswith("R"), names)
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("AppHost/AppHost/New.swift:1", r.stdout + r.stderr)

    def test_ten_file_swift_khong_ascii_van_chay_lint(self):
        # Mặc định git bọc tên không-ASCII thành "T\\303\\255nh.swift" ⇒ lọc `\\.swift$` trượt nếu không có
        # core.quotePath=false. Ép bật quotePath trong repo tạm để test không phụ thuộc cấu hình máy.
        self.git("config", "core.quotePath", "true")
        self.write("AppHost/AppHost/Features/Sample/SampleX.swift", "struct SampleX {}\n")
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "mẫu")
        self.write("AppHost/AppHost/Tính.swift", "let s = SampleX()\n")
        self.git("add", "-A")
        self.assertIn('"', self.git("diff", "--cached", "--name-only").stdout, "tiền đề: tên phải bị bọc khi quotePath bật")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("Tính.swift:1", r.stdout + r.stderr)

    def test_da_go_mau_thi_hook_van_qua(self):
        # App đã gỡ mẫu (không còn Features/Sample/) giữ hook: kiểu Sample… của chính app không bị chặn.
        self.write("AppHost/AppHost/Audio.swift", "struct SampleRateConverter {}\n")
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_co_feature_o_apphost_van_qua(self):
        self.write("AppHost/AppHost/AppHostApp.swift", "#if FEATURE_WEB_API\nstruct B {}\n#endif\n")
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_feature_o_file_apphost_khac_bi_chan(self):
        # Luật (d): cờ FEATURE_* chỉ ở AppHostApp.swift.
        self.write("AppHost/AppHost/App.swift", "#if FEATURE_WEB_API\nstruct B {}\n#endif\n")
        self.git("add", "-A")
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("AppHost/AppHost/App.swift:1", r.stdout + r.stderr)

    # --- khối 1c: danh sách symbol của app (AppHost/Config/debug_symbols.app.txt) ---
    APP_SYMS = "AppHost/Config/debug_symbols.app.txt"

    def test_file_symbol_app_moi_stage_kich_hoat_lint(self):
        # Chỉ stage file danh sách của app (không .swift): tên mồ côi trong đó phải bị lint bắt.
        self.write(self.APP_SYMS, "[binary]\nKhongConTonTai\n")
        self.git("add", self.APP_SYMS)
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("KhongConTonTai", r.stdout + r.stderr)

    def test_file_symbol_app_chua_stage_bi_tu_choi(self):
        self.write(self.APP_SYMS, "[binary]\n")
        self.git("add", self.APP_SYMS)
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "danh sách app")
        self.write(self.APP_SYMS, "[binary]\nKhongConTonTai\n")      # sửa nhưng KHÔNG stage
        self.write("Core/Bootstrap/B.swift", "struct B {}\n")
        self.git("add", "Core/Bootstrap/B.swift")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("CHƯA stage", r.stderr)
        self.assertIn(self.APP_SYMS, r.stderr)


class PreCommitManifestTests(PreCommitTests):
    """Khối (1d): ở template (không có core.lock), mọi file track phải thuộc một lớp của template.manifest.toml."""

    # Không chạy lại các test của lớp cha trong lớp con.
    test_stage_mot_nua_bi_tu_choi = None
    test_xcconfig_cu_trong_index_bi_tu_choi_va_goi_y_render = None
    test_cau_hinh_hong_khong_goi_y_render = None
    test_features_yml_chua_add_bi_tu_choi = None
    test_stage_du_ca_hai_thi_qua = None

    MANIFEST = "template.manifest.toml"
    MANIFEST_TEXT = (
        'schema = 1\n'
        '[sync]\npaths = [".githooks/", "tools/", "template.manifest.toml"]\n'
        '[seed]\npaths = ["app.config.toml", "AppHost/"]\n'
        '[template_only]\npaths = ["ghi-chu-rieng.md"]\n'
    )

    def setUp(self):
        super().setUp()
        for rel in ("tools/template/manifest.py", "tools/template/blocks.py"):
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)
        self.write(self.MANIFEST, self.MANIFEST_TEXT)
        self.write("ghi-chu-rieng.md", "# chỉ template\n")
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "thêm manifest")

    def test_cay_du_lop_thi_qua(self):
        self.write("tools/common/moi.py", "x = 1\n")
        self.git("add", "-A")
        before = self.head()
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(self.head(), before)

    def test_file_moi_chua_phan_lop_bi_chan(self):
        self.write("thu muc la/mới.txt", "x\n")
        self.git("add", "-A")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("thu muc la/mới.txt", r.stderr)
        self.assertIn(self.MANIFEST, r.stderr)

    def test_khai_file_moi_vao_manifest_thi_qua(self):
        self.write("thu muc la/mới.txt", "x\n")
        self.write(self.MANIFEST, self.MANIFEST_TEXT.replace('"AppHost/"]', '"AppHost/", "thu muc la/"]'))
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_manifest_chua_stage_bi_tu_choi(self):
        self.write("tools/common/moi.py", "x = 1\n")
        self.git("add", "-A")
        self.write(self.MANIFEST, self.MANIFEST_TEXT + "# sửa chưa stage\n")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("chưa stage", r.stderr)

    def test_manifest_hong_bi_chan(self):
        self.write(self.MANIFEST, self.MANIFEST_TEXT.replace("schema = 1", "schema = 9"))
        self.git("add", "-A")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("hỏng", r.stderr)

    def test_file_dong_bo_tro_toi_file_chi_template_bi_chan(self):
        # Hook chạy đủ luật (a)–(e): file sync nhắc đường dẫn của file chỉ-template ⇒ chặn; tên trần thì qua.
        self.write("tools/common/doc.md", "Xem `ghi-chu-rieng.md`.\n")
        self.git("add", "-A")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("tools/common/doc.md:1: nhắc ghi-chu-rieng.md", r.stderr)
        self.write("tools/common/doc.md", "Xem ghi chú riêng của template.\n")
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_co_core_lock_thi_khoi_khong_chay(self):
        # Repo là APP (không có dấu template, có core.lock): khối (1d) của template không chạy (khối 0 — lock khớp ⇒ qua).
        self.git("rm", "-q", TEMPLATE_MARKER)
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "thành app")
        dst = self.root / "tools/template/sync_core.py"
        shutil.copy2(REPO / "tools/template/sync_core.py", dst)
        sys.path.insert(0, str(REPO / "tools/template"))
        import manifest as mf
        import sync_core
        self.git("add", "-A")                     # build_lock lấy danh sách file từ git
        sync_core.write_lock(self.root, sync_core.build_lock(self.root, mf.load(self.root), source="x", tag="v0.0.1",
                                                             commit="c" * 40))
        self.write("thu muc la/mới.txt", "x\n")
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_template_khong_duoc_track_core_lock(self):
        # Template (có tools/template/new_app.py được track) + `git add core.lock` ⇒ chặn (nếu không: repo thành "app",
        # khối 1d tắt từ đó về sau).
        self.write("tools/template/new_app.py", "# chỉ template\n")
        self.write(self.MANIFEST, self.MANIFEST_TEXT)
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "template có new_app")
        self.write("core.lock", "{}\n")
        self.git("add", "core.lock")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("core.lock chỉ có ở app — repo template không được track file này", r.stderr)
        # Lock lạc CHƯA track ⇒ không vướng (commit file khác qua).
        self.git("rm", "-q", "--cached", "core.lock")
        self.write("tools/common/moi.py", "x = 1\n")
        self.git("add", "tools/common/moi.py")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_commit_dau_cua_template_qua(self):
        # HEAD chưa có (commit đầu của repository): loại repo xét theo index — có dấu template, không lock ⇒ template,
        # khối 1d chạy và qua. Đối chứng: cùng ca mà stage thêm core.lock ⇒ chặn (template không track lock).
        fresh = Path(self._tmp.name) / "template mới tinh"
        shutil.copytree(self.root, fresh, ignore=shutil.ignore_patterns(".git"))

        def g(*a):
            return subprocess.run(["git", *a], cwd=fresh, env=self.env, capture_output=True, text=True)

        g("init", "-q", "-b", "main")
        g("config", "core.hooksPath", ".githooks")
        g("add", "-A")
        self.assertNotEqual(g("rev-parse", "--verify", "-q", "HEAD").returncode, 0, "tiền đề: HEAD chưa có")
        (fresh / "core.lock").write_text("{}\n", encoding="utf-8")
        g("add", "core.lock")
        r = g(*GIT_ID, "commit", "-q", "-m", "khởi tạo template")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("repo template không được track file này", r.stderr)
        g("rm", "-q", "-f", "--cached", "core.lock")
        (fresh / "core.lock").unlink()
        r = g(*GIT_ID, "commit", "-q", "-m", "khởi tạo template")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(g("rev-parse", "--verify", "-q", "HEAD").returncode, 0)

    def test_nhanh_mo_coi_o_template_van_la_template(self):
        # `git checkout --orphan` ở template (lịch sử không có core.lock): vẫn là template ⇒ khối 1d chạy như thường.
        self.git("checkout", "-q", "--orphan", "mo-coi")
        self.write("thu muc la/mới.txt", "x\n")
        self.git("add", "-A")
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(self.MANIFEST, r.stderr)                 # luật của khối 1d, không phải "app thiếu lock"
        self.git("rm", "-q", "-f", "--cached", "thu muc la/mới.txt")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_template_xoa_manifest_py_thi_khoi_1d_bo_qua(self):
        # Hành vi hiện tại (ghi nhận): template không có lock mà xoá manifest.py ⇒ khối 1d tự bỏ qua (như repo tạm không
        # có tool) — cổng này chỉ báo sớm; manifest.py là file track nên selfcheck / `manifest.py check` thấy nó mất.
        self.git("rm", "-q", "tools/template/manifest.py")
        self.write("thu muc la/mới.txt", "x\n")
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_core_lock_lac_chua_track_van_chay_cong_manifest(self):
        # "App" = core.lock được TRACK. Lock lạc chưa add ở template ⇒ vẫn là template, khối (1d) vẫn chặn file chưa lớp.
        self.write("core.lock", "{}\n")
        self.write("thu muc la/mới.txt", "x\n")
        self.git("add", "thu muc la/mới.txt")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("thu muc la/mới.txt", r.stderr)

    def test_commit_a_doc_index_tam_cua_git(self):
        # `git commit -a` dựng index tạm (GIT_INDEX_FILE); .git/index lúc hook chạy còn nội dung CŨ. Xoá file duy nhất
        # khớp mục template_only rồi commit -a ⇒ mục không khớp file nào (luật b) — chỉ thấy được khi đọc index tạm.
        (self.root / "ghi-chu-rieng.md").unlink()
        before = self.head()
        r = self.git(*GIT_ID, "commit", "-q", "-a", "-m", "xoá")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn('mục "ghi-chu-rieng.md"', r.stderr)
        # Đối chứng: gỡ luôn mục khỏi manifest (stage một phần, rồi commit -a gom phần còn lại) ⇒ qua.
        self.write(self.MANIFEST, self.MANIFEST_TEXT.replace('"ghi-chu-rieng.md"', ''))
        self.git("add", self.MANIFEST)
        r = self.git(*GIT_ID, "commit", "-q", "-a", "-m", "xoá cả mục")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(self.head(), before)


GUIDANCE = "File này do template sở hữu — sửa ở template rồi chạy tools/template/sync_core.py sync --to <tag>"


class PreCommitCoreLockTests(PreCommitTests):
    """Khối (0): ở app (có core.lock), file lớp đồng bộ phải khớp digest trong core.lock — đọc từ index đang commit."""

    # Không chạy lại các test của lớp cha trong lớp con.
    test_stage_mot_nua_bi_tu_choi = None
    test_xcconfig_cu_trong_index_bi_tu_choi_va_goi_y_render = None
    test_cau_hinh_hong_khong_goi_y_render = None
    test_features_yml_chua_add_bi_tu_choi = None
    test_stage_du_ca_hai_thi_qua = None

    MANIFEST_TEXT = (
        'schema = 1\n'
        '[sync]\npaths = [".githooks/", "tools/", "Loi/", "template.manifest.toml"]\n'
        '[seed]\npaths = ["app.config.toml", "AppHost/"]\n'
        '[template_only]\npaths = []\n'
    )

    def setUp(self):
        super().setUp()
        for rel in ("tools/template/manifest.py", "tools/template/blocks.py", "tools/template/sync_core.py"):
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)
        self.git("rm", "-q", TEMPLATE_MARKER)       # mô phỏng APP: không có dấu template
        self.write("template.manifest.toml", self.MANIFEST_TEXT)
        self.write("Loi/loi.txt", "lõi của template\n")
        self.write_lock()
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "app có core.lock")

    def write_lock(self, tag="v0.4.0"):
        sys.path.insert(0, str(REPO / "tools/template"))
        import manifest as mf
        import sync_core
        self.git("add", "-A")                     # build_lock lấy danh sách file từ git (ls-files)
        sync_core.write_lock(self.root, sync_core.build_lock(self.root, mf.load(self.root), source="/nguon",
                                                             tag=tag, commit="d" * 40))

    def assert_refused(self, r, before, *paths):
        self.assertNotEqual(r.returncode, 0, "hook cho qua file đồng bộ sửa tay:\n" + r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        for rel in paths:
            self.assertIn(rel, r.stderr)
        self.assertIn(GUIDANCE, r.stderr)

    def test_sua_loi_o_app_bi_chan_co_loi_chi_duong(self):
        self.write("Loi/loi.txt", "sửa tay ở app\n")
        self.git("add", "-A")
        before = self.head()
        self.assert_refused(self.commit(), before, "M Loi/loi.txt")
        # Xoá file đồng bộ cũng bị chặn (D).
        self.git("rm", "-q", "-f", "Loi/loi.txt")
        self.assert_refused(self.commit(), before, "D Loi/loi.txt")

    def test_staged_sua_tay_roi_hoan_working_tree_van_bi_chan(self):
        # Hook so INDEX (thứ được commit), không so working tree: stage bản sửa tay rồi hoàn file trên đĩa ⇒ vẫn chặn.
        self.write("Loi/loi.txt", "sửa tay ở app\n")
        self.git("add", "Loi/loi.txt")
        self.write("Loi/loi.txt", "lõi của template\n")
        before = self.head()
        self.assert_refused(self.commit(), before, "M Loi/loi.txt")

    def test_commit_cua_dong_bo_qua(self):
        # Lệnh đồng bộ thay file + ghi lock mới, stage cả hai ⇒ qua.
        self.write("Loi/loi.txt", "lõi bản mới của template\n")
        self.write_lock("v0.5.0")
        self.git("add", "Loi/loi.txt", "core.lock")
        before = self.head()
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(self.head(), before)

    def test_commit_a_sua_tay_bi_chan(self):
        # `git commit -a`: hook nhận index tạm qua GIT_INDEX_FILE; .git/index còn bản cũ (khớp lock) — phải đọc index tạm.
        self.write("Loi/loi.txt", "sửa tay rồi commit -a\n")
        before = self.head()
        self.assert_refused(self.git(*GIT_ID, "commit", "-q", "-a", "-m", "sửa tay"), before, "M Loi/loi.txt")

    def test_commit_chi_dinh_file_sua_tay_bi_chan(self):
        # `git commit <file>`: index tạm next-index-*.lock.
        self.write("Loi/loi.txt", "sửa tay rồi commit <file>\n")
        before = self.head()
        self.assert_refused(self.git(*GIT_ID, "commit", "-q", "-m", "sửa tay", "--", "Loi/loi.txt"), before,
                            "M Loi/loi.txt")

    def test_commit_a_cua_dong_bo_qua(self):
        self.write("Loi/loi.txt", "lõi bản mới của template\n")
        self.write_lock("v0.5.0")
        before = self.head()
        r = self.git(*GIT_ID, "commit", "-q", "-a", "-m", "đồng bộ")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(self.head(), before)

    def test_file_rieng_cua_app_qua(self):
        self.write("AppHost/ghi-chu.txt", "riêng app\n")
        self.write("moi.txt", "không thuộc lớp nào — ở app không sao\n")
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_lock_hong_bi_chan(self):
        self.write("core.lock", "{ hỏng\n")
        self.git("add", "core.lock")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("core.lock bị gỡ, hỏng", r.stderr)

    # --- "app" = core.lock được track: xoá / gỡ lock không tắt cổng ---

    def test_git_rm_lock_va_sua_loi_bi_chan(self):
        self.write("Loi/loi.txt", "sửa tay ở app\n")
        self.git("add", "Loi/loi.txt")
        self.git("rm", "-q", "core.lock")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("git restore --staged --worktree core.lock", r.stderr)

    def test_xoa_lock_roi_commit_a_bi_chan(self):
        self.write("Loi/loi.txt", "sửa tay ở app\n")
        (self.root / "core.lock").unlink()
        before = self.head()
        r = self.git(*GIT_ID, "commit", "-q", "-a", "-m", "xoá lock")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("git restore --staged --worktree core.lock", r.stderr)

    def test_xoa_lock_cung_cong_cu_van_bi_chan(self):
        # "Là app" quyết định bằng git thuần (HEAD còn lock): gỡ cả lock lẫn công cụ Python của cổng không tắt được cổng.
        for tools in (("tools/template/manifest.py",), ("tools/template/manifest.py", "tools/template/sync_core.py")):
            with self.subTest(tools=tools):
                self.git("rm", "-q", "core.lock", *tools)
                self.write("Loi/loi.txt", "sửa tay ở app\n")
                self.git("add", "Loi/loi.txt")
                before = self.head()
                r = self.commit()
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.head(), before)
                # Luật "HEAD có lock, commit không có" đứng trước mọi luật theo loại repo ⇒ báo lock trước …
                self.assertIn("git restore --staged --worktree core.lock", r.stderr)
                # … khôi phục lock rồi thì báo tới công cụ còn thiếu.
                self.git("restore", "--source=HEAD", "--staged", "--worktree", "--", "core.lock")
                r = self.commit()
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.head(), before)
                self.assertIn("thiếu tools/template/manifest.py", r.stderr)
                self.assertIn("git restore --staged --worktree tools/template/manifest.py", r.stderr)
                self.git("restore", "--source=HEAD", "--staged", "--worktree", "--", "core.lock", "Loi/loi.txt", *tools)

    def test_xoa_ba_file_tren_dia_roi_commit_a_bi_chan(self):
        for rel in ("core.lock", "tools/template/manifest.py", "tools/template/sync_core.py"):
            (self.root / rel).unlink()
        self.write("Loi/loi.txt", "sửa tay ở app\n")
        before = self.head()
        r = self.git(*GIT_ID, "commit", "-q", "-a", "-m", "xoá cổng")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("git restore --staged --worktree core.lock", r.stderr)
        # Khôi phục riêng lock ⇒ lần commit -a kế tiếp báo công cụ còn thiếu.
        self.git("restore", "--source=HEAD", "--staged", "--worktree", "--", "core.lock")
        r = self.git(*GIT_ID, "commit", "-q", "-a", "-m", "xoá cổng")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("thiếu tools/template/manifest.py", r.stderr)

    def test_lock_go_da_commit_khong_verify_thi_commit_sau_bi_chan(self):
        # Gỡ lock rồi commit bằng --no-verify ⇒ repo không dấu template, không lock: commit KẾ TIẾP qua hook bị chặn.
        for tools in ((), ("tools/template/manifest.py", "tools/template/sync_core.py")):
            with self.subTest(tools=tools):
                self.git("rm", "-q", "core.lock", *tools)
                self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "gỡ lock")
                self.write("moi.txt", f"x {len(tools)}\n")
                self.git("add", "moi.txt")
                before = self.head()
                r = self.commit()
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.head(), before)
                self.assertIn("git log --diff-filter=D --oneline", r.stderr)
                self.assertIn("thiếu tools/template/manifest.py" if tools else "không có core.lock", r.stderr)
                # Khôi phục từ lịch sử đúng như hướng dẫn, rồi commit được.
                self.git("checkout", "HEAD^", "--", "core.lock", *tools)
                r = self.commit()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_git_rm_cached_lock_bi_chan(self):
        self.git("rm", "-q", "--cached", "core.lock")
        self.write("moi.txt", "x\n")
        self.git("add", "moi.txt")
        before = self.head()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.head(), before)
        self.assertIn("core.lock", r.stderr)

    def test_commit_dau_cua_app_moi_qua(self):
        # App mới: HEAD chưa có (unborn), lock đã stage cùng mọi file ⇒ khối 0 chạy và qua.
        fresh = Path(self._tmp.name) / "app mới tinh"
        shutil.copytree(self.root, fresh, ignore=shutil.ignore_patterns(".git"))
        env = self.env
        def g(*a):
            return subprocess.run(["git", *a], cwd=fresh, env=env, capture_output=True, text=True)
        g("init", "-q", "-b", "main")
        g("config", "core.hooksPath", ".githooks")
        g("add", "-A")
        self.assertNotEqual(g("rev-parse", "--verify", "-q", "HEAD").returncode, 0, "tiền đề: HEAD chưa có")
        r = g(*GIT_ID, "commit", "-q", "-m", "khởi tạo app")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # Đối chứng: cùng ca nhưng lõi đã bị sửa ⇒ chặn ngay từ commit đầu.
        fresh2 = Path(self._tmp.name) / "app mới tinh 2"
        shutil.copytree(self.root, fresh2, ignore=shutil.ignore_patterns(".git"))
        (fresh2 / "Loi/loi.txt").write_text("sửa trước commit đầu\n", encoding="utf-8")
        for a in (("init", "-q", "-b", "main"), ("config", "core.hooksPath", ".githooks"), ("add", "-A")):
            subprocess.run(["git", *a], cwd=fresh2, env=env, capture_output=True)
        r = subprocess.run(["git", *GIT_ID, "commit", "-q", "-m", "khởi tạo"], cwd=fresh2, env=env,
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("M Loi/loi.txt", r.stderr)

    # --- loại repo do HEAD quyết định; không commit nào qua hook làm mất lock hay biến app thành "template" ---

    def add_marker(self, root=None):
        root = root or self.root
        (root / TEMPLATE_MARKER).write_text("", encoding="utf-8")
        r = subprocess.run(["git", "add", TEMPLATE_MARKER], cwd=root, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def drop_marker(self):
        self.git("rm", "-q", "-f", "--cached", TEMPLATE_MARKER)
        (self.root / TEMPLATE_MARKER).unlink(missing_ok=True)

    def assert_blocked(self, r, before):
        self.assertNotEqual(r.returncode, 0, "hook cho qua:\n" + r.stdout + r.stderr)
        self.assertEqual(self.head(), before)

    def test_go_lock_them_dau_template_trong_mot_commit_bi_chan(self):
        # Tái hiện review vòng 3: `git rm core.lock [+ hai công cụ]` + thêm new_app.py rỗng + sửa lõi trong MỘT commit.
        # HEAD không có dấu template ⇒ vẫn là app ngay trong commit đó.
        gate_tools = ("tools/template/manifest.py", "tools/template/sync_core.py")
        for tools in ((), gate_tools):
            with self.subTest(tools=tools):
                self.git("rm", "-q", "core.lock", *tools)
                self.add_marker()
                self.write("Loi/loi.txt", "sửa tay ở app\n")
                self.git("add", "Loi/loi.txt")
                before = self.head()
                r = self.commit()
                self.assert_blocked(r, before)
                self.assertIn("git restore --staged --worktree core.lock", r.stderr)
                self.drop_marker()
                self.git("restore", "--source=HEAD", "--staged", "--worktree", "--", "core.lock", "Loi/loi.txt", *tools)
        # Đối chứng: repo tạm đã về nguyên trạng ⇒ commit file riêng của app qua (hook không chặn bừa).
        self.write("AppHost/ghi-chu.txt", "riêng app\n")
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_go_lock_them_dau_template_roi_commit_a_bi_chan(self):
        # Cùng ca, qua index tạm của `git commit -a`: dấu đã stage, lock + công cụ xoá trên đĩa, lõi sửa trên đĩa.
        gate_tools = ("tools/template/manifest.py", "tools/template/sync_core.py")
        for tools in ((), gate_tools):
            with self.subTest(tools=tools):
                self.add_marker()
                for rel in ("core.lock", *tools):
                    (self.root / rel).unlink()
                self.write("Loi/loi.txt", "sửa tay ở app\n")
                before = self.head()
                r = self.git(*GIT_ID, "commit", "-q", "-a", "-m", "giả làm template")
                self.assert_blocked(r, before)
                self.assertIn("git restore --staged --worktree core.lock", r.stderr)
                self.drop_marker()
                self.git("restore", "--source=HEAD", "--staged", "--worktree", "--", "core.lock", "Loi/loi.txt", *tools)

    def test_app_da_mat_lock_them_dau_template_van_la_app(self):
        # App đã mất lock (commit --no-verify trước đó): thêm dấu template ở commit kế tiếp KHÔNG biến nó thành template
        # — loại repo xét theo HEAD (chưa có dấu), không theo index đang commit.
        self.git("rm", "-q", "core.lock")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "gỡ lock")
        self.add_marker()
        self.write("Loi/loi.txt", "sửa tay ở app\n")
        self.git("add", "Loi/loi.txt")
        before = self.head()
        self.assert_blocked(self.commit(), before)

    def test_app_them_dau_template_giu_lock_bi_chan(self):
        # Thêm dấu template mà GIỮ lock. Ở fixture mặc định `tools/` là lớp đồng bộ; ở app thật manifest xếp file đánh
        # dấu vào template_only ⇒ luật A của sync_core không thấy nó (tiền đề kiểm ngay dưới) — hook phải tự chặn, nếu
        # không commit kế tiếp coi repo là "template".
        for real_manifest in (False, True):
            with self.subTest(real_manifest=real_manifest):
                if real_manifest:
                    self.write("template.manifest.toml", self.MANIFEST_TEXT.replace(
                        '[template_only]\npaths = []', f'[template_only]\npaths = ["{TEMPLATE_MARKER}"]'))
                    self.write_lock()
                    self.git("add", "-A")
                    self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "manifest như app thật")
                self.add_marker()
                if real_manifest:
                    r = subprocess.run([sys.executable, "tools/template/sync_core.py", "check", "--staged", "--root",
                                        str(self.root)], cwd=self.root, env=self.env, capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, "tiền đề: sync_core không báo file đánh dấu\n" + r.stdout + r.stderr)
                before = self.head()
                self.assert_blocked(self.commit(), before)
                self.assert_blocked(self.git(*GIT_ID, "commit", "-q", "-a", "-m", "thử"), before)
                self.drop_marker()

    def test_head_co_lock_ma_commit_khong_co_thi_chan_bat_ke_loai(self):
        # HEAD track CẢ dấu template lẫn lock (chỉ tới được bằng --no-verify) ⇒ loại = template, khối app không chạy;
        # commit làm mất lock vẫn bị chặn bởi luật "HEAD có lock, commit không có".
        self.add_marker()
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "có cả hai dấu")
        before = self.head()
        for how in ("rm", "rm --cached", "commit -a"):
            with self.subTest(how=how):
                if how == "commit -a":
                    (self.root / "core.lock").unlink()
                    r = self.git(*GIT_ID, "commit", "-q", "-a", "-m", "gỡ lock")
                else:
                    self.git(*how.split(), "-q", "core.lock")
                    r = self.commit()
                self.assert_blocked(r, before)
                self.assertIn("HEAD có core.lock nhưng commit này không có", r.stderr)
                self.assertIn("git restore --staged --worktree core.lock", r.stderr)
                self.git("restore", "--source=HEAD", "--staged", "--worktree", "--", "core.lock")
        # Giữ lock ⇒ "template track lock" cũng bị chặn; thông báo nêu lối ra thay vì chỉ ngược lại khối trên.
        self.write("moi.txt", "x\n")
        self.git("add", "moi.txt")
        r = self.commit()
        self.assert_blocked(r, before)
        self.assertIn(f"git rm {TEMPLATE_MARKER}", r.stderr)
        self.assertNotIn("HEAD có core.lock nhưng commit này không có", r.stderr)
        # Lối ra của app đúng như thông báo: gỡ file đánh dấu bằng một commit --no-verify ⇒ commit thường lại qua.
        self.git("rm", "-q", TEMPLATE_MARKER)
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "gỡ dấu template", "--", TEMPLATE_MARKER)
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_nhanh_mo_coi_khong_bien_app_thanh_template(self):
        # `git checkout --orphan`: HEAD chưa có nhưng repo ĐÃ có lịch sử mang core.lock ⇒ index có dấu template cũng
        # không thành template ("HEAD chưa có ⇒ xét index" chỉ dành cho commit đầu của một repository).
        self.git("checkout", "-q", "--orphan", "mo-coi")
        self.assertNotEqual(self.git("rev-parse", "--verify", "-q", "HEAD").returncode, 0, "tiền đề: HEAD chưa có")
        self.git("rm", "-q", "--cached", "core.lock")
        self.add_marker()
        self.write("Loi/loi.txt", "sửa tay ở app\n")
        self.git("add", "Loi/loi.txt")
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, "hook cho qua:\n" + r.stdout + r.stderr)
        self.assertNotEqual(self.git("rev-parse", "--verify", "-q", "HEAD").returncode, 0, "không được tạo commit")
        # Xoá luôn nhánh cũ (repo không còn ref nào): reflog của HEAD vẫn cho thấy lịch sử có lock ⇒ vẫn chặn.
        self.assertEqual(self.git("branch", "-q", "-D", "main").returncode, 0)
        self.assertEqual(self.git("for-each-ref").stdout.strip(), "", "tiền đề: không còn ref")
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, "hook cho qua:\n" + r.stdout + r.stderr)
        self.assertNotEqual(self.git("rev-parse", "--verify", "-q", "HEAD").returncode, 0, "không được tạo commit")
        # Đối chứng: nhánh mồ côi của app còn nguyên lock, không dấu, lõi khớp ⇒ qua.
        self.drop_marker()
        self.write("Loi/loi.txt", "lõi của template\n")
        self.git("add", "core.lock", "Loi/loi.txt")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_lock_intent_to_add_khong_lach_duoc(self):
        # `git add -N core.lock`: mục có trong index nhưng KHÔNG vào cây của commit. Khối 0 đọc lock từ index ⇒ rỗng ⇒ chặn.
        self.git("rm", "-q", "--cached", "core.lock")
        self.git("add", "-N", "core.lock")
        self.write("moi.txt", "x\n")
        self.git("add", "moi.txt")
        before = self.head()
        self.assert_blocked(self.commit(), before)

    def test_worktree_phu_va_thu_muc_con_cung_luat(self):
        # Cây phụ (`git worktree add`) + commit từ thư mục con: cùng luật, cùng kết quả.
        wt = Path(self._tmp.name) / "cây phụ có dấu cách"
        r = self.git("worktree", "add", "-q", "-b", "phu", str(wt))
        self.assertEqual(r.returncode, 0, r.stderr)
        sub = wt / "Loi"

        def g(*a, cwd=sub):
            return subprocess.run(["git", *a], cwd=cwd, env=self.env, capture_output=True, text=True)

        before = g("rev-parse", "HEAD").stdout.strip()
        # (1) gỡ lock + thêm dấu template + sửa lõi, commit từ thư mục con của cây phụ ⇒ chặn.
        self.assertEqual(g("rm", "-q", "../core.lock").returncode, 0)
        self.add_marker(wt)
        (sub / "loi.txt").write_text("sửa tay ở app\n", encoding="utf-8")
        g("add", "loi.txt")
        r = g(*GIT_ID, "commit", "-q", "-m", "giả làm template")
        self.assertNotEqual(r.returncode, 0, "hook cho qua:\n" + r.stdout + r.stderr)
        self.assertEqual(g("rev-parse", "HEAD").stdout.strip(), before)
        self.assertIn("git restore --staged --worktree core.lock", r.stderr)
        g("rm", "-q", "-f", "--cached", TEMPLATE_MARKER, cwd=wt)
        (wt / TEMPLATE_MARKER).unlink()
        g("restore", "--source=HEAD", "--staged", "--worktree", "--", "core.lock", "Loi/loi.txt", cwd=wt)
        # (2) xoá lock trên đĩa rồi `commit -a` từ thư mục con ⇒ chặn.
        (wt / "core.lock").unlink()
        r = g(*GIT_ID, "commit", "-q", "-a", "-m", "xoá lock")
        self.assertNotEqual(r.returncode, 0, "hook cho qua:\n" + r.stdout + r.stderr)
        self.assertEqual(g("rev-parse", "HEAD").stdout.strip(), before)
        g("restore", "--source=HEAD", "--staged", "--worktree", "--", "core.lock", cwd=wt)
        # (3) sửa lõi tay ⇒ chặn (M); (4) file riêng của app ⇒ qua.
        (sub / "loi.txt").write_text("sửa tay ở app\n", encoding="utf-8")
        r = g(*GIT_ID, "commit", "-q", "-a", "-m", "sửa tay")
        self.assertNotEqual(r.returncode, 0, "hook cho qua:\n" + r.stdout + r.stderr)
        self.assertIn("M Loi/loi.txt", r.stderr)
        g("restore", "--source=HEAD", "--staged", "--worktree", "--", "Loi/loi.txt", cwd=wt)
        (wt / "AppHost").mkdir(exist_ok=True)
        (wt / "AppHost" / "ghi-chu.txt").write_text("riêng app\n", encoding="utf-8")
        g("add", "../AppHost/ghi-chu.txt")
        r = g(*GIT_ID, "commit", "-q", "-m", "file của app")          # commit thường, vẫn từ thư mục con
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(g("rev-parse", "HEAD").stdout.strip(), before)

    # --- luật A: file mới trong thư mục lớp đồng bộ ---

    def test_file_moi_trong_thu_muc_dong_bo_bi_chan(self):
        for rel in ("Loi/Moi.swift", ".githooks/pre-push"):
            with self.subTest(rel=rel):
                self.write(rel, "x\n")
                self.git("add", rel)
                before = self.head()
                r = self.commit()
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.head(), before)
                self.assertIn(f"A {rel}", r.stderr)
                self.assertIn("File mới nằm trong thư mục do template sở hữu", r.stderr)
                self.assertNotIn(GUIDANCE, r.stderr)
                self.git("rm", "-q", "--cached", rel)

    def test_agent_skill_va_bai_hoc_cua_app_duoc_them(self):
        # Manifest khai harness TỪNG FILE / từng skill ⇒ agent, skill mới của app không thuộc lớp nào ⇒ được thêm.
        self.write("template.manifest.toml", self.MANIFEST_TEXT.replace(
            '"Loi/", ', '"Loi/", ".claude/agents/goc.md", ".claude/skills/goc/", "docs/lessons-learned/", ').replace(
            '"AppHost/"]', '"AppHost/", "docs/lessons-learned/app/"]'))
        self.write(".claude/agents/goc.md", "# gốc\n")
        self.write(".claude/skills/goc/SKILL.md", "# gốc\n")
        self.write("docs/lessons-learned/chung.md", "# chung\n")
        self.write("docs/lessons-learned/app/README.md", "# app\n")
        self.write_lock()
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "harness")
        self.write(".claude/agents/my-app-agent.md", "# app\n")
        self.write(".claude/skills/my-skill/SKILL.md", "# app\n")
        self.write("docs/lessons-learned/app/bai-hoc.md", "# app\n")
        self.git("add", "-A")
        # Chạy đúng lệnh khối 0 gọi (commit thật sẽ vướng khối 3 — lint harness không có trong repo tạm).
        r = subprocess.run([sys.executable, "tools/template/sync_core.py", "check", "--staged", "--root", str(self.root)],
                           cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.write(".claude/skills/goc/them.md", "# lén vào skill của template\n")
        self.git("add", "-A")
        r = subprocess.run([sys.executable, "tools/template/sync_core.py", "check", "--staged", "--root", str(self.root)],
                           cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (1, "A .claude/skills/goc/them.md"))

    def test_template_khong_co_lock_khong_chay_khoi_0(self):
        # Template (có dấu new_app.py, không có core.lock): khối 0 không chạy — sửa file "đồng bộ" thoải mái.
        self.git("rm", "-q", "core.lock")
        self.write(TEMPLATE_MARKER, "")
        self.git("add", TEMPLATE_MARKER)
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "về template")
        self.write("Loi/loi.txt", "template sửa lõi của chính nó\n")
        self.git("add", "-A")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(GUIDANCE, r.stderr)


if __name__ == "__main__":
    unittest.main()
