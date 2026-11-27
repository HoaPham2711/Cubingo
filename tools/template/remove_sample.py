#!/usr/bin/env python3
"""Gỡ tính năng mẫu (`Features/Sample/`) khỏi app bằng MỘT lệnh, và kiểm biên của nó.

    python3 tools/template/remove_sample.py [--root <gốc repo>] [--force]   # gỡ
    python3 tools/template/remove_sample.py --check [--root <gốc repo>]     # chỉ kiểm (selfcheck bước 1, pre-commit)

Quy ước đánh dấu (file `.swift` dưới `AppHost/`, NGOÀI hai thư mục mẫu):
  * Dòng nhắc mẫu nằm giữa hai dòng
        // sample:begin
        // sample:end
    Lệnh gỡ cắt cả khối, KỂ CẢ hai dòng dấu.
  * Chỗ nào gỡ mẫu xong cần một dòng thay thế, dòng đó viết sẵn ở dạng comment giữa
        // sample:else-begin
        // <dòng Swift thay thế>
        // sample:else-end
    Lệnh gỡ xoá hai dòng dấu và bỏ ĐÚNG MỘT `// ` ngay sau phần thụt lề của từng dòng ở giữa (dòng chỉ có `//` ⇒ dòng
    trống; dòng trống giữ nguyên). Thụt lề trước `//` giữ nguyên, nên dòng thay thế viết ở đúng cột của code.
  * Mỗi dấu chiếm TRỌN một dòng NGUỒN THẬT: chỉ thụt lề + `// sample:<loại>` (+ khoảng trắng cuối), và `//` đó là một
    comment thật (không nằm trong chuỗi nhiều dòng (ba dấu nháy kép) hay khối `/* */` — bộ quét comment/chuỗi dùng chung với
    `tools/release/lint_debug_symbols.py`). Dấu dính code/comment khác, dấu trong chuỗi/khối comment, dấu không cặp,
    khối lồng nhau (kể cả `begin` trong khối else hay ngược lại), dòng trong khối else không phải comment `//` ⇒ lỗi
    `file:dòng`.
  Bộ cắt là `tools/template/blocks.py` (dùng chung với lệnh tạo app, họ `template:`).

Tài liệu lớp seed (`SEED_DOCS`: `CLAUDE.md`, `README.md`, `.claude/rules/conventions.app.md`, `AppHost/project.yml`,
`docs/NEW_APP_CHECKLIST.md`; file vắng ⇒ bỏ qua im lặng, kể cả ở `--check` — ở template checklist chỉ có trong thư mục gieo): phần tả mẫu nằm giữa hai dòng `<!-- sample:begin -->` … `<!-- sample:end -->` (Markdown, không nhánh
else; nhắc dấu trong code inline là chữ) hoặc `# sample:begin` … `# sample:end` (YAML, nhánh else `# sample:else-begin`
như Swift với `# `). Cắt xong, nếu ngay trước khối là dòng trống thì dòng trống ngay sau khối bị bỏ — không bao giờ để
hai dòng trống liền nhau. Dòng NGOÀI khối không được mang dấu vết trong tài liệu (`DOC_TRACE_RE`: `Features/Sample`,
`tính năng mẫu`, `app mẫu`; thêm tên kiểu `Sample[A-Z]…` khi mẫu còn). Tài liệu lớp sync không có khối: chúng viết có
điều kiện ("nếu app còn `Features/Sample/`…") vì không tool nào được sửa file sync tại chỗ.

Dấu vết của mẫu (phân biệt hoa thường; COMMENT CŨNG TÍNH — câu tả mẫu ngoài khối sẽ tả code không còn sau khi gỡ):
  * `\\bSample[A-Z]\\w*` (kiểu), `\\bsample_[a-z]\\w*` (tên event/màn), `\\bsample[A-Z]\\w*` (biến `sampleDeps`…).
    Luật chữ thường này bắt cả tên hợp lệ của app như `sampleBuffer`/`sampleRate` — nó CHỈ áp khi `Features/Sample`
    còn (gỡ mẫu xong `--check` là no-op, hook không chặn chữ `sample…` của app nữa);
  * đoạn đường dẫn `Features/Sample`, cụm từ `tính năng mẫu`;
  * TÊN TRỌN của một route preview của mẫu, chỉ ở vị trí route: `AppPreview.<route>`, `"<route>"`, `` `<route>` `` và
    thành viên ngầm `.<route>` khi ký tự ngay trước `.` KHÔNG phải ký tự định danh hay `)`/`]`/`?`/`!`/`\\` (⇒ `case .items:`,
    `[.itemsDone]` bị bắt; `store.items`, key path `\\.items`, `let items`, `homeProfile`, comment "list items" thì không).
    Báo nhầm còn lại, có chủ ý, khi mẫu còn: chuỗi đúng bằng tên route (`json["items"]`), dòng nối tiếp bắt đầu bằng
    `.items`, `case .items:` của một enum khác — đặt chúng trong khối `// sample:` hoặc đổi tên. Tên route đọc từ
    các dòng `case a, b, …` trong khối `sample:begin` của `AppHost/AppHost/AppPreview.swift` (không gõ cứng); một `case`
    có raw value tường minh (`case c = "cc"`) trong khối đó ⇒ lỗi `file:dòng` rc 2 (không bỏ qua im lặng).
  Ranh giới từ ⇒ `AppEvent.shellSamples` (tên của lõi), `resample_x`, "Sample limit" (chữ hoa + khoảng trắng) không tính.
  `Core/` + `CoreOptional/` soi theo ba regex đầu + đường dẫn + cụm từ (không soi tên route — từ thường như `items`).

`--check` (rc 1 + `file:dòng`): cú pháp dấu; dòng NGOÀI khối `begin…end` (gồm cả dòng trong khối else — sau khi gỡ
chúng là code) mang dấu vết của mẫu; `Core/`/`CoreOptional/` mang dấu vết; cú pháp khối + dấu vết ngoài khối trong
`SEED_DOCS`. Hai thư mục mẫu đã không còn ⇒ Swift không soi nữa (app đã gỡ mẫu giữ nguyên hook mà không bị chữ `Sample…`
của chính nó chặn), chỉ còn kiểm `SEED_DOCS` không sót dấu `sample:` nào và không câu tả mẫu (`DOC_TRACE_RE`).
Có thư mục gieo `tools/template/seed/` (chỉ ở template) ⇒ cả `--check` lẫn lệnh gỡ kiểm cặp dấu `sample:` VÀ `template:`
trong mọi file của nó (dấu sai ở đó chỉ nổ muộn, lúc lệnh tạo app cắt khối); không cắt gì ở đó (file lớp template_only).

Gỡ (validate hết rồi mới ghi; mọi từ chối ⇒ KHÔNG ghi/xoá gì):
  1. gốc phải có `app.config.toml` + `AppHost/project.yml` (không thì rc 2);
  2. đủ các kiểm của `--check` (rc 1);
  3. mọi đường dẫn sẽ ghi/xoá: không thành phần nào từ gốc trở xuống là symlink, đường dẫn đã resolve nằm trong gốc,
     thư mục mẫu là thư mục thật (rc 1);
  3b. gốc có `template.manifest.toml` ⇒ không đường dẫn sẽ ghi/xoá nào thuộc lớp `sync` (rc 1; manifest hỏng rc 2) —
     cây không có manifest (cây test tối thiểu) bỏ qua kiểm này;
  4. git: còn thay đổi chưa commit ở đường dẫn sẽ ghi/xoá ⇒ rc 1 trừ khi `--force` (sửa trong khối bị cắt hay trong thư
     mục mẫu sẽ mất); không phải repo git ⇒ in một dòng rồi làm tiếp;
  5. ghi từng file nguyên tử (file tạm cùng thư mục + `os.replace`, giữ quyền file và kiểu xuống dòng LF/CRLF), xoá hai
     thư mục mẫu SAU CÙNG (không theo symlink). `OSError` giữa chừng ⇒ rc 2, in đường dẫn + các file đã đổi.
Chạy lại trên cây đã gỡ ⇒ rc 0, không đổi gì.

Exit: 0 OK · 1 lỗi đánh dấu/biên/an toàn · 2 sai cách dùng, gốc không đúng, lỗi đọc/ghi. Không in traceback.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import blocks  # noqa: E402  (bộ cắt khối dùng chung: Swift / Markdown / YAML)

APP_DIR = "AppHost"
MANIFEST_FILE = "template.manifest.toml"
# Tài liệu lớp seed (hoặc của riêng template) tả mẫu trong khối `<!-- sample:begin -->`…`end` / `# sample:begin`…`end`.
SEED_DOCS = ("CLAUDE.md", "README.md", ".claude/rules/conventions.app.md", "AppHost/project.yml",
             "docs/NEW_APP_CHECKLIST.md")
SEED_DIR = "tools/template/seed"   # thư mục gieo của template (app không có): chỉ kiểm cặp dấu, không cắt
SEED_DIR_FAMILIES = ("sample", "template")
ROOT_MARKERS = ("app.config.toml", "AppHost/project.yml")
SAMPLE_DIRS = ("AppHost/AppHost/Features/Sample", "AppHost/AppHostTests/Sample")
CORE_DIRS = ("Core", "CoreOptional")
APP_PREVIEW = "AppHost/AppHost/AppPreview.swift"

SYMBOL_RE = re.compile(r"\bSample[A-Z]\w*|\bsample_[a-z]\w*")
TRACE_RE = re.compile(r"\bSample[A-Z]\w*|\bsample_[a-z]\w*|\bsample[A-Z]\w*|Features/Sample|tính năng mẫu")
MARKER_RE = re.compile(r"^[ \t]*// sample:(begin|end|else-begin|else-end)[ \t]*$")
# Dấu vết trong tài liệu gieo: hẹp hơn TRACE_RE (tài liệu nhắc tên tool `sample_removal_check.sh`, chữ "sample" thường).
DOC_TRACE_RE = re.compile(r"Features/Sample|tính năng mẫu|app mẫu")
SYMBOL_TYPE_RE = re.compile(r"\bSample[A-Z]\w*")
CASE_LINE_RE = re.compile(r"^\s*case\s+([a-z]\w*(?:\s*,\s*[a-z]\w*)*)\s*$")
# Dòng khai case của enum (không phải `case .x:` của switch, không phải `case let`/`case var`) mà CASE_LINE_RE không đọc
# được — vd raw value tường minh `case c = "cc"`: route có tên khác giá trị ⇒ báo lỗi thay vì bỏ qua.
ENUM_CASE_RE = re.compile(r"^\s*case\s+(?!let\b|var\b)[A-Za-z_]")

# Việc tay còn lại sau khi gỡ: (đường dẫn, việc) — chỉ còn việc NỘI DUNG Swift của app. Tài liệu tự dọn: tài liệu lớp seed
# (`SEED_DOCS`) tả mẫu trong khối `sample:` bị cắt ở trên; tài liệu lớp sync viết có điều kiện ("nếu app còn
# `Features/Sample/`…") nên đúng cả trước lẫn sau khi gỡ. test_remove_sample.FollowUpsTests kiểm từng đường dẫn tồn tại và
# còn nhắc mẫu. Giữ khớp mục "Việc tay còn lại" ở AppHost/AppHost/Features/Sample/README.md.
FOLLOW_UPS = (
    ("AppHost/AppHost/AppOnboarding.swift", "thay nội dung tour mở đầu (trang của mẫu đã bị cắt)."),
    ("AppHost/AppHost/AppPaywall.swift", "thay bảng so sánh của paywall (dòng giữ chỗ \"Pro features\")."),
    ("AppHost/AppHost/WhatsNew/WhatsNewCatalog.swift", "thêm thẻ What's New của app."),
)
FINAL_STEPS = (
    "Sinh lại cấu hình: python3 tools/common/appconfig.py render (web.app_paths đã về [] — AASA ở web/site/wrangler.jsonc)",
    "Sinh lại project: cd AppHost && xcodegen generate",
    "Chạy lại: python3 tools/dev/run_tests.py --full && tools/template/selfcheck.sh --quick",
)


class Problem(Exception):
    """Lỗi đọc/ghi (rc 2)."""


def traces(line, route_re=None):
    found = [m.group(0) for m in TRACE_RE.finditer(line)]
    if route_re is not None:
        found += [m.group(0) for m in route_re.finditer(line)]
    return found


def sample_routes(root):
    """Tên route preview của mẫu: các dòng `case a, b` trong khối `sample:begin` của AppPreview.swift.

    Dòng `case` khai enum mà không đọc được (raw value `case c = "cc"`, …) ⇒ `Problem` kèm `file:dòng`."""
    path = root / APP_PREVIEW
    if not path.is_file():
        return []
    names, inside = [], False
    for no, line in enumerate(read(path).replace("\r\n", "\n").split("\n"), 1):
        m = MARKER_RE.match(line)
        if m:
            inside = m.group(1) == "begin"
            continue
        if inside:
            c = CASE_LINE_RE.match(line)
            if c:
                names += [n.strip() for n in c.group(1).split(",")]
            elif ENUM_CASE_RE.match(line):
                raise Problem(f"{APP_PREVIEW}:{no}: route của mẫu phải khai dạng `case a, b` (không raw value tường minh,"
                              f" không associated value): {line.strip()}")
    return names


def route_regex(names):
    """TÊN TRỌN của route mẫu ở vị trí route (xem docstring đầu file). Phải khớp `no_sample_traces` của
    sample_removal_check.sh."""
    if not names:
        return None
    alt = "|".join(re.escape(n) for n in sorted(set(names), key=len, reverse=True))
    return re.compile(r"\bAppPreview\.(?:{a})\b|\"(?:{a})\"|`(?:{a})`|(?<![\w)\]?!\\])\.(?:{a})\b".format(a=alt))


def transform(text, rel, route_re=None):
    """Phân tích một file Swift (xuống dòng đã chuẩn về `\\n`). Trả (văn bản sau khi gỡ, [lỗi], [dòng mang dấu vết ngoài
    khối]). Cắt khối bằng `blocks.walk` (kiểu `swift`, họ `sample`). Lỗi cú pháp ⇒ văn bản trả về không dùng được."""
    kept, _, errs = blocks.walk(text, "sample", "swift")
    errors = [f"{rel}:{no}: {msg}" for no, msg in errs]
    strays = []
    for no, line in kept:
        found = traces(line, route_re)
        if found:
            strays.append(f"{rel}:{no}: dấu vết của mẫu ({', '.join(found)}) ngoài khối `// sample:begin`…`end`")
    return "\n".join(line for _, line in kept), errors, strays


def doc_traces(line, present):
    """Dấu vết của mẫu trong một dòng tài liệu gieo (`DOC_TRACE_RE`; tên kiểu `Sample[A-Z]…` chỉ khi mẫu còn)."""
    found = [m.group(0) for m in DOC_TRACE_RE.finditer(line)]
    if present:
        found += [m.group(0) for m in SYMBOL_TYPE_RE.finditer(line)]
    return found


def analyse_docs(root, present):
    """Tài liệu lớp seed trong `SEED_DOCS` (vắng ⇒ bỏ qua). Mẫu còn: cú pháp khối `sample:` + dòng NGOÀI khối không mang
    dấu vết. Mẫu đã gỡ: không còn dấu `sample:` nào và không dấu vết. Trả ({đường dẫn: văn bản mới} cho file đổi, [lỗi])."""
    changes, problems = {}, []
    for rel in SEED_DOCS:
        path = root / rel
        if not path.is_file():
            continue
        raw = read(path)
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        style = blocks.style_for(rel)
        kept, marks, errs = blocks.walk(text, "sample", style)
        problems += [f"{rel}:{no}: {msg}" for no, msg in errs]
        if not present:
            problems += [f"{rel}:{no}: còn dấu `sample:{kind}` dù tính năng mẫu đã gỡ" for no, kind in marks]
        for no, line in kept:
            found = doc_traces(line, present)
            if found:
                problems.append(f"{rel}:{no}: tài liệu tả mẫu ({', '.join(found)}) ngoài khối sample:begin…end")
        if present and not errs:
            new = "\n".join(line for _, line in kept)
            if crlf:
                new = new.replace("\n", "\r\n")
            if new != raw:
                changes[path] = new
    return changes, problems


def seed_dir_problems(root):
    """Cặp dấu `sample:`/`template:` trong mọi file text của thư mục gieo (vắng ⇒ []). Không đi theo symlink, không ghi."""
    base = root / SEED_DIR
    if not base.is_dir() or base.is_symlink():
        return []
    problems = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        for n in sorted(filenames):
            path = Path(dirpath) / n
            rel = path.relative_to(root).as_posix()
            style = blocks.style_for(rel)
            if style is None or path.is_symlink():
                continue
            text = read(path).replace("\r\n", "\n")
            for fam in SEED_DIR_FAMILIES:
                _, _, errs = blocks.walk(text, fam, style)
                problems += [f"{rel}:{no}: {msg}" for no, msg in errs]
    return sorted(problems)


def sync_class_writes(root, paths):
    """Đường dẫn (tương đối) sẽ ghi/xoá mà `template.manifest.toml` xếp lớp `sync` — tool này chỉ ghi file lớp
    seed/template_only. Gốc không có manifest (cây tối thiểu) ⇒ []. Manifest hỏng ⇒ `Problem`."""
    if not (root / MANIFEST_FILE).is_file():
        return []
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import manifest  # noqa: E402
    try:
        m = manifest.load(root)
        return [rel for rel in paths if manifest.classify(m, rel) == "sync"]
    except manifest.ManifestError as e:
        raise Problem(f"{MANIFEST_FILE}: {e}")


def in_sample_dir(rel):
    return any(rel == d or rel.startswith(d + "/") for d in SAMPLE_DIRS)


def swift_files(root, top):
    """File .swift dưới root/top — KHÔNG đi theo symlink thư mục."""
    base = root / top
    if not base.is_dir():
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        for n in filenames:
            if n.endswith(".swift"):
                found.append(Path(dirpath) / n)
    return sorted(found)


def read(path):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise Problem(f"không đọc được {path}: {e}")


def analyse(root):
    """Kiểm cả cây. Trả ({đường dẫn: văn bản mới (đúng kiểu xuống dòng gốc)} cho file đổi, [lỗi])."""
    changes, problems = {}, []
    route_re = route_regex(sample_routes(root))
    for path in swift_files(root, APP_DIR):
        rel = path.relative_to(root).as_posix()
        if in_sample_dir(rel):
            continue
        raw = read(path)
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        new, errors, strays = transform(text, rel, route_re)
        problems += errors + strays
        if crlf:
            new = new.replace("\n", "\r\n")
        if not errors and new != raw:
            changes[path] = new
    for top in CORE_DIRS:
        for path in swift_files(root, top):
            rel = path.relative_to(root).as_posix()
            for no, line in enumerate(read(path).split("\n"), 1):
                found = traces(line)
                if found:
                    problems.append(f"{rel}:{no}: lõi mang dấu vết của mẫu ({', '.join(found)}) — Core/ không được biết mẫu")
    doc_changes, doc_problems = analyse_docs(root, sample_present(root))
    changes.update(doc_changes)
    cfg = config_without_sample_paths(root) if sample_present(root) else None  # app đã gỡ mẫu: paths là của app
    if cfg is not None:
        changes[root / "app.config.toml"] = cfg
    problems += doc_problems + seed_dir_problems(root)
    return changes, problems


APP_PATHS_RE = re.compile(r"^(\s*app_paths\s*=\s*)\[[^\]\n]*\]", re.M)


def config_without_sample_paths(root):
    """Nội dung `app.config.toml` với `web.app_paths = []` (đường dẫn mở app của mẫu: /items…) — None nếu không đổi.
    Chỉ đụng dòng `app_paths` một dòng; comment cuối dòng giữ nguyên. Cần `appconfig.py render` sau đó (AASA ở wrangler)."""
    path = root / "app.config.toml"
    if not path.is_file():
        return None
    raw = read(path)
    new = APP_PATHS_RE.sub(lambda m: m.group(1) + "[]", raw, count=1)
    return new if new != raw else None


def sample_present(root):
    return any(os.path.lexists(root / d) for d in SAMPLE_DIRS)


def unsafe(root, path, want_dir=False):
    """Lý do không được ghi/xoá `path` (rỗng = an toàn): symlink ở bất kỳ thành phần nào từ gốc trở xuống, đường dẫn
    resolve ra ngoài gốc, thư mục mẫu không phải thư mục thật."""
    reasons = []
    rel = path.relative_to(root)
    cur = root
    for part in rel.parts:
        cur = cur / part
        if os.path.islink(cur):
            reasons.append(f"thành phần là symlink: {cur.relative_to(root).as_posix()}")
            break
    try:
        resolved = path.resolve()
        if resolved != root and root not in resolved.parents:
            reasons.append(f"đường dẫn resolve ra ngoài --root: {resolved}")
    except OSError as e:
        reasons.append(f"không resolve được: {e}")
    if want_dir and not (path.is_dir() and not path.is_symlink()):
        reasons.append("không phải thư mục thật")
    return reasons


def git(root, *args):
    """git không khoá phụ (`--no-optional-locks`: `status` không ghi index) và không thừa hưởng biến `GIT_*` (hook
    pre-commit đặt `GIT_INDEX_FILE`/`GIT_DIR`… — để nguyên thì `-C <gốc>` vẫn đọc nhầm repo/index của hook)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args], capture_output=True, text=True,
                          env=env)


def dirty_paths(root, rels):
    """(là repo git?, [dòng status chưa commit dưới các đường dẫn sẽ ghi/xoá])."""
    try:
        top = git(root, "rev-parse", "--show-toplevel")
    except OSError:
        return False, []
    if top.returncode != 0:
        return False, []
    st = git(root, "status", "--porcelain", "--untracked-files=all", "--", *rels)
    if st.returncode != 0:
        raise Problem(f"git status lỗi: {st.stderr.strip()}")
    return True, [ln for ln in st.stdout.splitlines() if ln.strip()]


def write_atomic(path, text):
    mode = os.stat(path).st_mode & 0o7777
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gỡ tính năng mẫu (Features/Sample) / kiểm biên của nó")
    ap.add_argument("--root", default=str(ROOT), help="gốc repo (mặc định suy từ vị trí script)")
    ap.add_argument("--check", action="store_true", help="chỉ kiểm cú pháp dấu + dấu vết của mẫu ngoài khối")
    ap.add_argument("--force", action="store_true", help="gỡ cả khi đường dẫn sẽ ghi/xoá còn thay đổi chưa commit")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    missing = [m for m in ROOT_MARKERS if not (root / m).is_file()]
    if missing:
        print(f"remove_sample: {root} không phải gốc template (thiếu {', '.join(missing)}) — từ chối", file=sys.stderr)
        return 2
    present = sample_present(root)
    if args.check and not present:
        # App đã gỡ mẫu: Swift không còn gì để kiểm (chữ `Sample…` của app không bị chặn); chỉ soi tài liệu gieo không
        # còn dấu `sample:` / câu tả mẫu sót lại.
        try:
            _, problems = analyse_docs(root, False)
            problems += seed_dir_problems(root)
        except Problem as e:
            print(f"remove_sample: {e}", file=sys.stderr)
            return 2
        if problems:
            for p in problems:
                print(p)
            print(f"FAIL: {len(problems)} chỗ tài liệu gieo còn tả tính năng mẫu đã gỡ ({', '.join(SEED_DOCS)})")
            return 1
        print("remove_sample --check: OK (tính năng mẫu đã gỡ — tài liệu gieo không còn dấu vết)")
        return 0
    try:
        changes, problems = analyse(root)
    except Problem as e:
        print(f"remove_sample: {e}", file=sys.stderr)
        return 2
    if problems:
        for p in problems:
            print(p)
        print(f"FAIL: {len(problems)} lỗi đánh dấu/biên của tính năng mẫu"
              + ("" if args.check else " — KHÔNG ghi/xoá gì") + " (quy ước ở đầu tools/template/remove_sample.py)."
              " Luật dấu vết (kể cả `sampleX` chữ thường) chỉ áp khi Features/Sample còn — gỡ mẫu xong không chặn nữa")
        return 1
    if args.check:
        print("remove_sample --check: OK (dấu sample hợp lệ, không dấu vết của mẫu ngoài khối, Core/ sạch)")
        return 0
    deletes = [root / d for d in SAMPLE_DIRS if os.path.lexists(root / d)]
    if not changes and not deletes:
        print("remove_sample: OK — tính năng mẫu đã gỡ, không còn gì để làm")
        return 0

    # An toàn đường dẫn — trước MỌI thao tác ghi/xoá.
    bad = [f"{p.relative_to(root).as_posix()}: {r}" for p in changes for r in unsafe(root, p)]
    bad += [f"{p.relative_to(root).as_posix()}: {r}" for p in deletes for r in unsafe(root, p, want_dir=True)]
    if bad:
        for b in bad:
            print(b)
        print(f"FAIL: {len(bad)} đường dẫn không an toàn để ghi/xoá — KHÔNG ghi/xoá gì")
        return 1

    rels = [p.relative_to(root).as_posix() for p in list(changes) + deletes]
    # Lớp sở hữu: file lớp sync giống hệt ở mọi app, không tool nào sửa tại chỗ.
    try:
        sync = sync_class_writes(root, rels)
    except Problem as e:
        print(f"remove_sample: {e}", file=sys.stderr)
        return 2
    if sync:
        for rel in sync:
            print(f"{rel}: file lớp sync ({MANIFEST_FILE}) — remove_sample chỉ ghi file lớp seed/template_only")
        print(f"FAIL: {len(sync)} file lớp sync sẽ bị sửa/xoá — viết phần tả mẫu của chúng có điều kiện thay vì khối"
              " `sample:` — KHÔNG ghi/xoá gì")
        return 1
    try:
        is_git, dirty = dirty_paths(root, rels)
    except Problem as e:
        print(f"remove_sample: {e}", file=sys.stderr)
        return 2
    if not is_git:
        print("remove_sample: không phải repo git — không kiểm được thay đổi chưa commit, làm tiếp")
    elif dirty and not args.force:
        for d in dirty:
            print(f"  {d}")
        print("FAIL: còn thay đổi chưa commit ở file sẽ sửa/xoá — sửa nằm trong khối bị cắt hay trong thư mục mẫu sẽ MẤT."
              " Commit/stash trước, hoặc chạy lại với --force — KHÔNG ghi/xoá gì")
        return 1

    done = []
    for path, text in changes.items():
        rel = path.relative_to(root).as_posix()
        try:
            write_atomic(path, text)
        except OSError as e:
            print(f"remove_sample: ghi {rel} lỗi: {e}", file=sys.stderr)
            print(f"remove_sample: đã đổi {len(done)} file trước lỗi: {', '.join(done) or '(chưa file nào)'};"
                  " thư mục mẫu CHƯA xoá — xem git status", file=sys.stderr)
            return 2
        done.append(rel)
        print(f"  sửa: {rel}")
    for d in deletes:
        rel = d.relative_to(root).as_posix()
        try:
            shutil.rmtree(d)  # đã kiểm: thư mục thật, không symlink; rmtree không đi theo symlink bên trong
        except OSError as e:
            print(f"remove_sample: xoá {rel} lỗi: {e}", file=sys.stderr)
            print(f"remove_sample: đã sửa {len(done)} file: {', '.join(done) or '(không)'} — xem git status",
                  file=sys.stderr)
            return 2
        print(f"  xoá: {rel}/")
    print(f"remove_sample: OK — đã gỡ tính năng mẫu ({len(done)} file sửa). Việc tay còn lại:")
    steps = [f"{path}: {what}" for path, what in FOLLOW_UPS] + list(FINAL_STEPS)
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
