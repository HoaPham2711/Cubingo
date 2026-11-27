#!/usr/bin/env python3
"""Lint tĩnh cho String Catalog — chạy trên source, KHÔNG cần build (dùng được ở pre-commit).

Bắt 3 lớp lỗi mà `verify_catalog.py` (build-based) KHÔNG thấy được, vì chúng là *sự vắng mặt*:
chuỗi không được extract thì không để lại dấu vết nào trong `.stringsdata`.

  R1  Literal localize-được nằm trong vùng INTERNAL (file dưới thư mục `Internal/`, hoặc trong block
      `#if INTERNAL`). Phải dùng `dtext(...)` — xem `Core/Internal/InternalEntry.swift`.
  R2  Literal localize-được nằm trong nhánh `#else` của `#if INTERNAL`: build `Internal` sẽ
      KHÔNG extract nó → key sản phẩm biến mất khỏi catalog tuỳ config build.
  R3  Literal TRÔNG như localize nhưng không được extract vì nó là toán hạng của một biểu
      thức: `Text("Details".uppercased())`, `Text("a" + b)`. Kiểu suy ra `String` chứ không
      còn `LocalizedStringKey` → Xcode bỏ qua, chuỗi rơi khỏi hệ localize trong im lặng.
      (Bug thật, đã xảy ra ở app gốc.)
  R5  Literal localize-được trong khối `#Preview`. Xcode VẪN extract `#Preview` (đã đo), nên
      chuỗi mẫu của preview thành key thật, bắt mọi ngôn ngữ phải dịch nó. Dùng
      `Text(verbatim:)`.
  R4  Chuỗi tiếng Việt tại vị trí localize-được của bản SẢN PHẨM — tức chuỗi SẼ vào String
      Catalog (UI phải tiếng Anh). Vùng INTERNAL được miễn: chuỗi debug tiếng Việt là chủ đích
      và sau lớp 1 thì không vào catalog nữa.

Quét TOÀN BỘ `*.swift` dưới app root (không theo danh sách thư mục liệt kê tay — thư mục mới thêm
không được quét mà không ai biết).

Cố ý KHÔNG gác chuỗi tiếng Việt nằm ngoài vị trí localize-được (log, `precondition`, marker
parse). Đã thử ở app gốc: luật đó cho toàn dương-tính-giả (chuỗi nội bộ hợp lệ) — một cổng 100%
dương-tính-giả sẽ bị tắt đi rồi mục ruỗng. Chuỗi Việt đi qua biến `String` rồi mới tới chỗ hiển thị
thì lint tĩnh này không thấy — soát bằng mắt khi review.

    python3 tools/i18n/lint_localizable.py [file_hoặc_thư_mục ...]

Gốc thư mục nguồn lấy từ `appconfig.SRC_ROOTS` (một nguồn với mọi tool khác). Không thư mục nguồn nào
tồn tại ⇒ `FAIL:` rc 2 (không được báo OK khi không quét gì).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import appconfig  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
# Mọi thư mục nguồn của app (SRC_ROOTS) — rglob từng cái; không hardcode đường dẫn app.
APP_ROOTS: list[Path] = [REPO / r for r in appconfig.SRC_ROOTS]


def rel_to_roots(path: Path) -> Path:
    """Đường dẫn tương đối so với thư mục nguồn chứa `path`; ValueError nếu nằm ngoài mọi root."""
    for root in APP_ROOTS:
        try:
            return path.relative_to(root)
        except ValueError:
            continue
    raise ValueError(f"{path} nằm ngoài mọi thư mục nguồn")

# Thư mục chỉ chứa code của build INTERNAL — cả file là vùng debug, không cần dò `#if`. Template đặt code debug
# ở `Core/Internal/` (verify_catalog.py dùng cùng định nghĩa).
INTERNAL_ONLY_DIRS = {"Internal"}

# API nhận `LocalizedStringKey` (hoặc `Text`) ở vị trí đầu → literal ở đó SẼ được extract.
LOCALIZABLE_CALL = r"(?:Text|Button|Label|Toggle|Picker|Section|Stepper|Link|TextField|SecureField|NavigationLink|ProgressView|Menu|Alert)"
LOCALIZABLE_MODIFIER = r"(?:navigationTitle|help|confirmationDialog|alert|accessibilityLabel|accessibilityHint)"
LOCALIZABLE_POS = re.compile(
    rf'(?:\b{LOCALIZABLE_CALL}\(|\.{LOCALIZABLE_MODIFIER}\(|String\(localized:)\s*"'
)
# Literal ở vị trí localize-được nhưng bị nối/gọi method → kiểu thành `String`, KHÔNG extract.
OPERAND_AFTER = re.compile(r'\s*(?:\.\s*\w+\s*\(|\+)')
# `String(localized: someVariable)` — không phải literal thì không extract được.
R_LOCALIZED_NONLITERAL = re.compile(r'String\(localized:\s*(?!")([A-Za-z_][\w.]*)')
VN_CHARS = (
    "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
    "ùúủũụưừứửữựỳýỷỹỵđ"
    "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ"
    "ÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"
)
VN_RE = re.compile(f"[{VN_CHARS}]")


def internal_regions(lines: list[str]) -> tuple[set[int], set[int]]:
    """(dòng trong nhánh `#if INTERNAL`, dòng trong nhánh `#else` tương ứng) — 0-based.

    Đếm độ sâu để `#if` lồng bên trong không làm mất dấu `#endif` của khối ngoài.
    """
    in_if: set[int] = set()
    in_else: set[int] = set()
    stack: list[str] = []  # "if" | "else" | "other"
    for idx, line in enumerate(lines):
        s = line.strip()
        if s.startswith("#if"):
            stack.append("if" if re.match(r"#if\s+INTERNAL\b", s) else "other")
            continue
        if s.startswith("#elseif") and stack:
            continue
        if s.startswith("#else") and stack:
            if stack[-1] == "if":
                stack[-1] = "else"
            continue
        if s.startswith("#endif"):
            if stack:
                stack.pop()
            continue
        if "if" in stack:
            in_if.add(idx)
        elif "else" in stack and "other" not in stack:
            in_else.add(idx)
    return in_if, in_else


def strip_trailing_comment(line: str) -> str:
    """Cắt `// ...` cuối dòng, KHÔNG cắt nếu `//` nằm trong string literal."""
    in_string = escape = False
    for i, c in enumerate(line):
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c == "/" and line[i + 1: i + 2] == "/":
            return line[:i]
    return line


def preview_lines(lines: list[str]) -> set[int]:
    """Dòng thuộc block `#Preview { ... }`.

    KHÔNG được bỏ qua khi lint: Xcode extract cả `#Preview`, nên literal ở đây thành key thật
    trong catalog (đã đo: `"nội dung sheet"` của BottomSheetChrome lọt vào). Vùng này có luật
    riêng — xem R5.
    """
    out: set[int] = set()
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("#Preview"):
            depth, opened, j = 0, False, i
            while j < len(lines):
                depth += lines[j].count("{") - lines[j].count("}")
                opened = opened or "{" in lines[j]
                if opened and depth <= 0:
                    break
                j += 1
            out.update(range(i, j + 1))
            i = j + 1
        else:
            i += 1
    return out


def is_internal_only(path: Path) -> bool:
    rel = rel_to_roots(path)
    return bool(INTERNAL_ONLY_DIRS & set(rel.parts[:-1]))


def scan_string(line: str, i: int) -> int:
    """Trả về index NGAY SAU literal bắt đầu tại `i` (line[i] == '"')."""
    j, escape = i + 1, False
    while j < len(line):
        c = line[j]
        if escape:
            escape = False
        elif c == "\\":
            escape = True
        elif c == '"':
            return j + 1
        j += 1
    return j


def logical_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Gộp các dòng vật lý thành CÂU LỆNH logic → [(dòng bắt đầu 0-based, text đã gộp)].

    Cần thiết vì literal hay bị xuống dòng: `Text("a"\n + "b")` không được extract (kiểu
    thành `String`), còn `logReject("x",\n "chuỗi việt")` là log chứ không phải UI. Khớp regex
    trên từng dòng riêng lẻ đọc sai cả hai — đã đo: 10 dương-tính-giả R1 + 60 R4.

    Kết thúc câu lệnh khi độ sâu ngoặc về 0 VÀ dòng không kết thúc bằng toán tử nối.
    """
    out: list[tuple[int, str]] = []
    buf: list[str] = []
    start = 0
    depth = 0
    for idx, raw in enumerate(lines):
        code = strip_trailing_comment(raw)
        if not buf:
            start = idx
        buf.append(code.strip())
        i = 0
        while i < len(code):
            c = code[i]
            if c == '"':
                i = scan_string(code, i)
                continue
            if c in "([":
                depth += 1
            elif c in ")]":
                depth = max(0, depth - 1)
            i += 1
        if depth == 0 and not re.search(r"(?:\+|,|\|\||&&|\?|:)$", buf[-1]):
            out.append((start, " ".join(buf)))
            buf = []
    if buf:
        out.append((start, " ".join(buf)))
    return out


def localizable_literals(text: str) -> list[tuple[str, bool]]:
    """[(literal, có_được_extract_không)] tại mọi vị trí localize-được trong câu lệnh."""
    found: list[tuple[str, bool]] = []
    for m in LOCALIZABLE_POS.finditer(text):
        q = m.end() - 1                      # index của dấu " mở
        end = scan_string(text, q)
        literal = text[q + 1:end - 1]
        extracted = OPERAND_AFTER.match(text, end) is None
        found.append((literal, extracted))
    return found


def lint_file(path: Path) -> list[tuple[int, str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    whole_file_internal = is_internal_only(path)
    in_if, in_else = internal_regions(lines)
    preview = preview_lines(lines)

    out: list[tuple[int, str, str]] = []
    for idx, text in logical_lines(lines):
        if lines[idx].strip().startswith("//"):
            continue
        internal = whole_file_internal or idx in in_if
        n = idx + 1

        for literal, extracted in localizable_literals(text):
            if extracted and idx in preview:
                out.append((n, "R5", "literal trong #Preview vào thẳng String Catalog "
                                     "(Xcode extract cả #Preview) — dùng Text(verbatim:)"))
            elif extracted and internal:
                out.append((n, "R1", "literal localize-được trong vùng INTERNAL — dùng dtext(...)"))
            elif extracted and idx in in_else:
                out.append((n, "R2", "chuỗi sản phẩm trong nhánh #else của #if INTERNAL — "
                                     "build Internal sẽ không extract, đưa ra ngoài #if"))
            elif not extracted and not internal:
                out.append((n, "R3", "literal ở vị trí localize-được nhưng là toán hạng "
                                     "(.method()/+) nên thành String, KHÔNG được extract — "
                                     "bọc String(localized:) quanh literal trước"))
            if extracted and not internal and idx not in preview and VN_RE.search(literal):
                out.append((n, "R4", "chuỗi tiếng Việt sẽ vào String Catalog — UI phải tiếng Anh"))

        m = R_LOCALIZED_NONLITERAL.search(text)
        if m:
            out.append((n, "R3", f"String(localized:) nhận biến `{m.group(1)}` chứ không phải "
                                 f"literal — Xcode không extract được"))

    return out


def resolve(args: list[str]) -> list[Path]:
    if not args:
        return sorted(f for root in APP_ROOTS if root.is_dir() for f in root.rglob("*.swift"))
    files: list[Path] = []
    for a in args:
        p = Path(a)
        if not p.is_absolute():
            under_root = next((r / a for r in APP_ROOTS if (r / a).exists()), None)
            p = under_root if under_root is not None else Path.cwd() / a
        if p.is_dir():
            files.extend(sorted(p.rglob("*.swift")))
        elif p.is_file():
            files.append(p)
        else:
            print(f"CẢNH BÁO: không thấy {a}", file=sys.stderr)
    return files


# Fixture cho `--self-test`. Mỗi mục: (tên, nguồn Swift, tập rule PHẢI kêu).
# Lý do tồn tại: một cổng "xanh" chưa chắc gác được gì — phải phá cho nó đỏ mới tin.
# Xem docs/lessons-learned/ (bài "Test xanh ≠ test có gác").
SELF_TEST_CASES: list[tuple[str, str, set[str]]] = [
    ("R1 literal trong #if INTERNAL",
     '#if INTERNAL\nText("Pipeline A/B")\n#endif\n', {"R1"}),
    ("R1 literal trong file Internal/ (đường dẫn quyết định)",
     'Text("Settings (dev)")\n', {"R1"}),          # chạy với path giả trong Internal/
    ("R2 chuỗi sản phẩm trong nhánh #else",
     '#if INTERNAL\ndtext("Details & log")\n#else\nText("Details")\n#endif\n', {"R2"}),
    ("R3 literal là toán hạng .method()",
     'Text("Details".uppercased())\n', {"R3"}),
    ("R3 literal nối chuỗi cùng dòng",
     'Text("a" + suffix)\n', {"R3"}),
    ("R3 literal nối chuỗi XUỐNG DÒNG",
     'Text("phần một "\n     + "phần hai")\n', {"R3"}),
    ("R3 String(localized:) nhận biến",
     'let t = String(localized: someKey)\n', {"R3"}),
    ("R4 tiếng Việt sẽ vào catalog",
     'Text("Đặt lại mặc định")\n', {"R4"}),
    # --- các trường hợp PHẢI IM LẶNG ---
    ("sạch: chuỗi sản phẩm tiếng Anh", 'Text("Delete item")\n', set()),
    ("sạch: dtext trong #if INTERNAL",
     '#if INTERNAL\ndtext("Gói Pro")\n#endif\n', set()),
    ("sạch: log tiếng Việt ngoài vị trí localize",
     'log("[sync] danh sách rỗng — bỏ qua")\n', set()),
    ("sạch: nội suy nhiều đối số",
     'Text("raw \\(a) · model \\(b)")\n', set()),
    ("R5 literal trong #Preview",
     '#Preview {\n    Text("nội dung sheet")\n}\n', {"R5"}),
    ("sạch: Text(verbatim:) trong #Preview",
     '#Preview {\n    Text(verbatim: "nội dung sheet")\n}\n', set()),
    ("sạch: #if khác INTERNAL không tính là vùng debug",
     '#if targetEnvironment(simulator)\nText("Seed sample")\n#endif\n', set()),
]


def missing_roots_error(roots: list[Path]) -> str | None:
    """Thông báo lỗi khi KHÔNG thư mục nguồn nào tồn tại (quét 0 file mà báo OK = cổng qua trống)."""
    if any(r.is_dir() for r in roots):
        return None
    return ("không thư mục nguồn nào trong appconfig.SRC_ROOTS tồn tại: "
            + ", ".join(str(r) for r in roots) + " — không có gì để quét")


def self_test() -> int:
    """Chạy từng fixture, xác nhận rule kêu ĐÚNG tập mong đợi (thiếu lẫn thừa đều FAIL)."""
    import tempfile

    failed = 0
    with tempfile.TemporaryDirectory() as td:
        ok_missing = missing_roots_error([Path(td) / "khong-co"]) is not None
        ok_present = missing_roots_error([Path(td) / "khong-co", Path(td)]) is None
    if ok_missing and ok_present:
        print("  ok    thiếu mọi thư mục nguồn ⇒ lỗi; còn một thư mục ⇒ không lỗi")
    else:
        print(f"  FAIL  kiểm thư mục nguồn: thiếu-hết⇒lỗi={ok_missing}, còn-một⇒không-lỗi={ok_present}")
        failed += 1
    for name, src, want in SELF_TEST_CASES:
        sub = "Internal" if "file Internal/" in name else "Features"
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / sub
            d.mkdir(parents=True)
            f = d / "Fixture.swift"
            f.write_text(src, encoding="utf-8")
            global APP_ROOTS
            saved, APP_ROOTS = APP_ROOTS, [Path(td)]
            try:
                got = {r for _, r, _ in lint_file(f)}
            finally:
                APP_ROOTS = saved
        if got == want:
            print(f"  ok    {name}  -> {sorted(got) or '(im lặng)'}")
        else:
            print(f"  FAIL  {name}: mong {sorted(want)}, nhận {sorted(got)}")
            failed += 1
    print(f"\n{len(SELF_TEST_CASES) + 1 - failed}/{len(SELF_TEST_CASES) + 1} fixture đạt.")
    return 1 if failed else 0


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--self-test":
        return self_test()
    err = missing_roots_error(APP_ROOTS)
    if err:
        print(f"FAIL: {err}", file=sys.stderr)
        return 2

    total = 0
    outside = 0
    for f in resolve(args):
        try:
            rel = rel_to_roots(f)
        except ValueError:
            # Không im lặng bỏ qua: file ngoài app root là dấu hiệu gọi sai đường dẫn.
            print(f"BỎ QUA (ngoài app root): {f}", file=sys.stderr)
            outside += 1
            continue
        # In đường dẫn so với gốc repo: có nhiều root (AppHost/AppHost/, Core/) nên đường dẫn so với root mơ hồ.
        try:
            shown = f.resolve().relative_to(REPO)
        except ValueError:
            shown = rel
        for line_no, rule, msg in lint_file(f):
            print(f"{shown}:{line_no}: [{rule}] {msg}")
            total += 1
    if total:
        print(f"\n{total} vi phạm. Xem docstring đầu file này (R1–R5).",
              file=sys.stderr)
        return 1
    print(f"OK — không có vi phạm String Catalog trong source."
          + (f" ({outside} file ngoài app root bị bỏ qua)" if outside else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
