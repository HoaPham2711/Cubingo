"""Test cho appconfig — mỗi test dựng một repo git tạm, không đụng repo thật."""
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import appconfig  # noqa: E402

APPCONFIG_PY = str(HERE / "appconfig.py")
REPO = HERE.parents[1]
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
host_prod = "example.com"
host_dev = "dev.example.com"
app_paths = ["/items", "/items/*"]

[cloudflare]
d1_prod = ""
d1_dev = ""

[firebase]
app_check_prod = ""
app_check_dev = ""

[support]
email = "support@example.com"

[features]
paywall = true
web_api = true
apple_ads = true

[purchases]
product_ids = ["pro.monthly", "pro.yearly", "pro.lifetime"]
subscription_group = "pro"

[store]
locales = ["en-US"]

[analytics]
ga4_property = ""
bq_project = ""

[i18n]
languages = ["en"]
"""

GIT = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com"]


class AppConfigTests(unittest.TestCase):
    VALID = SAMPLE_CONFIG

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.write_config(self.VALID)

    def write_config(self, text):
        (self.root / "app.config.toml").write_text(text, encoding="utf-8")

    def test_load_doc_dung_gia_tri(self):
        cfg = appconfig.load(self.root)
        self.assertEqual(appconfig.get(cfg, "bundle.store"), "com.example.sample")
        self.assertEqual(appconfig.get(cfg, "features.paywall"), True)

    def test_thieu_khoa_bao_ten_khoa(self):
        self.write_config(self.VALID.replace('team_id = "0000000000"\n', ""))
        with self.assertRaisesRegex(appconfig.ConfigError, r"apple\.team_id"):
            appconfig.load(self.root)

    def test_gia_tri_sai_dang_bao_ten_khoa(self):
        self.write_config(self.VALID.replace('build = "1"', 'build = "1a"'))
        with self.assertRaisesRegex(appconfig.ConfigError, r"version\.build"):
            appconfig.load(self.root)

    def test_bundle_store_trung_internal_bi_tu_choi(self):
        self.write_config(self.VALID.replace("com.example.sample.internal", "com.example.sample"))
        with self.assertRaisesRegex(appconfig.ConfigError, r"bundle\.internal"):
            appconfig.load(self.root)

    def test_get_khoa_khong_ton_tai(self):
        with self.assertRaisesRegex(appconfig.ConfigError, r"khong\.co"):
            appconfig.get(appconfig.load(self.root), "khong.co")

    def test_ten_hien_thi_unicode_va_dau_nhay_giu_nguyen(self):
        self.write_config(self.VALID.replace('display_name = "Sample"', 'display_name = "Bé\'s Notes 2"'))
        out = appconfig.render_xcconfig(appconfig.load(self.root))
        self.assertIn("APP_DISPLAY_NAME_STORE = Bé's Notes 2\n", out)

    def test_ten_hien_thi_chua_comment_xcconfig_bi_tu_choi(self):
        self.write_config(self.VALID.replace('display_name = "Sample"', 'display_name = "A // B"'))
        with self.assertRaisesRegex(appconfig.ConfigError, r"app\.display_name"):
            appconfig.load(self.root)

    def test_xcconfig_cu_bi_phat_hien(self):
        cfg = appconfig.load(self.root)
        self.assertTrue(appconfig.write_xcconfig(self.root, cfg))
        self.assertTrue(appconfig.is_xcconfig_fresh(self.root, cfg))
        self.write_config(self.VALID.replace('build = "1"', 'build = "2"'))
        self.assertFalse(appconfig.is_xcconfig_fresh(self.root, appconfig.load(self.root)))

    def test_tim_goc_repo_tu_thu_muc_con(self):
        sub = self.root / "AppHost" / "AppHost"
        sub.mkdir(parents=True)
        self.assertEqual(appconfig.repo_root(sub).resolve(), self.root.resolve())

    def test_tim_goc_repo_tu_worktree(self):
        subprocess.run(GIT + ["commit", "-q", "--allow-empty", "-m", "init"], cwd=self.root, check=True)
        wt = Path(self._tmp.name) / "wt"
        subprocess.run(GIT + ["worktree", "add", "-q", str(wt)], cwd=self.root, check=True)
        self.assertEqual(appconfig.repo_root(wt).resolve(), wt.resolve())

    def test_cli_loi_cau_hinh_rc2_khong_traceback(self):
        self.write_config("[app]\n")
        r = subprocess.run([sys.executable, APPCONFIG_PY, "get", "app.slug"],
                           cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("FAIL:", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_fixture_plist_theo_config(self):
        cfg = appconfig.load(self.root)
        self.assertEqual(plistlib.loads(appconfig.fixture_plist(cfg, "Release"))["BUNDLE_ID"], "com.example.sample")
        self.assertEqual(plistlib.loads(appconfig.fixture_plist(cfg, "Debug"))["BUNDLE_ID"], "com.example.sample.internal")

    def test_gia_tri_rong_khong_co_khoang_trang_thua(self):
        out = appconfig.render_xcconfig(appconfig.load(self.root))
        self.assertIn("APP_STORE_ID =\n", out)
        self.assertNotIn(" \n", out)

    # --- I9: giá trị mà xcconfig sẽ làm đổi phải bị từ chối ngay ở load() ---

    def assert_tu_choi(self, old, new, key_rx):
        self.assertIn(old, self.VALID)
        self.write_config(self.VALID.replace(old, new))
        with self.assertRaisesRegex(appconfig.ConfigError, key_rx):
            appconfig.load(self.root)

    def test_slug_co_xuong_dong_cuoi_bi_tu_choi(self):
        self.assert_tu_choi('slug = "sample"', 'slug = "sample\\n"', r"app\.slug")

    def test_bundle_id_co_xuong_dong_cuoi_bi_tu_choi(self):
        self.assert_tu_choi('store = "com.example.sample"', 'store = "com.example.sample\\n"', r"bundle\.store")

    def test_build_co_xuong_dong_cuoi_bi_tu_choi(self):
        self.assert_tu_choi('build = "1"', 'build = "1\\n"', r"version\.build")

    def test_ten_hien_thi_co_bien_xcconfig_bi_tu_choi(self):
        self.assert_tu_choi('display_name = "Sample"', 'display_name = "${PRODUCT_NAME}"', r"app\.display_name")

    def test_ten_hien_thi_khoang_trang_dau_bi_tu_choi(self):
        self.assert_tu_choi('display_name = "Sample"', 'display_name = " Sample"', r"app\.display_name")

    def test_ten_hien_thi_khoang_trang_cuoi_bi_tu_choi(self):
        self.assert_tu_choi('display_name_internal = "Sample Dev"', 'display_name_internal = "Sample Dev "',
                            r"app\.display_name_internal")

    def test_gia_tri_hop_le_van_qua(self):
        text = (self.VALID.replace('display_name = "Sample"', 'display_name = "Bé\'s Notes 2"')
                .replace("com.example.sample.internal", "dev.thu-nghiem.GhiChu.noibo")
                .replace('store = "com.example.sample"', 'store = "dev.thu-nghiem.GhiChu"')
                .replace('host_prod = "example.com"', 'host_prod = "api.example.com"')
                .replace('host_dev = "dev.example.com"', 'host_dev = "dev-api.example.com"'))
        self.write_config(text)
        cfg = appconfig.load(self.root)
        self.assertEqual(appconfig.get(cfg, "bundle.store"), "dev.thu-nghiem.GhiChu")
        self.assertEqual(appconfig.get(cfg, "web.host_prod"), "api.example.com")

    # --- I8 / R8: web.* + lược đồ chặt ---

    def test_web_host_co_scheme_bi_tu_choi(self):
        self.assert_tu_choi('host_prod = "example.com"', 'host_prod = "https://example.com"', r"web\.host_prod")

    def test_web_host_so_nguyen_bi_tu_choi(self):
        self.assert_tu_choi('host_dev = "dev.example.com"', 'host_dev = 5', r"web\.host_dev")

    def test_web_host_co_duong_dan_hoac_khoang_trang_bi_tu_choi(self):
        self.assert_tu_choi('host_prod = "example.com"', 'host_prod = "example.com/api"', r"web\.host_prod")
        self.assert_tu_choi('host_prod = "example.com"', 'host_prod = "example .com"', r"web\.host_prod")

    def test_thieu_muc_web_van_qua_khi_tat_web_api(self):
        text = (self.VALID.replace('[web]\nhost_prod = "example.com"\nhost_dev = "dev.example.com"\napp_paths = ["/items", "/items/*"]\n', "")
                .replace("web_api = true", "web_api = false").replace("paywall = true", "paywall = false"))
        self.write_config(text)
        self.assertNotIn("[web]", (self.root / "app.config.toml").read_text(encoding="utf-8"))
        out = appconfig.render_xcconfig(appconfig.load(self.root))
        self.assertIn("APP_WEB_HOST_PROD =\n", out)
        self.assertIn("APP_FEATURE_WEB_API = NO\n", out)

    # --- P2 Task 1: công tắc tính năng, sản phẩm, email hỗ trợ, Features.generated.yml ---

    def test_render_sinh_ca_features_yml(self):
        cfg = appconfig.load(self.root); appconfig.write_generated(self.root, cfg)
        self.assertTrue((self.root / appconfig.FEATURES_YML).exists())
        self.assertTrue(appconfig.is_generated_fresh(self.root, cfg))

    def test_features_yml_cu_hoac_thieu_bi_phat_hien(self):
        cfg = appconfig.load(self.root)
        appconfig.write_generated(self.root, cfg)
        feat = self.root / appconfig.FEATURES_YML
        feat.write_text(feat.read_text(encoding="utf-8") + "# sửa tay\n", encoding="utf-8")
        self.assertFalse(appconfig.is_generated_fresh(self.root, cfg))
        feat.unlink()
        self.assertFalse(appconfig.is_generated_fresh(self.root, cfg))
        self.assertTrue(appconfig.write_generated(self.root, cfg))
        self.assertFalse(appconfig.write_generated(self.root, cfg))  # lần hai: không đổi gì

    # --- P2 Task 13: khối tuỳ chọn Web API — nội dung Features.generated.yml phụ thuộc features.web_api ---

    def render_features(self, web_api):
        self.write_config(self.VALID.replace("web_api = true", f"web_api = {'true' if web_api else 'false'}"))
        return appconfig.render_features_yml(appconfig.load(self.root))

    @staticmethod
    def body(text):
        return [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]

    def test_features_yml_bat_web_api_co_nguon_va_co(self):
        out = self.render_features(True)
        # Đường dẫn tính từ AppHost/Config/ (nơi file nằm), không phải từ project.yml.
        self.assertIn("      - path: ../../CoreOptional/WebAPI\n", out)
        self.assertIn("      - path: ../../CoreOptionalTests/WebAPI\n", out)
        self.assertIn("product: FirebaseAppCheck", out)
        self.assertIn("package: Firebase", out)
        # Cờ biên dịch nằm ở CẢ HAI target (AppHost và AppHostTests), nối vào giá trị kế thừa của project.
        self.assertEqual(out.count('SWIFT_ACTIVE_COMPILATION_CONDITIONS: "$(inherited) FEATURE_WEB_API"'), 2)
        self.assertIn("  AppHost:\n", out)
        self.assertIn("  AppHostTests:\n", out)
        # Nguồn test chỉ ở target test, nguồn khối chỉ ở target app.
        app, tests = out.split("  AppHostTests:\n")
        self.assertIn("../../CoreOptional/WebAPI", app)
        self.assertNotIn("CoreOptionalTests", app)
        self.assertIn("../../CoreOptionalTests/WebAPI", tests)
        self.assertNotIn("      - path: ../../CoreOptional/WebAPI\n", tests)
        self.assertNotIn("FirebaseAppCheck", tests)  # target test không link Firebase

    def test_features_yml_tat_web_api_rong(self):
        out = self.render_features(False)
        self.assertEqual(self.body(out), ["{}"])
        for needle in ("CoreOptional", "FirebaseAppCheck", "FEATURE_WEB_API"):
            self.assertNotIn(needle, out)

    def test_features_yml_khong_phu_thuoc_cong_tac_khac(self):
        # paywall/apple_ads không có khối tuỳ chọn trong thư mục riêng ⇒ không đổi spec XcodeGen.
        base = self.render_features(False)
        self.write_config(self.VALID.replace("web_api = true", "web_api = false").replace("apple_ads = true", "apple_ads = false"))
        self.assertEqual(appconfig.render_features_yml(appconfig.load(self.root)), base)

    def test_nguon_khoi_tuy_chon_nam_trong_cac_goc_tool(self):
        self.assertIn("CoreOptional/", appconfig.SRC_ROOTS)
        self.assertIn("CoreOptionalTests/", appconfig.TEST_ROOTS)

    def test_goc_khoi_dang_tat_theo_cong_tac(self):
        self.write_config(self.VALID.replace("web_api = true", "web_api = false"))
        src, tests = appconfig.disabled_block_roots(appconfig.load(self.root))
        self.assertEqual((src, tests), (("CoreOptional/WebAPI/",), ("CoreOptionalTests/WebAPI/",)))
        self.write_config(self.VALID)
        self.assertEqual(appconfig.disabled_block_roots(appconfig.load(self.root)), ((), ()))

    def test_check_do_khi_cong_tac_bat_ma_file_van_rong(self):
        # Config bật, file sinh ra ở trạng thái TẮT (`{}`) ⇒ cũ.
        cfg_off = self.VALID.replace("web_api = true", "web_api = false")
        self.write_config(cfg_off)
        appconfig.write_generated(self.root, appconfig.load(self.root))
        self.write_config(self.VALID)
        self.assertEqual(appconfig.stale_generated(self.root, appconfig.load(self.root)),
                         [appconfig.XCCONFIG, appconfig.FEATURES_YML, appconfig.WRANGLER_SITE])  # site: services API
        r = subprocess.run([sys.executable, APPCONFIG_PY, "check"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn(appconfig.FEATURES_YML, r.stderr)

    def test_check_do_khi_cong_tac_tat_ma_file_van_day(self):
        # Config tắt, file sinh ra ở trạng thái BẬT ⇒ cũ — và chỉ Features.generated.yml cũ (xcconfig đổi theo cờ
        # APP_FEATURE_WEB_API nên cũng cũ; cái cần chứng minh là file Features được nhận ra).
        appconfig.write_generated(self.root, appconfig.load(self.root))
        feat_on = (self.root / appconfig.FEATURES_YML).read_text(encoding="utf-8")
        self.write_config(self.VALID.replace("web_api = true", "web_api = false"))
        cfg = appconfig.load(self.root)
        (self.root / appconfig.XCCONFIG).write_text(appconfig.render_xcconfig(cfg), encoding="utf-8")  # xcconfig mới
        # Tắt web_api cũng bỏ `services` khỏi wrangler của site ⇒ file đó cũ theo.
        self.assertEqual(appconfig.stale_generated(self.root, cfg), [appconfig.FEATURES_YML, appconfig.WRANGLER_SITE])
        self.assertEqual((self.root / appconfig.FEATURES_YML).read_text(encoding="utf-8"), feat_on)
        r = subprocess.run([sys.executable, APPCONFIG_PY, "check"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.count(appconfig.FEATURES_YML), 1)
        self.assertNotIn(appconfig.XCCONFIG, r.stderr)

    def test_cli_check_do_khi_features_yml_cu(self):
        appconfig.write_generated(self.root, appconfig.load(self.root))
        ok = subprocess.run([sys.executable, APPCONFIG_PY, "check"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        (self.root / appconfig.FEATURES_YML).write_text("targets: {}\n", encoding="utf-8")
        r = subprocess.run([sys.executable, APPCONFIG_PY, "check"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn(appconfig.FEATURES_YML, r.stderr)

    def test_paywall_bat_ma_khong_co_san_pham_bi_tu_choi(self):
        self.write_config(self.VALID.replace('product_ids = ["pro.monthly", "pro.yearly", "pro.lifetime"]', "product_ids = []"))
        with self.assertRaisesRegex(appconfig.ConfigError, r"purchases\.product_ids"):
            appconfig.load(self.root)

    def test_paywall_tat_thi_san_pham_rong_van_qua(self):
        self.write_config(self.VALID.replace('product_ids = ["pro.monthly", "pro.yearly", "pro.lifetime"]', "product_ids = []")
                          .replace("paywall = true", "paywall = false"))
        out = appconfig.render_xcconfig(appconfig.load(self.root))
        self.assertIn("APP_FEATURE_PAYWALL = NO\n", out)
        self.assertIn("APP_PRODUCT_IDS =\n", out)

    def test_ma_san_pham_co_khoang_trang_bi_tu_choi(self):
        # APP_PRODUCT_IDS nối bằng dấu cách ⇒ id có dấu cách sẽ bị tách làm hai ở app.
        self.assert_tu_choi('"pro.yearly"', '"pro yearly"', r"purchases\.product_ids")

    # Tắt paywall trong hai test dưới: luật paywall cũng đòi host ⇒ không tắt thì nó "cứu" test khi nửa web_api bị bỏ.
    def test_web_api_bat_ma_thieu_host_bi_tu_choi(self):
        self.write_config(self.VALID.replace('host_prod = "example.com"', 'host_prod = ""')
                          .replace("paywall = true", "paywall = false"))
        with self.assertRaisesRegex(appconfig.ConfigError, r"web\.host_prod .*features\.web_api"):
            appconfig.load(self.root)

    def test_web_api_bat_ma_thieu_host_dev_bi_tu_choi(self):
        self.write_config(self.VALID.replace('host_dev = "dev.example.com"', 'host_dev = ""')
                          .replace("paywall = true", "paywall = false"))
        with self.assertRaisesRegex(appconfig.ConfigError, r"web\.host_dev .*features\.web_api"):
            appconfig.load(self.root)

    def test_web_api_va_paywall_tat_thi_host_rong_van_qua(self):
        self.write_config(self.VALID.replace('host_prod = "example.com"', 'host_prod = ""')
                          .replace('host_dev = "dev.example.com"', 'host_dev = ""')
                          .replace("web_api = true", "web_api = false")
                          .replace("paywall = true", "paywall = false"))
        self.assertEqual(appconfig.get(appconfig.load(self.root), "web.host_prod"), "")

    def test_paywall_bat_ma_thieu_host_bi_tu_choi(self):
        # Paywall cần link Điều khoản/Quyền riêng tư trên host web — kể cả khi web_api tắt.
        for key, cu in (("host_prod", 'host_prod = "example.com"'), ("host_dev", 'host_dev = "dev.example.com"')):
            with self.subTest(key):
                self.write_config(self.VALID.replace(cu, f'{key} = ""').replace("web_api = true", "web_api = false"))
                with self.assertRaisesRegex(appconfig.ConfigError, rf"web\.{key} .*features\.paywall"):
                    appconfig.load(self.root)

    def test_paywall_tat_web_api_tat_thi_thieu_host_van_qua(self):
        self.write_config(self.VALID.replace('host_prod = "example.com"', 'host_prod = ""')
                          .replace("web_api = true", "web_api = false").replace("paywall = true", "paywall = false"))
        appconfig.load(self.root)

    def test_email_ho_tro_sai_dang_bi_tu_choi(self):
        self.write_config(self.VALID.replace("support@example.com", "khong-phai-email"))
        with self.assertRaisesRegex(appconfig.ConfigError, r"support\.email"):
            appconfig.load(self.root)

    def test_email_ho_tro_rong_van_qua(self):
        self.write_config(self.VALID.replace("support@example.com", ""))
        self.assertIn("APP_SUPPORT_EMAIL =\n", appconfig.render_xcconfig(appconfig.load(self.root)))

    def test_co_tinh_nang_khong_phai_bool_bi_tu_choi(self):
        self.assert_tu_choi("apple_ads = true", 'apple_ads = "yes"', r"features\.apple_ads")

    def test_app_store_id_khong_phai_so_bi_tu_choi(self):
        self.assert_tu_choi('app_store_id = ""', 'app_store_id = "id123"', r"apple\.app_store_id")

    def test_xcconfig_co_bien_tinh_nang_va_san_pham(self):
        out = appconfig.render_xcconfig(appconfig.load(self.root))
        self.assertIn("APP_FEATURE_PAYWALL = YES\n", out)
        self.assertIn("APP_PRODUCT_IDS = pro.monthly pro.yearly pro.lifetime\n", out)

    def test_xcconfig_co_email_cua_hang_va_co_tat(self):
        text = (self.VALID.replace('app_store_id = ""', 'app_store_id = "123456789"')
                .replace("apple_ads = true", "apple_ads = false"))
        self.write_config(text)
        out = appconfig.render_xcconfig(appconfig.load(self.root))
        self.assertIn("APP_STORE_ID = 123456789\n", out)
        self.assertIn("APP_SUPPORT_EMAIL = support@example.com\n", out)
        self.assertIn("APP_FEATURE_APPLE_ADS = NO\n", out)
        self.assertIn("APP_FEATURE_WEB_API = YES\n", out)

    def test_khoa_la_bi_tu_choi_neu_ten(self):
        self.assert_tu_choi('host_prod = "example.com"', 'hostprod = "example.com"', r"web\.hostprod")

    def test_section_la_bi_tu_choi_neu_ten(self):
        self.write_config(self.VALID + '\n[webb]\nhost_prod = "example.com"\n')
        with self.assertRaisesRegex(appconfig.ConfigError, r"webb"):
            appconfig.load(self.root)

    def test_section_khong_phai_bang_bi_tu_choi(self):
        self.write_config('analytic = "x"\n' + self.VALID)
        with self.assertRaisesRegex(appconfig.ConfigError, r"analytic"):
            appconfig.load(self.root)

    def test_luoc_do_khop_dung_config_cua_template(self):
        # Lược đồ chặt phải nhận ĐÚNG mọi section/khoá có trong app.config.toml thật của template.
        real = appconfig.load(HERE.parents[1])
        self.assertEqual({s: set(v) for s, v in real.items()},
                         {s: set(v) for s, v in appconfig.SCHEMA.items()})

    # --- khoá store/analytics + thư mục theo slug ---

    def test_locale_mac_dinh_en_us(self):
        bo = self.VALID.replace('[store]\nlocales = ["en-US"]\n\n', "")
        self.assertNotIn("[store]", bo)
        self.write_config(bo)
        cfg = appconfig.load(self.root)
        self.assertEqual(appconfig.store_locales(cfg), ["en-US"])
        self.assertEqual(appconfig.primary_locale(cfg), "en-US")

    def test_locale_nhieu_dang_hop_le_va_locale_chinh(self):
        ds = ["vi", "en-US", "zh-Hans", "pt-BR", "ja", "fr-CA"]
        self.write_config(self.VALID.replace('["en-US"]', str(ds).replace("'", '"')))
        cfg = appconfig.load(self.root)
        self.assertEqual(appconfig.store_locales(cfg), ds)
        self.assertEqual(appconfig.primary_locale(cfg), "vi")

    def test_locale_sai_dang_bi_tu_choi(self):
        for xau in ('[]', '["en_US"]', '["EN-us"]', '["english"]', '[""]', '["en-US-x"]', '[1]', '"en-US"'):
            with self.subTest(xau=xau):
                self.assert_tu_choi('locales = ["en-US"]', f"locales = {xau}", r"store\.locales")

    def test_locale_trung_bi_tu_choi(self):
        self.assert_tu_choi('["en-US"]', '["en-US", "vi", "EN-us"]', r"store\.locales.*trùng")

    def test_state_dir_theo_slug_va_bien_moi_truong(self):
        cfg = appconfig.load(self.root)
        with tempfile.TemporaryDirectory(prefix="trang thai ") as t, \
                mock.patch.dict(os.environ, {"IOS_APP_FACTORY_STATE": t, "IOS_APP_FACTORY_CONFIG": t + "/cfg",
                                             "IOS_APP_FACTORY_BIN": t + "/bin"}):
            self.assertEqual(appconfig.state_dir(cfg, "aso"), Path(t) / "sample" / "aso")
            self.assertEqual(appconfig.config_dir(cfg), Path(t) / "cfg" / "sample")
            self.assertEqual(appconfig.shared_bin_dir(), Path(t) / "bin")
            self.assertFalse((Path(t) / "sample").exists(), "chỉ tính đường dẫn, không tạo thư mục")
            with self.assertRaises(appconfig.ConfigError):
                appconfig.state_dir(cfg, "../thoat")
        env = {k: v for k, v in os.environ.items() if not k.startswith("IOS_APP_FACTORY_")}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(appconfig.state_dir(cfg, "aso"),
                             Path.home() / "Library/Application Support/ios-app-factory/sample/aso")
            self.assertEqual(appconfig.config_dir(cfg), Path.home() / ".config/ios-app-factory/sample")
            self.assertEqual(appconfig.shared_bin_dir(), Path.home() / ".local/share/ios-app-factory")

    def test_seed_variables_du_tam_bien_tu_cau_hinh(self):
        cfg = appconfig.load(self.root)
        got = appconfig.seed_variables(cfg, template_tag="v9.9.9", date="2030-01-02")
        self.assertEqual(got, {
            "display_name": "Sample", "slug": "sample", "bundle_id": "com.example.sample",
            "host_prod": "example.com", "support_email": "support@example.com", "app_store_id": "",
            "marketing_version": "0.1.0", "primary_locale": "en-US", "template_tag": "v9.9.9", "date": "2030-01-02"})
        self.write_config(self.VALID.replace('locales = ["en-US"]', 'locales = ["vi", "en-US"]')
                          .replace('host_prod = "example.com"', 'host_prod = ""')
                          .replace("paywall = true", "paywall = false").replace("web_api = true", "web_api = false"))
        got2 = appconfig.seed_variables(appconfig.load(self.root), template_tag="t", date="d")
        self.assertEqual((got2["primary_locale"], got2["host_prod"]), ("vi", ""))

    def test_hai_slug_khac_thu_muc(self):
        cfg_a = appconfig.load(self.root)
        self.write_config(self.VALID.replace('slug = "sample"', 'slug = "khac-app"'))
        cfg_b = appconfig.load(self.root)
        with tempfile.TemporaryDirectory() as t, mock.patch.dict(os.environ, {"IOS_APP_FACTORY_STATE": t,
                                                                              "IOS_APP_FACTORY_CONFIG": t}):
            self.assertNotEqual(appconfig.state_dir(cfg_a, "aso"), appconfig.state_dir(cfg_b, "aso"))
            self.assertNotEqual(appconfig.config_dir(cfg_a), appconfig.config_dir(cfg_b))
        self.assertNotEqual(appconfig.state_dir(cfg_a, "aso"), appconfig.state_dir(cfg_b, "aso"))

    def test_cli_state_dir_config_dir_va_locales(self):
        env = dict(os.environ, IOS_APP_FACTORY_STATE=str(self.root / "st"), IOS_APP_FACTORY_CONFIG=str(self.root / "cf"))
        for args, want in ((["state-dir", "aso"], str(self.root / "st/sample/aso")),
                           (["config-dir"], str(self.root / "cf/sample")),
                           (["get", "store.locales"], "en-US")):
            r = subprocess.run([sys.executable, APPCONFIG_PY, *args], cwd=self.root, env=env,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), want)
        self.assertFalse((self.root / "st").exists())

    def test_ga4_property_sai_dang_bi_tu_choi(self):
        self.assert_tu_choi('ga4_property = ""', 'ga4_property = "properties/123"', r"analytics\.ga4_property")
        self.assert_tu_choi('ga4_property = ""', 'ga4_property = 123', r"analytics\.ga4_property")
        self.write_config(self.VALID.replace('ga4_property = ""', 'ga4_property = "123456789"'))
        appconfig.load(self.root)

    def test_bq_project_sai_dang_bi_tu_choi(self):
        for xau in ("Co Hoa", "ab", "-abcdef", "abcdef-", "ABCDEF"):
            with self.subTest(xau=xau):
                self.assert_tu_choi('bq_project = ""', f'bq_project = "{xau}"', r"analytics\.bq_project")
        self.write_config(self.VALID.replace('bq_project = ""', 'bq_project = "du-an-thu-123"'))
        appconfig.load(self.root)

    def test_khoa_moi_khong_doi_file_sinh_ra(self):
        base = appconfig.load(self.root)
        self.write_config(self.VALID.replace('["en-US"]', '["en-US", "vi"]').replace(
            'bq_project = ""', 'bq_project = "du-an-thu-123"'))
        moi = appconfig.load(self.root)
        self.assertEqual(appconfig._generated(base), appconfig._generated(moi))

    # --- P5 Task 7: privacy manifest sinh theo công tắc ---

    def copy_privacy_template(self):
        dst = self.root / appconfig.PRIVACY_TEMPLATE
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((REPO / appconfig.PRIVACY_TEMPLATE).read_bytes())

    def test_render_ghi_privacy_manifest_va_check_bat_lech(self):
        self.copy_privacy_template()
        appconfig.write_generated(self.root, appconfig.load(self.root))
        manifest = self.root / appconfig.PRIVACY_MANIFEST
        self.assertIn(b"NSPrivacyCollectedDataTypeEmailAddress", manifest.read_bytes())
        self.write_config(self.VALID.replace("web_api = true", "web_api = false"))
        cfg = appconfig.load(self.root)
        self.assertIn(appconfig.PRIVACY_MANIFEST, appconfig.stale_generated(self.root, cfg))
        r = subprocess.run([sys.executable, APPCONFIG_PY, "check"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn(appconfig.PRIVACY_MANIFEST, r.stderr)
        r = subprocess.run([sys.executable, APPCONFIG_PY, "render"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Đã ghi " + appconfig.PRIVACY_MANIFEST, r.stdout)
        self.assertNotIn(b"NSPrivacyCollectedDataTypeEmailAddress", manifest.read_bytes())
        self.assertEqual(appconfig.stale_generated(self.root, cfg), [])

    def test_khong_co_mau_thi_manifest_khong_do_render_quan(self):
        # Repo không có mẫu (app đã bỏ mẫu, giữ manifest tay) ⇒ render/check không đụng manifest.
        cfg = appconfig.load(self.root)
        self.assertNotIn(appconfig.PRIVACY_MANIFEST, [rel for rel, _ in appconfig._generated(cfg, self.root)])
        appconfig.write_generated(self.root, cfg)
        self.assertFalse((self.root / appconfig.PRIVACY_MANIFEST).exists())

    # --- P5 Task 8: associated-domains (Universal Link) theo host ---

    def config_khong_web(self):
        """Không web: tắt paywall + web_api (hai công tắc đòi host) rồi bỏ cả hai host."""
        return (self.VALID.replace('host_prod = "example.com"', 'host_prod = ""')
                .replace('host_dev = "dev.example.com"', 'host_dev = ""')
                .replace("web_api = true", "web_api = false").replace("paywall = true", "paywall = false"))

    def ents(self):
        return plistlib.loads((self.root / appconfig.ENTITLEMENTS).read_bytes())

    def write_project_yml(self, include=True):
        path = self.root / appconfig.PROJECT_YML
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["name: AppHost", "include:", "  - Config/Features.generated.yml"]
        if include:
            lines.append("  - Config/Entitlements.generated.yml")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_comment_nhac_duong_dan_khong_tinh_la_include(self):
        path = self.root / appconfig.PROJECT_YML
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("name: AppHost\n# TODO: thêm Config/Entitlements.generated.yml vào include\ninclude:\n"
                        "  - Config/Features.generated.yml\n", encoding="utf-8")
        cfg = appconfig.load(self.root)
        self.assertFalse(appconfig.includes_entitlements_fragment(self.root))
        self.assertNotIn(appconfig.ENTITLEMENTS, [rel for rel, _ in appconfig._generated(cfg, self.root)])
        # Không quản ⇒ render rồi check không lặp vô tận (check xanh ngay sau render).
        appconfig.write_generated(self.root, cfg)
        self.assertEqual(appconfig.stale_generated(self.root, cfg), [])

    def test_check_bao_note_khi_co_host_ma_chua_include(self):
        self.write_project_yml(include=False)
        appconfig.write_generated(self.root, appconfig.load(self.root))
        r = subprocess.run([sys.executable, APPCONFIG_PY, "check"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("NOTE: web.host_prod", r.stderr)
        self.write_project_yml()
        appconfig.write_generated(self.root, appconfig.load(self.root))
        r = subprocess.run([sys.executable, APPCONFIG_PY, "check"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("NOTE", r.stderr)

    def test_project_yml_chua_include_fragment_thi_khong_quan_entitlements(self):
        self.write_project_yml(include=False)
        rels = [rel for rel, _ in appconfig._generated(appconfig.load(self.root), self.root)]
        self.assertNotIn(appconfig.ENTITLEMENTS, rels)
        self.assertNotIn(appconfig.ENTITLEMENTS_YML, rels)
        self.write_project_yml()
        rels = [rel for rel, _ in appconfig._generated(appconfig.load(self.root), self.root)]
        self.assertIn(appconfig.ENTITLEMENTS, rels)
        self.assertIn(appconfig.ENTITLEMENTS_YML, rels)

    def test_co_host_thi_entitlement_co_dung_mot_applinks_theo_bien_build(self):
        self.write_project_yml()
        appconfig.write_generated(self.root, appconfig.load(self.root))
        self.assertEqual(self.ents(), {appconfig.ASSOCIATED_DOMAINS_KEY: ["applinks:$(APP_WEB_HOST)"]})

    def test_fragment_xcodegen_theo_host(self):
        # XcodeGen ghi đè .entitlements từ `entitlements.properties` ⇒ fragment include mới là nguồn của bản build.
        out = appconfig.render_entitlements_yml(appconfig.load(self.root))
        self.assertIn('        com.apple.developer.associated-domains: ["applinks:$(APP_WEB_HOST)"]\n', out)
        self.assertIn("targets:\n  AppHost:\n    entitlements:\n      properties:\n", out)
        self.write_config(self.config_khong_web())
        out = appconfig.render_entitlements_yml(appconfig.load(self.root))
        self.assertEqual(self.body(out), ["{}"])
        self.assertNotIn("associated-domains", out)

    def test_khong_host_thi_go_khoa_va_giu_khoa_khac(self):
        self.write_project_yml()
        path = self.root / appconfig.ENTITLEMENTS
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(plistlib.dumps({appconfig.ASSOCIATED_DOMAINS_KEY: ["applinks:cu.example.com"],
                                         "com.apple.developer.icloud-services": ["CloudKit"]}))
        self.write_config(self.config_khong_web())
        cfg = appconfig.load(self.root)
        self.assertIn(appconfig.ENTITLEMENTS, appconfig.stale_generated(self.root, cfg))
        appconfig.write_generated(self.root, cfg)
        self.assertEqual(self.ents(), {"com.apple.developer.icloud-services": ["CloudKit"]})
        self.assertEqual(appconfig.stale_generated(self.root, cfg), [])

    def test_check_bat_entitlement_lech_host(self):
        self.write_project_yml()
        self.write_config(self.config_khong_web())
        appconfig.write_generated(self.root, appconfig.load(self.root))
        self.assertEqual(self.ents(), {})
        self.write_config(self.VALID)
        r = subprocess.run([sys.executable, APPCONFIG_PY, "check"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn(appconfig.ENTITLEMENTS, r.stderr)
        r = subprocess.run([sys.executable, APPCONFIG_PY, "render"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Đã ghi " + appconfig.ENTITLEMENTS, r.stdout)
        self.assertIn(appconfig.ASSOCIATED_DOMAINS_KEY, self.ents())

    def test_entitlements_hong_thi_bao_loi_ten_file(self):
        self.write_project_yml()
        path = self.root / appconfig.ENTITLEMENTS
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("khong phai plist", encoding="utf-8")
        with self.assertRaisesRegex(appconfig.ConfigError, "AppHost.entitlements"):
            appconfig.stale_generated(self.root, appconfig.load(self.root))

    def test_host_prod_ma_thieu_host_dev_bi_tu_choi(self):
        self.write_config(self.config_khong_web().replace('host_prod = ""', 'host_prod = "example.com"'))
        with self.assertRaisesRegex(appconfig.ConfigError, r"web\.host_dev .*web\.host_prod"):
            appconfig.load(self.root)

    def test_entitlements_track_khop_cau_hinh_repo(self):
        # Bản track ở repo này phải đúng bằng bản render (appconfig check cũng gác; đây là đối chứng đọc tận nơi).
        real = appconfig.load(REPO)
        want = appconfig.opt(real, "web.host_prod", "") != ""
        got = plistlib.loads((REPO / appconfig.ENTITLEMENTS).read_bytes())
        self.assertEqual(appconfig.ASSOCIATED_DOMAINS_KEY in got, want)

    # --- I6: Python cũ ⇒ FAIL rõ ràng, không traceback ---

    def run_old_python(self, code):
        prelude = ("import sys; sys.version_info = (3, 9, 6, 'final', 0); "
                   f"sys.path.insert(0, {str(HERE)!r}); ")
        return subprocess.run([sys.executable, "-c", prelude + code], cwd=self.root,
                              capture_output=True, text=True)

    def test_python_cu_khi_import(self):
        r = self.run_old_python("import appconfig")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("FAIL: cần Python ≥ 3.11 (đang chạy 3.9)", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_python_cu_khi_chay_cli(self):
        r = self.run_old_python(f"import runpy; sys.argv = ['appconfig.py', 'check']; "
                                f"runpy.run_path({APPCONFIG_PY!r}, run_name='__main__')")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("FAIL: cần Python ≥ 3.11", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


class WranglerTests(unittest.TestCase):
    """P6 Task 1: khoá web/Cloudflare/Firebase + hai wrangler.jsonc sinh từ app.config.toml."""
    VALID = SAMPLE_CONFIG

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.write_config(self.VALID)

    def write_config(self, text):
        (self.root / "app.config.toml").write_text(text, encoding="utf-8")

    def cfg(self, text=None):
        if text is not None:
            self.write_config(text)
        return appconfig.load(self.root)

    @staticmethod
    def parse(text):
        lines = text.split("\n")
        assert lines[0].startswith("//"), "dòng đầu phải là chú thích SINH"
        return json.loads("\n".join(l for l in lines if not l.lstrip().startswith("//")))

    def api(self, text=None):
        return self.parse(appconfig.render_wrangler_api(self.cfg(text)))

    def site(self, text=None):
        return self.parse(appconfig.render_wrangler_site(self.cfg(text)))

    def test_wrangler_api_doc_dinh_danh_tu_cau_hinh(self):
        text = self.VALID.replace('d1_prod = ""', 'd1_prod = "11111111-2222-3333-4444-555555555555"').replace(
            'app_check_prod = ""', 'app_check_prod = "test-proj:123456"')
        raw = appconfig.render_wrangler_api(self.cfg(text))
        self.assertTrue(raw.startswith("// SINH bởi"))
        self.assertIn("không sửa tay", raw.split("\n")[0])
        w = self.parse(raw)
        self.assertEqual(w["name"], "sample-api")
        self.assertEqual(w["main"], "src/index.ts")
        self.assertEqual(w["compatibility_date"], "2026-08-22")
        self.assertEqual(w["compatibility_flags"], ["nodejs_compat"])
        self.assertIs(w["workers_dev"], False)
        self.assertIs(w["preview_urls"], False)
        self.assertEqual(w["d1_databases"], [{"binding": "DB", "database_name": "sample",
                                              "database_id": "11111111-2222-3333-4444-555555555555",
                                              "migrations_dir": "migrations"}])
        self.assertEqual(w["triggers"], {"crons": ["17 3 * * *"]})
        self.assertEqual(w["vars"], {"ASSN_BUNDLE_ID": "com.example.sample", "ASSN_ENVIRONMENTS": "Production",
                                     "APP_CHECK_PROJECTS": "test-proj:123456", "APP_CHECK_REQUIRED": "1",
                                     "PUBLIC_ORIGIN": "https://example.com"})
        self.assertNotIn("routes", w)

    def test_wrangler_site_khong_co_binding_api_khi_tat_web_api(self):
        w = self.site()
        self.assertEqual(w["name"], "sample-site")
        self.assertEqual(w["main"], "src/worker.ts")
        # Không bản sao `<slug>-site.<account>.workers.dev` / URL xem trước (bản đó cũng chuyển /api/*, kể cả admin).
        self.assertIs(w["workers_dev"], False)
        self.assertIs(w["preview_urls"], False)
        self.assertEqual(w["assets"], {"directory": "public", "binding": "ASSETS",
                                       "run_worker_first": ["/.well-known/*", "/api/*"],
                                       "not_found_handling": "404-page"})
        self.assertEqual(w["services"], [{"binding": "API", "service": "sample-api"}])
        self.assertEqual(w["env"]["dev"]["services"], [{"binding": "API", "service": "sample-api-dev"}])
        off = self.site(self.VALID.replace("web_api = true", "web_api = false"))
        self.assertNotIn("services", off)
        self.assertNotIn("services", off["env"]["dev"])
        # Site đứng một mình vẫn có AASA: vars + assets còn nguyên.
        self.assertEqual(off["vars"]["APP_IDS"], "0000000000.com.example.sample")
        self.assertEqual(off["vars"]["APP_PATHS"], '["/items", "/items/*"]')
        self.assertEqual(off["vars"]["NOINDEX"], "0")
        self.assertNotIn("routes", off)

    def test_env_dev_lap_du_binding_site_bundle_internal_api_bundle_store(self):
        text = self.VALID.replace('d1_dev = ""', 'd1_dev = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"').replace(
            'app_check_dev = ""', 'app_check_dev = "dev-proj:654321"')
        cfg = self.cfg(text)
        api = self.parse(appconfig.render_wrangler_api(cfg))["env"]["dev"]
        self.assertEqual(api["name"], "sample-api-dev")
        self.assertEqual(api["d1_databases"], [{"binding": "DB", "database_name": "sample-dev",
                                                "database_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                                                "migrations_dir": "migrations"}])
        self.assertEqual(api["triggers"], {"crons": ["17 3 * * *"]})
        # Thông báo App Store (kể cả Sandbox về dev) LUÔN mang bundle Store — bản .internal không có bản ghi trên App Store
        # Connect ⇒ dev lọc theo bundle Store, không phải .internal (lọc .internal = bỏ mọi thông báo Sandbox).
        self.assertEqual(api["vars"], {"ASSN_BUNDLE_ID": "com.example.sample",
                                       "ASSN_ENVIRONMENTS": "Sandbox", "APP_CHECK_PROJECTS": "dev-proj:654321",
                                       "APP_CHECK_REQUIRED": "0", "PUBLIC_ORIGIN": "https://dev.example.com"})
        site = self.parse(appconfig.render_wrangler_site(cfg))["env"]["dev"]
        self.assertEqual(site["name"], "sample-site-dev")
        self.assertEqual(site["routes"], [{"pattern": "dev.example.com", "custom_domain": True}])
        # Dev: Worker chạy trước MỌI đường dẫn — không thì trang tĩnh đi thẳng, thiếu X-Robots-Tag: noindex.
        self.assertEqual(site["assets"], {"directory": "public", "binding": "ASSETS", "run_worker_first": True,
                                          "not_found_handling": "404-page"})
        self.assertEqual(site["vars"], {"APP_IDS": "0000000000.com.example.sample.internal",
                                        "APP_PATHS": '["/items", "/items/*"]', "NOINDEX": "1"})
        self.assertNotIn("com.example.sample.internal", json.dumps(self.parse(appconfig.render_wrangler_api(cfg))["vars"]))

    def test_trang_web_gieo_cat_khoi_theo_cong_tac(self):
        page = ("<p>chung</p>\n<!-- feature:paywall:begin -->\n<p data-feature=\"paywall\">mua</p>\n"
                "<!-- feature:paywall:end -->\n<!-- feature:app_store:begin -->\n<a>store</a>\n"
                "<!-- feature:app_store:end -->\n")
        rel = "web/site/public/privacy/index.html"
        on = appconfig.render_web_seed(self.cfg(), rel, page)
        self.assertEqual(on, '<p>chung</p>\n<p data-feature="paywall">mua</p>\n')
        cfg = self.cfg(self.VALID.replace("paywall = true", "paywall = false")
                       .replace('app_store_id = ""', 'app_store_id = "123"'))
        self.assertEqual(appconfig.render_web_seed(cfg, rel, page), "<p>chung</p>\n<a>store</a>\n")
        # Ngoài web/site/public/ hoặc không phải trang text ⇒ nguyên văn.
        self.assertEqual(appconfig.render_web_seed(cfg, "docs/x.html", page), page)
        self.assertEqual(appconfig.render_web_seed(cfg, "web/site/public/m.js", page), page)
        with self.assertRaises(appconfig.ConfigError) as cm:
            appconfig.render_web_seed(cfg, rel, "<!-- feature:la:begin -->\nx\n<!-- feature:la:end -->\n")
        self.assertIn(rel, str(cm.exception))

    def test_khoi_mua_hang_luu_server_chi_khi_ca_paywall_lan_web_api(self):
        # `purchase_records` = paywall VÀ web_api: API lưu App Store Server Notifications (giao dịch, giá, hạn…) ⇒ trang
        # privacy phải nói — chỉ một trong hai công tắc thì không có gì được lưu ở server.
        page = ("<!-- feature:purchase_records:begin -->\n<p data-feature=\"purchase_records\">server</p>\n"
                "<!-- feature:purchase_records:end -->\n")
        rel = "web/site/public/privacy/index.html"
        self.assertEqual(appconfig.render_web_seed(self.cfg(), rel, page), '<p data-feature="purchase_records">server</p>\n')
        for off in ("paywall", "web_api"):
            cfg = self.cfg(self.VALID.replace(f"{off} = true", f"{off} = false"))
            self.assertFalse(appconfig.web_seed_switches(cfg)["purchase_records"], off)
            self.assertEqual(appconfig.render_web_seed(cfg, rel, page), "")

    def test_d1_rong_ra_todo_va_check_canh_bao(self):
        cfg = self.cfg()
        w = self.parse(appconfig.render_wrangler_api(cfg))
        self.assertEqual(w["d1_databases"][0]["database_id"], "TODO-d1-id")
        self.assertEqual(w["env"]["dev"]["d1_databases"][0]["database_id"], "TODO-d1-id")
        warns = appconfig.web_warnings(cfg)
        self.assertTrue(any("cloudflare.d1_prod" in x and "cloudflare.d1_dev" in x for x in warns), warns)
        done = self.cfg(self.VALID.replace('d1_prod = ""', 'd1_prod = "x1"').replace('d1_dev = ""', 'd1_dev = "x2"'))
        self.assertFalse(any("d1_" in x for x in appconfig.web_warnings(done)))
        cfg = self.cfg(self.VALID)
        appconfig.write_generated(self.root, cfg)
        r = subprocess.run([sys.executable, APPCONFIG_PY, "check"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("cloudflare.d1_prod", r.stderr)

    def test_d1_rong_khi_tat_web_api_thi_khong_canh_bao(self):
        # Ruling 11: web_api tắt ⇒ không có API ⇒ không cần D1 (deploy chỉ site).
        off = self.cfg(self.VALID.replace("web_api = true", "web_api = false"))
        self.assertEqual(appconfig.web_warnings(off), [])

    def test_external_site_la_bool_mac_dinh_false(self):
        self.assertFalse(appconfig.web_external_site(self.cfg(self.VALID)))
        on = self.cfg(self.VALID.replace('host_dev = "dev.example.com"',
                                         'host_dev = "dev.example.com"\nexternal_site = true'))
        self.assertTrue(appconfig.web_external_site(on))
        for bad in ('"true"', "1", '"yes"'):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(appconfig.ConfigError, r"web\.external_site"):
                    self.cfg(self.VALID.replace('host_dev = "dev.example.com"',
                                                f'host_dev = "dev.example.com"\nexternal_site = {bad}'))

    def test_app_check_rong_khi_bat_web_api_thi_check_canh_bao(self):
        warns = appconfig.web_warnings(self.cfg())
        self.assertTrue(any("firebase.app_check_prod" in x for x in warns), warns)
        off = self.cfg(self.VALID.replace("web_api = true", "web_api = false"))
        self.assertFalse(any("app_check" in x for x in appconfig.web_warnings(off)))
        full = self.cfg(self.VALID.replace('app_check_prod = ""', 'app_check_prod = "test-proj:123456"')
                        .replace('app_check_dev = ""', 'app_check_dev = "test-proj:123456"'))
        self.assertFalse(any("app_check" in x for x in appconfig.web_warnings(full)))
        bad = self.VALID.replace('app_check_prod = ""', 'app_check_prod = "chi-co-ten-du-an"')
        with self.assertRaisesRegex(appconfig.ConfigError, r"firebase\.app_check_prod"):
            self.cfg(bad)

    def test_app_paths_sai_dang_bi_tu_choi(self):
        for bad in ('["items"]', '["/a?b"]', '["/a#b"]', '[""]', '["/a b"]', '"/items"', '[1]'):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(appconfig.ConfigError, r"web\.app_paths"):
                    self.cfg(self.VALID.replace('["/items", "/items/*"]', bad))
        self.assertEqual(appconfig.web_app_paths(self.cfg(self.VALID)), ["/items", "/items/*"])
        self.assertEqual(appconfig.web_app_paths(self.cfg(self.VALID.replace('["/items", "/items/*"]', "[]"))), [])
        self.assertEqual(appconfig.web_app_paths(self.cfg(self.VALID.replace('app_paths = ["/items", "/items/*"]\n', ""))), [])

    def test_app_paths_rong_cho_aasa_van_hop_le_o_site(self):
        w = self.site(self.VALID.replace('["/items", "/items/*"]', "[]"))
        self.assertEqual(w["vars"]["APP_PATHS"], "[]")

    def test_khong_host_prod_thi_khong_sinh_wrangler(self):
        text = (self.VALID.replace('host_prod = "example.com"', 'host_prod = ""')
                .replace('host_dev = "dev.example.com"', 'host_dev = ""')
                .replace("web_api = true", "web_api = false").replace("paywall = true", "paywall = false"))
        cfg = self.cfg(text)
        rels = [rel for rel, _ in appconfig._generated(cfg, self.root)]
        self.assertNotIn(appconfig.WRANGLER_API, rels)
        self.assertNotIn(appconfig.WRANGLER_SITE, rels)
        self.assertEqual(appconfig.web_warnings(cfg), [])
        appconfig.write_generated(self.root, cfg)
        self.assertFalse((self.root / "web").exists())
        self.assertEqual(appconfig.stale_generated(self.root, cfg), [])
        # Có host ⇒ cả hai file có mặt trong danh sách sinh.
        rels = [rel for rel, _ in appconfig._generated(self.cfg(self.VALID), self.root)]
        self.assertIn(appconfig.WRANGLER_API, rels)
        self.assertIn(appconfig.WRANGLER_SITE, rels)

    def test_render_roi_check_khop(self):
        cfg = self.cfg()
        appconfig.write_generated(self.root, cfg)
        for rel in (appconfig.WRANGLER_API, appconfig.WRANGLER_SITE):
            self.parse((self.root / rel).read_text(encoding="utf-8"))  # JSONC parse được sau khi bỏ dòng //
        self.assertEqual(appconfig.stale_generated(self.root, cfg), [])
        r = subprocess.run([sys.executable, APPCONFIG_PY, "check"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        (self.root / appconfig.WRANGLER_SITE).write_text("// sửa tay\n{}\n", encoding="utf-8")
        self.assertEqual(appconfig.stale_generated(self.root, cfg), [appconfig.WRANGLER_SITE])
        r = subprocess.run([sys.executable, APPCONFIG_PY, "check"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn(appconfig.WRANGLER_SITE, r.stderr)

    def test_wrangler_track_khop_cau_hinh_repo(self):
        # Bản track ở repo này phải đúng bằng bản render (đối chứng đọc tận nơi).
        real = appconfig.load(REPO)
        self.assertEqual(appconfig.stale_generated(REPO, real), [])

    def test_khoa_cloudflare_firebase_sai_dang_bi_tu_choi(self):
        for old, new, key in (('d1_prod = ""', 'd1_prod = "co dau cach"', "cloudflare.d1_prod"),
                              ('d1_dev = ""', 'd1_dev = 5', "cloudflare.d1_dev"),
                              ('app_check_dev = ""', 'app_check_dev = "a:b"', "firebase.app_check_dev")):
            with self.subTest(key=key):
                with self.assertRaisesRegex(appconfig.ConfigError, key.replace(".", r"\.")):
                    self.cfg(self.VALID.replace(old, new))


def _clean_git_env():
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


class PrivacyManifestTests(unittest.TestCase):
    """Privacy manifest cắt từ mẫu THẬT của repo (AppHost/Config/PrivacyInfo.template.xcprivacy) theo công tắc."""

    ALWAYS = {"NSPrivacyCollectedDataTypeProductInteraction", "NSPrivacyCollectedDataTypeCrashData",
              "NSPrivacyCollectedDataTypePerformanceData", "NSPrivacyCollectedDataTypeDeviceID",
              "NSPrivacyCollectedDataTypeOtherDiagnosticData"}
    PURCHASE = "NSPrivacyCollectedDataTypePurchaseHistory"
    SUPPORT = "NSPrivacyCollectedDataTypeCustomerSupport"
    EMAIL = "NSPrivacyCollectedDataTypeEmailAddress"
    ADS = "NSPrivacyCollectedDataTypeAdvertisingData"

    @staticmethod
    def cfg(paywall=True, web_api=True, apple_ads=True):
        return {"features": {"paywall": paywall, "web_api": web_api, "apple_ads": apple_ads}}

    def render(self, **switches):
        return appconfig.render_privacy_manifest(self.cfg(**switches))

    @staticmethod
    def types(data: bytes) -> set[str]:
        return {d["NSPrivacyCollectedDataType"] for d in plistlib.loads(data)["NSPrivacyCollectedDataTypes"]}

    # Dữ liệu manifest tĩnh của template trước P5 (v0.4.0): bật cả ba công tắc phải ra ĐÚNG dữ liệu này.
    _PRE_P5 = [("AdvertisingData", "Analytics"), ("ProductInteraction", "Analytics"), ("CrashData", "AppFunctionality"),
               ("PerformanceData", "AppFunctionality"), ("DeviceID", "Analytics"),
               ("OtherDiagnosticData", "AppFunctionality"), ("PurchaseHistory", "AppFunctionality"),
               ("CustomerSupport", "AppFunctionality"), ("EmailAddress", "AppFunctionality")]
    PRE_P5_DATA = {
        "NSPrivacyTracking": False,
        "NSPrivacyTrackingDomains": [],
        "NSPrivacyCollectedDataTypes": [
            {"NSPrivacyCollectedDataType": "NSPrivacyCollectedDataType" + kind,
             "NSPrivacyCollectedDataTypeLinked": False, "NSPrivacyCollectedDataTypeTracking": False,
             "NSPrivacyCollectedDataTypePurposes": ["NSPrivacyCollectedDataTypePurpose" + purpose]}
            for kind, purpose in _PRE_P5],
        "NSPrivacyAccessedAPITypes": [
            {"NSPrivacyAccessedAPIType": "NSPrivacyAccessedAPICategoryUserDefaults",
             "NSPrivacyAccessedAPITypeReasons": ["CA92.1"]},
            {"NSPrivacyAccessedAPIType": "NSPrivacyAccessedAPICategoryDiskSpace",
             "NSPrivacyAccessedAPITypeReasons": ["7D9E.1"]}],
    }

    def test_bat_het_ra_dung_du_lieu_ban_truoc_p5(self):
        # Mẫu của TEMPLATE (app sửa mẫu của mình theo dữ liệu nó khai ⇒ chỉ soi ở repo template).
        if not (REPO / "tools" / "template" / "new_app.py").is_file():
            self.skipTest("repo app: mẫu privacy là của app, không so với dữ liệu template")
        self.assertEqual(plistlib.loads(self.render()), self.PRE_P5_DATA)

    def test_ban_track_dung_bang_ban_render_theo_config_cua_repo(self):
        # File đang track = render(mẫu của repo, công tắc của repo) từng byte (comment, thứ tự, dòng sinh, dòng cuối).
        tpl, manifest = REPO / appconfig.PRIVACY_TEMPLATE, REPO / appconfig.PRIVACY_MANIFEST
        if not tpl.is_file() or not manifest.is_file():
            self.skipTest("repo không có mẫu privacy (manifest giữ tay) hoặc chưa có manifest")
        real = appconfig.load(REPO)
        self.assertEqual(appconfig.render_privacy_manifest(real, tpl.read_bytes()), manifest.read_bytes())

    def test_file_sinh_co_dong_khong_sua_tay_ngay_sau_doctype(self):
        for switches in ({}, {"paywall": False, "web_api": False, "apple_ads": False}):
            lines = self.render(**switches).decode("utf-8").split("\n")
            at = next(i for i, x in enumerate(lines) if x.startswith("<!DOCTYPE"))
            self.assertEqual(lines[at + 1], appconfig.PRIVACY_GENERATED_HEADER)
            self.assertIn("KHÔNG sửa tay", lines[at + 1])
        self.assertNotIn(appconfig.PRIVACY_GENERATED_HEADER,
                         (REPO / appconfig.PRIVACY_TEMPLATE).read_text(encoding="utf-8")
                         if (REPO / appconfig.PRIVACY_TEMPLATE).is_file() else "")

    def test_mau_crlf_bao_dung_nguyen_nhan(self):
        tpl = "<?xml?>\n<!DOCTYPE plist>\n<plist><dict><key>K</key><array>\n<!-- feature:paywall:begin -->\n" \
              "<string>x</string>\n<!-- feature:paywall:end -->\n</array></dict></plist>\n"
        with self.assertRaises(appconfig.ConfigError) as cm:
            appconfig.render_privacy_manifest(self.cfg(), tpl.replace("\n", "\r\n"))
        self.assertIn("CRLF", str(cm.exception))
        self.assertIn("dòng 4", str(cm.exception))

    def test_tat_paywall_bo_purchase_history(self):
        self.assertEqual(self.types(self.render(paywall=False)), self.ALWAYS | {self.SUPPORT, self.EMAIL, self.ADS})

    def test_tat_web_api_bo_email_va_customer_support(self):
        out = self.render(web_api=False)
        self.assertEqual(self.types(out), self.ALWAYS | {self.PURCHASE, self.ADS})
        # Comment giải thích của khối Web API đi theo khối; comment ngoài khối (DiskSpace) ở lại.
        self.assertNotIn("Khối Web API".encode(), out)
        self.assertIn(b"7D9E.1", out)
        self.assertIn("Core/Support/DiagnosticsSnapshot.swift đọc dung lượng".encode(), out)

    def test_tat_apple_ads_bo_advertising_data(self):
        self.assertEqual(self.types(self.render(apple_ads=False)), self.ALWAYS | {self.PURCHASE, self.SUPPORT, self.EMAIL})

    def test_tat_het_van_la_plist_hop_le(self):
        out = self.render(paywall=False, web_api=False, apple_ads=False)
        self.assertEqual(self.types(out), self.ALWAYS)
        self.assertNotIn(b"feature:", out)
        self.assertTrue(out.endswith(b"</plist>\n"))
        data = plistlib.loads(out)
        self.assertIs(data["NSPrivacyTracking"], False)
        self.assertEqual(len(data["NSPrivacyAccessedAPITypes"]), 2)
        import shutil
        if shutil.which("plutil"):
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "thư mục có dấu cách" / "PrivacyInfo.xcprivacy"
                p.parent.mkdir()
                p.write_bytes(out)
                r = subprocess.run(["plutil", "-lint", str(p)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_khong_khoi_features_la_tat_het(self):
        self.assertEqual(self.types(appconfig.render_privacy_manifest({})), self.ALWAYS)

    def test_bang_privacy_blocks_khop_khoi_trong_mau(self):
        # Cổng 7 đối chiếu `.app` theo PRIVACY_BLOCKS ⇒ tắt từng công tắc phải bỏ ĐÚNG các kiểu bảng ghi.
        full = self.types(self.render())
        for b in appconfig.PRIVACY_BLOCKS:
            with self.subTest(switch=b["switch"]):
                out = self.types(self.render(**{b["switch"]: False}))
                self.assertEqual(full - out, set(b["types"]))
        self.assertEqual({b["info_key"] for b in appconfig.PRIVACY_BLOCKS},
                         {"FeaturePaywall", "FeatureWebAPI", "FeatureAppleAds"})

    def assert_dau_sai(self, text, needle):
        with self.assertRaises(appconfig.ConfigError) as ctx:
            appconfig.cut_feature_blocks(text, {"paywall": True, "web_api": False})
        self.assertRegex(str(ctx.exception), needle)

    def test_dau_khoi_sai_bi_tu_choi(self):
        self.assert_dau_sai("a\n<!-- feature:paywall:begin -->\nb\n", r"dòng 2: `feature:paywall:begin` không có dấu đóng")
        self.assert_dau_sai("<!-- feature:paywall:end -->\n", r"dòng 1: `feature:paywall:end` không cặp")
        self.assert_dau_sai("<!-- feature:paywall:begin -->\n<!-- feature:web_api:begin -->\n", r"dòng 2: .*lồng")
        self.assert_dau_sai("<!-- feature:la:begin -->\n", r"công tắc lạ 'la'")
        self.assert_dau_sai("<dict><!-- feature:paywall:begin -->\n", r"trọn một dòng")
        self.assert_dau_sai("<!-- feature:paywall:begin --> <!-- feature:paywall:end -->\n", r"trọn một dòng")

    def test_cat_giu_nguyen_dong_ngoai_khoi(self):
        text = ("x\n  <!-- feature:paywall:begin -->\n  p\n  <!-- feature:paywall:end -->\n"
                "\t<!-- feature:web_api:begin -->\nw\n<!-- feature:web_api:end -->\n  <!-- ghi chú -->\n")
        self.assertEqual(appconfig.cut_feature_blocks(text, {"paywall": True, "web_api": False}),
                         "x\n  p\n  <!-- ghi chú -->\n")

    def test_ket_qua_khong_phai_plist_bi_tu_choi(self):
        with self.assertRaises(appconfig.ConfigError):
            # Khối nuốt mất thẻ đóng `</dict>` ⇒ tắt paywall ra XML hỏng.
            appconfig.render_privacy_manifest(self.cfg(paywall=False),
                                              '<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0">\n<dict>\n'
                                              "<!-- feature:paywall:begin -->\n</dict>\n<!-- feature:paywall:end -->\n"
                                              "</plist>\n")
        # Cùng mẫu, paywall bật ⇒ hợp lệ (lỗi trên là do cắt, không phải do mẫu).
        appconfig.render_privacy_manifest(self.cfg(), '<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0">\n'
                                          "<dict>\n<!-- feature:paywall:begin -->\n</dict>\n"
                                          "<!-- feature:paywall:end -->\n</plist>\n")


if __name__ == "__main__":
    unittest.main()
