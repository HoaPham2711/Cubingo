#!/usr/bin/env python3
"""Lint: các danh sách tên debug luôn khớp nguồn — hai chiều, hai loại tên.

Hai file, đọc HỢP: `tools/release/debug_symbols.txt` (tên của lõi — template sở hữu) và
`AppHost/Config/debug_symbols.app.txt` (tên của app — app sở hữu, cùng định dạng; vắng file = rỗng). Một tên có ở cả
hai file ⇒ lỗi nêu cả hai file.

    python3 tools/release/lint_debug_symbols.py            # gốc repo suy từ vị trí script
    python3 tools/release/lint_debug_symbols.py --root DIR # gốc khác (test)

Vì sao: `verify_release_clean.sh` grep binary Release tìm từng tên ở mục `[binary]` của `debug_symbols.txt`. Cổng
chỉ gác được cái nó biết tên — thêm một type debug (bọc `#if INTERNAL`) mà quên ghi tên vào file thì không cổng nào
bắn; ngược lại, ghi tên mà code đó thật ra biên dịch cả ở Release (hoặc đã bị xoá/đổi tên) thì cổng đỏ vô cớ ở mọi
bản Release, hoặc im lặng không gác gì. Lint này quét NGUỒN (tĩnh, <1 s) nên bắt sớm ở pre-commit/selfcheck.

Hai loại tên (ruling R18 — xem đầu `debug_symbols.txt`):
  * `[binary]`: tên TYPE — metadata reflection giữ tên type trong binary nên grep binary có nghĩa (selfcheck còn
    đối chứng dương: mọi tên ở đây phải thấy trong `.app` Internal).
  * `[source-only]`: tên HÀM/BIẾN ghim bằng marker — tên hàm bị strip khỏi binary (cả Internal), grep binary không
    chứng minh gì; bảo vệ là `#if INTERNAL` + chính lint này.
  Type ở `[source-only]`, hàm/biến/typealias ở `[binary]`, tên ở cả hai mục, tên đứng trước mọi mục, mục lạ ⇒ lỗi.

Gốc quét: `appconfig.SRC_ROOTS` (`AppHost/AppHost/`, `Core/`) + `CoreOptional/` nếu có (chưa có thì bỏ qua, không
lỗi). Không quét thư mục test.

Chiều xuôi — mọi type khai trong vùng INTERNAL-only phải có tên ở mục `[binary]`:
  * Vùng INTERNAL-only = nhánh `#if` chỉ biên dịch khi có cờ INTERNAL: điều kiện đúng bằng `INTERNAL` (cho phép bọc
    ngoặc), hoặc `&&` ở mức ngoài cùng có MỘT toán hạng như vậy (`INTERNAL && canImport(UIKit)`,
    `os(iOS) && INTERNAL`, `INTERNAL && (A || B)`), hoặc `||` mà MỌI toán hạng như vậy; nhánh `#else` của điều kiện
    đúng bằng `!INTERNAL` cũng vậy. Một file bọc trọn `#if INTERNAL … #endif` cũng thế. Các `#if` khác lồng BÊN
    TRONG vùng đó vẫn là INTERNAL-only; `#if INTERNAL` lồng trong `#if DEBUG` thì khối lồng vẫn tính.
  * KHÔNG tính: nhánh `#else`/`#elseif` của `#if` thường (kể cả `#elseif INTERNAL`), `INTERNAL || X`,
    `(INTERNAL || X) && Y`, `!INTERNAL` (nhánh chính), và mã chỉ nằm trong `#if` khác (`#if DEBUG`).
  * Từ khoá nhận: struct, class, enum, actor, protocol (kèm `final`/`private`/`indirect`/`@MainActor`…).
  * LUẬT CHẶT, KHÔNG LỒNG-ĐƯỢC-MIỄN: type lồng trong một type INTERNAL-only cũng phải khai tên riêng của nó
    (`struct A { private struct B {} }` ⇒ cả A lẫn B). Lý do: một luật "chỉ type ngoài cùng" cần đếm ngoặc nhọn
    (dễ sai với chuỗi/closure), còn luật chặt không cần; cái giá là mọi helper lồng phải vào danh sách — nên mã
    INTERNAL mới nên tránh type lồng không cần thiết. Type lồng trong type THƯỜNG nhưng nằm trong `#if INTERNAL`
    (vd. `Entitlements.InternalProOverride`) đương nhiên tính.
Hàm/biến mặc định KHÔNG bị bắt buộc khai (quá nhiều hàm debug vô hại). Muốn ghim một hàm/biến NGUY HIỂM (vd. lối
bật Pro không trả tiền) thì đặt marker NGAY DÒNG TRÊN khai báo của nó, trong vùng INTERNAL-only:

    // debug-symbol: required
    func setProForInternalTesting(_ on: Bool) { … }

Tên đó từ đó BẮT BUỘC có ở mục `[source-only]` (marker đặt trên một type thì type vẫn thuộc `[binary]`). Marker đọc
từ văn bản gốc (trước khi xoá comment), phải là một dòng comment `//` đúng NGUYÊN VĂN như trên. Marker ngoài vùng
INTERNAL-only, dòng dưới không phải khai báo có tên, hoặc một comment có chữ `debug-symbol` mà không đúng nguyên văn
marker (gõ sai, `///`, `/* */`, sai khoảng trắng, đứng sau code cùng dòng) ⇒ lỗi rc 1 — marker viết gần đúng mà bị bỏ
qua im lặng thì người viết tưởng hàm đã được ghim. Xoá marker mà giữ tên trong file ⇒ vẫn rc 0 (tên vẫn bị buộc chỉ
khai trong vùng INTERNAL) — chỉ mất lớp "bắt quên".

Chiều ngược — mọi tên trong file phải còn khai, ĐÚNG LOẠI, VÀ chỉ khai trong vùng INTERNAL-only:
  * Khai = `struct|class|enum|actor|protocol|typealias <Tên>`, `func <Tên>`, `var|let <Tên>`.
  * Không còn khai ở đâu ⇒ lỗi (tên cũ/đổi tên: cổng binary sẽ gác chuỗi không bao giờ xuất hiện).
  * `[binary]` mà không có khai báo type (struct/class/enum/actor/protocol) nào ⇒ lỗi: hàm/biến/typealias không để
    lại tên trong binary, soi ở đó là an tâm giả. `[source-only]` mà có khai báo type ⇒ lỗi: type phải được soi
    binary.
  * Có một khai báo NGOÀI vùng INTERNAL-only (kể cả nhánh `#else`) ⇒ lỗi kèm `file:dòng`: tên đó biên dịch vào bản
    Release (với `[binary]`: `verify_release_clean.sh` sẽ FAIL mọi lần build Release).

Xử lý nguồn: bỏ comment `//`, `/* */` (lồng nhau được) và nội dung chuỗi — một dòng, nhiều dòng (ba dấu nháy), raw `#"…"#`, kể cả
nội suy `\\( … )` có chuỗi lồng — trước khi đọc `#if`/`#endif`/từ khoá, nên chữ `#endif` trong comment/chuỗi không
làm lệch.

Lỗ hổng đã biết (nói thẳng, không giả vờ):
  * Hàm/biến chỉ được bắt buộc khai khi có marker `// debug-symbol: required`: không gắn marker thì xoá tên hàm khỏi
    file không bị bắt (hàm chỉ-INTERNAL quá nhiều; lint không biết hàm nào nguy hiểm). Người viết phải gắn marker;
    xoá cả marker lẫn tên cũng không bị bắt. Tên `[source-only]` không được soi ở binary nào — chỗ dựa duy nhất là
    `#if INTERNAL` (trình biên dịch) + luật "chỉ khai trong vùng INTERNAL" ở đây.
  * `var|let <Tên>` khớp cả biến cục bộ cùng tên — chọn tên đủ riêng biệt. `case` của enum không dò.
  * `#if` trong chuỗi lồng sâu bất thường (chuỗi nhiều dòng có nội suy chứa chuỗi nhiều dòng khác) hoặc `#sourceLocation` không xử lý.
  * Không đánh giá `os()`/`canImport()`/cờ khác: `#if os(iOS) && INTERNAL` tính là INTERNAL-only (có INTERNAL ở
    `&&` ngoài cùng) dù khối đó có thể không biên dịch ở nền nào — chỉ làm thừa yêu cầu khai, không bao giờ thiếu.
  * `#endif` thừa/thiếu không được báo — trình biên dịch mới là nơi báo.

Exit code:
  0  khớp (`OK`)
  1  có vấn đề — mỗi dòng `đường/dẫn:dòng: <Tên> chưa khai` (xuôi) hoặc dòng nêu rõ lỗi (ngược), rồi `FAIL: …`
  2  sai cách dùng / thiếu `debug_symbols.txt` / gốc không tồn tại — in `FAIL: <lý do>`
Không bao giờ in traceback.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "common"))
import appconfig  # noqa: E402

SYMBOLS_REL = "tools/release/debug_symbols.txt"
APP_SYMBOLS_REL = "AppHost/Config/debug_symbols.app.txt"
OPTIONAL_ROOTS = ("CoreOptional/",)

# Từ khoá không phải tên (bắt nhầm `class func`, `class var`…).
NOT_A_NAME = {"func", "var", "let", "init", "deinit", "subscript", "override", "final", "static", "lazy", "private",
              "public", "internal", "fileprivate", "open", "mutating", "nonmutating", "convenience", "required",
              "dynamic", "weak", "unowned", "indirect", "nonisolated", "where", "typealias", "associatedtype"}
TYPE_RE = re.compile(r"(?<![.\w])(struct|class|enum|actor|protocol|typealias)\s+([A-Za-z_]\w*)")
FUNC_RE = re.compile(r"(?<![.\w])func\s+([A-Za-z_]\w*)")
VAR_RE = re.compile(r"(?<![.\w])(?:var|let)\s+([A-Za-z_]\w*)")
DIRECTIVE_RE = re.compile(r"^\s*#(if|elseif|else|endif)\b(.*)$")
# Chỉ type-từ-khoá bắt buộc khai ở chiều xuôi (typealias không tạo type mới ⇒ không bắt buộc).
FORWARD_KINDS = {"struct", "class", "enum", "actor", "protocol"}


class UsageError(Exception):
    """Sai cách dùng / thiếu file — rc 2."""


def blank_comments_and_strings(text: str, comment_lines: "set[int] | None" = None,
                               any_comment_lines: "set[int] | None" = None) -> str:
    """Thay comment + nội dung chuỗi bằng khoảng trắng (giữ nguyên xuống dòng ⇒ số dòng không đổi).
    `comment_lines` (nếu có) nhận số dòng (1-based) nơi một comment `//` THẬT (ngoài chuỗi) bắt đầu;
    `any_comment_lines` nhận mọi dòng có nội dung comment (`//` lẫn mọi dòng một khối `/* */` trải qua)."""
    out: list[str] = []
    n = len(text)
    i = 0
    # Ngăn xếp: ("str", hashes, multiline) hoặc ("interp", độ_sâu_ngoặc).
    stack: list[list] = []

    def blank(s: str) -> str:
        return "".join(c if c == "\n" else " " for c in s)

    while i < n:
        top = stack[-1] if stack else None
        if top is None or top[0] == "interp":
            if text.startswith("//", i):
                if comment_lines is not None:
                    comment_lines.add(text.count("\n", 0, i) + 1)
                if any_comment_lines is not None:
                    any_comment_lines.add(text.count("\n", 0, i) + 1)
                j = text.find("\n", i)
                j = n if j < 0 else j
                out.append(blank(text[i:j]))
                i = j
                continue
            if text.startswith("/*", i):
                depth, j = 1, i + 2
                while j < n and depth:
                    if text.startswith("/*", j):
                        depth += 1
                        j += 2
                    elif text.startswith("*/", j):
                        depth -= 1
                        j += 2
                    else:
                        j += 1
                if any_comment_lines is not None:
                    first = text.count("\n", 0, i) + 1
                    any_comment_lines.update(range(first, first + text.count("\n", i, j) + 1))
                out.append(blank(text[i:j]))
                i = j
                continue
            c = text[i]
            if c in '#"':
                k = i
                while k < n and text[k] == "#":
                    k += 1
                if k < n and text[k] == '"':
                    hashes = k - i
                    multi = text.startswith('"""', k)
                    stack.append(["str", hashes, multi])
                    q = 3 if multi else 1
                    out.append(blank(text[i:k + q]))
                    i = k + q
                    continue
            if top is not None:  # đang trong nội suy: đếm ngoặc để biết khi nào quay lại chuỗi
                if c == "(":
                    top[1] += 1
                elif c == ")":
                    top[1] -= 1
                    if top[1] == 0:
                        stack.pop()
                        out.append(" ")
                        i += 1
                        continue
                out.append(" " if c != "\n" else "\n")
            else:
                out.append(c)
            i += 1
            continue
        # Trong chuỗi.
        _, hashes, multi = top
        c = text[i]
        close = ('"""' if multi else '"') + "#" * hashes
        if text.startswith(close, i):
            stack.pop()
            out.append(blank(close))
            i += len(close)
            continue
        if c == "\\" and text.startswith("\\" + "#" * hashes + "(", i):
            skip = 1 + hashes + 1
            stack.append(["interp", 1])
            out.append(blank(text[i:i + skip]))
            i += skip
            continue
        if c == "\\" and not hashes:
            out.append(blank(text[i:i + 2]))
            i += 2
            continue
        if c == "\n" and not multi:  # chuỗi một dòng không thể xuống dòng: kết thúc để khỏi lan sang cả file
            stack.pop()
        out.append(c if c == "\n" else " ")
        i += 1
    return "".join(out)


def _strip_parens(cond: str) -> str:
    cond = cond.strip()
    while cond.startswith("(") and cond.endswith(")"):
        depth = 0
        for i, c in enumerate(cond):
            depth += (c == "(") - (c == ")")
            if depth == 0 and i < len(cond) - 1:
                return cond  # ngoặc đầu đóng sớm: `(A) && (B)`, không bọc trọn
        cond = cond[1:-1].strip()
    return cond


def _split_top(cond: str, op: str) -> list[str]:
    """Tách `cond` theo toán tử `op` ở MỨC NGOÀI CÙNG (tôn trọng ngoặc)."""
    parts, depth, cur, i = [], 0, "", 0
    while i < len(cond):
        c = cond[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if depth == 0 and cond.startswith(op, i):
            parts.append(cur)
            cur, i = "", i + len(op)
            continue
        cur += c
        i += 1
    parts.append(cur)
    return parts


def is_only(cond: str, atom) -> bool:
    """Điều kiện `#if` chỉ đúng khi `atom` đúng: bản thân là `atom` (bỏ ngoặc bọc); `&&` có MỘT toán hạng như vậy;
    `||` mà MỌI toán hạng như vậy. `atom(c)` nhận một toán hạng đã bỏ ngoặc bọc. Dùng chung với
    `lint_preview_code.py` (atom `targetEnvironment(simulator)`)."""
    cond = _strip_parens(cond)
    parts = _split_top(cond, "||")
    if len(parts) > 1:
        return all(is_only(p, atom) for p in parts)
    parts = _split_top(cond, "&&")
    if len(parts) > 1:
        return any(is_only(p, atom) for p in parts)
    return atom(cond)


def is_internal_only(cond: str) -> bool:
    """Điều kiện `#if` chỉ đúng khi có cờ INTERNAL: đúng bằng `INTERNAL`; `&&` có MỘT toán hạng như vậy;
    `||` mà MỌI toán hạng như vậy. `INTERNAL || X`, `!INTERNAL` ⇒ False (Release biên dịch được)."""
    return is_only(cond, lambda c: c == "INTERNAL")


def is_negated_internal(cond: str) -> bool:
    return _strip_parens(cond).replace(" ", "") == "!INTERNAL"


def region_lines(code_lines: "list[str]", only, negated=lambda cond: False) -> "tuple[dict[int, bool], set[int]]":
    """Đi ngăn xếp `#if` trên các dòng ĐÃ xoá comment/chuỗi ⇒ ({dòng 1-based: nằm trong vùng}, {dòng chỉ thị}).

    Vùng = nhánh của một `#if` có `only(cond)` đúng (lồng bao nhiêu `#if` khác bên trong cũng vẫn tính). `#elseif`
    và `#else` KHÔNG tính — trừ `#else` của một `#if` có `negated(cond)` đúng mà chưa qua `#elseif` (vd `#if !INTERNAL
    … #else`). Dòng chỉ thị mang trạng thái SAU khi áp chỉ thị đó."""
    # Mỗi khung #if: {"on": nhánh hiện tại nằm trong vùng?, "neg": #if gốc là phủ định, "alt": đã qua elseif}
    stack: list[dict] = []
    inside: dict[int, bool] = {}
    directives: set[int] = set()
    for no, line in enumerate(code_lines, start=1):
        m = DIRECTIVE_RE.match(line)
        if m:
            kind, cond = m.groups()
            if kind == "if":
                stack.append({"on": only(cond), "neg": negated(cond), "alt": False})
            elif kind == "elseif" and stack:
                stack[-1]["on"] = False
                stack[-1]["alt"] = True
            elif kind == "else" and stack:
                f = stack[-1]
                f["on"] = f["neg"] and not f["alt"]
            elif kind == "endif" and stack:
                stack.pop()
            directives.add(no)
        inside[no] = any(f["on"] for f in stack)
    return inside, directives


class Decl:
    __slots__ = ("path", "line", "kind", "name", "internal")

    def __init__(self, path, line, kind, name, internal):
        self.path, self.line, self.kind, self.name, self.internal = path, line, kind, name, internal


MARKER = "// debug-symbol: required"
MARKER_WORD = "debug-symbol"


def scan_source(rel: str, text: str) -> tuple[list[Decl], list[tuple[str, int, str, str]], list[str]]:
    """Một file ⇒ (mọi khai báo kèm cờ INTERNAL-only, tên BẮT BUỘC khai do marker (path, dòng, tên, kind), lỗi marker).

    Marker `// debug-symbol: required` đọc từ văn bản GỐC (comment bị xoá trắng ở bản dùng để phân tích) và phải
    đứng NGAY dòng trên một khai báo có tên nằm trong vùng INTERNAL-only. Comment nào có chữ `debug-symbol` mà không
    đúng nguyên văn marker ⇒ lỗi (marker gần đúng không được bị bỏ qua im lặng)."""
    decls: list[Decl] = []
    required: list[tuple[str, int, str, str]] = []
    problems: list[str] = []
    raw_lines = text.split("\n")
    comment_lines: set[int] = set()
    any_comment: set[int] = set()
    code_lines = blank_comments_and_strings(text, comment_lines, any_comment).split("\n")
    # `#if !INTERNAL … #else`: nhánh else chỉ biên dịch khi có INTERNAL (`negated`).
    line_internal, directives = region_lines(code_lines, is_internal_only, is_negated_internal)
    line_decls: dict[int, list[Decl]] = {}
    for no, line in enumerate(code_lines, start=1):
        if no in directives:
            continue
        internal = line_internal[no]
        here: list[Decl] = []
        for k, name in TYPE_RE.findall(line):
            if name not in NOT_A_NAME:
                here.append(Decl(rel, no, k, name, internal))
        for name in FUNC_RE.findall(line):
            here.append(Decl(rel, no, "func", name, internal))
        for name in VAR_RE.findall(line):
            if name not in NOT_A_NAME:
                here.append(Decl(rel, no, "var", name, internal))
        line_decls[no] = here
        decls.extend(here)
    for no, raw in enumerate(raw_lines, start=1):
        is_marker = raw.strip() == MARKER and not code_lines[no - 1].strip() and no in comment_lines
        if not is_marker:
            if no in any_comment and MARKER_WORD in raw.casefold():
                problems.append(f"{rel}:{no}: comment nhắc `{MARKER_WORD}` nhưng không đúng nguyên văn marker "
                                f"`{MARKER}` (một dòng riêng, comment `//`, đúng khoảng trắng) — marker viết gần đúng "
                                f"KHÔNG ghim được gì; sửa cho đúng hoặc bỏ chữ đó khỏi comment")
            continue
        below = line_decls.get(no + 1, [])
        if not below:
            problems.append(f"{rel}:{no}: marker `{MARKER}` không đứng ngay trên một khai báo có tên "
                            f"(type/func/var/let)")
        elif not line_internal.get(no + 1, False):
            problems.append(f"{rel}:{no}: marker `{MARKER}` đặt ngoài vùng `#if INTERNAL` — tên "
                            f"{below[0].name} biên dịch vào Release, marker vô nghĩa")
        else:
            required.append((rel, no + 1, below[0].name, below[0].kind))
    return decls, required, problems


BINARY = "binary"
SOURCE_ONLY = "source-only"
SECTIONS = (BINARY, SOURCE_ONLY)
SECTION_RE = re.compile(r"\[([^\]]*)\]")


def read_symbols(path: Path, rel: str = SYMBOLS_REL, optional: bool = False
                 ) -> tuple[dict[str, tuple[int, str, str]], list[str]]:
    """(tên → (số dòng 1-based, mục, đường dẫn tương đối của file), lỗi định dạng) của một file danh sách.
    `optional`: vắng file ⇒ rỗng (file của app).

    Cắt khoảng trắng/`\\r`, bỏ dòng trống và `#`. Dòng `[binary]`/`[source-only]` mở mục; tên trước mọi mục, mục lạ,
    tên trùng (cùng hay khác mục) ⇒ lỗi. Thiếu/không đọc được file ⇒ UsageError (rc 2)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if optional:
            return {}, []
        raise UsageError(f"không thấy {path} — không có danh sách symbol debug để đối chiếu")
    except (OSError, UnicodeDecodeError) as e:
        raise UsageError(f"không đọc được {path}: {e}")
    out: dict[str, tuple[int, str, str]] = {}
    problems: list[str] = []
    section = None
    for no, line in enumerate(raw.splitlines(), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = SECTION_RE.fullmatch(s)
        if m:
            if m.group(1) not in SECTIONS:
                problems.append(f"{rel}:{no}: mục lạ `{s}` (chỉ có [{BINARY}] và [{SOURCE_ONLY}])")
                section = "?"
            else:
                section = m.group(1)
            continue
        if section is None:
            problems.append(f"{rel}:{no}: {s} đứng trước mọi mục — đặt dưới [{BINARY}] (type) hoặc "
                            f"[{SOURCE_ONLY}] (hàm/biến ghim bằng marker)")
            continue
        if section == "?":
            continue  # đã báo mục lạ
        if s in out:
            problems.append(f"{rel}:{no}: {s} khai trùng (đã có ở dòng {out[s][0]}, mục [{out[s][1]}])")
            continue
        out[s] = (no, section, rel)
    return out, problems


def swift_files(root: Path) -> list[Path]:
    dirs = list(dict.fromkeys(root / r for r in (*appconfig.SRC_ROOTS, *OPTIONAL_ROOTS)))  # SRC_ROOTS đã có CoreOptional/
    files: list[Path] = []
    for d in dirs:
        if d.is_dir():
            files.extend(sorted(d.rglob("*.swift")))
    return files


def lint(root: Path) -> list[str]:
    symbols, problems = read_symbols(root / SYMBOLS_REL, SYMBOLS_REL)
    app_symbols, app_problems = read_symbols(root / APP_SYMBOLS_REL, APP_SYMBOLS_REL, optional=True)
    problems.extend(app_problems)
    for name, (no, section, rel) in app_symbols.items():
        if name in symbols:
            core = symbols[name]
            problems.append(f"{rel}:{no}: {name} khai trùng — đã có ở {core[2]}:{core[0]} (mục [{core[1]}]); "
                            f"mỗi tên chỉ ở MỘT file: tên của lõi ở {SYMBOLS_REL}, tên của app ở {APP_SYMBOLS_REL}")
        else:
            symbols[name] = (no, section, rel)
    decls: list[Decl] = []
    required: list[tuple[str, int, str, str]] = []
    for f in swift_files(root):
        rel = f.relative_to(root).as_posix()
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise UsageError(f"không đọc được {rel}: {e}")
        d, r, p = scan_source(rel, text)
        decls.extend(d)
        required.extend(r)
        problems.extend(p)

    # Xuôi: type trong vùng INTERNAL-only phải có tên ở mục [binary].
    for d in decls:
        if not (d.internal and d.kind in FORWARD_KINDS):
            continue
        if d.name not in symbols:
            problems.append(f"{d.path}:{d.line}: {d.name} chưa khai trong {SYMBOLS_REL} (của lõi) hoặc {APP_SYMBOLS_REL} (của app) "
                            f"(type chỉ-INTERNAL — thêm tên vào mục [{BINARY}])")
        elif symbols[d.name][1] != BINARY:
            problems.append(f"{d.path}:{d.line}: {d.name} là type nhưng nằm ở mục [{symbols[d.name][1]}] "
                            f"({symbols[d.name][2]}:{symbols[d.name][0]}) — type phải ở [{BINARY}] để được soi binary")
    # Xuôi (marker): hàm/biến đã ghim bằng marker phải có tên ở mục [source-only] (type có marker: luật type ở trên).
    for path, line, name, kind in required:
        if kind in FORWARD_KINDS:
            continue
        if name not in symbols:
            problems.append(f"{path}:{line}: {name} chưa khai trong {SYMBOLS_REL} (của lõi) hoặc {APP_SYMBOLS_REL} (của app) "
                            f"(có marker `{MARKER}` — thêm tên vào mục [{SOURCE_ONLY}])")
        elif symbols[name][1] != SOURCE_ONLY:
            problems.append(f"{path}:{line}: {name} (hàm/biến có marker) nằm ở mục [{symbols[name][1]}] "
                            f"({symbols[name][2]}:{symbols[name][0]}) — chuyển sang [{SOURCE_ONLY}]: tên hàm/biến "
                            f"không có trong binary nên soi binary là an tâm giả")
    # Ngược: tên trong file phải còn khai, đúng loại với mục, và chỉ trong vùng INTERNAL-only.
    by_name: dict[str, list[Decl]] = {}
    for d in decls:
        by_name.setdefault(d.name, []).append(d)
    for name, (no, section, rel) in symbols.items():
        found = by_name.get(name, [])
        if not found:
            problems.append(f"{rel}:{no}: {name} không còn khai ở đâu trong nguồn "
                            f"(đổi tên/đã xoá — sửa hoặc bỏ dòng)")
            continue
        is_type = any(d.kind in FORWARD_KINDS for d in found)
        if section == BINARY and not is_type:
            problems.append(f"{rel}:{no}: {name} ở mục [{BINARY}] nhưng không phải type "
                            f"(struct/class/enum/actor/protocol) — tên hàm/biến/typealias không có trong binary, "
                            f"chuyển sang [{SOURCE_ONLY}]")
        if section == SOURCE_ONLY and is_type:
            problems.append(f"{rel}:{no}: {name} ở mục [{SOURCE_ONLY}] nhưng là type — chuyển sang "
                            f"[{BINARY}] để cổng release soi binary")
        for d in found:
            if not d.internal:
                hint = ("verify_release_clean.sh sẽ FAIL" if section == BINARY
                        else "lối debug này lọt vào bản Store")
                problems.append(f"{d.path}:{d.line}: {name} ({rel}:{no}) khai NGOÀI vùng `#if INTERNAL` — "
                                f"bản Release vẫn biên dịch nó ⇒ {hint}")
    return sorted(set(problems))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Giữ tools/release/debug_symbols.txt + AppHost/Config/debug_symbols.app.txt khớp nguồn (xem docstring).")
    ap.add_argument("--root", default=str(ROOT), help="gốc repo (mặc định suy từ vị trí script)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    root = Path(args.root)
    try:
        if not root.is_dir():
            raise UsageError(f"gốc {root} không tồn tại")
        problems = lint(root)
    except UsageError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        print(f"FAIL: lint_debug_symbols — {len(problems)} vấn đề", file=sys.stderr)
        return 1
    print("OK: danh sách symbol debug (lõi + app) khớp nguồn (type chỉ-INTERNAL ở [binary], hàm/biến có marker ở [source-only], "
          "tên đã khai đúng loại và còn nằm trong #if INTERNAL)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
