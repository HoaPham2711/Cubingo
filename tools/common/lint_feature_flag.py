#!/usr/bin/env python3
"""Giữ biên giữa lõi và khối tuỳ chọn: cờ `FEATURE_*` chỉ sống ở `AppHost/`, và `Core/` không biết khối tuỳ chọn.

Bốn luật:
  (a) chuỗi `FEATURE_<TÊN>` (cờ biên dịch do `Features.generated.yml` đặt) KHÔNG được xuất hiện dưới `Core/`,
      `CoreOptional/`, `CoreTests/`, `CoreOptionalTests/`. Khối tuỳ chọn chỉ được biên dịch khi tính năng bật nên
      không cần cờ; `Core/` giống hệt nhau ở mọi app nên không được rẽ nhánh theo cờ — cần rẽ nhánh thì đọc
      `AppConfig.features` lúc chạy, còn chỗ chọn cài đặt cụ thể nằm ở `AppHost/`.
  (b) `Core/` và `CoreTests/` không được nhắc tên thư mục `CoreOptional` hay bất kỳ kiểu nào khai trong
      `CoreOptional/`. Target `CoreOnly` biên dịch `Core/` một mình và `AppHostTests` biên dịch `CoreTests/` cả
      khi tính năng tắt ⇒ tham chiếu như vậy làm hỏng build; lint này bắt sớm, trước khi phải build.

  (c) trong `.swift` dưới `AppHost/`, tên kiểu khai trong `CoreOptional/<Khối>/` (và chữ `CoreOptional`) chỉ được xuất
      hiện trong vùng `#if <cờ của khối>` … (`#else` | `#elseif` | `#endif`) — đã bỏ comment `//` và `/* */`. Cờ ↔
      thư mục khối lấy từ `appconfig.OPTIONAL_BLOCKS`. Vùng được tính theo điều kiện: `FLAG`, `FLAG && X` thì được;
      `!FLAG`, nhánh `#else` của `#if FLAG`, `FLAG || X` thì KHÔNG (nhánh đó vẫn biên dịch khi cờ tắt). Chuỗi ký tự
      KHÔNG bị bỏ nội dung (chỉ để nhận ra `//` nằm trong chuỗi): tên khối trong chuỗi ngoài vùng vẫn bị báo — chủ
      ý, thà báo thừa (đưa vào `#if` hoặc đổi chuỗi) còn hơn lọt một tham chiếu thật qua `"\\(Kiểu())"`.
  (d) `FEATURE_*` dưới `AppHost/` chỉ được ở `AppHost/AppHost/AppHostApp.swift` (chỗ duy nhất rẽ nhánh theo cờ).

Chạy tay:  python3 tools/common/lint_feature_flag.py [--root <gốc repo>]
Tự động:   tools/template/selfcheck.sh (bước 1), .githooks/pre-commit khi commit đụng .swift
Exit: 0 sạch, 1 có vi phạm, 2 không thấy thư mục nguồn nào.
"""
from __future__ import annotations

import argparse
import itertools
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appconfig  # noqa: E402

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = "AppHost"
FLAG_ALLOWED_FILE = "AppHost/AppHost/AppHostApp.swift"
# (a) mọi nơi KHÔNG phải AppHost/.
FLAG_FORBIDDEN_DIRS = ("Core", "CoreOptional", "CoreTests", "CoreOptionalTests")
# (b) nơi không được biết khối tuỳ chọn.
OPTIONAL_FORBIDDEN_DIRS = ("Core", "CoreTests")
OPTIONAL_DIR = "CoreOptional"
FLAG = re.compile(r"\bFEATURE_[A-Z0-9_]+\b")
TYPE_DECL = re.compile(
    r"^\s*(?:@\w+\s+)*(?:(?:public|internal|private|fileprivate|final|open)\s+)*"
    r"(?:class|struct|enum|protocol|actor)\s+([A-Z]\w*)", re.M)


def swift_files(root: Path, dirs: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        if (root / d).is_dir():
            out.extend(sorted((root / d).rglob("*.swift")))
    return out


def optional_type_names(root: Path) -> set[str]:
    names: set[str] = set()
    for f in swift_files(root, (OPTIONAL_DIR,)):
        names |= set(TYPE_DECL.findall(f.read_text(encoding="utf-8", errors="ignore")))
    return names


def lint(root: Path) -> list[str]:
    problems: list[str] = []
    for f in swift_files(root, FLAG_FORBIDDEN_DIRS):
        rel = f.relative_to(root).as_posix()
        for no, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            for m in FLAG.finditer(line):
                problems.append(f"{rel}:{no}: {m.group(0)} — cờ FEATURE_* chỉ được dùng trong AppHost/")
    names = optional_type_names(root)
    patterns = [(OPTIONAL_DIR, re.compile(rf"\b{OPTIONAL_DIR}\b"))]
    patterns += [(n, re.compile(rf"\b{re.escape(n)}\b")) for n in sorted(names)]
    for f in swift_files(root, OPTIONAL_FORBIDDEN_DIRS):
        rel = f.relative_to(root).as_posix()
        for no, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            for name, rx in patterns:
                if rx.search(line):
                    problems.append(f"{rel}:{no}: nhắc {name} — Core/CoreTests không được biết khối tuỳ chọn "
                                    f"(CoreOnly và AppHostTests biên dịch khi tính năng tắt)")
    return problems


def strip_comments(text: str) -> str:
    """Thay comment `//` và `/* */` (Swift cho lồng nhau) bằng khoảng trắng, giữ nguyên số dòng. Chuỗi `"..."` được
    bỏ qua khi tìm comment nhưng nội dung giữ nguyên (xem luật (c) ở docstring)."""
    out: list[str] = []
    i, n, depth = 0, len(text), 0
    while i < n:
        two = text[i:i + 2]
        if depth:
            if two == "/*":
                depth += 1
                out.append("  "); i += 2
            elif two == "*/":
                depth -= 1
                out.append("  "); i += 2
            else:
                out.append("\n" if text[i] == "\n" else " "); i += 1
        elif two == "//":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i)); i = j
        elif two == "/*":
            depth = 1
            out.append("  "); i += 2
        elif text[i] == '"':
            j = i + 1
            while j < n and text[j] != "\n" and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(text[i:j]); i = j
        else:
            out.append(text[i]); i += 1
    return "".join(out)


COND_TOKEN = re.compile(r"\s*(&&|\|\||!|\(|\)|[\w.]+(?:\([^()]*\))?)")


def parse_cond(cond: str):
    """Cây điều kiện `#if`: ('atom', tên) | ('not', x) | ('and', a, b) | ('or', a, b). Không hiểu ⇒ None."""
    toks: list[str] = []
    pos, cond = 0, cond.strip()
    while pos < len(cond):
        m = COND_TOKEN.match(cond, pos)
        if not m:
            return None
        toks.append(m.group(1)); pos = m.end()
    idx = [0]

    def peek():
        return toks[idx[0]] if idx[0] < len(toks) else None

    def take():
        idx[0] += 1
        return toks[idx[0] - 1]

    def p_or():
        left = p_and()
        while peek() == "||":
            take(); left = ("or", left, p_and())
        return left

    def p_and():
        left = p_not()
        while peek() == "&&":
            take(); left = ("and", left, p_not())
        return left

    def p_not():
        t = peek()
        if t == "!":
            take(); return ("not", p_not())
        if t == "(":
            take(); e = p_or()
            if take() != ")":
                raise ValueError
            return e
        if t is None or t in ("&&", "||", ")"):
            raise ValueError
        return ("atom", take())

    try:
        tree = p_or()
    except (ValueError, IndexError):
        return None
    return tree if idx[0] == len(toks) else None


def atoms_of(tree) -> set[str]:
    if tree[0] == "atom":
        return {tree[1]}
    return set().union(*(atoms_of(c) for c in tree[1:]))


def evaluate(tree, env: dict[str, bool]) -> bool:
    k = tree[0]
    if k == "atom":
        return env[tree[1]]
    if k == "not":
        return not evaluate(tree[1], env)
    if k == "and":
        return evaluate(tree[1], env) and evaluate(tree[2], env)
    return evaluate(tree[1], env) or evaluate(tree[2], env)


def branch_needs_flag(chain: list, branch_is_else: bool, flag: str) -> bool:
    """Nhánh hiện tại (điều kiện cuối của `chain`, hoặc `#else` sau cả chuỗi) có chắc chắn kéo theo `flag` không?
    = không có cách gán nào của các cờ khác làm nhánh đó chạy khi `flag` tắt. Điều kiện không hiểu ⇒ False."""
    if any(c is None for c in chain):
        return False
    atoms = set().union(*(atoms_of(c) for c in chain)) - {flag}
    if len(atoms) > 10:
        return False
    names = sorted(atoms)
    for values in itertools.product((False, True), repeat=len(names)):
        env = dict(zip(names, values)); env[flag] = False
        earlier = chain if branch_is_else else chain[:-1]
        if any(evaluate(c, env) for c in earlier):
            continue
        if branch_is_else or evaluate(chain[-1], env):
            return False
    return True


DIRECTIVE = re.compile(r"^\s*#(if|elseif|else|endif)\b(.*)$")


def allowed_lines(text: str, flags: list[str]) -> dict[str, set[int]]:
    """{cờ: tập số dòng (1-based) nằm trong vùng kéo theo cờ đó}. `text` đã bỏ comment."""
    result = {f: set() for f in flags}
    stack: list[dict] = []  # mỗi khung: {"chain": [cây…], "else": bool}
    for no, line in enumerate(text.splitlines(), start=1):
        m = DIRECTIVE.match(line)
        if m:
            kind, rest = m.groups()
            if kind == "if":
                stack.append({"chain": [parse_cond(rest)], "else": False})
            elif kind == "elseif" and stack:
                stack[-1]["chain"].append(parse_cond(rest))
            elif kind == "else" and stack:
                stack[-1]["else"] = True
            elif kind == "endif" and stack:
                stack.pop()
            continue
        for f in flags:
            if any(branch_needs_flag(fr["chain"], fr["else"], f) for fr in stack):
                result[f].add(no)
    return result


def lint_apphost(root: Path) -> list[str]:
    """Luật (c) và (d) cho `.swift` dưới `AppHost/`."""
    problems: list[str] = []
    blocks = []
    for b in appconfig.OPTIONAL_BLOCKS:
        names: set[str] = set()
        for f in sorted((root / b["src"]).rglob("*.swift")) if (root / b["src"]).is_dir() else []:
            names |= set(TYPE_DECL.findall(f.read_text(encoding="utf-8", errors="ignore")))
        blocks.append((b["flag"], b["src"], names))
    flags = [b[0] for b in blocks]
    for f in swift_files(root, (APP_DIR,)):
        rel = f.relative_to(root).as_posix()
        raw = f.read_text(encoding="utf-8", errors="ignore")
        if rel != FLAG_ALLOWED_FILE:
            for no, line in enumerate(raw.splitlines(), start=1):
                for m in FLAG.finditer(line):
                    problems.append(f"{rel}:{no}: {m.group(0)} — cờ FEATURE_* chỉ được dùng trong {FLAG_ALLOWED_FILE}")
        code = strip_comments(raw)
        allowed = allowed_lines(code, flags)
        for no, line in enumerate(code.splitlines(), start=1):
            for flag, src, names in blocks:
                pats = [(src.split("/")[0], re.compile(rf"\b{re.escape(src.split('/')[0])}\b"))]
                pats += [(n, re.compile(rf"\b{re.escape(n)}\b")) for n in sorted(names)]
                for name, rx in pats:
                    # Chữ `CoreOptional` chung cho mọi khối: được phép trong vùng của BẤT KỲ cờ nào.
                    ok = no in allowed[flag] if name in names else any(no in allowed[g] for g in flags)
                    if rx.search(line) and not ok:
                        problems.append(f"{rel}:{no}: nhắc {name} ngoài `#if {flag}` — khối tuỳ chọn chỉ được "
                                        f"biên dịch khi tính năng bật, tham chiếu ngoài vùng làm hỏng build khi tắt")
    return sorted(set(problems), key=lambda p: (p.split(":")[0], int(p.split(":")[1]), p))


def main() -> int:
    ap = argparse.ArgumentParser(description="Cờ FEATURE_* chỉ ở AppHost/; Core/ không biết CoreOptional/")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="gốc repo cần quét (mặc định: gốc của script)")
    root = Path(ap.parse_args().root).resolve()
    if not swift_files(root, FLAG_FORBIDDEN_DIRS) and not any((root / d).is_dir() for d in FLAG_FORBIDDEN_DIRS):
        print(f"FAIL: không tìm thấy thư mục nguồn nào ({', '.join(FLAG_FORBIDDEN_DIRS)}) dưới {root}")
        return 2
    problems = lint(root) + lint_apphost(root)
    if problems:
        print("FAIL: vi phạm biên lõi / khối tuỳ chọn:")
        for p in problems:
            print("  " + p)
        return 1
    print("OK: cờ FEATURE_* chỉ ở AppHost/, Core/ và CoreTests/ không biết khối tuỳ chọn, "
          "AppHost/ chỉ nhắc khối trong #if của khối")
    return 0


if __name__ == "__main__":
    sys.exit(main())
