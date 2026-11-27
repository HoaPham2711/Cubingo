"""Test cho tools/template/remove_sample.py — trên cây tạm dựng tay; test "cây thật" chạy trên BẢN CHÉP nguồn (không bao giờ ghi vào repo).

Chạy: python3 -m unittest discover -s tools/template -p 'test_*.py'
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "remove_sample.py"
REPO = HERE.parents[1]

APP = "AppHost/AppHost"
TESTS = "AppHost/AppHostTests"
FEATURE = f"{APP}/Features/Sample"
FEATURE_TESTS = f"{TESTS}/Sample"


def d(s):
    return textwrap.dedent(s).lstrip("\n")


def remove_sample_doc_trace():
    sys.path.insert(0, str(HERE))
    import remove_sample
    return remove_sample.DOC_TRACE_RE


class RemoveSampleTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo có dấu cách"
        self.write(f"{FEATURE}/SampleItemStore.swift", "final class SampleItemStore {}\n")
        self.write(f"{FEATURE}/README.md", "# mẫu\n")
        self.write(f"{FEATURE_TESTS}/SampleItemStoreTests.swift", "final class SampleItemStoreTests {}\n")
        self.write("Core/Purchases/PaywallView.swift", 'let rows = ["Sample limit", "Sample feature"]\n')
        self.write("app.config.toml", "[app]\n")
        self.write("AppHost/project.yml", "name: AppHost\n")

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def run_tool(self, *flags):
        # Bỏ mọi biến GIT_* (chạy từ hook pre-commit thì có GIT_INDEX_FILE/GIT_DIR của repo thật).
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *flags],
                              capture_output=True, text=True, env=env)

    def snapshot(self, top=None):
        """Băm mọi file dưới `top` (mặc định cả thư mục tạm của test, gồm thư mục "bên ngoài" của test symlink);
        KHÔNG đi theo symlink — symlink ghi bằng đích của nó."""
        top = Path(top or self._tmp.name)
        out = {}
        for dirpath, dirnames, filenames in os.walk(top, followlinks=False):
            for n in dirnames + filenames:
                p = Path(dirpath) / n
                rel = p.relative_to(top).as_posix()
                if p.is_symlink():
                    out[rel] = "-> " + os.readlink(p)
                elif p.is_file():
                    out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    def assert_rejected_unchanged(self, r, needle, before):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(needle, r.stdout)
        self.assertEqual(self.snapshot(), before, "lỗi đánh dấu ⇒ không được ghi/xoá gì")

    # --- gỡ ---

    def test_remove_sample_dat_app_paths_rong(self):
        self.write("app.config.toml", '[web]\nhost_prod = "example.com"\napp_paths = ["/items", "/items/*"]  # mẫu\n'
                                      '\n[support]\nemail = "a@example.com"\n')
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read("app.config.toml"),
                         '[web]\nhost_prod = "example.com"\napp_paths = []  # mẫu\n\n[support]\nemail = "a@example.com"\n')
        self.assertIn("appconfig.py render", r.stdout)
        # Chạy lại (mẫu đã gỡ) ⇒ không đổi gì.
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("app_paths = []", self.read("app.config.toml"))

    def test_cat_khoi_va_xoa_thu_muc(self):
        self.write(f"{APP}/AppShell.swift", d("""
            struct Shell {
                let a = 1
                // sample:begin
                let store = SampleItemStore()
                // sample:end
                let b = 2
            }
            """))
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read(f"{APP}/AppShell.swift"), "struct Shell {\n    let a = 1\n    let b = 2\n}\n")
        self.assertFalse((self.root / FEATURE).exists())
        self.assertFalse((self.root / FEATURE_TESTS).exists())
        self.assertNotIn("sample:", self.read(f"{APP}/AppShell.swift"))
        self.assertIn("xcodegen generate", r.stdout)
        self.assertIn("AppOnboarding.swift", r.stdout)

    def test_app_da_go_mau_giu_nguyen_app_paths_cua_app(self):
        # Mẫu đã gỡ: `app_paths` là của app (vd /notes) — chạy lại remove_sample không được xoá.
        cfg = '[web]\napp_paths = ["/notes"]\n'
        self.write("app.config.toml", cfg)
        shutil.rmtree(self.root / FEATURE)
        shutil.rmtree(self.root / FEATURE_TESTS)
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read("app.config.toml"), cfg)

    def test_nhanh_else_duoc_bo_comment(self):
        # Đúng quy ước Task 7–9: dấu và dòng thay thế cùng cột; dòng nối tiếp giữ phần thụt lề sau `// `.
        self.write(f"{APP}/HomeView.swift", d("""
            var body: some View {
                VStack {
                    // sample:begin
                    sampleSection
                    // sample:end
                    // sample:else-begin
                    // EmptyStateView(systemImage: "square.grid.2x2",
                    //                title: "Nothing")
                    //     .padding(.top, 40)
                    //
                    // sample:else-end
                }
            }
            """))
        self.write(f"{APP}/AppTab.swift", d("""
            // sample:begin
            typealias AppSidebarExtra = SampleFilter
            // sample:end
            // sample:else-begin
            // typealias AppSidebarExtra = Never
            // sample:else-end
            """))
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read(f"{APP}/HomeView.swift"), d("""
            var body: some View {
                VStack {
                    EmptyStateView(systemImage: "square.grid.2x2",
                                   title: "Nothing")
                        .padding(.top, 40)

                }
            }
            """))
        self.assertEqual(self.read(f"{APP}/AppTab.swift"), "typealias AppSidebarExtra = Never\n")

    def test_khong_de_hai_dong_trong_sau_khi_cat(self):
        self.write(f"{APP}/A.swift", "let a = 1\n\n// sample:begin\nlet s = SampleX()\n// sample:end\n\nlet b = 2\n")
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read(f"{APP}/A.swift"), "let a = 1\n\nlet b = 2\n")

    def test_dau_khong_cap_bi_tu_choi_va_khong_ghi(self):
        self.write(f"{APP}/A.swift", "// sample:begin\nlet s = SampleX()\n")
        self.write(f"{APP}/B.swift", "let a = 1\n// sample:end\n")
        before = self.snapshot()
        r = self.run_tool()
        self.assert_rejected_unchanged(r, f"{APP}/A.swift:1:", before)
        self.assertIn(f"{APP}/B.swift:2:", r.stdout)
        self.assertEqual(self.run_tool("--check").returncode, 1)

    def test_dau_long_nhau_bi_tu_choi(self):
        self.write(f"{APP}/A.swift", "// sample:begin\n// sample:begin\nlet s = SampleX()\n// sample:end\n// sample:end\n")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), f"{APP}/A.swift:2:", before)

    def test_begin_trong_else_bi_tu_choi(self):
        self.write(f"{APP}/A.swift", "// sample:else-begin\n// sample:begin\n// let a = 1\n// sample:end\n// sample:else-end\n")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), f"{APP}/A.swift:2:", before)

    def test_end_dong_khoi_else_bi_tu_choi(self):
        self.write(f"{APP}/A.swift", "// sample:else-begin\n// let a = 1\n// sample:end\n")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), f"{APP}/A.swift:3:", before)

    def test_dau_dinh_code_bi_tu_choi(self):
        self.write(f"{APP}/A.swift", "let s = SampleX() // sample:begin\n// sample:end\n")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), f"{APP}/A.swift:1:", before)

    def test_dong_trong_khoi_else_khong_phai_comment_bi_tu_choi(self):
        self.write(f"{APP}/A.swift", "// sample:else-begin\nlet a = 1\n// sample:else-end\n")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), f"{APP}/A.swift:2:", before)

    def test_loi_o_file_sau_thi_khong_ap_dung_mot_phan(self):
        # File đầu (theo thứ tự quét) hợp lệ, file sau hỏng ⇒ KHÔNG file nào bị ghi, thư mục mẫu còn nguyên.
        self.write(f"{APP}/A.swift", "// sample:begin\nlet s = SampleX()\n// sample:end\n")
        self.write(f"{APP}/Z.swift", "// sample:begin\nlet s = SampleY()\n")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), f"{APP}/Z.swift:1:", before)
        self.assertTrue((self.root / FEATURE).is_dir())

    def test_go_khi_con_symbol_ngoai_khoi_bi_tu_choi(self):
        self.write(f"{APP}/A.swift", "let s = SampleX()\n")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), f"{APP}/A.swift:1:", before)

    def test_chay_hai_lan_la_khong_doi(self):
        self.write(f"{APP}/A.swift", "let a = 1\n// sample:begin\nlet s = SampleX()\n// sample:end\n"
                                     "// sample:else-begin\n// let s = 0\n// sample:else-end\n")
        self.assertEqual(self.run_tool().returncode, 0)
        after_first = self.snapshot()
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.snapshot(), after_first)
        self.assertIn("không còn gì để làm", r.stdout)
        self.assertEqual(self.read(f"{APP}/A.swift"), "let a = 1\nlet s = 0\n")

    # --- --check ---

    def test_check_bat_symbol_sample_ngoai_khoi(self):
        self.write(f"{APP}/A.swift", "let a = 1\nlet s = SampleItemStore()\n")
        self.write(f"{TESTS}/B.swift", 'Track.log("sample_export")\n')
        before = self.snapshot()
        r = self.run_tool("--check")
        self.assert_rejected_unchanged(r, f"{APP}/A.swift:2:", before)
        self.assertIn("SampleItemStore", r.stdout)
        self.assertIn(f"{TESTS}/B.swift:1:", r.stdout)

    def test_check_bat_ca_comment(self):
        self.write(f"{APP}/A.swift", "/// Dựng store (`SampleUserProperties.install`).\nlet a = 1\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"{APP}/A.swift:1:", r.stdout)

    def test_check_khong_bat_ten_loi_va_chu_thuong(self):
        # Ranh giới từ + phân biệt hoa thường: tên của lõi, biến chữ thường, chữ thường trong chuỗi KHÔNG phải symbol.
        self.write(f"{APP}/A.swift", d("""
            AppEvent.shellSamples.forEach(Track.log)
            let title = "Sample limit"   // Samples are fine
            let resample_x = 0
            let homeScreen = 1
            """))
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # --- dấu vết mở rộng: chữ thường sampleX, đường dẫn, cụm từ, tên route của mẫu ---

    def test_check_bat_bien_chu_thuong_sample(self):
        self.write(f"{APP}/A.swift", "let sampleDeps = 1\nlet sampleRoutes: [String] = []\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"{APP}/A.swift:1:", r.stdout)
        self.assertIn(f"{APP}/A.swift:2:", r.stdout)

    def test_sample_samples_trong_thu_muc_mau_hoac_khoi_thi_duoc(self):
        self.write(f"{FEATURE}/SampleEvents.swift", "extension AppEvent { static var sampleSamples: [AppEvent] { [] } }\n")
        self.write(f"{TESTS}/T.swift", "// sample:begin\nlet x = AppEvent.shellSamples + AppEvent.sampleSamples\n"
                                        "// sample:end\nlet y = AppEvent.shellSamples\n")
        self.assertEqual(self.run_tool("--check").returncode, 0)
        self.write(f"{TESTS}/U.swift", "let z = AppEvent.sampleSamples\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"{TESTS}/U.swift:1:", r.stdout)
        self.assertNotIn("T.swift", r.stdout)

    def test_check_bat_duong_dan_va_cum_tu(self):
        self.write(f"{APP}/A.swift", "/// Vỏ app: nối `Core/` và `Features/Sample/`.\n/// Phần Home của tính năng mẫu.\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"{APP}/A.swift:1:", r.stdout)
        self.assertIn(f"{APP}/A.swift:2:", r.stdout)

    def test_check_bat_ten_route_cua_mau_doc_tu_app_preview(self):
        self.write(f"{APP}/AppPreview.swift", d("""
            enum AppPreview: String {
                case home, settings
                // sample:begin
                case homeEmpty, itemDetail
                // sample:end
            }
            """))
        self.write(f"{APP}/Other.swift", "// route `itemDetail` mở chi tiết\nlet r = \"homeEmpty\"\nlet h = \"home\"\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"{APP}/Other.swift:1:", r.stdout)
        self.assertIn(f"{APP}/Other.swift:2:", r.stdout)
        self.assertNotIn(f"{APP}/Other.swift:3:", r.stdout, "route của khung không phải dấu vết")

    def write_routes(self):
        self.write(f"{APP}/AppPreview.swift", d("""
            enum AppPreview: String {
                case home, settings
                // sample:begin
                case homePro, items, itemsDone, itemDetail
                // sample:end
            }
            """))

    def test_route_mau_chi_bat_ten_tron_o_vi_tri_route(self):
        # Từ thường trùng/bắt đầu bằng tên route (biến, thuộc tính, comment tiếng Anh) KHÔNG phải dấu vết — chỉ tên
        # TRỌN ở vị trí route: AppPreview.<r>, "<r>", `<r>`, thành viên ngầm .<r> (không đứng sau định danh/)/]/?/!).
        self.write_routes()
        clean = [
            "let items = 1",
            "let n = store.items.count",
            "let homeProfile = 1",
            "let itemAddress = \"x\"",
            "// we list items here",
            "let r = \"home\"",
            "let homeView = HomeView()",
            "let c = load().items + list[0].items + maybe?.items + forced!.items",
            "let x = AppPreview.itemsCount",
            "let k = list.map(\\.items)",
        ]
        self.write(f"{APP}/Clean.swift", "\n".join(clean) + "\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        flagged = {
            1: "case .itemsDone: break",
            2: "let a = AppPreview.items",
            3: "let b = \"itemDetail\"",
            4: "// route `homePro` mở Home Pro",
            5: "let set: [AppPreview] = [.itemsDone]",
        }
        self.write(f"{APP}/Dirty.swift", "\n".join(flagged[i] for i in sorted(flagged)) + "\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        for no in flagged:
            self.assertIn(f"{APP}/Dirty.swift:{no}:", r.stdout, flagged[no])
        self.assertNotIn("Clean.swift", r.stdout)
        self.assertIn("chỉ áp khi Features/Sample còn", r.stdout)

    def test_route_mau_co_raw_value_bao_loi_to(self):
        self.write(f"{APP}/AppPreview.swift", d("""
            enum AppPreview: String {
                case home
                // sample:begin
                case items
                case c = "cc"
                // sample:end
            }
            """))
        before = self.snapshot()
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(f"{APP}/AppPreview.swift:5:", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(self.run_tool().returncode, 2)
        self.assertEqual(self.snapshot(), before)

    # --- dấu trong chuỗi nhiều dòng / khối comment ---

    def test_dau_trong_chuoi_nhieu_dong_bi_tu_choi(self):
        self.write(f"{APP}/A.swift", 'let s = """\n// sample:begin\n"""\n')
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), f"{APP}/A.swift:2:", before)
        self.assertEqual(self.run_tool("--check").returncode, 1)

    def test_dau_trong_khoi_comment_bi_tu_choi(self):
        self.write(f"{APP}/A.swift", "/*\n// sample:end\n*/\nlet a = 1\n")
        before = self.snapshot()
        r = self.run_tool("--check")
        self.assert_rejected_unchanged(r, f"{APP}/A.swift:2:", before)
        self.assertIn("/* */", r.stdout)

    # --- gốc + an toàn đường dẫn ---

    def test_goc_khong_phai_template_rc2_khong_doi(self):
        (self.root / "app.config.toml").unlink()
        self.write(f"{APP}/A.swift", "// sample:begin\nlet s = SampleX()\n// sample:end\n")
        before = self.snapshot()
        r = self.run_tool()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("không phải gốc template", r.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_thieu_project_yml_rc2(self):
        (self.root / "AppHost/project.yml").unlink()
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def outside(self):
        o = Path(self._tmp.name) / "outside"
        (o / "Features/Sample").mkdir(parents=True)
        (o / "Features/Sample/Keep.swift").write_text("struct Keep {}\n", encoding="utf-8")
        return o

    def test_thu_muc_cha_la_symlink_ra_ngoai_bi_tu_choi(self):
        o = self.outside()
        shutil.rmtree(self.root / f"{APP}/Features")
        os.symlink(o / "Features", self.root / f"{APP}/Features")
        self.write(f"{APP}/A.swift", "// sample:begin\nlet s = SampleX()\n// sample:end\n")
        before = self.snapshot()
        r = self.run_tool()
        self.assert_rejected_unchanged(r, "thành phần là symlink", before)
        self.assertIn("ngoài --root", r.stdout)
        self.assertTrue((o / "Features/Sample/Keep.swift").is_file())

    def test_symlink_tro_vao_trong_goc_van_bi_tu_choi(self):
        # Không ra ngoài gốc nhưng vẫn là symlink: xoá qua nó sẽ xoá nhầm `elsewhere/Features/Sample`.
        shutil.rmtree(self.root / f"{APP}/Features")
        self.write("elsewhere/Features/Sample/Keep.swift", "struct Keep {}\n")
        os.symlink(self.root / "elsewhere/Features", self.root / f"{APP}/Features")
        before = self.snapshot()
        r = self.run_tool()
        self.assert_rejected_unchanged(r, "thành phần là symlink", before)
        self.assertNotIn("ngoài --root", r.stdout)

    def test_thu_muc_mau_la_symlink_bi_tu_choi(self):
        o = self.outside()
        shutil.rmtree(self.root / FEATURE)
        os.symlink(o / "Features/Sample", self.root / FEATURE)
        before = self.snapshot()
        r = self.run_tool()
        self.assert_rejected_unchanged(r, f"{FEATURE}: thành phần là symlink", before)
        self.assertNotIn("Traceback", r.stdout + r.stderr)

    def test_thu_muc_mau_la_file_bi_tu_choi(self):
        shutil.rmtree(self.root / FEATURE)
        self.write(FEATURE, "không phải thư mục\n")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), "không phải thư mục thật", before)

    def test_file_swift_la_symlink_ra_ngoai_bi_tu_choi(self):
        o = self.outside()
        (o / "A.swift").write_text("// sample:begin\nlet s = SampleX()\n// sample:end\n", encoding="utf-8")
        (self.root / APP).mkdir(parents=True, exist_ok=True)
        os.symlink(o / "A.swift", self.root / f"{APP}/A.swift")
        before = self.snapshot()
        r = self.run_tool()
        self.assert_rejected_unchanged(r, f"{APP}/A.swift: thành phần là symlink", before)

    # --- ghi nguyên tử / lỗi giữa chừng ---

    def test_loi_ghi_giua_chung_rc2_khong_xoa_thu_muc(self):
        self.write(f"{APP}/A.swift", "// sample:begin\nlet s = SampleX()\n// sample:end\nlet a = 1\n")
        self.write(f"{APP}/ro/Z.swift", "// sample:begin\nlet s = SampleY()\n// sample:end\nlet z = 1\n")
        ro = self.root / f"{APP}/ro"
        os.chmod(ro, 0o555)
        self.addCleanup(os.chmod, ro, 0o755)
        r = self.run_tool()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        self.assertIn(f"ghi {APP}/ro/Z.swift lỗi", r.stderr)
        self.assertIn(f"{APP}/A.swift", r.stderr, "phải nói file nào đã đổi")
        self.assertTrue((self.root / FEATURE).is_dir(), "thư mục mẫu xoá SAU CÙNG — lỗi ghi ⇒ còn nguyên")
        self.assertTrue((self.root / FEATURE_TESTS).is_dir())
        self.assertIn("SampleY", self.read(f"{APP}/ro/Z.swift"), "file lỗi giữ nguyên nội dung cũ (ghi nguyên tử)")
        self.assertEqual([p.name for p in ro.iterdir()], ["Z.swift"], "không để lại file tạm")

    def test_giu_quyen_file(self):
        p = self.write(f"{APP}/A.swift", "// sample:begin\nlet s = SampleX()\n// sample:end\n")
        os.chmod(p, 0o640)
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(os.stat(p).st_mode & 0o777, 0o640)

    def test_giu_xuong_dong_crlf(self):
        p = self.root / f"{APP}/A.swift"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"let a = 1\r\n// sample:begin\r\nlet s = SampleX()\r\n// sample:end\r\n"
                      b"// sample:else-begin\r\n// let s = 0\r\n// sample:else-end\r\nlet b = 2\r\n")
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(p.read_bytes(), b"let a = 1\r\nlet s = 0\r\nlet b = 2\r\n")

    def test_khong_de_dong_trong_truoc_dau_dong_ngoac(self):
        self.write(f"{APP}/A.swift", "struct A {\n    let a = 1\n\n    // sample:begin\n    let s = SampleX()\n"
                                     "    // sample:end\n}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(self.read(f"{APP}/A.swift"), "struct A {\n    let a = 1\n}\n")

    # --- cây git còn thay đổi chưa commit ---

    def git(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@invalid", "-c", "commit.gpgsign=false",
                               *args], cwd=self.root, env=env, capture_output=True, text=True, check=True)

    def init_repo(self):
        self.write(f"{APP}/A.swift", "// sample:begin\nlet s = SampleX()\n// sample:end\nlet a = 1\n")
        self.write("docs/note.md", "ghi chú\n")
        self.git("init", "-q")
        top = self.git("rev-parse", "--show-toplevel").stdout.strip()
        self.assertEqual(Path(top).resolve(), self.root.resolve(), "repo tạm phải là gốc, không phải repo thật")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")

    def test_cay_ban_bi_tu_choi_tru_khi_force(self):
        self.init_repo()
        self.write(f"{FEATURE}/SampleItemStore.swift", "final class SampleItemStore { let sua = 1 }\n")
        before = self.snapshot()
        r = self.run_tool()
        self.assert_rejected_unchanged(r, "chưa commit", before)
        self.assertIn("--force", r.stdout)
        r = self.run_tool("--force")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.root / FEATURE).exists())

    def test_file_chua_add_trong_thu_muc_mau_tinh_la_ban(self):
        self.init_repo()
        self.write(f"{FEATURE_TESTS}/New.swift", "struct New {}\n")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), "chưa commit", before)

    def test_thay_doi_o_file_khong_dung_toi_thi_van_go(self):
        self.init_repo()
        self.write("docs/note.md", "sửa\n")
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read(f"{APP}/A.swift"), "let a = 1\n")

    def test_khong_phai_repo_git_thi_in_ghi_chu_roi_go(self):
        self.write(f"{APP}/A.swift", "// sample:begin\nlet s = SampleX()\n// sample:end\n")
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("không phải repo git", r.stdout)

    def test_check_symbol_trong_khoi_else_bi_bat(self):
        # Dòng của khối else thành code sau khi gỡ ⇒ không được nhắc mẫu.
        self.write(f"{APP}/A.swift", "// sample:else-begin\n// let s = SampleX()\n// sample:else-end\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"{APP}/A.swift:2:", r.stdout)

    def test_check_trong_khoi_begin_thi_duoc(self):
        self.write(f"{APP}/A.swift", "// sample:begin\n/// `SampleX` của mẫu\nlet s = SampleX()\n// sample:end\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_check_core_nhac_mau_bi_bat(self):
        self.write("Core/Telemetry/Bad.swift", "let x = SampleItem.self\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("Core/Telemetry/Bad.swift:1:", r.stdout)
        self.assertNotIn("PaywallView.swift", r.stdout, "chữ 'Sample limit' trong chuỗi không phải symbol")

    def test_check_core_optional_nhac_mau_bi_bat(self):
        self.write("CoreOptional/WebAPI/Bad.swift", 'let e = "sample_export"\n')
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("CoreOptional/WebAPI/Bad.swift:1:", r.stdout)

    def test_check_khong_con_thu_muc_mau_la_noop(self):
        # App đã gỡ mẫu giữ hook: chữ Sample… của chính app (vd kiểu âm thanh) không bị chặn.
        self.assertEqual(self.run_tool().returncode, 0)
        self.write(f"{APP}/Audio.swift", "struct SampleRateConverter {}\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("đã gỡ", r.stdout)

    def test_check_khong_ghi_gi(self):
        self.write(f"{APP}/A.swift", "// sample:begin\nlet s = SampleX()\n// sample:end\n")
        before = self.snapshot()
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_goc_khong_co_apphost_rc2(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(Path(self._tmp.name) / "khong-co")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)


    # --- tài liệu lớp seed (SEED_DOCS) ---

    SEED_MANIFEST = d("""
        schema = 1
        [sync]
        paths = ["Core/", "docs/kien-truc.md"]
        [seed]
        paths = ["AppHost/", "app.config.toml", "CLAUDE.md", "README.md"]
        [template_only]
        paths = []
        """)

    def write_docs(self):
        self.write("CLAUDE.md", d("""
            # CLAUDE.md

            Đoạn chung.

            <!-- sample:begin -->
            - App mẫu ở `AppHost/AppHost/Features/Sample/` (`SampleItemStore`).
            <!-- sample:end -->

            ## Build
            Nhắc `<!-- sample:begin -->` trong code inline là chữ.
            """))
        self.write("README.md", "# App\n<!-- sample:begin -->\n## Tính năng mẫu\n<!-- sample:end -->\n")
        self.write(".claude/rules/conventions.app.md", d("""
            # Quy ước
            <!-- sample:begin -->
            Ví dụ: `SampleDependencies`.
            <!-- sample:end -->
            - Một tính năng một thư mục.
            """))
        self.write("AppHost/project.yml", d("""
            name: AppHost
            targets:
              AppHost:
                sources:
                  # sample:begin
                  # README (vd Features/Sample/README.md) không vào .app.
                  # sample:end
                  - path: AppHost
            """))

    def test_cat_khoi_trong_file_gieo(self):
        self.write_docs()
        self.write("template.manifest.toml", self.SEED_MANIFEST)   # đều là seed ⇒ được ghi
        self.assertEqual(self.run_tool("--check").returncode, 0)
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read("CLAUDE.md"),
                         "# CLAUDE.md\n\nĐoạn chung.\n\n## Build\nNhắc `<!-- sample:begin -->` trong code inline là chữ.\n")
        self.assertEqual(self.read("README.md"), "# App\n")
        self.assertEqual(self.read(".claude/rules/conventions.app.md"), "# Quy ước\n- Một tính năng một thư mục.\n")
        self.assertEqual(self.read("AppHost/project.yml"),
                         "name: AppHost\ntargets:\n  AppHost:\n    sources:\n      - path: AppHost\n")
        for rel in ("CLAUDE.md", "README.md", ".claude/rules/conventions.app.md", "AppHost/project.yml"):
            self.assertIn(f"sửa: {rel}", r.stdout)
        # Lần hai không đổi gì.
        before = self.snapshot()
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_khoi_sai_trong_file_gieo_bi_tu_choi(self):
        self.write("CLAUDE.md", "# A\n<!-- sample:begin -->\nx\n")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), "CLAUDE.md:2:", before)
        self.write("CLAUDE.md", "# A\nApp mẫu ở `AppHost/AppHost/Features/Sample/`.\n")   # tả mẫu ngoài khối
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("CLAUDE.md:2:", r.stdout)
        # Mẫu còn ⇒ tên kiểu `Sample…` ngoài khối trong tài liệu gieo cũng là dấu vết.
        self.write("CLAUDE.md", "# A\nStore là `SampleItemStore`.\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("CLAUDE.md:2: tài liệu tả mẫu (SampleItemStore)", r.stdout)

    def test_tu_choi_ghi_file_lop_dong_bo(self):
        self.write_docs()
        self.write("template.manifest.toml", self.SEED_MANIFEST.replace(
            '"CLAUDE.md", ', "").replace('"docs/kien-truc.md"]', '"docs/kien-truc.md", "CLAUDE.md"]'))
        before = self.snapshot()
        r = self.run_tool()
        self.assert_rejected_unchanged(r, "CLAUDE.md: file lớp sync", before)
        self.assertNotIn("README.md: file lớp sync", r.stdout)
        # Manifest hỏng ⇒ rc 2, không ghi gì.
        self.write("template.manifest.toml", "schema = 1\n")
        before = self.snapshot()
        r = self.run_tool()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_sau_khi_go_file_gieo_khong_con_dau_vet(self):
        self.write_docs()
        self.assertEqual(self.run_tool().returncode, 0)
        for rel in ("CLAUDE.md", "README.md", ".claude/rules/conventions.app.md", "AppHost/project.yml"):
            text = self.read(rel)
            self.assertNotRegex(text, r"(?m)^\s*(<!--|#) sample:", rel)
            self.assertNotRegex(text, remove_sample_doc_trace(), rel)
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("đã gỡ", r.stdout)
        # Gỡ xong mà tài liệu gieo còn dấu / câu tả mẫu ⇒ --check đỏ (tên kiểu Sample… của app thì được).
        self.write("README.md", "# App\n<!-- sample:begin -->\nx\n<!-- sample:end -->\nKiểu `SampleRateConverter`.\n")
        self.write("CLAUDE.md", "# A\nXem tính năng mẫu.\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("README.md:2:", r.stdout)
        self.assertIn("CLAUDE.md:2:", r.stdout)
        self.assertNotIn("README.md:5:", r.stdout)

    def test_file_gieo_symlink_hoac_ban_bi_tu_choi(self):
        self.write_docs()
        outside = Path(self._tmp.name) / "ngoai"
        outside.mkdir()
        (outside / "README.md").write_text("# App\n<!-- sample:begin -->\nx\n<!-- sample:end -->\n", encoding="utf-8")
        (self.root / "README.md").unlink()
        (self.root / "README.md").symlink_to(outside / "README.md")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), "README.md: thành phần là symlink", before)
        (self.root / "README.md").unlink()
        self.write("README.md", "# App\n")
        self.init_repo()
        self.write("CLAUDE.md", self.read("CLAUDE.md") + "sửa dở\n")
        before = self.snapshot()
        self.assert_rejected_unchanged(self.run_tool(), "chưa commit", before)

    def test_checklist_app_moi_cat_khoi_mau(self):
        rel = "docs/NEW_APP_CHECKLIST.md"
        self.write(rel, "# Việc tay\n\n- [ ] Team id.\n<!-- sample:begin -->\n- [ ] Gỡ tính năng mẫu.\n<!-- sample:end -->\n"
                        "- [ ] Push.\n")
        self.assertEqual(self.run_tool("--check").returncode, 0)
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read(rel), "# Việc tay\n\n- [ ] Team id.\n- [ ] Push.\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # Gỡ xong mà checklist còn bước gỡ mẫu ngoài khối ⇒ --check đỏ.
        self.write(rel, "# Việc tay\n- [ ] Gỡ tính năng mẫu.\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"{rel}:2:", r.stdout)

    def test_khong_co_checklist_thi_khong_loi(self):
        self.assertFalse((self.root / "docs/NEW_APP_CHECKLIST.md").exists())
        self.assertEqual(self.run_tool("--check").returncode, 0)
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(self.run_tool("--check").returncode, 0)

    def test_thu_muc_gieo_dau_khong_cap_bi_bao(self):
        seed = "tools/template/seed"
        self.write(f"{seed}/README.md", "# $display_name\n<!-- sample:begin -->\nmẫu\n<!-- sample:end -->\n")
        self.write(f"{seed}/docs/NEW_APP_CHECKLIST.md", "# x\n")
        self.assertEqual(self.run_tool("--check").returncode, 0)
        self.write(f"{seed}/docs/NEW_APP_CHECKLIST.md", "# x\n<!-- sample:begin -->\n- [ ] gỡ\n")
        self.write(f"{seed}/docs/ROADMAP.md", "# R\n<!-- template:end -->\n")
        before = self.snapshot()
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"{seed}/docs/NEW_APP_CHECKLIST.md:2:", r.stdout)
        self.assertIn(f"{seed}/docs/ROADMAP.md:2:", r.stdout)
        self.assert_rejected_unchanged(self.run_tool(), f"{seed}/docs/ROADMAP.md:2:", before)
        # Mẫu đã gỡ: --check vẫn kiểm thư mục gieo.
        self.write(f"{seed}/docs/NEW_APP_CHECKLIST.md", "# x\n")
        self.write(f"{seed}/docs/ROADMAP.md", "# R\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.write(f"{seed}/docs/ROADMAP.md", "# R\n<!-- template:begin -->\n")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"{seed}/docs/ROADMAP.md:2:", r.stdout)
        # Thư mục gieo không bị cắt khối (file lớp template_only).
        self.assertIn("<!-- sample:begin -->", self.read(f"{seed}/README.md"))

class FollowUpsTests(unittest.TestCase):
    """CHỈ ĐỌC cây thật: mọi đường dẫn trong FOLLOW_UPS tồn tại và còn nhắc mẫu ở HEAD — danh sách không được mục."""
    TRACE = re.compile(r"Sample|sample|tính năng mẫu|app mẫu")

    def test_follow_ups_chi_con_viec_swift(self):
        # Tài liệu tự dọn (SEED_DOCS cắt khối, tài liệu sync viết có điều kiện) ⇒ chỉ còn việc nội dung Swift của app.
        sys.path.insert(0, str(HERE))
        import remove_sample
        self.assertEqual([rel for rel, _ in remove_sample.FOLLOW_UPS],
                         [f"{APP}/AppOnboarding.swift", f"{APP}/AppPaywall.swift", f"{APP}/WhatsNew/WhatsNewCatalog.swift"])
        if not (REPO / FEATURE).is_dir():
            self.skipTest("cây đã gỡ mẫu")
        for rel, what in remove_sample.FOLLOW_UPS:
            p = REPO / rel
            self.assertTrue(p.is_file(), f"FOLLOW_UPS nhắc file không có: {rel}")
            self.assertTrue(what.strip(), rel)
            self.assertRegex(p.read_text(encoding="utf-8"), self.TRACE, f"{rel} không còn nhắc mẫu — bỏ khỏi FOLLOW_UPS")

    def test_readme_cua_mau_liet_ke_cung_cac_file(self):
        sys.path.insert(0, str(HERE))
        import remove_sample
        readme = REPO / FEATURE / "README.md"
        if not readme.is_file():
            self.skipTest("cây đã gỡ mẫu")
        text = readme.read_text(encoding="utf-8")
        for rel, _ in remove_sample.FOLLOW_UPS:
            self.assertIn(rel, text, f"README của mẫu (Việc tay còn lại) thiếu {rel}")


class RealTreeTests(unittest.TestCase):
    def test_cay_that_check_sach(self):
        # Chạy trên BẢN CHÉP nguồn thật (AppHost/ + Core/ + CoreOptional/), không bao giờ trên cây thật: một lỗi khiến
        # `--check` ghi file (đã xảy ra khi phá code thử) không được phép sửa nguồn của repo.
        with tempfile.TemporaryDirectory() as tmp:
            for top in ("AppHost/AppHost", "AppHost/AppHostTests", "Core", "CoreOptional"):
                if (REPO / top).is_dir():
                    shutil.copytree(REPO / top, Path(tmp) / top,
                                    ignore=shutil.ignore_patterns("*.xcodeproj", "xcuserdata"))
            for rel in ("app.config.toml", "AppHost/project.yml"):
                shutil.copy2(REPO / rel, Path(tmp) / rel)
            r = subprocess.run([sys.executable, str(SCRIPT), "--check", "--root", tmp], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            # Cây còn mẫu ⇒ phải kiểm thật; cây đã gỡ (app thật, bản chép của sample_removal_check.sh) ⇒ no-op.
            if (REPO / FEATURE).is_dir():
                self.assertIn("không dấu vết của mẫu ngoài khối", r.stdout, "cây còn mẫu mà --check không kiểm")
            else:
                self.assertIn("đã gỡ", r.stdout)


if __name__ == "__main__":
    unittest.main()
