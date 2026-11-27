"""Test cổng release verify_release_clean.sh trên một `.app` GIẢ tối thiểu (không build Xcode).

Mỗi test dựng một repo git tạm chép script cổng + appconfig + stamp_whats_new thật, một `.app` có Info.plist,
GoogleService-Info.plist, PrivacyInfo.xcprivacy và một Mach-O thật biên dịch bằng clang (có/không có chuỗi giả
symbol debug — `strings` không quét byte nối thêm sau Mach-O nên không giả được bằng cách nối). Chạy với SKIP_CATALOG_CHECK=1 (cổng String Catalog cần build thật — selfcheck phủ).
Mọi biến GIT_* bị gỡ khỏi env (docs/lessons-learned/test-git-trong-hook-dung-repo-that.md).
"""
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "common"))
import appconfig  # noqa: E402

CONFIG = """\
[app]
slug = "demo"
display_name = "Demo"
display_name_internal = "Demo Dev"

[bundle]
store = "com.example.demo"
internal = "com.example.demo.internal"

[apple]
team_id = "0000000000"

[version]
marketing = "1.2.3"
build = "45"

[web]
host_prod = ""
host_dev = ""
# Các test cổng khác dựng app có host mà không có web/site/public ⇒ khai site ngoài repo (cổng 16 SKIP). Test cổng 16
# đặt lại false (`with_site`, `no_site`).
external_site = true
"""
DEBUG_SYMBOL = "InternalDebugMarkerView"
C_PLAIN = "int main(void) { return 0; }\n"
C_DEBUG = f'const char *marker = "{DEBUG_SYMBOL}";\nint main(void) {{ return marker[0] == 0; }}\n'
SAMPLE_MARKER = "SampleItemStore"
C_SAMPLE = f'const char *marker = "{SAMPLE_MARKER}";\nint main(void) {{ return marker[0] == 0; }}\n'
COPIED = ("tools/release/verify_release_clean.sh", "tools/release/debug_symbols.txt",
          "tools/release/stamp_whats_new.py", "tools/release/lint_debug_symbols.py", "tools/common/appconfig.py",
          "web/tools/check_site.py")
# Paywall bật cần host web (appconfig: link Điều khoản/Quyền riêng tư) — WebHost của .app thử = host_prod.
PAYWALL_ON = CONFIG.replace('host_prod = ""', 'host_prod = "example.com"').replace(
    'host_dev = ""', 'host_dev = "dev.example.com"') + """
[features]
paywall = true

[purchases]
product_ids = ["p.monthly", "p.lifetime"]
"""

# Cổng 7: kiểu dữ liệu theo khoá Info.plist của từng khối tuỳ chọn — viết tay ĐỘC LẬP với appconfig.PRIVACY_BLOCKS
# (test của appconfig giữ bảng đó khớp mẫu; ở đây cổng phải đúng với chính kiểu Apple, không chép bảng của nó).
BLOCK_TYPES = {
    "FeaturePaywall": ("NSPrivacyCollectedDataTypePurchaseHistory",),
    "FeatureWebAPI": ("NSPrivacyCollectedDataTypeCustomerSupport", "NSPrivacyCollectedDataTypeEmailAddress"),
    "FeatureAppleAds": ("NSPrivacyCollectedDataTypeAdvertisingData",),
}
ALWAYS_TYPES = ("NSPrivacyCollectedDataTypeProductInteraction", "NSPrivacyCollectedDataTypeCrashData")


GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in ("ALLOW_FIXTURE_PLIST", "SKIP_CATALOG_CHECK", "SKIP_SYMBOL_LINT",
                         "ALLOW_SAMPLE_IN_RELEASE")}
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    env["SKIP_CATALOG_CHECK"] = "1"
    # Repo giả không có nguồn Swift ⇒ lint_debug_symbols (cổng 1b) bỏ qua; một test riêng chạy nó thật.
    env["SKIP_SYMBOL_LINT"] = "1"
    env.update(extra)
    return env


@unittest.skipUnless(shutil.which("clang") and shutil.which("nm"), "cần macOS (clang + nm)")
class VerifyReleaseCleanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._bins = tempfile.TemporaryDirectory()
        cls.binaries = {}
        for name, src in (("plain", C_PLAIN), ("debug", C_DEBUG), ("sample", C_SAMPLE)):
            c = Path(cls._bins.name) / f"{name}.c"
            c.write_text(src, encoding="utf-8")
            out = Path(cls._bins.name) / name
            subprocess.run(["clang", "-o", str(out), str(c)], check=True, capture_output=True)
            cls.binaries[name] = out.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls._bins.cleanup()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo có dấu cách"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, env=clean_env(), check=True)
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=self.root, env=clean_env(),
                             capture_output=True, text=True).stdout.strip()
        self.assertEqual(Path(top).resolve(), self.root.resolve())
        for rel in COPIED:
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)
        self.set_config(CONFIG)
        # Repo tạm mô phỏng TEMPLATE (cổng 15 bỏ qua): dấu nhận diện dương tools/template/new_app.py được track. Các test
        # mô phỏng app gỡ nó (make_app_repo).
        marker = self.root / "tools" / "template" / "new_app.py"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("", encoding="utf-8")
        subprocess.run(["git", "add", "tools/template/new_app.py"], cwd=self.root, env=clean_env(), check=True)
        self.app = Path(self._tmp.name) / "Demo.app"
        self.make_app()

    # --- dựng dữ liệu ---

    def set_config(self, text, render=True):
        (self.root / appconfig.CONFIG_FILE).write_text(text, encoding="utf-8")
        self.cfg = appconfig.load(self.root)
        if render:
            appconfig.write_generated(self.root, self.cfg)

    def make_app(self, info=None, gsp=None, with_debug_symbol=False, extra_files=(), binary=None, privacy=None):
        if self.app.exists():
            shutil.rmtree(self.app)
        self.app.mkdir()
        base = {
            "CFBundleExecutable": "Demo",
            "CFBundleIdentifier": "com.example.demo",
            "CFBundleDisplayName": "Demo",
            "CFBundleShortVersionString": "1.2.3",
            "CFBundleVersion": "45",
            "UIDeviceFamily": [1],
            "WebHost": "",
            "FeaturePaywall": "NO",
            "FeatureWebAPI": "NO",
            "FeatureAppleAds": "NO",
        }
        base.update(info or {})
        (self.app / "Info.plist").write_bytes(plistlib.dumps(base))
        # Plist "thật": không mang dấu fixture.
        g = {"BUNDLE_ID": "com.example.demo", "PROJECT_ID": "demo-prod", "API_KEY": "AIzaThatLooksReal"}
        if gsp is not None:
            g = gsp
        (self.app / "GoogleService-Info.plist").write_bytes(plistlib.dumps(g))
        # Privacy manifest: mặc định khớp công tắc của Info.plist (kiểu luôn có + kiểu của mọi khối YES); `privacy` =
        # danh sách kiểu dữ liệu khai đúng như vậy (test cổng 7 dựng lệch).
        if privacy is None:
            privacy = list(ALWAYS_TYPES) + [t for key, types in BLOCK_TYPES.items() if base.get(key) == "YES"
                                            for t in types]
        manifest = {"NSPrivacyTracking": False, "NSPrivacyCollectedDataTypes": [
            {"NSPrivacyCollectedDataType": t, "NSPrivacyCollectedDataTypeLinked": False} for t in privacy]}
        (self.app / "PrivacyInfo.xcprivacy").write_bytes(plistlib.dumps(manifest))
        binary_name, binary = binary, self.app / "Demo"
        binary.write_bytes(self.binaries[binary_name or ("debug" if with_debug_symbol else "plain")])
        binary.chmod(0o755)
        for rel in extra_files:
            f = self.app / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("{}", encoding="utf-8")

    def gate(self, *flags, target=None, **env):
        target = str(target or self.app)
        return subprocess.run(["bash", str(self.root / "tools/release/verify_release_clean.sh"), *flags, target],
                              cwd=self._tmp.name, env=clean_env(**env), capture_output=True, text=True)

    def assert_pass(self, r):
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS", r.stdout)

    def assert_fail(self, r, needle):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(needle, r.stdout + r.stderr)

    # --- đối chứng dương ---

    def test_app_dung_cau_hinh_thi_qua(self):
        self.assert_pass(self.gate())

    # --- I7a: plist fixture ---

    def test_plist_fixture_bi_tu_choi(self):
        self.make_app(gsp=plistlib.loads(appconfig.fixture_plist(self.cfg, "Release")))
        self.assert_fail(self.gate(), "fixture")

    def test_plist_fixture_chi_co_api_key_sentinel_van_bi_tu_choi(self):
        self.make_app(gsp={"BUNDLE_ID": "com.example.demo", "PROJECT_ID": "x", "API_KEY": appconfig.FIXTURE_API_KEY})
        self.assert_fail(self.gate(), "fixture")

    def test_plist_fixture_duoc_phep_khi_co_bien(self):
        self.make_app(gsp=plistlib.loads(appconfig.fixture_plist(self.cfg, "Release")))
        self.assert_pass(self.gate(ALLOW_FIXTURE_PLIST="1"))

    # --- I7b: appconfig check + đối chiếu Info.plist với cấu hình ---

    def test_xcconfig_cu_bi_tu_choi(self):
        self.set_config(CONFIG.replace('build = "45"', 'build = "46"'), render=False)
        self.make_app(info={"CFBundleVersion": "46"})
        self.assert_fail(self.gate(), "render")

    def test_cau_hinh_hong_bi_tu_choi(self):
        (self.root / appconfig.CONFIG_FILE).write_text(CONFIG.replace('team_id = "0000000000"\n', ""),
                                                      encoding="utf-8")
        self.assert_fail(self.gate(), "apple.team_id")

    def test_ten_hien_thi_lech_cau_hinh_bi_tu_choi(self):
        self.make_app(info={"CFBundleDisplayName": "Demo Khác"})
        self.assert_fail(self.gate(), "CFBundleDisplayName")

    def test_marketing_version_lech_bi_tu_choi(self):
        self.make_app(info={"CFBundleShortVersionString": "1.2.4"})
        self.assert_fail(self.gate(), "CFBundleShortVersionString")

    def test_build_number_lech_bi_tu_choi(self):
        self.make_app(info={"CFBundleVersion": "44"})
        self.assert_fail(self.gate(), "CFBundleVersion")

    # --- I7c: dòng debug_symbols.txt có khoảng trắng / CRLF vẫn gác ---

    def write_symbols(self, text):
        (self.root / "tools/release/debug_symbols.txt").write_bytes(text.encode("utf-8"))

    def test_symbol_co_khoang_trang_cuoi_va_crlf_van_gac(self):
        self.write_symbols("# chú thích\r\n [binary] \r\n  InternalDebugMarkerView \t\r\n")
        self.make_app(with_debug_symbol=True)
        self.assert_fail(self.gate(), "còn symbol debug 'InternalDebugMarkerView'")

    def test_danh_sach_chi_khoang_trang_la_qua_trong(self):
        self.write_symbols("# chỉ chú thích\r\n[binary]\r\n   \r\n\t\n[source-only]\nhamDebug\n")
        self.assert_fail(self.gate(), "không có dòng nào có hiệu lực")

    def test_symbol_khong_co_trong_binary_thi_qua(self):
        self.write_symbols("[binary]\r\nInternalDebugMarkerView\r\n")
        self.assert_pass(self.gate())

    def test_symbol_dong_sach_van_gac(self):
        # Đối chứng: binary có symbol + danh sách gốc (LF) ⇒ bị bắt; nếu cái này không đỏ thì test CRLF vô nghĩa.
        self.make_app(with_debug_symbol=True)
        self.assert_fail(self.gate(), "còn symbol debug 'InternalDebugMarkerView'")

    # --- Plan 4 Task 3: danh sách của lõi + danh sách của app, cổng 1 đọc hợp ---

    def write_app_symbols(self, text):
        p = self.root / "AppHost/Config/debug_symbols.app.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))

    def test_ten_app_chi_o_file_app_van_bi_cong_1_bat(self):
        self.write_symbols("[binary]\nMotTenKhacCuaLoi\n")
        self.write_app_symbols("# danh sách của app\n[binary]\nInternalDebugMarkerView\n")
        self.make_app(with_debug_symbol=True)
        self.assert_fail(self.gate(), "còn symbol debug 'InternalDebugMarkerView'")

    def test_thieu_file_app_cong_1_van_chay_voi_file_loi(self):
        self.write_symbols("[binary]\nInternalDebugMarkerView\n")
        self.assertFalse((self.root / "AppHost/Config/debug_symbols.app.txt").exists())
        self.make_app(with_debug_symbol=True)
        self.assert_fail(self.gate(), "còn symbol debug 'InternalDebugMarkerView'")

    def test_ten_trung_hai_file_cong_1_tu_choi(self):
        self.write_symbols("[binary]\nInternalDebugMarkerView\n")
        self.write_app_symbols("[binary]\nInternalDebugMarkerView\n")
        self.assert_fail(self.gate(), "debug_symbols.app.txt")

    def test_doi_chung_duong_doc_ca_ten_cua_app(self):
        # Đối chứng dương trên .app Internal: tên [binary] của app không có trong binary cũng phải bị bắt.
        self.write_symbols("[binary]\nInternalDebugMarkerView\n")
        self.write_app_symbols("[binary]\nTenAppKhongCoTrongBinary\n")
        self.make_app(with_debug_symbol=True)
        r = self.gate("--expect-debug-symbols")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("TenAppKhongCoTrongBinary", r.stdout + r.stderr)

    # --- R18: hai mục [binary] / [source-only] ---

    def test_chi_soi_muc_binary(self):
        # Tên ở [source-only] có mặt trong binary vẫn KHÔNG bị soi (tên hàm vốn bị strip — soi là an tâm giả);
        # tên [binary] không có trong binary ⇒ qua. Nếu script grep nhầm mục, test này đỏ.
        self.write_symbols("[binary]\nKhongCoTrongBinary\n[source-only]\nInternalDebugMarkerView\n")
        self.make_app(with_debug_symbol=True)
        r = self.gate()
        self.assert_pass(r)
        self.assertIn("soi 1 tên [binary]", r.stdout)
        self.assertIn("1 tên [source-only] không soi binary", r.stdout)

    def test_muc_binary_van_bi_soi(self):
        self.write_symbols("[source-only]\nhamDebug\n[binary]\nInternalDebugMarkerView\n")
        self.make_app(with_debug_symbol=True)
        self.assert_fail(self.gate(), "còn symbol debug 'InternalDebugMarkerView'")

    def test_ten_truoc_moi_muc_bi_tu_choi(self):
        self.write_symbols("InternalDebugMarkerView\n[binary]\nKhac\n")
        self.assert_fail(self.gate(), "đứng trước mọi mục")

    def test_muc_la_bi_tu_choi(self):
        self.write_symbols("[binary]\nKhac\n[binnary]\nX\n")
        self.assert_fail(self.gate(), "mục lạ '[binnary]'")

    def test_lint_nguon_chay_trong_cong(self):
        # Không SKIP_SYMBOL_LINT: repo giả không có nguồn khai InternalDebugMarkerView ⇒ lint báo mồ côi ⇒ cổng FAIL.
        self.write_symbols("[binary]\nInternalDebugMarkerView\n")
        self.assert_fail(self.gate(SKIP_SYMBOL_LINT="0"), "lệch nguồn")
        src = self.root / "Core" / "Internal" / "Marker.swift"
        src.parent.mkdir(parents=True)
        src.write_text("#if INTERNAL\nstruct InternalDebugMarkerView {}\n#endif\n", encoding="utf-8")
        self.assert_pass(self.gate(SKIP_SYMBOL_LINT="0"))

    # --- R18: đối chứng dương trên .app Internal (--expect-debug-symbols) ---

    def test_doi_chung_moi_ten_binary_co_mat_thi_qua(self):
        self.write_symbols("[binary]\nInternalDebugMarkerView\n[source-only]\nhamKhongCoTrongBinary\n")
        self.make_app(with_debug_symbol=True)
        r = self.gate("--expect-debug-symbols")
        self.assert_pass(r)
        self.assertIn("1/1 tên [binary]", r.stdout)

    def test_doi_chung_ten_binary_vang_mat_la_muc_vo_tac_dung(self):
        self.write_symbols("[binary]\nInternalDebugMarkerView\nTypeBiOptimizerBo\n")
        self.make_app(with_debug_symbol=True)
        r = self.gate("--expect-debug-symbols")
        self.assert_fail(r, "mục vô tác dụng: 'TypeBiOptimizerBo'")
        self.assertNotIn("'InternalDebugMarkerView' ([binary]) không có", r.stdout)

    def test_doi_chung_binary_khong_co_gi_thi_do(self):
        self.write_symbols("[binary]\nInternalDebugMarkerView\n")
        self.make_app(with_debug_symbol=False)
        self.assert_fail(self.gate("--expect-debug-symbols"), "mục vô tác dụng: 'InternalDebugMarkerView'")

    def test_doi_chung_muc_binary_rong_thi_do(self):
        self.write_symbols("[source-only]\nhamDebug\n")
        self.make_app(with_debug_symbol=True)
        self.assert_fail(self.gate("--expect-debug-symbols"), "không có dòng nào có hiệu lực")

    def test_doi_chung_khong_kiem_dinh_danh(self):
        # Chế độ đối chứng chạy trên .app Internal (bundle id khác Store) — không được FAIL vì định danh.
        self.write_symbols("[binary]\nInternalDebugMarkerView\n")
        self.make_app(info={"CFBundleIdentifier": "com.example.demo.internal"}, with_debug_symbol=True)
        self.assert_pass(self.gate("--expect-debug-symbols"))

    # --- cổng 14: tính năng mẫu của template ---

    def test_con_tinh_nang_mau_thi_fail(self):
        self.make_app(binary="sample")
        self.assert_fail(self.gate(), "còn tính năng mẫu trong bản Store — chạy tools/template/remove_sample.py")

    def test_cho_phep_bang_bien_moi_truong(self):
        self.make_app(binary="sample")
        r = self.gate(ALLOW_SAMPLE_IN_RELEASE="1")
        self.assert_pass(r)
        self.assertIn("cổng 14 (tính năng mẫu): BỎ QUA", r.stdout)

    def test_bien_khac_1_khong_cho_phep(self):
        self.make_app(binary="sample")
        self.assert_fail(self.gate(ALLOW_SAMPLE_IN_RELEASE="0"), "còn tính năng mẫu")

    def make_archive(self, **kw):
        """`.xcarchive` giả bọc `.app` (Products/Applications/Demo.app); trả đường dẫn archive."""
        archive = Path(self._tmp.name) / "Demo.xcarchive"
        self.app = archive / "Products" / "Applications" / "Demo.app"
        self.app.parent.mkdir(parents=True, exist_ok=True)
        self.make_app(**kw)
        return archive

    def test_archive_khong_duoc_bo_qua_cong_14(self):
        archive = self.make_archive(binary="sample")
        r = self.gate(target=archive, ALLOW_SAMPLE_IN_RELEASE="1")
        self.assert_fail(r, "ALLOW_SAMPLE_IN_RELEASE=1 không áp dụng cho .xcarchive")
        self.assertNotIn("BỎ QUA — binary còn", r.stdout)

    def test_archive_sach_thi_qua(self):
        archive = self.make_archive()
        self.assert_pass(self.gate(target=archive))

    def test_app_tran_van_duoc_bo_qua_cong_14(self):
        # Đối chứng: cùng binary nhưng .app trần (sản phẩm build của tự kiểm) ⇒ biến có hiệu lực.
        self.make_app(binary="sample")
        self.assert_pass(self.gate(ALLOW_SAMPLE_IN_RELEASE="1"))

    # --- cổng 16: nội dung site (web/site/public) trước khi ra bản ---

    SITE_PAGES = ("index.html", "privacy/index.html", "terms/index.html", "support/index.html")
    # Host "đã điền thật" (không thuộc tên miền dành riêng — check_site --release từ chối example.com, *.test…).
    SITE_HOST = "demo-site.net"

    def host_config(self, external=False):
        self.set_config(CONFIG.replace('host_prod = ""', f'host_prod = "{self.SITE_HOST}"')
                        .replace('host_dev = ""', f'host_dev = "dev.{self.SITE_HOST}"')
                        .replace("external_site = true", f"external_site = {'true' if external else 'false'}"))

    def with_site(self, placeholder_in=None):
        """App có web (host) + bốn trang bất biến; `placeholder_in` = trang còn chữ giữ chỗ."""
        self.host_config()
        for rel in self.SITE_PAGES:
            text = "<p>TEMPLATE-PLACEHOLDER — mô tả</p>\n" if rel == placeholder_in else "<p>nội dung thật</p>\n"
            p = self.root / "web/site/public" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        self.make_app(info={"WebHost": self.SITE_HOST})

    def test_cong_16_tu_choi_placeholder(self):
        self.with_site(placeholder_in="terms/index.html")
        r = self.gate()
        self.assert_fail(r, "cổng 16")
        self.assertIn("terms/index.html", r.stdout + r.stderr)

    def test_cong_16_site_xong_thi_qua(self):
        self.with_site()
        r = self.gate()
        self.assert_pass(r)
        self.assertIn("cổng 16", r.stdout)

    def test_cong_16_thieu_trang_bat_bien_bi_tu_choi(self):
        self.with_site()
        (self.root / "web/site/public/privacy/index.html").unlink()
        self.assert_fail(self.gate(), "cổng 16")

    def test_cong_16_khong_co_web_thi_bo_qua(self):
        r = self.gate()
        self.assert_pass(r)
        self.assertIn("cổng 16 (site): BỎ QUA", r.stdout)

    def test_cong_16_co_host_ma_thieu_cong_cu_thi_fail(self):
        self.with_site()
        (self.root / "web/tools/check_site.py").unlink()
        self.assert_fail(self.gate(), "web/tools/check_site.py")

    def test_cong_16_cho_phep_cho_giu_cho_o_app_tran(self):
        # Tự kiểm của template (app sinh ra còn chữ giữ chỗ) đặt biến: vẫn kiểm trang bất biến, chỉ hạ giữ chỗ thành cảnh báo.
        self.with_site(placeholder_in="terms/index.html")
        r = self.gate(ALLOW_SITE_PLACEHOLDER="1")
        self.assert_pass(r)
        self.assertIn("ALLOW_SITE_PLACEHOLDER=1", r.stdout)
        (self.root / "web/site/public/privacy/index.html").unlink()
        self.assert_fail(self.gate(ALLOW_SITE_PLACEHOLDER="1"), "cổng 16")

    def test_cong_16_co_host_ma_khong_co_site_thi_fail(self):
        # Ruling 12: thiếu web/site/public/ mà không khai site ngoài repo ⇒ FAIL, không bao giờ in OK (check_site.py
        # tự SKIP khi thiếu thư mục — cổng không được dựa vào đó). Cả .app lẫn .xcarchive.
        self.host_config()
        self.make_app(info={"WebHost": self.SITE_HOST})
        r = self.gate()
        self.assert_fail(r, "web/site/public")
        self.assertNotIn("cổng 16 (site): OK", r.stdout)
        archive = self.make_archive(info={"WebHost": self.SITE_HOST})
        self.assert_fail(self.gate(target=archive), "web/site/public")

    def test_cong_16_site_ngoai_repo_thi_skip_thay_ro(self):
        self.host_config(external=True)
        (self.root / "web/tools/check_site.py").unlink()     # không cần công cụ khi site ở ngoài repo
        self.make_app(info={"WebHost": self.SITE_HOST})
        r = self.gate()
        self.assert_pass(r)
        self.assertIn("cổng 16 (site): SKIP (web.external_site)", r.stdout)
        self.assertNotIn("cổng 16 (site): OK", r.stdout)

    def test_cong_16_archive_khong_duoc_bo_qua_giu_cho(self):
        archive = self.make_archive()
        self.with_site(placeholder_in="terms/index.html")
        self.assert_fail(self.gate(target=archive, ALLOW_SITE_PLACEHOLDER="1"),
                         "ALLOW_SITE_PLACEHOLDER=1 không áp dụng cho .xcarchive")

    # --- cổng 4: không *.md trong bundle ---

    def test_file_md_trong_app_bi_tu_choi(self):
        self.make_app(extra_files=("Features/Sample/README.md",))
        self.assert_fail(self.gate(), "Markdown")

    def test_readme_trong_sampledata_cung_bi_tu_choi(self):
        self.make_app(extra_files=("SampleData/README.md",))
        self.assert_fail(self.gate(), "Markdown")

    def test_md_cua_ben_thu_ba_trong_frameworks_plugins_bundle_thi_qua(self):
        # Resource bundle / framework / extension của bên thứ ba được ship README — không phải tài liệu nguồn của app.
        self.make_app(extra_files=("Frameworks/Vendor.framework/README.md", "PlugIns/Ext.appex/NOTES.md",
                                   "Vendor_Resources.bundle/README.md", "Sub/Deep.bundle/CHANGELOG.md"))
        self.assert_pass(self.gate())

    def test_md_cua_app_canh_bundle_van_bi_tu_choi(self):
        # Đối chứng: cùng cây có bundle bên thứ ba, nhưng README nằm ở resource của app ⇒ vẫn FAIL, đúng file đó.
        self.make_app(extra_files=("Vendor_Resources.bundle/README.md", "Frameworks/Vendor.framework/README.md",
                                   "Docs/GUIDE.md", "FrameworksNotes.md"))
        r = self.gate()
        self.assert_fail(r, "Markdown")
        self.assertIn("Docs/GUIDE.md", r.stdout)
        self.assertIn("FrameworksNotes.md", r.stdout)
        self.assertNotIn("Vendor_Resources.bundle/README.md", r.stdout)
        self.assertNotIn("Vendor.framework/README.md", r.stdout)

    def test_khong_co_thi_qua(self):
        # Không có mốc ⇒ qua dù KHÔNG đặt biến, và không in dòng "BỎ QUA" (biến chỉ có tác dụng khi có mốc).
        r = self.gate()
        self.assert_pass(r)
        self.assertNotIn("cổng 14", r.stdout)
        self.assertNotIn("tính năng mẫu trong bản Store", r.stdout)

    def test_sai_cach_dung_rc2(self):
        r = subprocess.run(["bash", str(self.root / "tools/release/verify_release_clean.sh"), "--expect-debug-symbols"],
                           cwd=self._tmp.name, env=clean_env(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    # --- Cổng 13: paywall ---

    def paywall_on(self, **info):
        self.set_config(PAYWALL_ON)
        base = {"FeaturePaywall": "YES", "ProductIDs": "p.monthly p.lifetime", "WebHost": "example.com"}
        base.update(info)
        return base

    def test_paywall_bat_du_dieu_kien_thi_qua(self):
        self.make_app(info=self.paywall_on())
        self.assert_pass(self.gate())

    def test_paywall_bat_thieu_product_ids_bi_tu_choi(self):
        self.make_app(info=self.paywall_on(ProductIDs=""))
        self.assert_fail(self.gate(), "ProductIDs rỗng")
        self.make_app(info=self.paywall_on(ProductIDs="  "))
        self.assert_fail(self.gate(), "ProductIDs rỗng")

    def test_paywall_bat_thieu_webhost_bi_tu_choi(self):
        self.make_app(info=self.paywall_on(WebHost=""))
        self.assert_fail(self.gate(), "WebHost rỗng")

    def test_paywall_bat_co_file_storekit_trong_app_bi_tu_choi(self):
        self.make_app(info=self.paywall_on(), extra_files=("Products.storekit",))
        self.assert_fail(self.gate(), "Products.storekit")
        self.make_app(info=self.paywall_on(), extra_files=("Plugins/X.appex/Khac.STOREKIT",))
        self.assert_fail(self.gate(), "Khac.STOREKIT")

    def test_paywall_tat_thi_bo_qua(self):
        # Cấu hình mặc định của test không có [features] ⇒ paywall tắt: ProductIDs/WebHost rỗng không bị bắt.
        self.make_app(info={"ProductIDs": "", "WebHost": ""})
        r = self.gate()
        self.assert_pass(r)
        self.assertIn("cổng 13 (paywall): BỎ QUA", r.stdout)

    def test_paywall_tat_van_cam_file_storekit_trong_app(self):
        # File StoreKit thử trong .app là rò dữ liệu thử dù app không bán gì ⇒ kiểm KHÔNG phụ thuộc công tắc paywall.
        self.make_app(info={"ProductIDs": ""}, extra_files=("Products.storekit",))
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Products.storekit", r.stdout)

    def test_feature_paywall_lech_cau_hinh_bi_tu_choi(self):
        self.make_app(info=self.paywall_on(FeaturePaywall="NO"))
        self.assert_fail(self.gate(), "FeaturePaywall là 'NO'")
        self.set_config(CONFIG)
        self.make_app(info={"FeaturePaywall": "YES"})
        self.assert_fail(self.gate(), "FeaturePaywall là 'YES'")

    # --- Cổng 7: privacy manifest khớp công tắc trong Info.plist ---

    ALL_ON = {"FeaturePaywall": "YES", "FeatureWebAPI": "YES", "FeatureAppleAds": "YES",
              "ProductIDs": "p.monthly p.lifetime", "WebHost": "example.com"}

    def test_manifest_khop_cong_tac_thi_qua(self):
        self.set_config(PAYWALL_ON)
        self.make_app(info=self.ALL_ON)
        self.assert_pass(self.gate())
        self.set_config(CONFIG)
        self.make_app()   # tắt hết ⇒ chỉ kiểu luôn có
        self.assert_pass(self.gate())

    def test_khai_bao_khoi_tat_thi_fail(self):
        for key, types in BLOCK_TYPES.items():
            with self.subTest(key=key):
                self.make_app(privacy=list(ALWAYS_TYPES) + [types[-1]])
                r = self.gate()
                self.assert_fail(r, f"privacy manifest còn khai {types[-1]} — {key} = NO")
                self.assertEqual(r.stdout.count("privacy manifest"), 1, r.stdout)

    def test_thieu_khai_bao_khoi_bat_thi_fail(self):
        self.set_config(PAYWALL_ON)
        every = list(ALWAYS_TYPES) + [t for types in BLOCK_TYPES.values() for t in types]
        for key, types in BLOCK_TYPES.items():
            for t in types:
                with self.subTest(thieu=t):
                    self.make_app(info=self.ALL_ON, privacy=[x for x in every if x != t])
                    self.assert_fail(self.gate(), f"privacy manifest THIẾU {t} — {key} = YES")

    def test_lech_nhieu_kieu_neu_tung_kieu(self):
        # web_api tắt mà còn đủ hai kiểu ⇒ hai dòng FAIL, mỗi kiểu một dòng.
        types = BLOCK_TYPES["FeatureWebAPI"]
        self.make_app(privacy=list(ALWAYS_TYPES) + list(types))
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        for t in types:
            self.assertIn(f"còn khai {t}", r.stdout)

    def test_info_thieu_khoa_cong_tac_thi_fail(self):
        self.make_app()
        info = plistlib.loads((self.app / "Info.plist").read_bytes())
        del info["FeatureAppleAds"]
        (self.app / "Info.plist").write_bytes(plistlib.dumps(info))
        self.assert_fail(self.gate(), "Info.plist FeatureAppleAds là None (cần YES|NO)")

    def test_manifest_hong_thi_fail(self):
        (self.app / "PrivacyInfo.xcprivacy").write_bytes(b"<plist><dict>")
        self.assert_fail(self.gate(), "không đọc được Info.plist / PrivacyInfo.xcprivacy")

    def test_manifest_sinh_tu_mau_that_qua_cong_moi_to_hop(self):
        # Bốn tổ hợp feature_matrix_check dựng (bật hết, tắt hết, tắt từng cái): manifest do appconfig cắt từ MẪU THẬT
        # phải qua cổng 7 với Info.plist cùng công tắc.
        combos = [dict(paywall=True, web_api=True, apple_ads=True), dict(paywall=False, web_api=False, apple_ads=False),
                  dict(paywall=False, web_api=True, apple_ads=True), dict(paywall=True, web_api=False, apple_ads=True),
                  dict(paywall=True, web_api=True, apple_ads=False)]
        keys = {"paywall": "FeaturePaywall", "web_api": "FeatureWebAPI", "apple_ads": "FeatureAppleAds"}
        for combo in combos:
            with self.subTest(**combo):
                cfg_text = PAYWALL_ON.replace("[features]\npaywall = true\n", "[features]\n" + "".join(
                    f"{k} = {str(v).lower()}\n" for k, v in combo.items()))
                self.set_config(cfg_text)
                manifest = appconfig.render_privacy_manifest(self.cfg)
                info = dict(self.ALL_ON, **{keys[k]: ("YES" if v else "NO") for k, v in combo.items()})
                self.make_app(info=info)
                (self.app / "PrivacyInfo.xcprivacy").write_bytes(manifest)
                self.assert_pass(self.gate())

    # --- I8: cổng 10 WebHost ---

    def test_webhost_dung_host_prod_thi_qua(self):
        self.set_config(CONFIG.replace('host_prod = ""', 'host_prod = "api.example.com"')
                        .replace('host_dev = ""', 'host_dev = "dev.example.com"'))
        self.make_app(info={"WebHost": "api.example.com"})
        self.assert_pass(self.gate())

    def test_webhost_tro_dev_bi_tu_choi(self):
        self.set_config(CONFIG.replace('host_prod = ""', 'host_prod = "api.example.com"')
                        .replace('host_dev = ""', 'host_dev = "dev.example.com"'))
        self.make_app(info={"WebHost": "dev.example.com"})
        self.assert_fail(self.gate(), "WebHost")

    # --- cổng 10: Universal Link (associated-domains) trên bản ĐÃ KÝ (ký ad-hoc kèm entitlement) ---

    WEB = (CONFIG.replace('host_prod = ""', 'host_prod = "api.example.com"')
           .replace('host_dev = ""', 'host_dev = "dev.example.com"'))

    def sign(self, domains):
        """Ký ad-hoc `.app` với entitlement associated-domains = `domains` (`None` ⇒ entitlement không có khoá)."""
        ents = {} if domains is None else {"com.apple.developer.associated-domains": domains}
        ents["com.apple.security.get-task-allow"] = False  # khoá khác: luôn có gì đó để ký
        path = Path(self._tmp.name) / "ents.plist"
        path.write_bytes(plistlib.dumps(ents))
        r = subprocess.run(["codesign", "-s", "-", "-f", "--entitlements", str(path), str(self.app)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    @unittest.skipUnless(shutil.which("codesign"), "cần codesign")
    def test_applinks_host_prod_thi_qua(self):
        self.set_config(self.WEB)
        self.make_app(info={"WebHost": "api.example.com"})
        self.sign(["applinks:api.example.com"])
        self.assert_pass(self.gate())

    @unittest.skipUnless(shutil.which("codesign"), "cần codesign")
    def test_applinks_host_dev_o_ban_store_thi_fail(self):
        self.set_config(self.WEB)
        self.make_app(info={"WebHost": "api.example.com"})
        self.sign(["applinks:dev.example.com"])
        r = self.gate()
        self.assert_fail(r, "host dev 'dev.example.com'")
        # Mục prod đủ mà THÊM mục dev ⇒ vẫn đỏ vì host dev (không chỉ vì "đúng một mục").
        self.sign(["applinks:api.example.com", "webcredentials:dev.example.com"])
        self.assert_fail(self.gate(), "host dev 'dev.example.com'")

    @unittest.skipUnless(shutil.which("codesign"), "cần codesign")
    def test_applinks_thieu_hoac_thua_thi_fail(self):
        self.set_config(self.WEB)
        self.make_app(info={"WebHost": "api.example.com"})
        for domains in ([], ["applinks:api.example.com?mode=developer"],
                        ["applinks:api.example.com", "applinks:khac.example.com"]):
            with self.subTest(domains=domains):
                self.sign(domains)
                self.assert_fail(self.gate(), "đúng một mục applinks:api.example.com")

    @unittest.skipUnless(shutil.which("codesign"), "cần codesign")
    def test_ban_ky_co_host_ma_thieu_khoa_thi_fail(self):
        self.set_config(self.WEB)
        self.make_app(info={"WebHost": "api.example.com"})
        r = self.gate()
        self.assert_pass(r)   # đối chứng: chưa ký ⇒ qua, nhưng nói rõ là chưa soi
        self.assertIn("cổng 10 BỎ QUA: build không ký", r.stdout)
        self.sign(None)
        r = self.gate()
        self.assert_fail(r, "bản đã ký thiếu entitlement associated-domains")
        self.assertNotIn("cổng 10 BỎ QUA", r.stdout)

    @unittest.skipUnless(shutil.which("codesign"), "cần codesign")
    def test_host_dev_la_chuoi_con_cua_host_prod_van_qua(self):
        self.set_config(CONFIG.replace('host_prod = ""', 'host_prod = "www.example.com"')
                        .replace('host_dev = ""', 'host_dev = "example.com"'))
        self.make_app(info={"WebHost": "www.example.com"})
        self.sign(["applinks:www.example.com"])
        self.assert_pass(self.gate())

    @unittest.skipUnless(shutil.which("codesign"), "cần codesign")
    def test_khong_host_ma_co_associated_domains_thi_fail(self):
        self.sign(None)
        self.assert_pass(self.gate())  # đối chứng: đã ký, không khoá ⇒ qua
        self.sign(["applinks:api.example.com"])
        self.assert_fail(self.gate(), "web.host_prod rỗng nhưng entitlement có associated-domains")


    # --- cổng 15: lõi khớp core.lock (chỉ ở app) ---

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, env=clean_env(), capture_output=True, text=True)

    def copy_template_tools(self):
        for rel in ("tools/template/sync_core.py", "tools/template/manifest.py", "tools/template/blocks.py"):
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)

    def make_app_repo(self):
        """Biến repo tạm thành "app": chép sync_core + manifest + blocks, khai manifest, một file lõi, track mọi file,
        ghi core.lock (dựng từ danh sách của git) và track nó; gỡ dấu template (new_app.py)."""
        self.git("rm", "-q", "-f", "tools/template/new_app.py")
        self.copy_template_tools()
        (self.root / "template.manifest.toml").write_text(
            'schema = 1\n[sync]\npaths = ["tools/", "Loi/", "template.manifest.toml"]\n'
            '[seed]\npaths = ["app.config.toml", "AppHost/"]\n[template_only]\npaths = []\n', encoding="utf-8")
        (self.root / "Loi").mkdir()
        (self.root / "Loi" / "loi.txt").write_text("lõi của template\n", encoding="utf-8")
        sys.path.insert(0, str(REPO / "tools" / "template"))
        import manifest as mf
        import sync_core
        self.git("add", "-A")
        sync_core.write_lock(self.root, sync_core.build_lock(self.root, mf.load(self.root), source="/nguon",
                                                             tag="v0.4.0", commit="e" * 40))
        self.git("add", "core.lock")

    def test_khong_track_lock_thi_bo_qua_ca_khi_co_lock_lac(self):
        # Đi đường git (có manifest.py): lock lạc chưa track ⇒ vẫn là template.
        self.copy_template_tools()
        (self.root / "core.lock").write_text("{ lạc", encoding="utf-8")
        r = self.gate()
        self.assert_pass(r)
        self.assertIn("đây là template", r.stdout)
        self.assertNotIn("quyết định theo file", r.stdout)

    def test_lock_bi_xoa_khoi_dia_nhung_con_track_thi_fail(self):
        self.make_app_repo()
        (self.root / "core.lock").unlink()
        r = self.gate()
        self.assert_fail(r, "git restore --staged --worktree core.lock")
        self.assertNotIn("đây là template", r.stdout)

    def test_file_moi_track_trong_thu_muc_dong_bo_thi_fail(self):
        self.make_app_repo()
        (self.root / "Loi" / "Moi.swift").write_text("extension X {}\n", encoding="utf-8")
        self.assert_pass(self.gate())              # chưa track ⇒ chưa tính
        self.git("add", "Loi/Moi.swift")
        self.assert_fail(self.gate(), "A Loi/Moi.swift")

    def test_lock_go_da_commit_thi_fail(self):
        # Gỡ lock (± công cụ) và COMMIT bằng --no-verify: repo không có dấu template ⇒ vẫn là app ⇒ FAIL, không "BỎ QUA".
        self.make_app_repo()
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "app")
        for tools, needle in (((), "không có core.lock"),
                              (("tools/template/manifest.py", "tools/template/sync_core.py"),
                               "thiếu tools/template/manifest.py")):
            with self.subTest(tools=tools):
                self.git("rm", "-q", "core.lock", *tools)
                (self.root / "Loi" / "loi.txt").write_text("sửa\n", encoding="utf-8")
                self.git(*GIT_ID, "commit", "-q", "-a", "--no-verify", "-m", "gỡ cổng")
                r = self.gate()
                self.assert_fail(r, needle)
                self.assertIn("git log --diff-filter=D --oneline", r.stdout)
                self.assertNotIn("đây là template", r.stdout)
                self.git("checkout", "HEAD^", "--", "core.lock", "Loi/loi.txt", *tools)
                self.assert_pass(self.gate())
                self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "khôi phục")

    def test_khong_dau_template_khong_lock_thi_fail(self):
        # Clone kiểu "app chưa đặt core.hooksPath, HEAD không có lock": không dấu template, không lock ⇒ FAIL.
        self.git("rm", "-q", "-f", "tools/template/new_app.py")
        self.copy_template_tools()
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "app thiếu lock")
        r = self.gate()
        self.assert_fail(r, "không có core.lock")
        self.assertNotIn("đây là template", r.stdout)

    def test_xoa_lock_va_cong_cu_khong_tat_duoc_cong(self):
        # `git rm core.lock tools/template/manifest.py (+ sync_core.py)` + sửa lõi: quyết định "là app" bằng git thuần
        # (HEAD còn lock) ⇒ thiếu công cụ là FAIL, không phải "đây là template".
        self.make_app_repo()
        self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", "app")
        for extra in ((), ("tools/template/sync_core.py",)):
            with self.subTest(extra=extra):
                self.git("rm", "-q", "core.lock", "tools/template/manifest.py", *extra)
                (self.root / "Loi" / "loi.txt").write_text("sửa\n", encoding="utf-8")
                r = self.gate()
                self.assert_fail(r, "thiếu tools/template/manifest.py")
                self.assertIn("git restore --staged --worktree tools/template/manifest.py", r.stdout)
                self.assertNotIn("đây là template", r.stdout)
                # Đưa repo TẠM về như cũ cho vòng sau (đúng lệnh khôi phục mà cổng chỉ).
                self.git("restore", "--source=HEAD", "--staged", "--worktree", "--", "core.lock",
                         "tools/template/manifest.py", "Loi/loi.txt", *extra)
                self.assert_pass(self.gate())

    # Lịch sử từng có core.lock ⇒ app dù có dấu template; ở app lock phải được TRACK; loại repo xét theo HEAD.

    MARKER = "tools/template/new_app.py"

    def commit(self, msg, *extra):
        r = self.git(*GIT_ID, "commit", "-q", "--no-verify", "-m", msg, *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_app_go_lock_them_dau_template_da_commit_van_la_app(self):
        # App gỡ lock (± công cụ) + thêm new_app.py rỗng + sửa lõi, commit bằng --no-verify: HEAD có dấu template nhưng
        # LỊCH SỬ có core.lock ⇒ vẫn là app ⇒ FAIL, không "BỎ QUA … đây là template".
        self.make_app_repo()
        self.commit("app")
        for tools, needle in (((), "không có core.lock được track"),
                              (("tools/template/manifest.py", "tools/template/sync_core.py"),
                               "thiếu tools/template/manifest.py")):
            with self.subTest(tools=tools):
                self.git("rm", "-q", "core.lock", *tools)
                (self.root / self.MARKER).write_text("", encoding="utf-8")
                self.git("add", self.MARKER)
                (self.root / "Loi" / "loi.txt").write_text("sửa\n", encoding="utf-8")
                self.commit("giả làm template", "-a")
                self.assertEqual(self.git("cat-file", "-e", f"HEAD:{self.MARKER}").returncode, 0, "tiền đề: HEAD có dấu")
                r = self.gate()
                self.assert_fail(r, needle)
                self.assertIn("đây là app (lịch sử có core.lock)", r.stdout)
                self.assertNotIn("đây là template", r.stdout)
                # Khôi phục: gỡ dấu, lấy lại lock + lõi (+ công cụ) từ lịch sử ⇒ qua.
                self.git("rm", "-q", self.MARKER)
                self.git("checkout", "HEAD^", "--", "core.lock", "Loi/loi.txt", *tools)
                self.assert_pass(self.gate())
                self.commit("khôi phục")

    def test_app_giu_lock_co_dau_template_van_kiem_loi(self):
        # App thêm dấu template bằng --no-verify mà giữ lock: lịch sử có lock ⇒ vẫn là app ⇒ lõi lệch vẫn FAIL.
        self.make_app_repo()
        self.commit("app")
        (self.root / self.MARKER).write_text("", encoding="utf-8")
        self.git("add", self.MARKER)
        (self.root / "Loi" / "loi.txt").write_text("sửa tay ở app\n", encoding="utf-8")
        self.commit("có cả hai dấu", "-a")
        r = self.gate()
        self.assert_fail(r, "M Loi/loi.txt")
        self.assertNotIn("đây là template", r.stdout)

    def test_lock_chi_con_tren_dia_khong_track_thi_fail(self):
        # `git rm --cached core.lock` + commit --no-verify: lock chỉ còn trên đĩa (clone khác không có) ⇒ FAIL.
        self.make_app_repo()
        self.commit("app")
        r = self.gate()                              # app nguyên vẹn đã commit ⇒ qua
        self.assert_pass(r)
        self.assertNotIn("đây là template", r.stdout)
        self.git("rm", "-q", "--cached", "core.lock")
        self.commit("bỏ track lock")
        self.assertTrue((self.root / "core.lock").is_file(), "tiền đề: lock còn trên đĩa")
        r = self.gate()
        self.assert_fail(r, "không có core.lock được track")
        self.assertIn("KHÔNG được track", r.stdout)
        self.assertIn("git add core.lock", r.stdout)
        self.assertNotIn("đây là template", r.stdout)
        # `git add -N` (intent-to-add): có mục trong index nhưng không vào commit nào ⇒ vẫn là "chỉ trên đĩa".
        self.git("add", "-N", "core.lock")
        self.assertEqual(self.git("ls-files", "--error-unmatch", "core.lock").returncode, 0, "tiền đề: ls-files thấy mục")
        self.assert_fail(self.gate(), "KHÔNG được track")
        self.git("add", "core.lock")
        self.assert_pass(self.gate())

    def test_goc_khong_phai_repo_git_thi_xet_file_tren_dia(self):
        # Gốc của script là thư mục CON của một repo git (không phải toplevel) ⇒ nhánh "không phải repo git": loại repo
        # theo file đánh dấu trên đĩa, lock phải có trên đĩa; có in rõ là đang xét đĩa.
        inner = self.root / "cây xuất"
        for rel in COPIED:
            dst = inner / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)

        def gate():
            return subprocess.run(["bash", str(inner / "tools/release/verify_release_clean.sh"), str(self.app)],
                                  cwd=self._tmp.name, env=clean_env(), capture_output=True, text=True)

        note = "gốc không phải repo git — quyết định theo file tools/template/new_app.py trên đĩa"
        (inner / self.MARKER).parent.mkdir(parents=True, exist_ok=True)
        (inner / self.MARKER).write_text("", encoding="utf-8")
        r = gate()
        self.assert_pass(r)
        self.assertIn(note, r.stdout)
        self.assertIn("đây là template", r.stdout)
        (inner / self.MARKER).unlink()
        for rel in ("tools/template/sync_core.py", "tools/template/manifest.py", "tools/template/blocks.py"):
            shutil.copy2(REPO / rel, inner / rel)
        r = gate()
        self.assert_fail(r, "không có core.lock trên đĩa")
        self.assertIn(note, r.stdout)
        self.assertIn(f"đây là TEMPLATE mà {self.MARKER} đã bị gỡ", r.stdout)
        # Có lock trên đĩa ⇒ không còn báo thiếu lock; đi tiếp tới sync_core (lock hỏng ⇒ FAIL của bước đó).
        (inner / "core.lock").write_text("{ hỏng", encoding="utf-8")
        r = gate()
        self.assert_fail(r, "core.lock bị gỡ, hỏng")
        self.assertNotIn("không có core.lock trên đĩa", r.stdout)

    def test_template_da_commit_thi_bo_qua(self):
        self.copy_template_tools()
        self.git("add", "-A")
        self.commit("template")
        r = self.gate()
        self.assert_pass(r)
        self.assertIn("BỎ QUA — có tools/template/new_app.py, đây là template", r.stdout)
        # Lock lạc được stage ở template (chưa commit): lịch sử chưa có lock ⇒ vẫn là template (pre-commit chặn commit đó).
        (self.root / "core.lock").write_text("{ lạc", encoding="utf-8")
        self.git("add", "core.lock")
        r = self.gate()
        self.assert_pass(r)
        self.assertIn("đây là template", r.stdout)

    def test_template_mat_file_danh_dau_thi_fail_neu_ca_hai_kha_nang(self):
        # Template gỡ new_app.py bằng --no-verify: không dấu, lịch sử không có lock ⇒ FAIL, thông báo nêu CẢ hai khả năng
        # (app mất lock / template mất file đánh dấu) chứ không khẳng định "lock đã bị gỡ".
        self.copy_template_tools()
        self.git("add", "-A")
        self.commit("template")
        self.git("rm", "-q", self.MARKER)
        self.commit("gỡ dấu")
        r = self.gate()
        self.assert_fail(r, f"đây là TEMPLATE mà {self.MARKER} đã bị gỡ")
        self.assertIn("đây là APP đã mất lock", r.stdout)
        self.assertIn(f"git checkout <commit>^ -- {self.MARKER}", r.stdout)
        self.assertNotIn("lịch sử có core.lock", r.stdout)
        self.assertNotIn("đây là template", r.stdout)
        # Loại repo xét theo HEAD: dấu mới chỉ stage lại ⇒ vẫn FAIL; commit rồi ⇒ template, BỎ QUA.
        self.git("checkout", "HEAD^", "--", self.MARKER)
        self.assert_fail(self.gate(), f"đây là TEMPLATE mà {self.MARKER} đã bị gỡ")
        self.commit("khôi phục dấu")
        r = self.gate()
        self.assert_pass(r)
        self.assertIn("đây là template", r.stdout)

    def test_khong_co_lock_thi_bo_qua(self):
        r = self.gate()
        self.assert_pass(r)
        self.assertIn("cổng 15", r.stdout)
        self.assertIn("đây là template", r.stdout)

    def test_loi_khop_lock_thi_qua(self):
        self.make_app_repo()
        r = self.gate()
        self.assert_pass(r)
        self.assertNotIn("đây là template", r.stdout)

    def test_lech_loi_thi_fail(self):
        self.make_app_repo()
        (self.root / "Loi" / "loi.txt").write_text("sửa tay ở app\n", encoding="utf-8")
        r = self.gate()
        self.assert_fail(r, "M Loi/loi.txt")
        self.assertIn("lệch core.lock", r.stdout)

    def test_lock_hong_thi_fail(self):
        self.make_app_repo()
        (self.root / "core.lock").write_text("{ hỏng", encoding="utf-8")
        self.assert_fail(self.gate(), "core.lock bị gỡ, hỏng")

    def test_co_lock_thieu_sync_core_thi_fail(self):
        self.make_app_repo()
        (self.root / "tools" / "template" / "sync_core.py").unlink()
        self.assert_fail(self.gate(), "thiếu tools/template/sync_core.py")


class TemplateInfoPlistTests(unittest.TestCase):
    """I8: khoá WebHost mà cổng 10 đọc phải thực sự được khai trong project.yml + Info.plist sinh ra."""

    def test_info_plist_co_webhost_tu_build_setting(self):
        info = plistlib.loads((REPO / appconfig.SRC_ROOTS[0] / "Info.plist").read_bytes())
        self.assertEqual(info.get("WebHost"), "$(APP_WEB_HOST)")

    def test_project_yml_noi_app_web_host_theo_config(self):
        text = (REPO / appconfig.PROJ_DIR / "project.yml").read_text(encoding="utf-8")
        self.assertIn("WebHost: $(APP_WEB_HOST)", text)
        self.assertRegex(text, r"Release:\s*\{[^}]*APP_WEB_HOST: \$\(APP_WEB_HOST_PROD\)")
        self.assertRegex(text, r"Debug:\s*\{[^}]*APP_WEB_HOST: \$\(APP_WEB_HOST_DEV\)")
        self.assertRegex(text, r"Internal:\s*\{[^}]*APP_WEB_HOST: \$\(APP_WEB_HOST_DEV\)")


if __name__ == "__main__":
    unittest.main()
