import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ui_shots  # noqa: E402


class BuildCmdTests(unittest.TestCase):
    def test_mac_dinh_chi_chay_test_chup_man(self):
        cmd = ui_shots.build_cmd("UDID1")
        self.assertIn("-only-testing:AppHostUITests/UIShotsTests/testChupMan", cmd)
        self.assertIn("id=UDID1", cmd)
        self.assertEqual(cmd[:2], ["xcodebuild", "test"])
        self.assertIn("AppHost-UIShots", cmd)

    def test_derived_data_nam_duoi_temp_da_ignore(self):
        cmd = ui_shots.build_cmd("U")
        dd = cmd[cmd.index("-derivedDataPath") + 1]
        repo = os.path.dirname(os.path.dirname(HERE))
        self.assertEqual(os.path.relpath(dd, repo), os.path.join(".temp", "DerivedData", "uishots"))
        r = subprocess.run(["git", "check-ignore", "-q", os.path.join(dd, "Build", "x")], cwd=repo,
                           env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")})
        self.assertEqual(r.returncode, 0, f"{dd} không bị git ignore")

    def test_all_tests_bo_only_testing(self):
        cmd = ui_shots.build_cmd("U", all_tests=True)
        self.assertFalse([c for c in cmd if c.startswith("-only-testing")])

    def test_ten_test_khop_nguon_swift(self):
        src = open(os.path.join(ui_shots.ROOT, "AppHostUITests", "UIShotsTests.swift"),
                   encoding="utf-8").read()
        target, cls, meth = ui_shots.ONLY_TESTING.split("/")
        self.assertTrue(os.path.isdir(os.path.join(ui_shots.ROOT, target)))
        self.assertRegex(src, r"final class %s\b" % re.escape(cls))
        self.assertRegex(src, r"func %s\(" % re.escape(meth))


APP_PREVIEW_FIXTURE = '''import SwiftUI
/// enum AppPreview { case fake }  — comment không tính
enum AppPreview: String, UIPreviewRoute {
    case home, onboarding
    // sample:begin
    case homeEmpty, items
    // sample:end
    case feedback // comment cuối dòng

    var isOnboarding: Bool {
        switch self {
        case .onboarding: return true
        // sample:begin
        case .items: return false
        // sample:end
        default: return false
        }
    }
    static let s = "case notARoute"
    var t: Int { switch self { case .home: 1
        default: 2 } }
}
enum Other { case nope }
'''


class RoutesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, text):
        p = os.path.join(self.tmp.name, "AppPreview.swift")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        from pathlib import Path
        return Path(p)

    def test_all_doc_route_tu_app_preview(self):
        routes = ui_shots.routes_from_app_preview(self.write(APP_PREVIEW_FIXTURE))
        self.assertEqual(routes, ["home", "onboarding", "homeEmpty", "items", "feedback"])

    def test_all_mo_rong_mot_lan_giu_thu_tu(self):
        self.assertEqual(ui_shots.expand_targets(["settings", "all", "home"], routes=["home", "settings", "x"]),
                         ["settings", "home", "x"])
        self.assertEqual(ui_shots.expand_targets(["home", "settings"], routes=[]), ["home", "settings"])

    def test_file_that_co_route_khung_va_route_mau(self):
        routes = ui_shots.routes_from_app_preview()
        self.assertEqual(routes[:6], ["home", "onboarding", "settings", "paywall", "whatsNew", "feedback"])
        self.assertEqual(len(routes), len(set(routes)))

    def test_khong_co_enum_la_loi(self):
        with self.assertRaises(ValueError):
            ui_shots.routes_from_app_preview(self.write("enum Other { case a }\n"))

    def test_case_co_raw_value_la_loi_kem_dong(self):
        text = "enum AppPreview: String {\n    case home\n    // sample:begin\n    case c = \"cc\"\n    // sample:end\n}\n"
        with self.assertRaises(ValueError) as cm:
            ui_shots.routes_from_app_preview(self.write(text))
        self.assertIn("AppPreview.swift:4:", str(cm.exception))
        self.assertIn('case c = "cc"', str(cm.exception))

    def test_label_hop_le_va_khong_hop_le(self):
        for ok in ("p3", "p3/default", "p3-final/onboarding-ax", "a.b_c-1"):
            self.assertIsNone(ui_shots.label_error(ok), ok)
        for bad in ("../x", "p3/../../x", "/abs", "..", "-x", "", "a b", "p3/..", ".hidden", "x\\y"):
            self.assertIsNotNone(ui_shots.label_error(bad), bad)

    def test_huong_tu_dong_theo_loai_may(self):
        self.assertEqual(ui_shots.auto_orient("iPad Pro 13-inch (M5)"), "landscape")
        self.assertEqual(ui_shots.auto_orient("factory-x-123"), "portrait")
        self.assertEqual(ui_shots.auto_orient(""), "portrait")

    def test_label_chon_thu_muc_duoi_temp_ui_shots(self):
        self.assertEqual(ui_shots.output_dir(None, "p3"), ui_shots.SHOTS_ROOT / "p3")
        self.assertEqual(ui_shots.output_dir(None, None), ui_shots.SHOTS_ROOT / "default")
        self.assertEqual(os.path.relpath(ui_shots.SHOTS_ROOT, ui_shots.REPO_ROOT), os.path.join(".temp", "ui-shots"))


class Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class ContentSizeTests(unittest.TestCase):
    """Runner giả: ghi mọi lệnh; xcodebuild trả `xc_rc` hoặc ném `xc_raise`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.calls = []

    def runner(self, xc_rc=0, xc_raise=None):
        def run(cmd, **kw):
            self.calls.append(list(cmd))
            if cmd[0] == "xcodebuild":
                if xc_raise:
                    raise xc_raise
                return Proc(xc_rc, "", "** TEST FAILED **")
            return Proc(0)
        return run

    def sizes(self):
        return [c[-1] for c in self.calls if c[:3] == ["xcrun", "simctl", "ui"]]

    def shoot(self, **kw):
        from pathlib import Path
        return ui_shots.shoot("U", ["home"], "portrait", Path(self.tmp.name) / "out", content_size="accessibility-large",
                              **kw)

    def test_content_size_duoc_tra_ve_large_khi_loi(self):
        rc = self.shoot(runner=self.runner(xc_rc=65))
        self.assertEqual(rc, 65)
        self.assertEqual(self.sizes(), ["accessibility-large", "large"])
        self.assertEqual(self.calls[-1], ["xcrun", "simctl", "ui", "U", "content_size", "large"])
        xc = next(i for i, c in enumerate(self.calls) if c[0] == "xcodebuild")
        self.assertLess(self.calls.index(["xcrun", "simctl", "ui", "U", "content_size", "accessibility-large"]), xc)

    def test_content_size_tra_ve_large_khi_bi_ngat(self):
        with self.assertRaises(KeyboardInterrupt):
            self.shoot(runner=self.runner(xc_raise=KeyboardInterrupt()))
        self.assertEqual(self.sizes(), ["accessibility-large", "large"])

    def test_content_size_tra_ve_large_khi_thieu_anh(self):
        rc = self.shoot(runner=self.runner(xc_rc=0))
        self.assertEqual(rc, 1)  # không có ảnh nào ⇒ THIẾU
        self.assertEqual(self.sizes(), ["accessibility-large", "large"])

    def test_khong_co_content_size_thi_khong_dung_simctl_ui(self):
        from pathlib import Path
        ui_shots.shoot("U", ["home"], "portrait", Path(self.tmp.name) / "o", runner=self.runner(xc_rc=65))
        self.assertEqual(self.sizes(), [])


SCRIPT = os.path.join(HERE, "ui_shots.py")
# xcodebuild giả: ghi marker (đối số) rồi tạo ảnh cho các target trong $FAKE_PNGS (cách nhau dấu phẩy).
FAKE_XCODEBUILD = """#!/bin/sh
echo "$@" >> "$FAKE_MARKER"
case "$TEST_RUNNER_UISHOTS_ORIENT" in landscape) sfx=land ;; *) sfx=port ;; esac
echo "$TEST_RUNNER_UISHOTS" > "$FAKE_MARKER.routes"
IFS=,
for t in $FAKE_PNGS; do : > "$TEST_RUNNER_UISHOTS_DIR/$t-$sfx.png"; done
exit 0
"""
# xcrun giả: ghi đối số vào $FAKE_XCRUN_LOG (không đụng simulator thật).
FAKE_XCRUN = """#!/bin/sh
echo "$@" >> "$FAKE_XCRUN_LOG"
exit 0
"""
# sips giả: ghi đối số vào $FAKE_SIPS_LOG, thoát với mã $FAKE_SIPS_RC (mặc định 0).
FAKE_SIPS = """#!/bin/sh
echo "$@" >> "$FAKE_SIPS_LOG"
echo "sips giả lỗi" >&2
exit "${FAKE_SIPS_RC:-0}"
"""


class CliWithFakeXcodebuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        bindir = os.path.join(self.tmp.name, "bin")
        os.makedirs(bindir)
        with open(os.path.join(bindir, "xcodebuild"), "w") as f:
            f.write(FAKE_XCODEBUILD)
        os.chmod(os.path.join(bindir, "xcodebuild"), 0o755)
        with open(os.path.join(bindir, "sips"), "w") as f:
            f.write(FAKE_SIPS)
        os.chmod(os.path.join(bindir, "sips"), 0o755)
        with open(os.path.join(bindir, "xcrun"), "w") as f:
            f.write(FAKE_XCRUN)
        os.chmod(os.path.join(bindir, "xcrun"), 0o755)
        self.sips_log = os.path.join(self.tmp.name, "sips.log")
        self.xcrun_log = os.path.join(self.tmp.name, "xcrun.log")
        self.marker = os.path.join(self.tmp.name, "called")
        self.out = os.path.join(self.tmp.name, "out")
        self.env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"], FAKE_MARKER=self.marker,
                        FAKE_SIPS_LOG=self.sips_log, FAKE_XCRUN_LOG=self.xcrun_log)

    def run_cli(self, *args, pngs="", sips_rc=0, dest=None):
        dest = ["--out", self.out] if dest is None else dest
        return subprocess.run([sys.executable, SCRIPT, "--udid", "U", *dest, *args],
                              capture_output=True, text=True,
                              env=dict(self.env, FAKE_PNGS=pngs, FAKE_SIPS_RC=str(sips_rc)))

    def test_all_gui_moi_route_cho_xcuitest(self):
        routes = ui_shots.routes_from_app_preview()
        r = self.run_cli("--orient", "portrait", "all", pngs=",".join(routes))
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.marker + ".routes") as f:
            self.assertEqual(f.read().strip().split(","), routes)

    def test_orient_auto_may_khong_phai_ipad_la_doc(self):
        r = self.run_cli("home", pngs="home")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.out, "home-port.png")))
        self.assertFalse(os.path.exists(self.sips_log))

    def test_content_size_cli_dat_roi_tra_large(self):
        r = self.run_cli("--orient", "portrait", "--content-size", "extra-large", "home", pngs="")
        self.assertEqual(r.returncode, 1, r.stderr)  # thiếu ảnh
        with open(self.xcrun_log) as f:
            ui = [l.split() for l in f.read().splitlines() if l.startswith("simctl ui")]
        self.assertEqual(ui, [["simctl", "ui", "U", "content_size", "extra-large"],
                              ["simctl", "ui", "U", "content_size", "large"]])

    def test_content_size_sai_ten_rc2(self):
        r = self.run_cli("--content-size", "huge", "home")
        self.assertEqual(r.returncode, 2)

    def test_label_ra_ngoai_rc2_khong_goi_xcodebuild(self):
        r = self.run_cli("home", dest=["--label", "../ngoai"], pngs="home")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--label", r.stderr)
        self.assertFalse(os.path.exists(self.marker))

    def test_out_va_label_loai_tru_nhau(self):
        r = self.run_cli("--label", "x", "home")
        self.assertEqual(r.returncode, 2)

    def test_anh_cuon_ngang_cung_duoc_xoay(self):
        os.makedirs(self.out, exist_ok=True)
        # xcodebuild giả chỉ tạo ảnh chính; ảnh cuộn đặt sẵn như UIShotsTests ghi.
        open(os.path.join(self.out, "settings-scrolled-land.png"), "w").close()
        r = self.run_cli("--orient", "landscape", "settings", pngs="settings")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.sips_log) as f:
            rotated = f.read()
        self.assertIn("settings-land.png", rotated)
        self.assertIn("settings-scrolled-land.png", rotated)

    def test_print_cmd_khong_goi_xcodebuild(self):
        r = self.run_cli("--print-cmd", "home")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("xcodebuild test "))
        self.assertFalse(os.path.exists(self.marker), "--print-cmd đã gọi xcodebuild")

    def test_print_cmd_all_tests_khong_co_only_testing(self):
        r = self.run_cli("--print-cmd", "--all-tests", "home")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("-only-testing", r.stdout)
        self.assertIn("-only-testing:", self.run_cli("--print-cmd", "home").stdout)

    def test_du_anh_rc0(self):
        r = self.run_cli("--orient", "portrait", "home", "library", pngs="home,library")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(self.marker))

    def test_thieu_anh_rc1(self):
        r = self.run_cli("--orient", "portrait", "home", "library", pngs="home")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("THIẾU", r.stderr)
        self.assertIn("library-port.png", r.stderr)

    def test_ngang_sips_xanh_rc0(self):
        r = self.run_cli("--orient", "landscape", "home", "library", pngs="home,library")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.sips_log) as f:
            self.assertEqual(len(f.read().splitlines()), 2)  # xoay đúng 2 ảnh ngang

    def test_ngang_sips_loi_rc1(self):
        r = self.run_cli("--orient", "landscape", "home", "library", pngs="home,library", sips_rc=1)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("sips", r.stderr)
        self.assertIn("home-land.png", r.stderr)


if __name__ == "__main__":
    unittest.main()
