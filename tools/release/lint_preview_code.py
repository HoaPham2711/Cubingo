#!/usr/bin/env python3
"""Lint: kiểu seed/store giả của route preview chỉ biên dịch cho Simulator.

    python3 tools/release/lint_preview_code.py            # gốc repo suy từ vị trí script
    python3 tools/release/lint_preview_code.py --root DIR # gốc khác (test)

Vì sao: route `-uiPreview` (chụp ảnh trên Simulator) dựng dữ liệu mẫu và store giả. Cổng ở lõi
(`UIPreviewLaunch.rawRoute` luôn `nil` trên device) chặn KÍCH HOẠT, nhưng mã seed vẫn nằm trong binary device nếu
không bọc `#if targetEnvironment(simulator)` — dữ liệu mẫu lọt vào bản App Store. Quy ước đặt tên làm cho việc này
kiểm được tĩnh: mọi kiểu seed/store giả có tên kết thúc bằng `PreviewSeed` hoặc `PreviewStore`.

Luật: mọi khai báo `struct|class|enum|actor <Tên>` với `<Tên>` kết thúc bằng `PreviewSeed`/`PreviewStore`, dưới các
gốc nguồn của app/Core (`appconfig.SRC_ROOTS` + `CoreOptional/` nếu có; không quét thư mục test), phải nằm trong
vùng chỉ-Simulator:
  * nhánh chính của `#if targetEnvironment(simulator)` (cho phép bọc ngoặc, khoảng trắng), hoặc của một `&&` ở mức
    ngoài cùng có MỘT toán hạng như vậy (`DEBUG && targetEnvironment(simulator)`), hoặc `||` mà MỌI toán hạng như
    vậy; các `#if` khác lồng bên trong vùng đó vẫn tính;
  * KHÔNG tính: nhánh `#else`/`#elseif` (kể cả `#else` của `#if !targetEnvironment(simulator)` — viết điều kiện
    dương cho rõ), `#if DEBUG` một mình, `targetEnvironment(simulator) || X`.
Không có ngoại lệ cho `#Preview` của Xcode: canvas build cho Simulator, nên store giả của `#Preview` bọc
`#if DEBUG && targetEnvironment(simulator)` vẫn chạy trong canvas.

Bộ xoá comment/chuỗi và bộ đi ngăn xếp `#if` dùng CHUNG với `lint_debug_symbols.py` (`blank_comments_and_strings`,
`region_lines`, `is_only`) — cùng giới hạn đã nói ở docstring của file đó.

Exit code: 0 sạch (`OK`); 1 vi phạm — mỗi dòng `đường/dẫn:dòng: <Tên> …` rồi `FAIL: …`; 2 sai cách dùng / gốc không
tồn tại / không đọc được file. Không bao giờ in traceback.
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lint_debug_symbols as scanner  # noqa: E402

ROOT = scanner.ROOT
DECL_RE = re.compile(r"(?<![.\w])(struct|class|enum|actor)\s+([A-Za-z_]\w*(?:PreviewSeed|PreviewStore))\b")
SIM_ATOM = "targetEnvironment(simulator)"


def is_simulator_only(cond: str) -> bool:
    return scanner.is_only(cond, lambda c: c.replace(" ", "") == SIM_ATOM)


def scan_source(rel: str, text: str) -> list[str]:
    """Một file ⇒ danh sách vi phạm `rel:dòng: <Tên> …`."""
    code_lines = scanner.blank_comments_and_strings(text).split("\n")
    inside, directives = scanner.region_lines(code_lines, is_simulator_only)
    problems = []
    for no, line in enumerate(code_lines, start=1):
        if no in directives:
            continue
        for kind, name in DECL_RE.findall(line):
            if not inside[no]:
                problems.append(f"{rel}:{no}: {name} ({kind} seed/store giả của preview) nằm ngoài "
                                f"`#if {SIM_ATOM}` — bọc nó (nhánh #else/#elseif không tính) để mã preview không "
                                f"vào binary device")
    return problems


def lint(root: Path) -> list[str]:
    problems: list[str] = []
    for f in scanner.swift_files(root):
        rel = f.relative_to(root).as_posix()
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise scanner.UsageError(f"không đọc được {rel}: {e}")
        problems.extend(scan_source(rel, text))
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Kiểu *PreviewSeed/*PreviewStore phải nằm trong "
                                             "#if targetEnvironment(simulator) (xem docstring).")
    ap.add_argument("--root", default=str(ROOT), help="gốc repo (mặc định suy từ vị trí script)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    root = Path(args.root)
    try:
        if not root.is_dir():
            raise scanner.UsageError(f"gốc {root} không tồn tại")
        problems = lint(root)
    except scanner.UsageError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        print(f"FAIL: lint_preview_code — {len(problems)} kiểu preview biên dịch ngoài Simulator", file=sys.stderr)
        return 1
    print("OK: mọi kiểu *PreviewSeed/*PreviewStore nằm trong #if targetEnvironment(simulator)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
