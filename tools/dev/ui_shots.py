#!/usr/bin/env python3
"""Chụp màn theo HƯỚNG (iPad ngang / iPhone dọc) qua XCUITest — xem skill ui-preview-sim.

    tools/dev/ui_shots.py home settings                              # sim riêng của worktree (iPhone, dọc)
    tools/dev/ui_shots.py all --label p3-task9                       # mọi route của AppPreview ⇒ .temp/ui-shots/p3-task9/
    tools/dev/ui_shots.py --udid <iPad UDID> --label x all           # iPad ⇒ tự chọn ngang
    tools/dev/ui_shots.py --content-size accessibility-extra-large --label ax items itemDetail
    tools/dev/ui_shots.py --udid <UDID> --orient portrait --out <dir> home

Máy dev không có Simulator.app để ⌘→, `simctl` không xoay được thiết bị; chỉ XCUITest
(`XCUIDevice.orientation`) xoay được. Scheme riêng `AppHost-UIShots` (Debug, bundle id nội bộ)
— không nằm trong L1/L2. Mỗi target là một route `-uiPreview` (`case` của `enum AppPreview` trong
`AppHost/AppHost/AppPreview.swift`); `all` = MỌI `case` đọc thẳng từ file đó (kể cả trong khối `// sample:`) — một
nguồn, thêm route không phải sửa script. Ảnh ghi ra `<out>/<target>-land.png` / `-port.png` (route cuộn như
`settings` có thêm `<target>-scrolled-*.png`); ảnh ngang — kể cả ảnh cuộn — được xoay đứng lại để đọc thẳng.
Route sai tên ⇒ báo THIẾU ảnh, rc 1.

- `--udid` mặc định: sim riêng của worktree (`sim_pool.py ensure`, iPhone).
- `--orient auto` (mặc định): sim iPad ⇒ landscape, còn lại ⇒ portrait (iPhone chỉ hỗ trợ dọc).
- `--out DIR` hoặc `--label TÊN` (⇒ `.temp/ui-shots/TÊN/`; TÊN khớp `^[A-Za-z0-9][A-Za-z0-9._/-]*$`, được có thư mục
  con như `p3/default`, không có thành phần `..`, sai ⇒ rc 2); không có cả hai ⇒ `.temp/ui-shots/default/`.
- `--content-size <cỡ>`: đặt Dynamic Type của sim (`xcrun simctl ui <udid> content_size <cỡ>`) trước khi chụp và
  LUÔN trả về `large` sau đó (cả khi chụp lỗi, Ctrl-C hay SIGTERM).

DerivedData riêng ở `.temp/DerivedData/uishots` (đã git-ignore) — không làm bẩn cây nguồn.
`tools/template/selfcheck.sh` (bản đủ) build-for-testing scheme này để nó không mục.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))
import appconfig  # noqa: E402
from lint_debug_symbols import blank_comments_and_strings  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = REPO_ROOT / appconfig.PROJ_DIR
DERIVED_DATA = REPO_ROOT / ".temp" / "DerivedData" / "uishots"
SHOTS_ROOT = REPO_ROOT / ".temp" / "ui-shots"
APP_PREVIEW = REPO_ROOT / appconfig.PROJ_DIR / appconfig.PROJ_DIR / "AppPreview.swift"
# Mặc định CHỈ chạy test chụp ảnh: target UITests có thể có test hành vi khác (chậm, hoặc đỏ trên một loại máy làm
# xcodebuild treo lâu ở `simctl diagnose`). --all-tests để chạy cả target.
ONLY_TESTING = f"{appconfig.UITEST_TARGET}/UIShotsTests/testChupMan"
DEFAULT_CONTENT_SIZE = "large"
CONTENT_SIZES = ("extra-small", "small", "medium", "large", "extra-large", "extra-extra-large",
                 "extra-extra-extra-large", "accessibility-medium", "accessibility-large",
                 "accessibility-extra-large", "accessibility-extra-extra-large",
                 "accessibility-extra-extra-extra-large")
CASE_RE = re.compile(r"^\s*case\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*$")
CASE_START_RE = re.compile(r"^\s*case\b")
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def label_error(label: str):
    """Lý do `--label` không hợp lệ (None = hợp lệ). Cho phép thư mục con (`p3/default`), cấm `..`, `/` đầu, ký tự lạ —
    nhãn thành đường dẫn dưới `.temp/ui-shots/`, không được trỏ ra ngoài."""
    if not LABEL_RE.match(label):
        return "phải khớp ^[A-Za-z0-9][A-Za-z0-9._/-]*$"
    if ".." in label.split("/"):
        return "không được có thành phần `..`"
    return None


def build_cmd(udid: str, all_tests: bool = False) -> list:
    cmd = ["xcodebuild", "test",
           "-project", str(REPO_ROOT / appconfig.PROJECT),
           "-scheme", appconfig.UISHOTS_SCHEME,
           "-configuration", "Debug",
           "-destination", f"id={udid}",
           "-derivedDataPath", str(DERIVED_DATA)]
    if not all_tests:
        cmd.append(f"-only-testing:{ONLY_TESTING}")
    cmd.append("CODE_SIGNING_ALLOWED=NO")
    return cmd


def routes_from_app_preview(path: Path = APP_PREVIEW) -> list:
    """Tên các `case` khai ở MỨC NGOÀI CÙNG của `enum AppPreview` (comment/chuỗi đã xoá trắng; `case` trong switch
    của property nằm sâu hơn một cấp ngoặc nên bị bỏ). Không thấy enum / không có case / `case` có raw value tường
    minh (`case c = "cc"`) ⇒ ValueError kèm `file:dòng`."""
    text = path.read_text(encoding="utf-8")
    code = blank_comments_and_strings(text)
    m = re.search(r"\benum\s+AppPreview\b[^{]*\{", code)
    if not m:
        raise ValueError(f"không thấy `enum AppPreview` trong {path}")
    depth, i, line, routes = 1, m.end(), "", []
    while i < len(code) and depth > 0:
        c = code[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == "\n":
            mm = CASE_RE.match(line)
            if mm:
                routes += [n.strip() for n in mm.group(1).split(",")]
            elif CASE_START_RE.match(line):
                # `case c = "cc"` (raw value tường minh), associated value… ⇒ tên route ≠ giá trị `-uiPreview`: báo to.
                no = code.count("\n", 0, i) + 1
                raise ValueError(f"{path}:{no}: route phải khai dạng `case a, b` (không raw value tường minh, "
                                 f"không associated value): {text.split(chr(10))[no - 1].strip()}")
            line = ""
            i += 1
            continue
        if depth == 1 and c not in "{}":
            line += c
        elif c in "{}":
            line += " "  # dòng có ngoặc không phải dòng case thuần
        i += 1
    if not routes:
        raise ValueError(f"`enum AppPreview` trong {path} không có case nào")
    return routes


def expand_targets(targets: list, routes=None) -> list:
    """`all` ⇒ mọi route (một lần, đúng thứ tự khai); target khác giữ nguyên; bỏ trùng."""
    out = []
    for t in targets:
        for r in ((routes if routes is not None else routes_from_app_preview()) if t == "all" else [t]):
            if r not in out:
                out.append(r)
    return out


def auto_orient(device_name: str) -> str:
    return "landscape" if "ipad" in device_name.lower() else "portrait"


def device_name(udid: str, runner=subprocess.run) -> str:
    r = runner(["xcrun", "simctl", "list", "devices", "-j"], capture_output=True, text=True)
    try:
        for devs in json.loads(r.stdout or "{}").get("devices", {}).values():
            for d in devs:
                if d.get("udid") == udid:
                    return d.get("name", "")
    except ValueError:
        pass
    return ""


def worktree_udid() -> str:
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "dev" / "sim_pool.py"), "ensure",
                        "--repo", str(REPO_ROOT)], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"sim_pool.py ensure lỗi: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip().splitlines()[-1]


def set_content_size(udid: str, size: str, runner=subprocess.run) -> bool:
    r = runner(["xcrun", "simctl", "ui", udid, "content_size", size], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"cảnh báo: không đặt được content_size={size} trên {udid}: {(r.stderr or r.stdout).strip()}",
              file=sys.stderr)
        return False
    return True


def output_dir(out, label) -> Path:
    if out:
        return Path(out).resolve()
    return SHOTS_ROOT / (label or "default")


def collect(out: Path, targets: list, orient: str, runner=subprocess.run) -> int:
    """Kiểm đủ ảnh + xoay ảnh ngang (cả ảnh `-scrolled-`). rc 0/1."""
    suffix = "land" if orient == "landscape" else "port"
    missing = rotate_failed = 0
    for t in targets:
        p = out / f"{t}-{suffix}.png"
        if not p.exists():
            print(f"THIẾU {p}", file=sys.stderr)
            missing += 1
            continue
        shots = [p] + [q for q in [out / f"{t}-scrolled-{suffix}.png"] if q.exists()]
        for s in shots:
            # XCUIScreen chụp theo khung DỌC gốc của màn — xoay lại cho ảnh ngang đọc được thẳng.
            if orient == "landscape":
                rr = runner(["sips", "-r", "270", str(s)], capture_output=True, text=True)
                if rr.returncode != 0:
                    # Ảnh chưa xoay mà báo xanh ⇒ người xem đọc ảnh nghiêng tưởng là bố cục lỗi — coi là thất bại.
                    print(f"FAIL: sips không xoay được {s} (rc={rr.returncode}): "
                          f"{(rr.stderr or rr.stdout).strip()}", file=sys.stderr)
                    rotate_failed += 1
                    continue
            print(s)
    # xcodebuild xanh mà thiếu ảnh (target sai tên, test bị skip…) KHÔNG phải thành công.
    if missing:
        print(f"FAIL: thiếu {missing}/{len(targets)} ảnh", file=sys.stderr)
        return 1
    if rotate_failed:
        print(f"FAIL: không xoay được {rotate_failed} ảnh", file=sys.stderr)
        return 1
    return 0


def shoot(udid: str, targets: list, orient: str, out: Path, all_tests: bool = False, content_size=None,
          runner=subprocess.run) -> int:
    """Chạy XCUITest chụp ảnh. `content_size` ⇒ đặt trước, LUÔN trả `large` sau (finally)."""
    if content_size:
        set_content_size(udid, content_size, runner)
    try:
        out.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ,
                   TEST_RUNNER_UISHOTS=",".join(targets),
                   TEST_RUNNER_UISHOTS_ORIENT=orient,
                   TEST_RUNNER_UISHOTS_DIR=str(out))
        r = runner(build_cmd(udid, all_tests), env=env, capture_output=True, text=True)
        if r.returncode != 0:
            lines = ((r.stdout or "") + (r.stderr or "")).splitlines()
            # Lý do thật (XCTFail, lỗi build) thường nằm xa trước 30 dòng cuối — in riêng ra trước.
            reasons = list(dict.fromkeys(l.strip() for l in lines if ": error:" in l or "XCTAssert" in l))
            for line in reasons[:10]:
                print(line, file=sys.stderr)
            print("\n".join(lines[-30:]), file=sys.stderr)
            return r.returncode
        return collect(out, targets, orient, runner)
    finally:
        if content_size:
            set_content_size(udid, DEFAULT_CONTENT_SIZE, runner)


def _sigterm(signum, frame):
    # SIGTERM ⇒ ngoại lệ ⇒ khối finally của `shoot` trả content_size về `large`.
    raise SystemExit(128 + signum)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="+", help="route -uiPreview, hoặc `all` (mọi case của AppPreview)")
    ap.add_argument("--udid", help="mặc định: sim riêng của worktree (sim_pool.py ensure)")
    ap.add_argument("--orient", choices=["auto", "landscape", "portrait"], default="auto")
    dest = ap.add_mutually_exclusive_group()
    dest.add_argument("--out", help="thư mục ảnh")
    dest.add_argument("--label", help="tên đợt ảnh ⇒ .temp/ui-shots/<label>/")
    ap.add_argument("--content-size", choices=CONTENT_SIZES,
                    help="Dynamic Type của sim khi chụp; luôn trả về `large` sau đó")
    ap.add_argument("--all-tests", action="store_true",
                    help="chạy cả target UITests, không chỉ testChupMan")
    ap.add_argument("--print-cmd", action="store_true", help="in lệnh xcodebuild rồi thoát, không chạy")
    args = ap.parse_args(argv)
    if args.label is not None:
        why = label_error(args.label)
        if why:
            print(f"FAIL: --label {args.label!r} {why}", file=sys.stderr)
            return 2

    try:
        targets = expand_targets(args.targets)
    except (OSError, ValueError) as e:
        print(f"FAIL: không đọc được danh sách route: {e}", file=sys.stderr)
        return 2
    try:
        udid = args.udid or worktree_udid()
    except RuntimeError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    if args.print_cmd:
        print(" ".join(build_cmd(udid, args.all_tests)))
        return 0
    orient = args.orient if args.orient != "auto" else auto_orient(device_name(udid))
    out = output_dir(args.out, args.label)
    print(f"[ui_shots] {len(targets)} route · {orient} · {udid} ⇒ {out}", file=sys.stderr)
    signal.signal(signal.SIGTERM, _sigterm)
    return shoot(udid, targets, orient, out, args.all_tests, args.content_size)


if __name__ == "__main__":
    sys.exit(main())
