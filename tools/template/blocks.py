#!/usr/bin/env python3
"""Khối đánh dấu `<họ>:begin … <họ>:end` trong file nguồn/tài liệu — một bộ cắt dùng chung cho mọi kiểu file.

Hai họ đang dùng: `sample` (phần của tính năng mẫu — `remove_sample.py` cắt khi gỡ mẫu) và `template` (phần chỉ đúng
ở template — lệnh tạo app cắt trong file lớp seed trước khi chép sang app). Ba kiểu dấu (`STYLES`):

  * `swift` — `// <họ>:begin`, `// <họ>:end`, và nhánh thay thế `// <họ>:else-begin` … `// <họ>:else-end` mà dòng ở
    giữa viết dạng comment `// <code>` (khi cắt: bỏ hai dòng dấu và ĐÚNG MỘT `// ` sau phần thụt lề của mỗi dòng; dòng
    chỉ có `//` ⇒ dòng trống). Dấu phải là comment `//` THẬT — không nằm trong chuỗi nhiều dòng hay khối `/* */` (bộ
    quét của `tools/release/lint_debug_symbols.py`). Chữ `<họ>:begin|end|else-begin|else-end` ở bất kỳ đâu khác trên
    một dòng không phải dấu ⇒ lỗi (dấu dính code).
  * `hash` — giống `swift` với `#` thay `//` (`.yml`, `.yaml`, `.toml`, `.sh`); không có kiểm chuỗi/comment.
  * `md` — `<!-- <họ>:begin -->` và `<!-- <họ>:end -->`, KHÔNG có nhánh else. Chỉ dòng ngoài khối code rào (```/~~~)
    mới có thể là dấu; nhắc dấu trong code inline (`` `<!-- sample:begin -->` ``) là chữ, không phải dấu. Một dòng
    còn `<!-- <họ>:…` sau khi bỏ code inline mà không đứng một mình ⇒ lỗi.

Mỗi dấu chiếm TRỌN một dòng (thụt lề + dấu + khoảng trắng cuối). Không cặp, lồng nhau (kể cả `begin` trong khối else),
dòng trong khối else không phải comment ⇒ `BlockError` có số dòng (1-based). Họ khác không bị đụng.

Dòng trống sau khi cắt một khối `begin…end`: nếu ngay trước khối là dòng trống thì các dòng trống ngay sau khối bị bỏ
(không bao giờ hai dòng trống liền nhau do cắt); kiểu `swift` còn bỏ dòng trống đó khi dòng kế là `}`. Khối ở cuối file
⇒ không để dòng trống thừa ở cuối. Kiểu xuống dòng CRLF được giữ.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

STYLES = {"swift": "// ", "hash": "# ", "md": None}   # md: <!-- họ:begin --> … <!-- họ:end -->, không có nhánh else
SUFFIX_STYLE = {".swift": "swift", ".md": "md", ".yml": "hash", ".yaml": "hash", ".toml": "hash", ".sh": "hash"}
KINDS = ("begin", "end", "else-begin", "else-end")
FENCE_RE = re.compile(r"^[ \t]*(```|~~~)")
INLINE_CODE_RE = re.compile(r"(`+).*?\1")


class BlockError(Exception):
    """Dấu khối sai (không cặp, lồng nhau, dính chữ, dòng else không phải comment). `line` = số dòng 1-based."""

    def __init__(self, line: int, message: str):
        super().__init__(f"dòng {line}: {message}")
        self.line = line
        self.message = message


def style_for(rel: str) -> str | None:
    """Kiểu dấu theo đuôi file: `.swift` → swift; `.md` → md; `.yml`/`.yaml`/`.toml`/`.sh` → hash; khác ⇒ None."""
    name = rel.rsplit("/", 1)[-1]
    if "." not in name.lstrip("."):
        return None
    return SUFFIX_STYLE.get("." + name.rsplit(".", 1)[-1])


def _patterns(family: str, style: str):
    if style not in STYLES:
        raise ValueError(f"kiểu dấu lạ: {style!r} (có: {', '.join(STYLES)})")
    fam = re.escape(family)
    if style == "md":
        marker = re.compile(rf"^[ \t]*<!--[ \t]*{fam}:(begin|end)[ \t]*-->[ \t]*$")
        token = re.compile(rf"<!--[ \t]*{fam}:(?:else-begin|else-end|begin|end)(?![\w-])")
        return marker, token, None
    lead = re.escape(STYLES[style].strip())
    marker = re.compile(rf"^[ \t]*{lead} {fam}:(begin|end|else-begin|else-end)[ \t]*$")
    token = re.compile(rf"{fam}:(?:else-begin|else-end|begin|end)(?![\w-])")
    else_line = re.compile(rf"^([ \t]*){lead}(?: (.*))?$")
    return marker, token, else_line


def _real_comment_lines(text: str) -> set[int]:
    """Dòng bắt đầu một comment `//` THẬT của Swift (ngoài chuỗi / khối `/* */`)."""
    release = str(Path(__file__).resolve().parent.parent / "release")
    if release not in sys.path:
        sys.path.insert(0, release)
    import lint_debug_symbols as scanner  # noqa: E402  (bộ quét comment/chuỗi dùng chung)
    lines: set[int] = set()
    scanner.blank_comments_and_strings(text, comment_lines=lines)
    return lines


def walk(text: str, family: str, style: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]], list[tuple[int, str]]]:
    """Một lượt qua văn bản (xuống dòng `\\n`). Trả (dòng giữ lại sau khi cắt [(số dòng gốc, dòng)],
    dấu [(số dòng, loại)], lỗi [(số dòng, thông điệp)]). Có lỗi ⇒ danh sách dòng giữ lại không dùng được."""
    marker_re, token_re, else_re = _patterns(family, style)
    real_comment = _real_comment_lines(text) if style == "swift" else None
    shown = f"<!-- {family}:<loại> -->" if style == "md" else f"{STYLES[style]}{family}:<loại>"
    kept: list[tuple[int, str]] = []
    marks: list[tuple[int, str]] = []
    errors: list[tuple[int, str]] = []
    state, opened = None, 0          # None | "begin" | "else"
    just_cut = False                 # vừa cắt một khối begin…end
    in_fence = False
    for no, line in enumerate(text.split("\n"), 1):
        if style == "md" and FENCE_RE.match(line):
            in_fence = not in_fence
        m = None if in_fence and style == "md" else marker_re.match(line)
        if m is None and not (style == "md" and in_fence):
            probe = INLINE_CODE_RE.sub("", line) if style == "md" else line
            if token_re.search(probe):
                errors.append((no, f"dấu {family} phải chiếm trọn một dòng `{shown}`: {line.strip()}"))
                continue
        if m and real_comment is not None and no not in real_comment:
            errors.append((no, f"dấu {family} nằm trong chuỗi nhiều dòng hoặc khối /* */ — không phải dòng nguồn thật"))
            continue
        if m:
            kind = m.group(1)
            if kind in ("begin", "else-begin"):
                if state is not None:
                    errors.append((no, f"`{family}:{kind}` lồng trong khối `{family}:{state}` mở ở dòng {opened}"))
                    continue
                state, opened = kind.replace("else-begin", "else"), no
            else:
                want = "begin" if kind == "end" else "else"
                if state != want:
                    where = "ngoài mọi khối" if state is None else f"trong khối `{family}:{state}` mở ở dòng {opened}"
                    errors.append((no, f"`{family}:{kind}` không cặp ({where})"))
                    continue
                # Chỉ sau khi CẮT một khối begin…end (dòng trống của khối else là chủ ý, giữ nguyên).
                state, just_cut = None, kind == "end"
            marks.append((no, kind))
            continue
        if state == "begin":
            continue
        if state == "else":
            if line.strip() == "":
                kept.append((no, line))
                continue
            em = else_re.match(line)
            if em is None:
                errors.append((no, f"dòng trong khối `{family}:else` phải là comment `{STYLES[style]}<code>`: "
                                   f"{line.strip()}"))
                continue
            # `<thụt lề>// <code>` ⇒ `<thụt lề><code>`; `<thụt lề>//` trần ⇒ dòng trống.
            line = "" if em.group(2) is None else em.group(1) + em.group(2)
        if just_cut and kept and kept[-1][1].strip() == "":
            if line.strip() == "":
                continue
            if style == "swift" and line.lstrip().startswith("}"):
                kept.pop()
        just_cut = False
        kept.append((no, line))
    if state is not None:
        errors.append((opened, f"`{family}:{'else-begin' if state == 'else' else 'begin'}` không có dấu đóng"))
    return kept, marks, errors


def scan(text: str, family: str, style: str) -> list[tuple[int, str]]:
    """Các dấu của họ `family` [(số dòng, loại)]; dấu sai ⇒ `BlockError` (lỗi đầu tiên theo số dòng)."""
    _, marks, errors = walk(text.replace("\r\n", "\n"), family, style)
    if errors:
        no, msg = min(errors)
        raise BlockError(no, msg)
    return marks


def cut(text: str, family: str, style: str) -> str:
    """Văn bản sau khi cắt mọi khối `family:begin…end` (kể cả dòng dấu) và bỏ comment nhánh else. Sai ⇒ `BlockError`."""
    crlf = "\r\n" in text
    kept, _, errors = walk(text.replace("\r\n", "\n"), family, style)
    if errors:
        no, msg = min(errors)
        raise BlockError(no, msg)
    out = "\n".join(line for _, line in kept)
    return out.replace("\n", "\r\n") if crlf else out
