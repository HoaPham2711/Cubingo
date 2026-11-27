#!/usr/bin/env python3
"""Chạy test theo PHẠM VI thay đổi — thang kiểm chứng L1/L2 (xem .claude/rules/conventions.core.md).

    tools/dev/run_tests.py                 # L1: test liên quan tới file đã đổi (so với develop + worktree)
    tools/dev/run_tests.py --base main     # đổi mốc so sánh
    tools/dev/run_tests.py --full          # L2: toàn bộ suite
    tools/dev/run_tests.py FooTests BarTests            # chạy đúng các class này
    tools/dev/run_tests.py FooTests/test_x              # chạy đúng 1 test
    tools/dev/run_tests.py --no-build ...  # test-without-building (bundle đã build, chỉ chạy lại)
    tools/dev/run_tests.py --list          # chỉ in các class sẽ chạy, không chạy
    tools/dev/run_tests.py --storekit      # CHỈ LiveStoreClientTests, qua scheme AppHost-StoreKitTests (host ký ad-hoc)
    tools/dev/run_tests.py --tsan FooTests # Thread Sanitizer (DerivedData riêng .temp/DerivedData/tsan)

Cách chọn test (L1):
  1. File test đã đổi → chạy chính các class trong file đó.
  2. File nguồn .swift đã đổi → (a) test file cùng tiền tố tên (`Foo.swift` → `Foo*Tests.swift`),
     (b) test file nhắc tới BẤT KỲ type nào khai báo trong file đó.
  3. Đụng thứ không map được (.metal, .cpp/.h, project.yml, Info.plist, *.xcstrings, *.xcconfig,
     *.entitlements, *.xcprivacy, app.config.toml) → leo thang lên FULL suite. Map sai = bỏ sót hồi
     quy, nên chỗ nào không chắc thì chạy hết.
  Mốc so sánh (`--base`, mặc định develop) không có ở local thì thử `origin/<base>`; vẫn không có ⇒
  `FAIL:` rc 2 (không âm thầm coi là 0 file đổi).
  4. File .swift không có test nào nhắc tới (View thuần…) → chỉ build (compile-check), in rõ ra.

Log đầy đủ ghi vào .temp/test-logs/<timestamp>.log; stdout chỉ in test fail + dòng tổng kết.

Cổng chống xanh giả: xcodebuild trả rc=0 nhưng kết quả không đáng tin thì script trả rc=3 và in
`[false-green]`. Gồm: không chạy test nào; test/class được chỉ định không chạy; tên test đã chạy lệch
với nguồn (chạy test đã gỡ, hoặc class chạy mà thiếu test mới); file test sửa trước lệnh mà chưa được
biên dịch. Không bắt được: binary cũ khi tên test khớp, code app đổi mà build bỏ sót.

Trước mỗi lần chạy test, script gỡ app bundle id nội bộ khỏi sim (dữ liệu app trên sim đó mất). Đo ở app
gốc: cài đè thì 4/15 lần sim khởi động bản cũ từ containermanagerd/Dead/, gỡ trước thì 0/15.

Config test LUÔN là Debug (cờ INTERNAL, bundle id nội bộ) — không bao giờ Release/Store: bundle
id Store làm app host đụng StoreKit sandbox thật → hộp thoại đăng nhập treo suite. Hook
.claude/hooks/guard_test_config.py chặn thêm ở mức harness cho mọi lệnh xcodebuild gõ tay.

`--storekit`: LiveStoreClientTests bị scheme chính skip (`skippedTests` trong project.yml) — `-only-testing`
không vượt được skip đó, nên nó chạy qua scheme riêng `AppHost-StoreKitTests`, 1 simulator, host ký ad-hoc kèm
`tools/dev/storekit_test_host.entitlements` (`get-task-allow`). File `.xcscheme` chưa sinh (chưa chạy
`xcodegen generate`) ⇒ `FAIL:` rc 2 kèm thông báo, không chạy gì. `--storekit --no-build` chỉ đúng khi lần
build trước cũng là `--storekit` (binary của L1/L2 không ký nên StoreKit từ chối). Treo quá ~1 phút = hộp thoại
hệ thống trên sim — chụp sim (`xcrun simctl io <udid> screenshot <file>`) thay vì chờ.

Cấu hình (`app.config.toml`) nạp LƯỜI trong main(): `--help` chạy được cả khi cấu hình hỏng; cấu hình
hỏng ⇒ `FAIL: <thông báo>` rc 2, không traceback.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import appconfig  # noqa: E402


def _find_repo():
    """Gốc repo theo cwd (worktree đang làm việc); không ở trong repo git ⇒ FAIL rc 2, không traceback."""
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write("FAIL: không ở trong repo git — chạy từ trong working tree của app\n")
        raise SystemExit(2)
    return r.stdout.strip()


REPO = _find_repo()
PROJ_DIR = os.path.join(REPO, appconfig.PROJ_DIR)
SRC_ROOTS = appconfig.SRC_ROOTS
TEST_ROOTS = appconfig.TEST_ROOTS
TEST_TARGET = appconfig.TEST_TARGET
SCHEME = appconfig.SCHEME
CONFIG = "Debug"                       # KHÔNG đổi sang Release — xem docstring
STOREKIT_SCHEME = appconfig.STOREKIT_SCHEME
STOREKIT_CLASS = "LiveStoreClientTests"
STOREKIT_ENTITLEMENTS = os.path.join(REPO, "tools", "dev", "storekit_test_host.entitlements")
# Đổi những file này thì không suy ra được test nào bị ảnh hưởng → chạy hết.
ESCALATE = re.compile(r"\.(metal|cpp|c|h|hpp|mm|m|xcstrings|plist|xcconfig|entitlements|xcprivacy)$"
                      r"|(^|/)project\.yml$")
TYPE_DECL = re.compile(
    r"^\s*(?:@\w+\s+)*(?:(?:public|internal|private|fileprivate|final|open)\s+)*"
    r"(?:class|struct|enum|protocol|actor)\s+([A-Z]\w+)", re.M)
TEST_CLASS = re.compile(r"^\s*(?:final\s+)?class\s+(\w+)\s*:\s*XCTestCase", re.M)
TEST_OWNER_OR_METHOD = re.compile(
    r"^\s*(?:@\w+\s+)*(?:final\s+)?class\s+(?P<cls>\w+)\s*:\s*XCTestCase"
    r"|^extension\s+(?P<ext>\w+)"
    r"|^\s*(?:@\w+\s+)*func\s+(?P<method>test\w*)\s*\(\s*\)", re.M)
# Không neo đầu dòng: stdout của app có lúc ghi xen vào giữa dòng này.
TEST_RAN = re.compile(r"Test Case '-\[\w+\.(\w+) (\w+)\]' (?:started|passed|failed|skipped)")
# Chạy song song (clone simulator) xcodebuild in format khác và KHÔNG in dòng tổng `Executed N tests`:
#   Test case 'FooTests.testA()' passed on 'Clone 1 of <sim> - AppHost (91571)' (0.001 seconds)
TEST_RAN_PAR = re.compile(r"Test case '(\w+)\.(\w+)\(\)' (passed|failed|skipped) on '")
# Số worker mặc định cho --full (L2): 3 clone là điểm cân bằng đo được ở app gốc (suite vài nghìn test).
# L1 (vài class) mặc định 1: clone + boot tốn hơn phần lợi.
DEFAULT_PARALLEL_FULL = 3
# TSan build ra object khác hẳn build thường ⇒ DerivedData riêng, không làm bẩn/buộc build lại cache L1/L2. Tên phải
# nằm dưới một thư mục `DerivedData/` để `objects_dir` (cổng binary cũ) vẫn tìm được Objects-normal.
TSAN_DERIVED_DATA = os.path.join(REPO, ".temp", "DerivedData", "tsan")
# Mã thoát riêng khi xcodebuild báo thành công nhưng kết quả không đáng tin.
RC_FALSE_GREEN = 3


_CFG = None


class BaseRefError(Exception):
    """Không có nhánh mốc để so sánh phạm vi L1."""


def sh(*args, **kw):
    return subprocess.run(list(args), capture_output=True, text=True, **kw)


def config():
    """app.config.toml đã kiểm — nạp lười, một lần (ConfigError cho main() in FAIL)."""
    global _CFG
    if _CFG is None:
        _CFG = appconfig.load(Path(REPO))
    return _CFG


def host_bundle_id():
    """Bundle id của app host khi test (Debug ⇒ bundle id nội bộ)."""
    return appconfig.get(config(), "bundle.internal")


def resolve_base(base, repo=None):
    """Ref mốc thật sự dùng: `base` nếu có ở local, không thì `origin/<base>`; không có cả hai ⇒ BaseRefError."""
    repo = repo or REPO
    for ref in (base, f"origin/{base}"):
        if sh("git", "rev-parse", "--verify", "--quiet", ref + "^{commit}", cwd=repo).returncode == 0:
            return ref
    raise BaseRefError(f"không có nhánh mốc '{base}' (cả '{base}' lẫn 'origin/{base}') — truyền --base <nhánh có thật>, "
                       f"chỉ định class, hoặc --full")


def changed_files(base, repo=None):
    """File đổi so với merge-base(base, HEAD) + thay đổi chưa commit + file mới chưa track."""
    repo = repo or REPO
    ref = resolve_base(base, repo)
    r = sh("git", "merge-base", ref, "HEAD", cwd=repo)
    mb = r.stdout.strip()
    if r.returncode != 0 or not mb:
        raise BaseRefError(f"'{ref}' và HEAD không có tổ tiên chung — không suy ra được file đổi")
    files = set(sh("git", "diff", "--name-only", mb, cwd=repo).stdout.split())
    files |= set(sh("git", "diff", "--name-only", "HEAD", cwd=repo).stdout.split())
    files |= set(sh("git", "ls-files", "--others", "--exclude-standard", cwd=repo).stdout.split())
    return sorted(f for f in files if os.path.exists(os.path.join(repo, f)))


def test_files(disabled=((), ())):
    """{đường dẫn: nội dung} của mọi file test trong TEST_ROOTS (root vắng mặt thì bỏ qua).

    `disabled` = (thư mục nguồn, thư mục test) của khối tuỳ chọn đang TẮT (`appconfig.disabled_block_roots`): test
    của khối đó không có trong build nên không được tính là "nguồn có mà không chạy" (cổng binary cũ)."""
    out = {}
    skip = tuple(disabled[1])
    for tr in TEST_ROOTS:
        for dirpath, _, names in os.walk(os.path.join(REPO, tr)):
            for n in names:
                if n.endswith(".swift"):
                    p = os.path.join(dirpath, n)
                    rel = os.path.relpath(p, REPO)
                    if rel.startswith(skip):
                        continue
                    out[rel] = open(p, encoding="utf-8").read()
    return out


def select(files, tests, disabled=((), ())):
    """Trả (classes, escalate_reasons, untested_sources).

    `disabled`: xem `test_files`. File nằm trong khối tuỳ chọn đang tắt không vào build ⇒ không ảnh hưởng gì."""
    classes, escalate, untested = set(), [], []
    skip = tuple(disabled[0]) + tuple(disabled[1])
    for f in files:
        if f.startswith(skip):
            continue                                   # khối tuỳ chọn đang tắt: không được biên dịch, không có test
        if f == appconfig.CONFIG_FILE:
            escalate.append(f)                         # định danh/version/cờ tính năng: ảnh hưởng mọi thứ
            continue
        if f.startswith(TEST_ROOTS) and f.endswith(".swift"):
            classes |= set(TEST_CLASS.findall(tests.get(f, "")))
            continue
        if not f.startswith(tuple(r.split("/")[0] + "/" for r in SRC_ROOTS + TEST_ROOTS)):
            continue                                   # docs/, tools/, web/ … không ảnh hưởng app
        if ESCALATE.search(f):
            escalate.append(f)
            continue
        if not (f.startswith(SRC_ROOTS) and f.endswith(".swift")):
            continue
        base = os.path.splitext(os.path.basename(f))[0]
        types = set(TYPE_DECL.findall(open(os.path.join(REPO, f), encoding="utf-8").read()))
        pats = [re.compile(r"\b%s\b" % re.escape(t)) for t in types]
        hit = set()
        for tf, src in tests.items():
            tbase = os.path.basename(tf)
            if tbase.startswith(base) and tbase.endswith("Tests.swift") or any(p.search(src) for p in pats):
                hit |= set(TEST_CLASS.findall(src))
        if hit:
            classes |= hit
        else:
            untested.append(f)
    return classes, escalate, untested


def declared_tests(tests):
    """{class: {method}} đọc từ nguồn test, tính cả method trong `extension Class`.

    Mọi `#if` trong thư mục test (INTERNAL, DEBUG, simulator) đều bật ở Debug + Simulator, nên không
    cần loại method nằm trong khối điều kiện."""
    out = {}
    for src in tests.values():
        owner = None
        for m in TEST_OWNER_OR_METHOD.finditer(src):
            if m.group("cls") or m.group("ext"):
                owner = m.group("cls") or m.group("ext")
                if m.group("cls"):
                    out.setdefault(owner, set())
                continue
            if owner:
                out.setdefault(owner, set()).add(m.group("method"))
    return out


def executed_tests(text):
    """{(class, method)} đã chạy (cả format nối tiếp lẫn song song). Test skipped vẫn tính: nó có trong binary."""
    return set(TEST_RAN.findall(text)) | {(c, m) for c, m, _ in TEST_RAN_PAR.findall(text)}


def executed_total(text):
    """Tổng số test đã chạy: dòng `Executed N tests` cuối (nối tiếp), không có thì đếm dòng kết quả song song."""
    totals = re.findall(r"Executed (\d+) tests?,", text)
    if totals:
        return int(totals[-1])
    return len(TEST_RAN_PAR.findall(text))


def is_failure_line(line):
    return bool(re.search(r"error:|: XCTAssert|' failed \(|' failed on '", line))


def xcresult_results(data):
    """{(class, method): 'Passed'|'Failed'|'Skipped'|…} từ JSON `xcresulttool get test-results tests`."""
    out = {}

    def walk(n):
        if n.get("nodeType") == "Test Case":
            ident = n.get("nodeIdentifier") or ""
            cls, _, meth = ident.partition("/")
            meth = meth[:-2] if meth.endswith("()") else meth
            if cls and meth:
                out[(cls, meth)] = n.get("result", "")
        for c in n.get("children", []) or []:
            walk(c)

    for t in data.get("testNodes", []):
        walk(t)
    return out


def xcresult_failures(data):
    """{(class, method): [thông điệp lỗi]} của test Failed."""
    msgs = {}

    def walk(n):
        if n.get("nodeType") == "Test Case" and n.get("result") == "Failed":
            cls, _, meth = (n.get("nodeIdentifier") or "").partition("/")
            meth = meth[:-2] if meth.endswith("()") else meth
            msgs[(cls, meth)] = [c.get("name", "") for c in n.get("children", []) or []
                                 if c.get("nodeType") == "Failure Message"]
        for c in n.get("children", []) or []:
            walk(c)

    for t in data.get("testNodes", []):
        walk(t)
    return msgs


def read_xcresult(text):
    """JSON test-results của bundle .xcresult cuối cùng nhắc trong log; None nếu không đọc được."""
    paths = re.findall(r"(/\S+?\.xcresult)\b", text)
    if not paths:
        return None
    r = sh("xcrun", "xcresulttool", "get", "test-results", "tests", "--path", paths[-1])
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def rerun_verdict(failed, rerun_log):
    """Sau khi chạy lại NỐI TIẾP các test đỏ lúc song song: (vẫn_đỏ, chỉ_đỏ_khi_song_song).
    Test không thấy kết quả ở lượt chạy lại = vẫn đỏ (không được coi là xanh)."""
    passed = set()
    for line in rerun_log.splitlines():
        m = re.search(r"Test Case '-\[\w+\.(\w+) (\w+)\]' (passed|failed|skipped)", line)
        if m and m.group(3) in ("passed", "skipped"):
            passed.add((m.group(1), m.group(2)))
    still = [t for t in failed if t not in passed]
    flaky = [t for t in failed if t in passed]
    return still, flaky


def rerun_command(cmd, n_action, failed):
    """Lệnh chạy lại NỐI TIẾP đúng các test đỏ: test-without-building, bỏ cờ song song và -only-testing cũ."""
    rest, out, i = cmd[1 + n_action:], [], 0
    while i < len(rest):
        x = rest[i]
        if x in ("-parallel-testing-enabled", "-parallel-testing-worker-count"):
            i += 2
            continue
        if not x.startswith("-only-testing:"):
            out.append(x)
        i += 1
    return (["xcodebuild", "test-without-building"] + out + parallel_flags(1)
            + [f"-only-testing:{TEST_TARGET}/{c}/{m}" for c, m in failed])


def tsan_flags(enabled):
    """Cờ xcodebuild cho `--tsan`. Lưu ý: TSan đổi bố cục stack ⇒ đọc bộ nhớ lệch hàng (`load(as:)` trên buffer
    không căn) có thể làm host crash lúc khởi động dù build thường chạy được."""
    return ["-enableThreadSanitizer", "YES", "-derivedDataPath", TSAN_DERIVED_DATA] if enabled else []


def parallel_workers(requested, full):
    """Số worker: người gọi chỉ định thì theo, không thì L2 dùng DEFAULT_PARALLEL_FULL, L1 = 1."""
    if requested is not None:
        return max(1, requested)
    return DEFAULT_PARALLEL_FULL if full else 1


def parallel_flags(n):
    if n <= 1:
        return ["-parallel-testing-enabled", "NO"]
    return ["-parallel-testing-enabled", "YES", "-parallel-testing-worker-count", str(n)]


def false_green_problems(text, only, declared, manual, ran=None):
    """Lý do kết quả test không đáng tin dù xcodebuild có thể trả rc=0. Rỗng = không phát hiện gì.

    `only` là danh sách -only-testing (rỗng = cả suite). `manual` = người gọi tự chỉ định, khi đó
    class không có test nào cũng là lỗi; L1 tự chọn theo regex nên có thể vớ phải class nền.
    `ran`: tập test đã chạy lấy từ xcresult (chế độ song song) — khi có thì dùng thay cho log."""
    problems = []
    if (len(ran) if ran is not None else executed_total(text)) == 0:
        problems.append("xcodebuild không chạy test nào (Executed 0 tests hoặc không có dòng tổng kết).")
    ran = executed_tests(text) if ran is None else set(ran)
    ran_classes = {c for c, _ in ran}
    for t in only:
        cls, _, method = t.partition("/")
        if method:
            if (cls, method) not in ran:
                problems.append(f"test được chỉ định không chạy: {t}")
        elif cls not in ran_classes and (manual or declared.get(cls)):
            problems.append(f"class được chỉ định không chạy test nào: {t}")
    # So với nguồn: lệch tên nghĩa là binary vừa chạy không phải bản build từ nguồn hiện tại.
    for cls, method in sorted(ran):
        if method not in declared.get(cls, ()):
            problems.append(f"binary cũ: vừa chạy {cls}/{method} nhưng nguồn không còn test này.")
    whole = {t for t in only if "/" not in t}
    for cls in sorted(ran_classes):
        if only and cls not in whole:
            continue                                   # chỉ chạy vài method của class này
        for method in sorted(declared.get(cls, set()) - {m for c, m in ran if c == cls}):
            problems.append(f"binary cũ: nguồn có {cls}/{method} nhưng test này không chạy.")
    return problems


def skipped_compile_problems(sources, objects, started_at):
    """File test đã sửa TRƯỚC khi lệnh bắt đầu mà chưa được biên dịch: build đã bỏ sót nó.

    So với `<file>.d`, không so với binary: sửa comment thì Swift biên dịch lại và ghi lại .d nhưng
    giữ nguyên .o, nên binary không đổi mtime. File sửa sau `started_at` không tính; không có thư mục
    object thì không kết luận."""
    if not os.path.isdir(objects):
        return []
    problems = []
    for src in sources:
        name = os.path.basename(str(src))
        modified = os.path.getmtime(src)
        if modified > started_at:
            continue
        dep = os.path.join(objects, os.path.splitext(name)[0] + ".d")
        if not os.path.exists(dep):
            problems.append(f"{name} chưa từng được biên dịch: file chưa vào project? Chạy xcodegen generate.")
        elif os.path.getmtime(dep) < modified:
            problems.append(f"binary cũ: {name} đã sửa nhưng build không biên dịch lại.")
    return problems


def objects_dir(text, tsan=False):
    # test-without-building không có dòng Build/, chỉ có đường dẫn xcresult trong Logs/.
    # Build TSan đặt object ở `Objects-normal-tsan` (đo 2026-11-09) — sai thư mục thì cổng báo nhầm "chưa biên dịch".
    # Build TSan dùng -derivedDataPath cố định dưới REPO — đường dẫn đó có thể chứa dấu cách (regex bên dưới cắt ở
    # dấu cách), nên với tsan khớp thẳng chuỗi đã biết thay vì đoán lại từ log.
    if tsan:
        m = TSAN_DERIVED_DATA if TSAN_DERIVED_DATA + "/" in text else None
    else:
        m = re.search(r"(/[^\s\"']*/DerivedData/[^/\s]+)/(?:Build|Logs)/", text)
        m = m and m.group(1)
    return m and os.path.join(m, "Build", "Intermediates.noindex", SCHEME + ".build",
                              f"{CONFIG}-iphonesimulator", TEST_TARGET + ".build",
                              "Objects-normal-tsan" if tsan else "Objects-normal", "arm64")


def pick_sim(udid, shared=False):
    """Sim cho lượt chạy: --udid > sim RIÊNG của worktree (tools/dev/sim_pool.py, mặc định) > --shared-sim (cũ:
    iPhone đang boot). Sim riêng tránh hai phiên song song cài đè app của nhau."""
    if udid:
        return udid
    if not shared:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import sim_pool
        u = sim_pool.ensure(REPO)
        try:
            for act in sim_pool.gc(keep=sim_pool.sim_name(REPO)):
                print(f"[sim] {act}")
        except Exception as e:  # dọn dẹp lỗi không được làm hỏng lượt test
            print(f"[sim] bỏ qua dọn dẹp: {e}")
        print(f"[sim] {sim_pool.sim_name(REPO)} ({u})")
        return u
    devs = json.loads(sh("xcrun", "simctl", "list", "devices", "available", "-j").stdout)["devices"]
    allv = [d for rt, ds in devs.items() if "iOS" in rt for d in ds]
    for d in allv:
        if d["state"] == "Booted" and "iPhone" in d["name"]:
            return d["udid"]
    # Ưu tiên iPhone 16 Pro (máy quen của suite), không có thì iPhone bất kỳ còn available — sau khi
    # Xcode đổi bộ sim (2026-10-17 chỉ còn iPhone 17/Air) script từng chết vì tên cứng.
    preferred = [d for d in allv if d["name"].startswith("iPhone 16 Pro")]
    fallback = [d for d in allv if d["name"].startswith("iPhone") and "Listing" not in d["name"]]
    for d in preferred + fallback:
        sh("xcrun", "simctl", "boot", d["udid"])
        sh("xcrun", "simctl", "bootstatus", d["udid"])
        return d["udid"]
    sys.exit("Không tìm thấy simulator iPhone — truyền --udid")


def storekit_scheme_exists():
    return os.path.isfile(os.path.join(REPO, appconfig.PROJECT, "xcshareddata", "xcschemes",
                                       STOREKIT_SCHEME + ".xcscheme"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*", help="Class hoặc Class/testMethod")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--base", default="develop")
    ap.add_argument("--no-build", action="store_true", help="test-without-building")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--udid")
    ap.add_argument("--shared-sim", action="store_true",
                    help="dùng iPhone đang boot như trước (mặc định: sim riêng của worktree, tools/dev/sim_pool.py)")
    ap.add_argument("--parallel", type=int, metavar="N",
                    help=f"số clone simulator chạy song song (mặc định: --full {DEFAULT_PARALLEL_FULL}, còn lại 1)")
    ap.add_argument("--storekit", action="store_true",
                    help=f"chạy {STOREKIT_CLASS} qua scheme {STOREKIT_SCHEME} (scheme chính skip class này; "
                         f"host ký ad-hoc kèm get-task-allow)")
    ap.add_argument("--tsan", action="store_true",
                    help="bật Thread Sanitizer (build riêng ở .temp/DerivedData/tsan, chậm hơn nhiều — chỉ định class)")
    a = ap.parse_args()

    # Nạp cấu hình SAU argparse (--help không cần cấu hình), trước mọi việc khác.
    try:
        stale = appconfig.stale_generated(Path(REPO), config())
        if stale:
            print(f"FAIL: {', '.join(stale)} cũ — chạy python3 tools/common/appconfig.py render", file=sys.stderr)
            return 2
    except appconfig.ConfigError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    if a.storekit and not storekit_scheme_exists():
        print(f"FAIL: chưa có file scheme {STOREKIT_SCHEME}.xcscheme — --storekit không có gì để chạy. Scheme khai "
              f"trong project.yml: chạy xcodegen generate trong {appconfig.PROJ_DIR}/ rồi thử lại.",
              file=sys.stderr)
        return 2

    only, mode = [], ""
    scheme = SCHEME
    if a.storekit:
        scheme, only, mode = STOREKIT_SCHEME, [STOREKIT_CLASS], "StoreKit (--storekit)"
    elif a.full:
        mode = "FULL (--full)"
    elif a.targets:
        only, mode = a.targets, "chỉ định tay"
    else:
        try:
            files = changed_files(a.base)
        except BaseRefError as e:
            print(f"FAIL: {e}", file=sys.stderr)
            return 2
        disabled = appconfig.disabled_block_roots(config())
        classes, escalate, untested = select(files, test_files(disabled), disabled)
        print(f"[scope] {len(files)} file đổi so với {a.base} (merge-base) + worktree")
        for u in untested:
            print(f"[scope] không test nào nhắc tới: {u} → chỉ được compile-check")
        if escalate:
            mode = "FULL (leo thang: " + ", ".join(escalate[:4]) + (" …" if len(escalate) > 4 else "") + ")"
        elif classes:
            only, mode = sorted(classes), f"L1 · {len(classes)} class"
        elif untested:
            mode = "BUILD-ONLY"
        else:
            print("[scope] không có thay đổi nào ảnh hưởng app — không chạy gì.")
            return 0
    print(f"[scope] chế độ: {mode}")
    if scheme == SCHEME and any(t.split("/")[0] == STOREKIT_CLASS for t in only):
        only = [t for t in only if t.split("/")[0] != STOREKIT_CLASS]
        print(f"[scope] {STOREKIT_CLASS} bị skip mặc định (StoreKit có thể bật hộp thoại đăng nhập) "
              f"— đụng code StoreKit thì chạy thêm: tools/dev/run_tests.py --storekit")
        if not only:
            print("[scope] không còn class nào để chạy.")
            return 0
    if only:
        print("[scope] " + " ".join(only))
    if a.list:
        return 0

    udid = pick_sim(a.udid, a.shared_sim)
    action = ["build"] if mode == "BUILD-ONLY" else (["test-without-building"] if a.no_build else ["test"])
    # StoreKit chạy đúng 1 class trên sim đã ký riêng — không clone.
    workers = 1 if a.storekit else parallel_workers(a.parallel, full=mode.startswith("FULL"))
    cmd = ["xcodebuild", *action, "-project", os.path.basename(appconfig.PROJECT),
           "-scheme", scheme, "-destination", f"id={udid}",
           "-configuration", CONFIG]
    cmd += tsan_flags(a.tsan)
    # storekitd chỉ nhận cấu hình của SKTestSession từ app có `get-task-allow` ("not installed for
    # development"); bị từ chối thì Product.products rơi sang sandbox thật và trả rỗng. Build không
    # ký không có entitlement nào, nên riêng --storekit ký ad-hoc kèm entitlement này.
    cmd += (["CODE_SIGN_IDENTITY=-", "CODE_SIGN_STYLE=Manual",
             f"CODE_SIGN_ENTITLEMENTS={STOREKIT_ENTITLEMENTS}"] if a.storekit
            else ["CODE_SIGNING_ALLOWED=NO"])
    # Mặc định xcodebuild chạy `simctl diagnose` (sysdiagnose) khi test có sự cố — đo được treo
    # >10 phút SAU khi test đã xong (2026-09-27). Log test đã đủ để chẩn đoán; không chờ thêm.
    if action != ["build"]:
        cmd += ["-collect-test-diagnostics", "never"]
        # Song song: xcodebuild tự clone sim đích thành N bản, chia class, rồi tự xoá clone khi xong.
        cmd += parallel_flags(workers)
        if workers > 1:
            print(f"[run] song song {workers} clone simulator")
    cmd += [f"-only-testing:{TEST_TARGET}/{t}" for t in only]

    # Cài đè lên bản cũ thì thỉnh thoảng sim khởi động app từ container vừa bị thay
    # (Library/Caches/com.apple.containermanagerd/Dead/…): test chạy binary của lần trước dù build đúng.
    if action != ["build"]:
        sh("xcrun", "simctl", "uninstall", udid, host_bundle_id())

    logdir = os.path.join(REPO, ".temp", "test-logs")
    os.makedirs(logdir, exist_ok=True)
    log = os.path.join(logdir, dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".log")
    t0 = time.time()
    with open(log, "w") as fh:
        rc = subprocess.run(cmd, cwd=PROJ_DIR, stdout=fh, stderr=subprocess.STDOUT).returncode
    text = open(log, encoding="utf-8", errors="replace").read()
    seen = set()
    for line in text.splitlines():
        if is_failure_line(line) and line not in seen:
            seen.add(line)
            print(line.strip())
    # xcodebuild in "Executed …" cho TỪNG suite; dòng cuối cùng là tổng của cả lần chạy.
    executed = re.findall(r"Executed \d+ tests?,.*", text)
    if executed:
        print(executed[-1].strip())
    elif TEST_RAN_PAR.search(text):
        verdicts = [v for _, _, v in TEST_RAN_PAR.findall(text)]
        print(f"Executed {len(verdicts)} tests (song song), {verdicts.count('skipped')} skipped, "
              f"{verdicts.count('failed')} failures")
    problems = []
    ran = None
    if action != ["build"] and workers > 1:
        # Song song: log bị stdout app chen mất đầu dòng ⇒ đọc kết quả từ xcresult (nguồn chuẩn).
        data = read_xcresult(text)
        if data is None:
            print("[run] không đọc được xcresult — dùng log (có thể báo xanh giả oan ở chế độ song song)")
        else:
            res = xcresult_results(data)
            ran = set(res)
            fails = xcresult_failures(data)
            print(f"[run] xcresult: {len(res)} test, {sum(v == 'Skipped' for v in res.values())} skipped, "
                  f"{len(fails)} failed")
            if fails:
                for (c, m), msgs in list(fails.items())[:20]:
                    print(f"  ✗ {c}/{m}: {(msgs or ['?'])[0][:200]}")
                # Chạy lại NỐI TIẾP trên sim gốc: một clone hỏng (app chạy từ container Dead, mất tài nguyên —
                # gặp 2026-11-06) làm đỏ hàng loạt test vô can; lỗi thật thì vẫn đỏ ở lượt này.
                failed = sorted(fails)
                print(f"[rerun] chạy lại nối tiếp {len(failed)} test đỏ trên sim gốc…")
                cmd2 = rerun_command(cmd, len(action), failed)
                sh("xcrun", "simctl", "uninstall", udid, host_bundle_id())
                log2 = log.replace(".log", "-rerun.log")
                with open(log2, "w") as fh:
                    subprocess.run(cmd2, cwd=PROJ_DIR, stdout=fh, stderr=subprocess.STDOUT)
                still, flaky = rerun_verdict(failed, open(log2, encoding="utf-8", errors="replace").read())
                if flaky:
                    print(f"[flaky-song-song] {len(flaky)} test chỉ đỏ khi chạy song song, nối tiếp thì xanh "
                          f"(log: {os.path.relpath(log2, REPO)}): " + ", ".join(f"{c}/{m}" for c, m in flaky[:8])
                          + (" …" if len(flaky) > 8 else ""))
                for c, m in still:
                    print(f"[rerun] VẪN ĐỎ khi chạy nối tiếp: {c}/{m}")
                if not still and rc == 65:
                    rc = 0  # mọi test đỏ đều chỉ đỏ khi song song
                elif still and rc == 0:
                    rc = 65
    if action != ["build"]:
        tests = test_files(appconfig.disabled_block_roots(config()))
        problems = false_green_problems(text, only, declared_tests(tests), bool(a.targets), ran=ran)
        objects = objects_dir(text, tsan=a.tsan)
        if objects:
            problems += skipped_compile_problems([os.path.join(REPO, f) for f in tests], objects, t0)
    for p in problems:
        print(f"[false-green] {p}")
    if problems:
        print("[false-green] Kết quả này KHÔNG được tính là xanh. Kiểm tên test; nếu nguồn đúng thì "
              "gỡ app khỏi sim (simctl uninstall) hoặc chạy xcodebuild với -derivedDataPath build.")
    status = "SUCCEEDED" if rc == 0 and not problems else "FAILED"
    rc = rc or (RC_FALSE_GREEN if problems else 0)
    print(f"[run] {' '.join(action)} {status} rc={rc} · {time.time() - t0:.0f}s · log: {os.path.relpath(log, REPO)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
