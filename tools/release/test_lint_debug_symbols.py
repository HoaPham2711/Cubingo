"""Test cho lint_debug_symbols.py: `debug_symbols.txt` luôn khớp nguồn (type/hàm chỉ-INTERNAL).

Mỗi test dựng một gốc tạm (Core/…, tools/release/debug_symbols.txt) rồi chạy script thật với `--root`.
Chạy: python3 -m unittest tools/release/test_lint_debug_symbols.py
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "lint_debug_symbols.py"
REPO = HERE.parents[1]


class LintDebugSymbolsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "gốc có dấu cách"
        self.root.mkdir()
        self.symbols()  # file rỗng có hiệu lực: mỗi test tự đặt danh sách

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def symbols(self, *names, src=(), raw=None):
        """`names` vào mục [binary] (type), `src` vào mục [source-only] (hàm/biến có marker)."""
        if raw is None:
            raw = ("# chú thích\n\n[binary]\n" + "".join(n + "\n" for n in names)
                   + "\n[source-only]\n" + "".join(n + "\n" for n in src))
        self.write("tools/release/debug_symbols.txt", raw)

    def app_symbols(self, *names, src=(), raw=None):
        """Danh sách của APP (AppHost/Config/debug_symbols.app.txt), cùng định dạng hai mục."""
        if raw is None:
            raw = ("[binary]\n" + "".join(n + "\n" for n in names) + "[source-only]\n" + "".join(n + "\n" for n in src))
        self.write("AppHost/Config/debug_symbols.app.txt", raw)

    def run_lint(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                              capture_output=True, text=True)

    def out(self, r):
        return r.stdout + r.stderr

    # ---- Bốn ca của brief ----------------------------------------------------------------------------------------

    def test_type_trong_if_internal_chua_khai_bi_bat(self):
        self.write("Core/Internal/X.swift", "#if INTERNAL\nstruct BiMat: View {}\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/Internal/X.swift:2: BiMat chưa khai", self.out(r))
        self.assertNotIn("Traceback", self.out(r))

    def test_type_o_nhanh_else_khong_tinh(self):
        self.write("Core/Internal/X.swift", "#if INTERNAL\nstruct A {}\n#else\nstruct B {}\n#endif\n")
        self.symbols("A")
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, self.out(r))

    def test_ten_trong_danh_sach_khong_con_khai_bi_bat(self):
        self.symbols("KhongConTonTai")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("KhongConTonTai", self.out(r))
        self.assertIn("debug_symbols.txt", self.out(r))

    def test_if_long_nhau_va_dieu_kien_ghep(self):
        self.write("Core/X.swift", "#if INTERNAL || WHATSNEW_ALLOW_UNRELEASED\nenum Mo {}\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, self.out(r))   # điều kiện ghép không phải "chỉ INTERNAL"

    # ---- Mở rộng (controller) ------------------------------------------------------------------------------------

    def test_ham_da_liet_ke_khai_duoi_if_internal_thi_qua(self):
        self.write("Core/E.swift", "final class E {\n    #if INTERNAL\n    func setPro(_ on: Bool) {}\n    #endif\n}\n")
        self.symbols(src=("setPro",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, self.out(r))

    def test_ten_chi_khai_ngoai_vung_internal_la_loi(self):
        self.write("Core/E.swift", "struct LotRaRelease {}\n")
        self.symbols("LotRaRelease")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/E.swift:1", self.out(r))
        self.assertIn("LotRaRelease", self.out(r))

    def test_ham_khai_ngoai_vung_internal_la_loi(self):
        self.write("Core/E.swift", "enum E {\n    static func batPro() {}\n}\n")
        self.symbols(src=("batPro",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/E.swift:2", self.out(r))

    def test_ten_khai_o_nhanh_else_cua_internal_la_loi(self):
        # Bản Release biên dịch nhánh #else ⇒ tên có trong binary Release.
        self.write("Core/X.swift", "#if INTERNAL\nstruct A {}\n#else\nstruct A {}\n#endif\n")
        self.symbols("A")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/X.swift:4", self.out(r))

    def test_khai_hai_noi_mot_noi_ngoai_vung_la_loi(self):
        self.write("Core/X.swift", "#if INTERNAL\nfunc f() {}\n#endif\nfunc f(_ x: Int) {}\n")
        self.symbols(src=("f",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/X.swift:4", self.out(r))

    def test_if_internal_long_trong_if_debug(self):
        self.write("Core/X.swift", "#if DEBUG\n#if INTERNAL\nstruct A {}\n#endif\nstruct B {}\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/X.swift:3: A chưa khai", self.out(r))
        self.assertNotIn("B chưa khai", self.out(r))      # B chỉ trong #if DEBUG, không phải INTERNAL
        self.symbols("A")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_if_khac_long_trong_if_internal_van_la_internal(self):
        self.write("Core/X.swift", "#if INTERNAL\n#if DEBUG\nstruct A {}\n#endif\nenum B {}\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("A chưa khai", self.out(r))
        self.assertIn("B chưa khai", self.out(r))

    def test_if_internal_long_trong_nhanh_else_cua_if_khac(self):
        self.write("Core/X.swift", "#if INTERNAL\nstruct Ngoai {}\n#else\n#if INTERNAL\nstruct A {}\n#endif\n#endif\n")
        self.symbols("Ngoai", "A")
        # `A` nằm trong khối `#if INTERNAL` lồng (mã chết ở nhánh else) ⇒ vẫn là vùng INTERNAL-only.
        self.assertEqual(self.run_lint().returncode, 0)

    def test_ca_file_boc_if_internal(self):
        self.write("Core/Internal/F.swift", "// công cụ nội bộ\n#if INTERNAL\nimport SwiftUI\n\nstruct CaFile: View {\n"
                   "    private struct Trong {}\n}\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/Internal/F.swift:5: CaFile chưa khai", self.out(r))
        self.assertIn("Core/Internal/F.swift:6: Trong chưa khai", self.out(r))  # luật chặt: type lồng cũng phải khai
        self.symbols("CaFile", "Trong")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_type_ngoai_moi_if_khong_can_khai(self):
        self.write("Core/X.swift", "struct Thuong {}\n#if DEBUG\nenum ChiDebug {}\n#endif\n")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_elseif_internal_khong_tinh(self):
        self.write("Core/X.swift", "#if FOO\nstruct F {}\n#elseif INTERNAL\nstruct A {}\n#endif\n")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_phu_dinh_va_or_la_khong_tinh(self):
        self.write("Core/X.swift", "#if !INTERNAL\nenum A {}\n#endif\n#if (INTERNAL || X) && Y\nenum B {}\n#endif\n"
                   "#if INTERNAL || X\nenum C {}\n#endif\n")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_and_voi_mot_toan_hang_internal_la_tinh(self):
        for i, cond in enumerate(["INTERNAL && canImport(UIKit)", "os(iOS) && INTERNAL", "(INTERNAL) && X",
                                  "INTERNAL && (A || B)", "(INTERNAL && X)"]):
            with self.subTest(cond=cond):
                self.write("Core/X.swift", f"#if {cond}\nenum Ten{i} {{}}\n#endif\n")
                r = self.run_lint()
                self.assertEqual(r.returncode, 1, self.out(r))
                self.assertIn(f"Core/X.swift:2: Ten{i} chưa khai", self.out(r))

    def test_nhanh_else_cua_phu_dinh_internal_la_internal(self):
        self.write("Core/X.swift", "#if !INTERNAL\nenum Thuong {}\n#else\nenum ChiInternal {}\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("ChiInternal chưa khai", self.out(r))
        self.assertNotIn("Thuong chưa khai", self.out(r))
        self.symbols("ChiInternal")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_else_sau_elseif_cua_phu_dinh_khong_tinh(self):
        self.write("Core/X.swift", "#if !INTERNAL\nenum A {}\n#elseif FOO\nenum B {}\n#else\nenum C {}\n#endif\n")
        self.assertEqual(self.run_lint().returncode, 0)

    # ---- Marker `// debug-symbol: required` ----------------------------------------------------------------------

    MARK = "// debug-symbol: required"

    def test_marker_thieu_ten_rc1(self):
        self.write("Core/E.swift", f"enum E {{\n    #if INTERNAL\n    {self.MARK}\n    static func batPro() {{}}\n"
                   "    #endif\n}\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/E.swift:4: batPro chưa khai", self.out(r))

    def test_marker_co_ten_rc0(self):
        self.write("Core/E.swift", f"enum E {{\n    #if INTERNAL\n    /// doc\n    {self.MARK}\n"
                   "    static func batPro() {}\n    #endif\n}\n")
        self.symbols(src=("batPro",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, self.out(r))

    def test_marker_cho_var_va_let(self):
        self.write("Core/E.swift", f"#if INTERNAL\n{self.MARK}\nlet coBat = 1\n#endif\n")
        self.assertEqual(self.run_lint().returncode, 1)
        self.symbols(src=("coBat",))
        self.assertEqual(self.run_lint().returncode, 0)

    def test_marker_ngoai_vung_internal_rc1(self):
        self.write("Core/E.swift", f"enum E {{\n    {self.MARK}\n    static func batPro() {{}}\n}}\n")
        self.symbols(src=("batPro",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/E.swift:2", self.out(r))
        self.assertIn("marker", self.out(r))

    def test_marker_khong_kem_khai_bao_rc1(self):
        self.write("Core/E.swift", f"#if INTERNAL\n{self.MARK}\n\nlet x = 1\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/E.swift:2: marker", self.out(r))
        self.write("Core/E.swift", f"#if INTERNAL\n{self.MARK}\n#endif\n")
        self.assertEqual(self.run_lint().returncode, 1)

    def test_xoa_marker_giu_ten_van_rc0(self):
        self.write("Core/E.swift", "#if INTERNAL\nfunc batPro() {}\n#endif\n")
        self.symbols(src=("batPro",))
        self.assertEqual(self.run_lint().returncode, 0)

    def test_marker_trong_chuoi_khong_tinh(self):
        self.write("Core/E.swift", f'let s = """\n{self.MARK}\n"""\nlet x = 1\n')
        self.assertEqual(self.run_lint().returncode, 0)

    def test_endif_va_if_trong_comment_khong_lam_lech(self):
        self.write("Core/X.swift",
                   "#if INTERNAL\n// #endif giả trong comment\n/// #endif nữa\n/* #endif\n#endif */\n"
                   "struct A {}\n#endif\nstruct NgoaiVung {}\n")
        self.symbols("A")
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, self.out(r))    # NgoaiVung ở ngoài #endif thật ⇒ không cần khai

    def test_if_trong_chuoi_khong_mo_khoi(self):
        self.write("Core/X.swift", 'let s = "#if INTERNAL"\nstruct Thuong {}\nlet m = """\n#if INTERNAL\n"""\n'
                   "struct Khac {}\n")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_chuoi_noi_suy_co_dau_nhay_khong_lam_lech(self):
        self.write("Core/X.swift", 'let s = "a \\(f("b")) c"\n#if INTERNAL\nstruct A {}\n#endif\nstruct Thuong {}\n')
        self.symbols("A")
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, self.out(r))

    def test_tu_khoa_type_trong_comment_hoac_chuoi_khong_tinh(self):
        self.write("Core/X.swift", '#if INTERNAL\n/// struct Gia {}\nlet s = "enum GiaNua {}"\n#endif\n')
        self.assertEqual(self.run_lint().returncode, 0)

    def test_class_func_khong_bi_nhan_la_class(self):
        self.write("Core/X.swift", "#if INTERNAL\nfinal class A { class func make() {} }\n#endif\n")
        self.symbols("A")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_modifier_va_attribute_truoc_type(self):
        self.write("Core/X.swift", "#if INTERNAL\n@MainActor final class A {}\nprivate indirect enum B {}\n"
                   "public protocol C {}\nactor D {}\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        for n in "ABCD":
            self.assertIn(f"{n} chưa khai", self.out(r))

    def test_core_optional_vang_mat_khong_loi(self):
        self.write("Core/X.swift", "struct Thuong {}\n")
        self.assertFalse((self.root / "CoreOptional").exists())
        self.assertEqual(self.run_lint().returncode, 0)

    def test_core_optional_duoc_quet_khi_co(self):
        self.write("CoreOptional/Sdk/Y.swift", "#if INTERNAL\nstruct TuyChon {}\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("CoreOptional/Sdk/Y.swift:2: TuyChon chưa khai", self.out(r))

    def test_core_optional_chi_bao_mot_lan(self):
        # SRC_ROOTS đã chứa `CoreOptional/` ⇒ lint không được quét nó hai lần (báo trùng dòng).
        self.write("CoreOptional/Sdk/Y.swift", "#if INTERNAL\nstruct TuyChon {}\n#endif\n")
        self.assertEqual(self.out(self.run_lint()).count("CoreOptional/Sdk/Y.swift:2: TuyChon chưa khai"), 1)

    def test_quet_ca_thu_muc_app(self):
        self.write("AppHost/AppHost/Z.swift", "#if INTERNAL\nstruct CuaApp {}\n#endif\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("AppHost/AppHost/Z.swift:2: CuaApp chưa khai", self.out(r))

    def test_test_target_khong_bi_quet(self):
        self.write("CoreTests/T.swift", "#if INTERNAL\nfinal class TTests {}\n#endif\n")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_thieu_file_symbols_rc2(self):
        (self.root / "tools/release/debug_symbols.txt").unlink()
        r = self.run_lint()
        self.assertEqual(r.returncode, 2, self.out(r))
        self.assertIn("debug_symbols.txt", self.out(r))
        self.assertNotIn("Traceback", self.out(r))

    def test_goc_khong_ton_tai_rc2(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root / "khong-co")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_dong_symbols_cat_khoang_trang_va_bo_chu_thich(self):
        self.write("Core/X.swift", "#if INTERNAL\nstruct A {}\n#endif\n")
        self.symbols(raw="# chú thích\n\n [binary] \r\n  A \r\n")
        self.assertEqual(self.run_lint().returncode, 0)

    # ---- Hai mục [binary] / [source-only] (ruling R18) ------------------------------------------------------------

    def test_type_nam_o_source_only_la_loi(self):
        self.write("Core/X.swift", "#if INTERNAL\nstruct A {}\n#endif\n")
        self.symbols(src=("A",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/X.swift:2: A là type nhưng nằm ở mục [source-only]", self.out(r))
        self.assertIn("A ở mục [source-only] nhưng là type", self.out(r))

    def test_ham_co_marker_nam_o_binary_la_loi(self):
        self.write("Core/E.swift", f"#if INTERNAL\n{self.MARK}\nfunc batPro() {{}}\n#endif\n")
        self.symbols("batPro")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/E.swift:3: batPro (hàm/biến có marker) nằm ở mục [binary]", self.out(r))
        self.symbols(src=("batPro",))
        self.assertEqual(self.run_lint().returncode, 0)

    def test_ham_khong_marker_nam_o_binary_la_loi(self):
        # Tên hàm không có trong binary ⇒ để ở [binary] là cổng soi chuỗi không bao giờ xuất hiện.
        self.write("Core/E.swift", "#if INTERNAL\nfunc batPro() {}\n#endif\n")
        self.symbols("batPro")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("batPro ở mục [binary] nhưng không phải type", self.out(r))

    def test_typealias_o_binary_la_loi(self):
        self.write("Core/E.swift", "#if INTERNAL\ntypealias BiDanh = Int\n#endif\n")
        self.symbols("BiDanh")
        self.assertIn("không phải type", self.out(self.run_lint()))
        self.symbols(src=("BiDanh",))
        self.assertEqual(self.run_lint().returncode, 0)

    def test_ten_truoc_moi_muc_la_loi(self):
        self.write("Core/X.swift", "#if INTERNAL\nstruct A {}\n#endif\n")
        self.symbols(raw="# chú thích\nA\n[binary]\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("debug_symbols.txt:2: A đứng trước mọi mục", self.out(r))

    def test_muc_la_la_loi(self):
        self.write("Core/X.swift", "#if INTERNAL\nstruct A {}\n#endif\n")
        self.symbols(raw="[binary]\nA\n[binnary]\nB\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("mục lạ `[binnary]`", self.out(r))

    def test_ten_trung_hai_muc_la_loi(self):
        self.write("Core/X.swift", "#if INTERNAL\nstruct A {}\n#endif\n")
        self.symbols("A", src=("A",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("A khai trùng", self.out(r))

    def test_ten_mo_coi_o_source_only_la_loi(self):
        self.symbols(src=("khongConHam",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("khongConHam không còn khai", self.out(r))

    def test_source_only_khai_ngoai_vung_la_loi(self):
        self.write("Core/E.swift", "func batPro() {}\n")
        self.symbols(src=("batPro",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/E.swift:1: batPro", self.out(r))
        self.assertIn("lọt vào bản Store", self.out(r))

    # ---- Marker viết gần đúng ⇒ lỗi, không bỏ qua im lặng ---------------------------------------------------------

    def test_marker_gan_dung_la_loi(self):
        for bad in ("//debug-symbol: required", "// debug-symbol:required", "// debug-symbols: required",
                    "/// debug-symbol: required", "/* debug-symbol: required */", "//  debug-symbol: required",
                    "// Debug-Symbol: required", "// debug-symbol: requried"):
            with self.subTest(bad=bad):
                self.write("Core/E.swift", f"#if INTERNAL\n{bad}\nfunc batPro() {{}}\n#endif\n")
                self.symbols(src=("batPro",))
                r = self.run_lint()
                self.assertEqual(r.returncode, 1, self.out(r))
                self.assertIn("Core/E.swift:2: comment nhắc `debug-symbol`", self.out(r))

    def test_marker_sau_code_cung_dong_la_loi(self):
        self.write("Core/E.swift", f"#if INTERNAL\nfunc batPro() {{}} {self.MARK}\n#endif\n")
        self.symbols(src=("batPro",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/E.swift:2: comment nhắc", self.out(r))

    def test_marker_trong_khoi_comment_nhieu_dong_la_loi(self):
        self.write("Core/E.swift", f"#if INTERNAL\n/*\n{self.MARK}\n*/\nfunc batPro() {{}}\n#endif\n")
        self.symbols(src=("batPro",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Core/E.swift:3: comment nhắc", self.out(r))

    def test_chu_debug_symbol_trong_chuoi_khong_tinh(self):
        self.write("Core/E.swift", 'let s = "debug-symbol: requried"\n')
        self.assertEqual(self.run_lint().returncode, 0)

    # ---- Tách danh sách lõi / app (Plan 4, Task 3) ---------------------------------------------------------------

    def test_doc_hop_hai_file(self):
        self.write("Core/Internal/X.swift", "#if INTERNAL\nstruct CuaLoi {}\n#endif\n")
        self.write("AppHost/AppHost/Internal/Y.swift", "#if INTERNAL\nstruct CuaApp {}\n#endif\n")
        self.symbols("CuaLoi")
        self.app_symbols("CuaApp")
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, self.out(r))
        # Tên của app KHÔNG khai ở file nào ⇒ vẫn bị bắt (union không nuốt mất luật xuôi).
        self.app_symbols()
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("AppHost/AppHost/Internal/Y.swift:2: CuaApp chưa khai", self.out(r))

    def test_ten_trung_hai_file_bi_tu_choi(self):
        self.write("Core/Internal/X.swift", "#if INTERNAL\nstruct Trung {}\n#endif\n")
        self.symbols("Trung")
        self.app_symbols("Trung")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("Trung", self.out(r))
        self.assertIn("tools/release/debug_symbols.txt", self.out(r))
        self.assertIn("AppHost/Config/debug_symbols.app.txt", self.out(r))
        self.assertNotIn("Traceback", self.out(r))

    def test_thieu_file_app_coi_la_rong(self):
        self.write("Core/Internal/X.swift", "#if INTERNAL\nstruct CuaLoi {}\n#endif\n")
        self.symbols("CuaLoi")
        self.assertFalse((self.root / "AppHost/Config/debug_symbols.app.txt").exists())
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, self.out(r))

    def test_loi_trong_file_app_neu_ten_file_app(self):
        self.app_symbols("MoCoi")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("AppHost/Config/debug_symbols.app.txt:2: MoCoi không còn khai", self.out(r))

    def test_marker_ham_cua_app_ghi_o_file_app(self):
        self.write("AppHost/AppHost/Internal/Z.swift",
                   "enum Z {\n    #if INTERNAL\n    // debug-symbol: required\n    static func batGi() {}\n    #endif\n}\n")
        r = self.run_lint()
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn("batGi chưa khai", self.out(r))
        self.app_symbols(src=("batGi",))
        self.assertEqual(self.run_lint().returncode, 0)

    def test_marker_dung_khong_bi_bao_gan_dung(self):
        self.write("Core/E.swift", f"#if INTERNAL\n    {self.MARK}   \nfunc batPro() {{}}\n#endif\n")
        self.symbols(src=("batPro",))
        r = self.run_lint()
        self.assertEqual(r.returncode, 0, self.out(r))

    def test_mac_dinh_doc_repo_that_tu_vi_tri_script(self):
        # Không truyền --root: script tự tìm gốc theo vị trí của nó và cây thật phải sạch.
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=self._tmp.name)
        self.assertEqual(r.returncode, 0, self.out(r))
        self.assertTrue((REPO / "tools/release/debug_symbols.txt").is_file())


if __name__ == "__main__":
    unittest.main()
