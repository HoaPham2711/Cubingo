#!/usr/bin/env python3
"""Test cho phần phân tích log của run_tests.py — không gọi xcodebuild.

Các ca lấy từ 4 lần báo xanh giả có thật ở app gốc:
`Executed 0 tests` + rc=0, chạy test đã gỡ khỏi nguồn, build không biên dịch file test vừa sửa."""
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_tests  # noqa: E402
sys.path.insert(0, str(HERE.parent / "common"))
import appconfig  # noqa: E402


def case(cls, method, verdict="passed"):
    return (f"Test Case '-[AppHostTests.{cls} {method}]' started.\n"
            f"Test Case '-[AppHostTests.{cls} {method}]' {verdict} (0.001 seconds).\n")


SRC = {
    "T/FooTests.swift": """
final class FooTests: XCTestCase {
    func testA() throws {}
    @MainActor func test_b() async throws {}
    func helper() {}
    // func testCommented() {}
    func testWithArg(_ x: Int) {}
}
final class BaseFixture: XCTestCase {
    func makeThing() {}
}
""",
    "T/Foo+More.swift": """
extension FooTests {
    func testFromExtension() {}
}
final class BarTests: XCTestCase {
    func testBar() {}
}
""",
}


class DeclaredTestsTests(unittest.TestCase):

    def test_lay_dung_method_theo_class_ke_ca_extension(self):
        d = run_tests.declared_tests(SRC)
        self.assertEqual(d["FooTests"], {"testA", "test_b", "testFromExtension"})
        self.assertEqual(d["BarTests"], {"testBar"})

    def test_class_khong_co_test_van_duoc_biet_den(self):
        self.assertEqual(run_tests.declared_tests(SRC)["BaseFixture"], set())


class ExecutedTestsTests(unittest.TestCase):

    def test_tinh_ca_test_skipped_vi_no_van_co_trong_binary(self):
        log = case("FooTests", "testA") + case("FooTests", "test_b", "skipped") + case("BarTests", "testBar", "failed")
        self.assertEqual(run_tests.executed_tests(log),
                         {("FooTests", "testA"), ("FooTests", "test_b"), ("BarTests", "testBar")})

    def test_dong_bi_log_khac_chen_vao_giua(self):
        # Gặp thật ở L2: stdout của app ghi xen, "Test Case" không còn ở đầu dòng.
        log = ("2026-10-31 18:15:01.090615+0700 AppTest Case "
               "'-[AppHostTests.FooTests testA]' started.\n"
               "Host[39948:31440210] [player] signalled err=-12864\n")
        self.assertEqual(run_tests.executed_tests(log), {("FooTests", "testA")})

    def test_dong_started_bi_nuot_van_con_dong_ket_qua(self):
        log = "Test Case '-[AppHostTests.FooTests testA]' passed (0.001 seconds).\n"
        self.assertEqual(run_tests.executed_tests(log), {("FooTests", "testA")})

    def test_log_khong_co_gi(self):
        self.assertEqual(run_tests.executed_tests("Test Suite 'FooTests' started\n"), set())


class FalseGreenTests(unittest.TestCase):

    def check(self, log, only=(), scoped_manual=False):
        return run_tests.false_green_problems(log, only, run_tests.declared_tests(SRC), scoped_manual)

    def test_executed_0_khi_chi_dinh_test_la_loi(self):
        log = "\t Executed 0 tests, with 0 failures (0 unexpected) in 0.000 (0.001) seconds\n"
        problems = self.check(log, ["FooTests/testA"], True)
        self.assertTrue(any("0 test" in p for p in problems), problems)

    def test_khong_co_dong_executed_cung_la_loi(self):
        self.assertTrue(self.check("** TEST SUCCEEDED **\n"))

    def test_full_suite_executed_0_cung_la_loi(self):
        self.assertTrue(self.check("Executed 0 tests, with 0 failures\n"))

    def test_chi_dinh_method_khong_ton_tai(self):
        log = case("FooTests", "testA") + "Executed 1 test, with 0 failures\n"
        problems = self.check(log, ["FooTests/testKhongTonTai"], True)
        self.assertTrue(any("FooTests/testKhongTonTai" in p for p in problems), problems)

    def test_chi_dinh_method_co_chay_thi_sach(self):
        log = case("FooTests", "testA") + "Executed 1 test, with 0 failures\n"
        self.assertEqual(self.check(log, ["FooTests/testA"], True), [])

    def test_chi_dinh_class_khong_chay_test_nao(self):
        log = case("FooTests", "testA") + "Executed 1 test, with 0 failures\n"
        problems = self.check(log, ["FooTests", "BarTests"], True)
        self.assertTrue(any("BarTests" in p for p in problems), problems)

    def test_L1_class_khong_khai_bao_test_duoc_bo_qua(self):
        # L1 tự chọn theo regex `class X: XCTestCase`, có thể vớ phải class nền không có test nào.
        log = case("FooTests", "testA") + case("FooTests", "test_b") + case("FooTests", "testFromExtension") \
            + "Executed 3 tests, with 0 failures\n"
        self.assertEqual(self.check(log, ["FooTests", "BaseFixture"], False), [])

    def test_chi_dinh_tay_class_khong_co_test_la_loi(self):
        log = case("FooTests", "testA") + case("FooTests", "test_b") + case("FooTests", "testFromExtension") \
            + "Executed 3 tests, with 0 failures\n"
        self.assertTrue(self.check(log, ["FooTests", "BaseFixture"], True))

    def test_chay_test_da_go_khoi_nguon_la_binary_cu(self):
        log = case("FooTests", "testA") + case("FooTests", "test_b") + case("FooTests", "testFromExtension") \
            + case("FooTests", "testTEMPDaGo") + "Executed 4 tests, with 0 failures\n"
        problems = self.check(log)
        self.assertTrue(any("FooTests/testTEMPDaGo" in p for p in problems), problems)

    def test_test_co_trong_nguon_ma_khong_chay_la_binary_cu(self):
        # Class có chạy nhưng thiếu method: binary chưa có test vừa thêm.
        log = case("FooTests", "testA") + case("FooTests", "test_b") + "Executed 2 tests, with 0 failures\n"
        problems = self.check(log, ["FooTests"], True)
        self.assertTrue(any("FooTests/testFromExtension" in p for p in problems), problems)

    def test_chi_dinh_mot_method_khong_doi_cac_method_khac_cua_class(self):
        log = case("FooTests", "testA") + "Executed 1 test, with 0 failures\n"
        self.assertEqual(self.check(log, ["FooTests/testA"], True), [])

    def test_full_class_bi_scheme_skip_khong_bi_doi(self):
        # Scheme chính skip cả class LiveStoreClientTests: class không chạy gì thì không suy ra binary cũ.
        log = case("FooTests", "testA") + case("FooTests", "test_b") + case("FooTests", "testFromExtension") \
            + "Executed 3 tests, with 0 failures\n"
        self.assertEqual(self.check(log), [])

    def test_test_fail_co_ten_dung_khong_bi_coi_la_xanh_gia(self):
        log = case("FooTests", "testA", "failed") + "Executed 1 test, with 1 failure\n"
        self.assertEqual(self.check(log, ["FooTests/testA"], True), [])


class SkippedCompileTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root / "FooTests.swift"
        self.src.write_text("x")
        self.objects = self.root / "objects"
        self.objects.mkdir()
        self.dep = self.objects / "FooTests.d"
        self.dep.write_text("y")

    def stamp(self, path, t):
        os.utime(path, (t, t))

    def check(self, started_at=3000):
        return run_tests.skipped_compile_problems([self.src], self.objects, started_at)

    def test_nguon_moi_hon_file_d_la_build_bo_sot(self):
        self.stamp(self.dep, 1000)
        self.stamp(self.src, 2000)
        problems = self.check()
        self.assertTrue(any("FooTests.swift" in p for p in problems), problems)

    def test_file_d_moi_hon_nguon_thi_sach(self):
        # Sửa comment: Swift biên dịch lại, ghi lại .d, nhưng .o và binary giữ nguyên mtime.
        self.stamp(self.src, 1000)
        self.stamp(self.dep, 2000)
        self.assertEqual(self.check(), [])

    def test_sua_nguon_trong_luc_dang_chay_khong_tinh(self):
        # Sửa sau khi lệnh đã bắt đầu: build không có lỗi gì, chỉ là kết quả chưa phủ lần sửa đó.
        self.stamp(self.dep, 2000)
        self.stamp(self.src, 3500)
        self.assertEqual(self.check(), [])

    def test_nguon_khong_co_file_d_la_chua_vao_project(self):
        self.dep.unlink()
        self.stamp(self.src, 2000)
        problems = self.check()
        self.assertTrue(any("xcodegen" in p for p in problems), problems)

    def test_khong_tim_thay_thu_muc_object_thi_khong_ket_luan(self):
        self.stamp(self.src, 2000)
        self.assertEqual(run_tests.skipped_compile_problems([self.src], self.root / "khong-co", 3000), [])


def pcase(cls, method, verdict="passed", clone=1):
    # Format khi chạy song song (-parallel-testing-enabled YES), lấy từ log thật 2026-11-06.
    return (f"Test case '{cls}.{method}()' {verdict} on 'Clone {clone} of factory-x-42cde5 - "
            f"AppHost (91571)' (0.001 seconds)\n")


class ParallelLogTests(unittest.TestCase):
    """Chạy song song: không có dòng `Test Case '-[…]'` lẫn dòng tổng `Executed N tests`."""

    def test_doc_duoc_test_da_chay(self):
        log = pcase("FooTests", "testA") + pcase("FooTests", "test_b", "skipped", 2) + pcase("BarTests", "testBar", "failed", 3)
        self.assertEqual(run_tests.executed_tests(log),
                         {("FooTests", "testA"), ("FooTests", "test_b"), ("BarTests", "testBar")})

    def test_ten_test_co_chu_unicode(self):
        log = pcase("FooTests", "testĐoGócVuông")
        self.assertEqual(run_tests.executed_tests(log), {("FooTests", "testĐoGócVuông")})

    def test_tong_so_tinh_tu_dong_ket_qua(self):
        log = pcase("FooTests", "testA") + pcase("FooTests", "test_b") + pcase("FooTests", "testFromExtension") \
            + pcase("BarTests", "testBar")
        self.assertEqual(run_tests.executed_total(log), 4)
        self.assertEqual(run_tests.false_green_problems(log, [], run_tests.declared_tests(SRC), False), [])

    def test_song_song_khong_chay_gi_van_la_xanh_gia(self):
        problems = run_tests.false_green_problems("** TEST EXECUTE SUCCEEDED **\n", [], run_tests.declared_tests(SRC),
                                                  False)
        self.assertTrue(any("không chạy test nào" in p for p in problems), problems)

    def test_song_song_thieu_test_trong_nguon_van_bat_binary_cu(self):
        log = pcase("FooTests", "testA") + pcase("FooTests", "test_b")  # thiếu testFromExtension
        problems = run_tests.false_green_problems(log, [], run_tests.declared_tests(SRC), False)
        self.assertTrue(any("testFromExtension" in p for p in problems), problems)

    def test_dong_fail_song_song_duoc_in(self):
        line = pcase("BarTests", "testBar", "failed").strip()
        self.assertTrue(run_tests.is_failure_line(line))
        self.assertFalse(run_tests.is_failure_line(pcase("BarTests", "testBar").strip()))

    def test_khong_tinh_trung_dong_started(self):
        log = "Test case 'FooTests.testA()' started on 'Clone 1 of x' \n" + pcase("FooTests", "testA")
        self.assertEqual(run_tests.executed_total(log), 1)


XCR = {"testNodes": [{"nodeType": "Test Plan", "name": "P", "children": [
    {"nodeType": "Unit test bundle", "name": "AppHostTests", "children": [
        {"nodeType": "Test Suite", "name": "FooTests", "children": [
            {"nodeType": "Test Case", "name": "testA()", "nodeIdentifier": "FooTests/testA()", "result": "Passed"},
            {"nodeType": "Test Case", "name": "test_b()", "nodeIdentifier": "FooTests/test_b()", "result": "Skipped"},
            {"nodeType": "Test Case", "name": "testFromExtension()", "nodeIdentifier": "FooTests/testFromExtension()",
             "result": "Failed", "children": [
                 {"nodeType": "Failure Message", "name": "Foo.swift:12: XCTUnwrap failed: expected non-nil value"}]},
        ]},
        {"nodeType": "Test Suite", "name": "BarTests", "children": [
            {"nodeType": "Test Case", "name": "testBar()", "nodeIdentifier": "BarTests/testBar()", "result": "Passed"}]},
    ]}]}]}


class XcresultTests(unittest.TestCase):
    """Chạy song song: kết quả lấy từ xcresult (log bị stdout app chen mất đầu dòng — gặp thật 2026-11-06)."""

    def test_doc_ket_qua_tung_test(self):
        r = run_tests.xcresult_results(XCR)
        self.assertEqual(r[("FooTests", "testA")], "Passed")
        self.assertEqual(r[("FooTests", "test_b")], "Skipped")
        self.assertEqual(r[("FooTests", "testFromExtension")], "Failed")
        self.assertEqual(len(r), 4)

    def test_loi_va_thong_diep(self):
        f = run_tests.xcresult_failures(XCR)
        self.assertEqual(list(f), [("FooTests", "testFromExtension")])
        self.assertIn("XCTUnwrap", f[("FooTests", "testFromExtension")][0])

    def test_cong_xanh_gia_dung_tap_tu_xcresult(self):
        ran = set(run_tests.xcresult_results(XCR))
        # log rỗng (dòng bị chen hỏng) nhưng xcresult đủ ⇒ không báo xanh giả
        self.assertEqual(run_tests.false_green_problems("", [], run_tests.declared_tests(SRC), False, ran=ran), [])
        # một method của class CÓ chạy mà vắng ⇒ binary cũ (cả class vắng thì có thể do scheme skip — không bắt)
        ran.discard(("FooTests", "testA"))
        problems = run_tests.false_green_problems("", [], run_tests.declared_tests(SRC), False, ran=ran)
        self.assertTrue(any("FooTests/testA" in p for p in problems), problems)

    def test_ket_luan_sau_khi_chay_lai(self):
        fails = [("FooTests", "testA"), ("BarTests", "testBar")]
        rerun_log = case("FooTests", "testA", "passed") + case("BarTests", "testBar", "failed") + \
            "Executed 2 tests, with 1 failure\n"
        still, flaky = run_tests.rerun_verdict(fails, rerun_log)
        self.assertEqual(still, [("BarTests", "testBar")])
        self.assertEqual(flaky, [("FooTests", "testA")])

    def test_chay_lai_ma_khong_thay_ket_qua_thi_coi_la_van_do(self):
        still, flaky = run_tests.rerun_verdict([("FooTests", "testA")], "** TEST EXECUTE FAILED **\n")
        self.assertEqual((still, flaky), ([("FooTests", "testA")], []))


class RerunCommandTests(unittest.TestCase):

    def test_bo_song_song_va_chi_chay_test_do(self):
        cmd = ["xcodebuild", "test", "-project", "P", "-destination", "id=U", "-collect-test-diagnostics", "never",
               "-parallel-testing-enabled", "YES", "-parallel-testing-worker-count", "3",
               "-only-testing:AppHostTests/FooTests"]
        r = run_tests.rerun_command(cmd, 1, [("FooTests", "testA")])
        self.assertEqual(r[:2], ["xcodebuild", "test-without-building"])
        self.assertNotIn("YES", r)
        self.assertNotIn("-parallel-testing-worker-count", r)
        self.assertEqual(r[-3:], ["-parallel-testing-enabled", "NO", "-only-testing:AppHostTests/FooTests/testA"])
        self.assertIn("id=U", r)


class ParallelPolicyTests(unittest.TestCase):

    def test_full_mac_dinh_song_song_l1_thi_khong(self):
        self.assertEqual(run_tests.parallel_workers(None, full=True), run_tests.DEFAULT_PARALLEL_FULL)
        self.assertEqual(run_tests.parallel_workers(None, full=False), 1)
        self.assertEqual(run_tests.parallel_workers(1, full=True), 1)
        self.assertEqual(run_tests.parallel_workers(4, full=False), 4)

    def test_co_xcodebuild(self):
        self.assertEqual(run_tests.parallel_flags(1), ["-parallel-testing-enabled", "NO"])
        self.assertEqual(run_tests.parallel_flags(3),
                         ["-parallel-testing-enabled", "YES", "-parallel-testing-worker-count", "3"])


class TsanTests(unittest.TestCase):

    def test_co_tsan_dung_derived_data_rieng(self):
        self.assertEqual(run_tests.tsan_flags(False), [])
        f = run_tests.tsan_flags(True)
        self.assertEqual(f[:2], ["-enableThreadSanitizer", "YES"])
        self.assertEqual(f[2:], ["-derivedDataPath", run_tests.TSAN_DERIVED_DATA])

    def test_chay_lai_giu_co_tsan(self):
        cmd = ["xcodebuild", "test", "-project", "P", *run_tests.tsan_flags(True),
               "-only-testing:AppHostTests/FooTests"]
        r = run_tests.rerun_command(cmd, 1, [("FooTests", "testA")])
        self.assertIn("-enableThreadSanitizer", r)
        self.assertIn(run_tests.TSAN_DERIVED_DATA, r)

    def test_cong_binary_cu_tim_duoc_objects_cua_build_tsan(self):
        log = f"x {run_tests.TSAN_DERIVED_DATA}/Build/Products/Debug-iphonesimulator/AppHost.app/y\n"
        self.assertEqual(run_tests.objects_dir(log, tsan=True), os.path.join(
            run_tests.TSAN_DERIVED_DATA, "Build", "Intermediates.noindex", "AppHost.build",
            "Debug-iphonesimulator", "AppHostTests.build", "Objects-normal-tsan", "arm64"))


class ObjectsDirTests(unittest.TestCase):

    def test_tsan_duong_dan_repo_co_dau_cach(self):
        # Repo nằm dưới đường dẫn có dấu cách (vd bản chép thử đổi định danh) — regex cũ cắt ở dấu cách.
        dd = "/tmp/factory rename check/app copy/.temp/DerivedData/tsan"
        with mock.patch.object(run_tests, "TSAN_DERIVED_DATA", dd):
            log = f"x {dd}/Build/Products/Debug-iphonesimulator/AppHost.app/y\n"
            self.assertEqual(run_tests.objects_dir(log, tsan=True), os.path.join(
                dd, "Build", "Intermediates.noindex", "AppHost.build", "Debug-iphonesimulator",
                "AppHostTests.build", "Objects-normal-tsan", "arm64"))
            self.assertIsNone(run_tests.objects_dir("không có đường dẫn\n", tsan=True))

    def test_lay_tu_log(self):
        log = "x /Users/a/DerivedData/P-abc/Build/Products/Debug-iphonesimulator/AppHost.app/y\n"
        self.assertEqual(
            run_tests.objects_dir(log),
            "/Users/a/DerivedData/P-abc/Build/Intermediates.noindex/AppHost.build/"
            "Debug-iphonesimulator/AppHostTests.build/Objects-normal/arm64")

    def test_log_no_build_chi_co_duong_dan_xcresult(self):
        log = "\t/Users/a/DerivedData/P-abc/Logs/Test/Test-X.xcresult\n"
        self.assertTrue(run_tests.objects_dir(log).startswith("/Users/a/DerivedData/P-abc/Build/Intermediates.noindex/"))

    def test_khong_co_trong_log(self):
        self.assertIsNone(run_tests.objects_dir("không có đường dẫn\n"))


class ScopeIdentityTests(unittest.TestCase):
    """I5: đổi định danh/cấu hình app không suy ra được test nào ⇒ phải leo thang FULL, không 'không chạy gì'."""

    def assert_leo_thang(self, f):
        classes, escalate, untested = run_tests.select([f], {})
        self.assertEqual(escalate, [f], f"{f} không leo thang FULL")

    def test_app_config_toml_leo_thang(self):
        self.assert_leo_thang(appconfig.CONFIG_FILE)

    def test_xcconfig_leo_thang(self):
        self.assert_leo_thang(appconfig.XCCONFIG)

    def test_entitlements_leo_thang(self):
        self.assert_leo_thang(appconfig.SRC_ROOTS[0] + "AppHost.entitlements")

    def test_privacy_manifest_leo_thang(self):
        self.assert_leo_thang(appconfig.SRC_ROOTS[0] + "PrivacyInfo.xcprivacy")

    def test_nguon_trong_core_chon_test_trong_core_tests(self):
        # Core/ và CoreTests/ nằm NGOÀI AppHost/ — L1 vẫn phải map nguồn lõi sang test của nó.
        src = "Core/Bootstrap/AppEnvironment.swift"
        self.assertTrue(src.startswith(appconfig.SRC_ROOTS))
        tests = {"CoreTests/Bootstrap/AppEnvironmentTests.swift": "final class AppEnvironmentTests: XCTestCase {}\n"}
        self.assertEqual(run_tests.select([src], tests), ({"AppEnvironmentTests"}, [], []))

    def test_sua_test_trong_core_tests_chay_dung_class(self):
        f = "CoreTests/Bootstrap/XTests.swift"
        self.assertEqual(run_tests.select([f], {f: "final class XTests: XCTestCase {}\n"}), ({"XTests"}, [], []))

    def test_nguon_khoi_tuy_chon_chon_test_cua_khoi(self):
        # CoreOptional/ nằm trong SRC_ROOTS ⇒ L1 map nguồn khối sang test CoreOptionalTests/ (không bị coi là "ngoài app").
        src = "CoreOptional/WebAPI/WebAPIFeedbackTransport.swift"
        self.assertTrue(src.startswith(appconfig.SRC_ROOTS))
        tests = {"CoreOptionalTests/WebAPI/WebAPIFeedbackTransportTests.swift":
                 "final class WebAPIFeedbackTransportTests: XCTestCase {}\n"}
        with tempfile.TemporaryDirectory() as td, mock.patch.object(run_tests, "REPO", td):
            p = Path(td, src)
            p.parent.mkdir(parents=True)
            p.write_text("final class WebAPIFeedbackTransport {}\n")
            self.assertEqual(run_tests.select([src], tests), ({"WebAPIFeedbackTransportTests"}, [], []))

    def test_khoi_dang_tat_khong_nam_trong_build_nen_bi_bo_qua(self):
        # web_api = false: test của khối không có trong binary (chọn là xanh giả), nguồn khối không được biên dịch.
        src = "CoreOptional/WebAPI/WebAPIFeedbackTransport.swift"
        tf = "CoreOptionalTests/WebAPI/WebAPIFeedbackTransportTests.swift"
        tests = {tf: "final class WebAPIFeedbackTransportTests: XCTestCase {}\n"}
        off = (("CoreOptional/WebAPI/",), ("CoreOptionalTests/WebAPI/",))
        self.assertEqual(run_tests.select([src, tf], tests, disabled=off), (set(), [], []))

    def test_khoi_dang_tat_van_chon_core_binh_thuong(self):
        f = "CoreTests/Bootstrap/XTests.swift"
        off = (("CoreOptional/WebAPI/",), ("CoreOptionalTests/WebAPI/",))
        self.assertEqual(run_tests.select([f], {f: "final class XTests: XCTestCase {}\n"}, disabled=off),
                         ({"XTests"}, [], []))

    def test_test_files_bo_test_cua_khoi_dang_tat(self):
        # declared_tests (cổng xanh giả "nguồn có mà không chạy") đọc từ test_files(): test của khối tắt phải vắng.
        with tempfile.TemporaryDirectory() as td, mock.patch.object(run_tests, "REPO", td):
            for rel in ("CoreTests/A/ATests.swift", "CoreOptionalTests/WebAPI/BTests.swift"):
                p = Path(td, rel)
                p.parent.mkdir(parents=True)
                p.write_text("final class X: XCTestCase {}\n")
            on = run_tests.test_files()
            off = run_tests.test_files(disabled=(("CoreOptional/WebAPI/",), ("CoreOptionalTests/WebAPI/",)))
        self.assertEqual(sorted(on), ["CoreOptionalTests/WebAPI/BTests.swift", "CoreTests/A/ATests.swift"])
        self.assertEqual(sorted(off), ["CoreTests/A/ATests.swift"])

    def test_root_khoi_tuy_chon_vang_mat_khong_loi(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.object(run_tests, "REPO", td):
            Path(td, "CoreTests").mkdir()
            self.assertEqual(run_tests.test_files(), {})

    def test_file_ngoai_app_van_bo_qua(self):
        self.assertEqual(run_tests.select(["docs/ROADMAP.md", "tools/x.py"], {}), (set(), [], []))


GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]


def _clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


class BaseRefTests(unittest.TestCase):
    """I5: thiếu nhánh mốc không được âm thầm thành '0 file đổi'."""

    def setUp(self):
        import subprocess
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.run = lambda *a: subprocess.run(["git", *a], cwd=self.root, env=_clean_env(),
                                             capture_output=True, text=True, check=True)
        self.run("init", "-q", "-b", "main")
        Path(self.root, "a.txt").write_text("a\n")
        self.run("add", "a.txt")
        self.run(*GIT_ID, "commit", "-q", "-m", "base")

    def test_thieu_nhanh_moc_la_loi_ro_rang(self):
        with mock.patch.dict(os.environ, _clean_env(), clear=True):
            with self.assertRaisesRegex(run_tests.BaseRefError, r"develop"):
                run_tests.changed_files("develop", repo=self.root)

    def test_co_origin_cua_nhanh_moc_thi_dung_no(self):
        self.run("update-ref", "refs/remotes/origin/develop", "HEAD")
        Path(self.root, "b.txt").write_text("b\n")
        self.run("add", "b.txt")
        self.run(*GIT_ID, "commit", "-q", "-m", "b")
        with mock.patch.dict(os.environ, _clean_env(), clear=True):
            self.assertEqual(run_tests.changed_files("develop", repo=self.root), ["b.txt"])


RUN_TESTS_PY = HERE / "run_tests.py"


class CliConfigTests(unittest.TestCase):
    """I6: cấu hình hỏng ⇒ FAIL rc 2, không traceback; --help vẫn chạy. Repo tạm chép tool thật."""

    def setUp(self):
        import shutil
        import subprocess
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo tạm"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, env=_clean_env(), check=True)
        for rel in ("tools/dev/run_tests.py", "tools/dev/sim_pool.py", "tools/common/appconfig.py"):
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HERE.parents[1] / rel, dst)
        shutil.copy2(HERE.parents[1] / appconfig.CONFIG_FILE, self.root / appconfig.CONFIG_FILE)
        appconfig.write_generated(self.root, appconfig.load(self.root))

    def cli(self, *args):
        import subprocess
        return subprocess.run([sys.executable, "tools/dev/run_tests.py", *args], cwd=self.root,
                              env=_clean_env(), capture_output=True, text=True)

    def break_config(self):
        p = self.root / appconfig.CONFIG_FILE
        text = p.read_text(encoding="utf-8")
        new = "\n".join(l for l in text.splitlines() if not l.startswith("team_id")) + "\n"
        self.assertNotEqual(new, text)
        p.write_text(new, encoding="utf-8")

    def test_cau_hinh_hong_fail_rc2_khong_traceback(self):
        self.break_config()
        r = self.cli("--list")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("FAIL:", r.stderr)
        self.assertIn("apple.team_id", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_features_yml_cu_fail_rc2(self):
        (self.root / appconfig.FEATURES_YML).write_text("targets: {}\n", encoding="utf-8")
        r = self.cli("--list")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(appconfig.FEATURES_YML, r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_help_chay_duoc_khi_cau_hinh_hong(self):
        self.break_config()
        r = self.cli("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("--storekit", r.stdout)

    def test_storekit_khi_chua_sinh_scheme_thoat_sach(self):
        r = self.cli("--storekit")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(appconfig.STOREKIT_SCHEME, r.stderr)
        self.assertIn("xcodegen generate", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_thieu_nhanh_moc_cli_fail_rc2(self):
        r = self.cli("--list", "--base", "khong-co-nhanh-nay")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("FAIL:", r.stderr)
        self.assertIn("khong-co-nhanh-nay", r.stderr)
        self.assertNotIn("0 file đổi", r.stdout)


class ConfigTests(unittest.TestCase):

    def test_hang_so_lay_tu_appconfig(self):
        self.assertEqual(run_tests.SCHEME, appconfig.SCHEME)
        self.assertEqual(run_tests.TEST_TARGET, appconfig.TEST_TARGET)
        self.assertEqual(run_tests.host_bundle_id(), appconfig.get(appconfig.load(), "bundle.internal"))

    def test_khong_con_ten_repo_nguon(self):
        src = Path(run_tests.__file__).read_text(encoding="utf-8")
        self.assertNotIn("LiDARTextured" + "Scanner", src)


if __name__ == "__main__":
    unittest.main()
