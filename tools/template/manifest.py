#!/usr/bin/env python3
"""Ba lớp sở hữu của mọi file đang track (`template.manifest.toml`) + cổng "mọi file có lớp".

    python3 tools/template/manifest.py check [--staged] [--root R]          # rc 0 sạch · 1 vi phạm · 2 manifest hỏng
    python3 tools/template/manifest.py classify <đường dẫn>… [--root R]     # in lớp của từng đường dẫn
    python3 tools/template/manifest.py list <lớp> [--root R]                # in các file track thuộc lớp đó

Ba lớp:
  * `sync`          — template sở hữu, giống hệt từng byte ở mọi app (lệnh đồng bộ thay nguyên file);
  * `seed`          — chép một lần lúc tạo app, sau đó app sở hữu; file trong `overlay_dir` (thư mục gieo) đè lên /
                      tạo ra file cùng đường dẫn tương đối trong app;
  * `template_only` — không bao giờ tới app.

Lược đồ manifest (TOML, đọc bằng `tomllib`):

    schema = 1
    [sync]
    paths = ["Core/", …]                    # kết thúc bằng "/" = cả thư mục; không thì đúng một file
    [seed]
    paths = ["app.config.toml", "AppHost/", …]
    overlay_dir = "tools/template/seed"      # tuỳ chọn
    [template_only]
    paths = [ … ]

Luật phân lớp: mục khai DÀI NHẤT khớp đường dẫn thắng (`.claude/skills/` là sync, một thư mục con khai riêng ở lớp
khác thắng nó). Cùng một mục khai ở hai lớp ⇒ manifest hỏng (rc 2).

`check` báo (mỗi vi phạm một dòng):
  (a) file track không thuộc lớp nào;
  (b) mục khai không khớp file track nào;
  (c) file trong `overlay_dir` mà đường dẫn đích đang là file track của template và không thuộc `template_only`;
  (d) file text lớp `sync`/`seed` nhắc — trong backtick hoặc đích link Markdown — đường dẫn RESOLVE được tới một file
      track lớp `template_only` (từ gốc repo; link Markdown tương đối thì thử thêm từ thư mục của file nhắc; từ trong
      backtick mở đầu bằng `./`/`../` thì tính từ thư mục của file nhắc). Đường dẫn
      là đích của thư mục gieo được miễn (app có file đó). Thư mục, tên trần không resolve, file nhị phân/không UTF-8
      không tính. File lớp `seed` được soi theo đúng nội dung app nhận: sau khi cắt khối `template:` (`blocks.py`;
      số dòng báo lỗi là số dòng gốc);
  (e) khối `template:begin`/`template:end` sai (không cặp, lồng nhau, dấu dính chữ) trong file lớp `seed`;
  (f) `CHANGELOG.md` lớp `template_only` (tức là của template): mục `## Chưa phát hành` (nếu có) và mọi mục
      `## vX.Y.Z — …` từ v0.4.0 phải có tiểu mục `### Việc phải làm tay khi lên bản này` (lệnh đồng bộ in nó cho app;
      v0.1.0–v0.3.0 được miễn).

`check --staged` (pre-commit): danh sách file đọc từ index git ĐANG commit — `GIT_INDEX_FILE` của hook được giữ khi nó
thuộc chính repo `--root` (`git commit -a` dựng index tạm; `.git/index` lúc đó là nội dung cũ).
Ở app (`core.lock` được TRACK — trong HEAD hoặc index; xem `is_app`) `check` chỉ in một dòng nhắc và rc 0 — cổng của app
là `sync_core.py check`. `core.lock` lạc chưa track ở template KHÔNG làm nó thành app.
    python3 tools/template/manifest.py is-app [--staged] [--root R]         # rc 0 app · 1 template · 2 không phải repo git

Mọi lệnh git: môi trường đã gỡ `GIT_*` (hook đặt `GIT_DIR`, thắng `-C`; riêng `--staged` giữ `GIT_INDEX_FILE` như trên),
`--no-optional-locks`, `core.quotePath=false`, tên tách bằng NUL (`ls-files -z`) ⇒ tên có dấu cách / không ASCII đúng.
Tool chỉ đọc, không ghi gì.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import posixpath
import re
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blocks  # noqa: E402  (bộ cắt khối dùng chung)

MANIFEST_FILE = "template.manifest.toml"
LOCK_FILE = "core.lock"     # có ở gốc ⇔ đây là app (sync_core.py)
SCHEMA = 1
CLASSES = ("sync", "seed", "template_only")
SECTION_KEYS = {"sync": {"paths"}, "seed": {"paths", "overlay_dir"}, "template_only": {"paths"}}
TEXT_SUFFIXES = {".md", ".swift", ".py", ".sh", ".yml", ".yaml", ".toml", ".json", ".js", ".txt"}

BACKTICK_RE = re.compile(r"`([^`\n]+)`")
MD_LINK_RE = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# Hậu tố không thuộc đường dẫn: `file.md:12`, `file.md:12-20`, `file.md#muc`.
LINE_SUFFIX_RE = re.compile(r":\d+(?:-\d+)?$")
WORD_STRIP = "\"'()[]{}<>,;"


class ManifestError(Exception):
    """Manifest hỏng / không đọc được / gốc không phải repo git (CLI rc 2)."""


# ---------------------------------------------------------------- manifest

def _check_entry(cls: str, entry) -> str:
    if not isinstance(entry, str) or not entry:
        raise ManifestError(f"[{cls}] paths: mục phải là chuỗi khác rỗng, gặp {entry!r}")
    parts = entry.rstrip("/").split("/")
    if (entry.startswith("/") or "\\" in entry or "//" in entry
            or any(p in ("", ".", "..") for p in parts)):
        raise ManifestError(f"[{cls}] paths: \"{entry}\" phải là đường dẫn tương đối chuẩn (không '/', '.', '..', '\\' thừa)")
    return entry


def validate(data: dict) -> dict:
    """Kiểm lược đồ của dict đã đọc từ TOML; trả bản chuẩn hoá cùng hình. Sai ⇒ ManifestError."""
    if not isinstance(data, dict):
        raise ManifestError("manifest phải là một bảng TOML")
    unknown = set(data) - {"schema", *CLASSES}
    if unknown:
        raise ManifestError(f"khoá lạ ở gốc manifest: {', '.join(sorted(unknown))}")
    if data.get("schema") != SCHEMA or isinstance(data.get("schema"), bool):
        raise ManifestError(f"schema phải là {SCHEMA}, gặp {data.get('schema')!r}")
    out: dict = {"schema": SCHEMA}
    owner: dict[str, str] = {}
    for cls in CLASSES:
        sec = data.get(cls)
        if not isinstance(sec, dict):
            raise ManifestError(f"thiếu bảng [{cls}]")
        extra = set(sec) - SECTION_KEYS[cls]
        if extra:
            raise ManifestError(f"[{cls}]: khoá lạ {', '.join(sorted(extra))}")
        paths = sec.get("paths")
        if not isinstance(paths, list):
            raise ManifestError(f"[{cls}] paths phải là một danh sách")
        clean = []
        for entry in paths:
            entry = _check_entry(cls, entry)
            if entry in owner:
                where = "cùng lớp" if owner[entry] == cls else f"cả [{owner[entry]}] lẫn [{cls}]"
                raise ManifestError(f"\"{entry}\" khai hai lần ({where})")
            owner[entry] = cls
            clean.append(entry)
        out[cls] = {"paths": clean}
        if cls == "seed" and "overlay_dir" in sec:
            od = sec["overlay_dir"]
            if not isinstance(od, str) or not od:
                raise ManifestError("[seed] overlay_dir phải là chuỗi khác rỗng")
            out[cls]["overlay_dir"] = _check_entry("seed.overlay_dir", od).rstrip("/")
    return out


def load(root: Path) -> dict:
    """Đọc + kiểm `template.manifest.toml` ở gốc. Thiếu file / TOML hỏng / sai lược đồ ⇒ ManifestError."""
    path = Path(root) / MANIFEST_FILE
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise ManifestError(f"không đọc được {MANIFEST_FILE}: {e.strerror or e}") from None
    return parse(raw)


def parse(raw: bytes) -> dict:
    """Đọc + kiểm manifest từ bytes (vd blob trong index). TOML hỏng / sai lược đồ ⇒ ManifestError."""
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise ManifestError(f"{MANIFEST_FILE} không phải TOML hợp lệ: {e}") from None
    return validate(data)


def _matches(entry: str, rel: str) -> bool:
    return rel.startswith(entry) if entry.endswith("/") else rel == entry


def classify(manifest: dict, rel: str) -> str | None:
    """Lớp của `rel` theo mục khai dài nhất khớp; không mục nào khớp ⇒ None. Một mục ở hai lớp ⇒ ManifestError."""
    best: tuple[int, str] | None = None
    seen: dict[str, str] = {}
    for cls in CLASSES:
        for entry in manifest[cls]["paths"]:
            if entry in seen and seen[entry] != cls:
                raise ManifestError(f"\"{entry}\" khai ở cả [{seen[entry]}] lẫn [{cls}]")
            seen[entry] = cls
            if _matches(entry, rel) and (best is None or len(entry) > best[0]):
                best = (len(entry), cls)
    return best[1] if best else None


# ---------------------------------------------------------------- git + file

def _clean_env() -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(root: Path, *args: str, env: dict | None = None, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "--no-optional-locks", "-c", "core.quotePath=false", "-C", str(root), *args],
                          capture_output=True, env=_clean_env() if env is None else env, input=stdin)


def hook_index(root: Path) -> str | None:
    """Đường dẫn TUYỆT ĐỐI của index git đang commit, khi tool chạy trong pre-commit của chính repo ở `root`.

    `git commit -a` / `git commit <đường dẫn>` dựng index tạm (`.git/index.lock`, `.git/next-index-*.lock`) và đặt
    `GIT_INDEX_FILE` cho hook; gỡ hết `GIT_*` rồi đọc `.git/index` là đọc nội dung CŨ (sửa tay lọt qua). Chỉ nhận khi
    file đó nằm trong git dir (hoặc common dir) của `root`; trỏ index của repo KHÁC ⇒ ManifestError (không đoán, không
    lặng lẽ đọc `.git/index`). Chưa đặt / `root` không phải repo git ⇒ None.
    Đường dẫn tương đối (commit thường: `.git/index`) tính từ cwd — cwd của hook là gốc work tree."""
    raw = os.environ.get("GIT_INDEX_FILE")
    if not raw:
        return None
    idx = os.path.realpath(raw if os.path.isabs(raw) else os.path.join(os.getcwd(), raw))
    try:
        r = _git(root, "rev-parse", "--absolute-git-dir", "--git-common-dir")
    except OSError:
        return None
    if r.returncode != 0:
        return None
    lines = r.stdout.decode("utf-8", "surrogateescape").splitlines()
    dirs = set()
    for d in lines[:2]:
        d = d if os.path.isabs(d) else os.path.join(str(root), d)
        dirs.add(os.path.realpath(d))
    if any(os.path.dirname(idx) == d for d in dirs):
        return idx
    raise ManifestError(f"GIT_INDEX_FILE={raw} không thuộc repo {root} — không biết index nào đang được commit"
                        " (chạy lệnh trong chính repo đó, hoặc bỏ biến này)")


def is_app(root: Path, *, staged: bool = False) -> bool | None:
    """MỘT nơi quyết định "đây là app": `core.lock` được TRACK — có trong HEAD hoặc trong index (`staged=True`: index git
    đang commit, `hook_index`). Chỉ có file trên đĩa (chưa track) KHÔNG tính: template có lock lạc vẫn là template; app
    xoá/gỡ lock vẫn là app (cổng lệch lõi báo lock bị gỡ). Commit đầu của app mới (HEAD chưa có, lock đã stage) ⇒ app.
    `root` không phải repo git ⇒ None (người gọi tự quyết theo đĩa và nói rõ).
    Đây là vị từ "lock được track" (nhắc Ruling 6 của `check`, thông báo của sync_core). Pre-commit và cổng 15 KHÔNG dùng
    hàm này: chúng nhận diện DƯƠNG template (`new_app.py` của template (thư mục tools/template) được track) bằng git thuần, mọi repo khác là app
    — app gỡ lock (kể cả đã commit) hay xoá tool Python vẫn bị chặn."""
    env = git_env(root, staged=staged)
    try:
        r = _git(root, "rev-parse", "--is-inside-work-tree", env=env)
    except OSError:
        return None
    if r.returncode != 0 or r.stdout.strip() != b"true":
        return None
    if _git(root, "cat-file", "-e", f"HEAD:./{LOCK_FILE}", env=env).returncode == 0:
        return True
    r = _git(root, "ls-files", "-z", "--", f":(literal){LOCK_FILE}", env=env)
    return LOCK_FILE in r.stdout.decode("utf-8", "surrogateescape").split("\0")


def git_env(root: Path, *, staged: bool = False) -> dict:
    """Môi trường cho lệnh git trên repo `root`: gỡ mọi `GIT_*`; `staged=True` giữ lại index của hook (`hook_index`)."""
    env = _clean_env()
    if staged:
        idx = hook_index(root)
        if idx:
            env["GIT_INDEX_FILE"] = idx
    return env


def tracked(root: Path, *, staged: bool = False) -> list[str]:
    """Đường dẫn tương đối (dấu `/`) của mọi file trong index của repo ở `root`, đã sắp xếp. `staged=True` (pre-commit):
    đọc đúng index git đang commit (`hook_index`)."""
    try:
        r = _git(root, "ls-files", "-z", env=git_env(root, staged=staged))
    except OSError as e:
        raise ManifestError(f"không chạy được git: {e}") from None
    if r.returncode != 0:
        msg = r.stderr.decode("utf-8", "replace").strip()
        raise ManifestError(f"{root}: không phải repo git ({msg})")
    return sorted(p for p in r.stdout.decode("utf-8", "surrogateescape").split("\0") if p)


def overlay_targets(root: Path, manifest: dict, files: list[str] | None = None) -> list[str]:
    """Đường dẫn ĐÍCH (tương đối gốc app) của các file track trong `overlay_dir`. Chưa có thư mục/khai ⇒ []."""
    od = manifest["seed"].get("overlay_dir")
    if not od:
        return []
    prefix = od + "/"
    files = tracked(root) if files is None else files
    return sorted(f[len(prefix):] for f in files if f.startswith(prefix))


def digest(path: Path) -> str:
    """sha256 hex của nội dung; thêm hậu tố "+x" khi file có bit thực thi CỦA CHỦ (git chỉ ghi bit này: 100755 /
    100644 — template và app checkout bằng git luôn cùng kết quả dù umask khác). Symlink ⇒ ManifestError."""
    path = Path(path)
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode):
        raise ManifestError(f"{path}: là symlink — không băm")
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest() + ("+x" if st.st_mode & 0o100 else "")


# ---------------------------------------------------------------- hàm móc của khối `template:`

def seed_lines_in_app(rel: str, text: str) -> list[tuple[int, str]]:
    """Các dòng (số dòng GỐC, nội dung) của file lớp seed mà APP nhận được — tức là sau khi cắt khối `template:`
    (lệnh tạo app cắt đúng như vậy). Kiểu file không có dấu (`blocks.style_for` = None), không có chữ `template:`, hay
    khối sai (luật e báo) ⇒ mọi dòng. Luật (d) soi đúng danh sách này."""
    style = blocks.style_for(rel)
    normalized = text.replace("\r\n", "\n")
    if style is None or "template:" not in normalized:
        return list(enumerate(text.splitlines(), start=1))
    kept, _, errors = blocks.walk(normalized, "template", style)
    if errors:
        return list(enumerate(text.splitlines(), start=1))
    if kept and kept[-1][1] == "" and normalized.endswith("\n"):
        kept = kept[:-1]          # phần tử rỗng sau dấu xuống dòng cuối (splitlines không có)
    return kept


def template_block_problems(rel: str, text: str) -> list[str]:
    """Luật (e): khối `template:begin`/`template:end` sai trong file lớp seed (lỗi đầu tiên), dạng `file:dòng: …`."""
    style = blocks.style_for(rel)
    if style is None or "template:" not in text:
        return []
    try:
        blocks.scan(text, "template", style)
    except blocks.BlockError as e:
        return [f"{rel}:{e.line}: {e.message}"]
    return []


# ---------------------------------------------------------------- luật (d)

def _is_text(rel: str) -> bool:
    return posixpath.splitext(posixpath.basename(rel))[1] in TEXT_SUFFIXES or "." not in posixpath.basename(rel).lstrip(".")


def _read_text(path: Path) -> str | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _clean_word(word: str) -> str | None:
    word = word.strip(WORD_STRIP).rstrip(".:")
    word = word.split("#", 1)[0]
    word = LINE_SUFFIX_RE.sub("", word)
    if not word or any(c in word for c in "*?$<>{}|\\") or "://" in word or word.startswith("/"):
        return None
    return word


def _resolve(word: str, rel_dir: str, is_link: bool) -> list[str]:
    """Các ứng viên đường dẫn chuẩn hoá (tương đối gốc) của một từ; ứng viên thoát gốc bị bỏ.
    Từ gốc repo; link Markdown thử thêm từ thư mục của file nhắc; từ trong backtick bắt đầu bằng `./`/`../` thì CHỈ
    tính từ thư mục của file nhắc (rõ ràng là đường dẫn tương đối)."""
    if word.startswith(("./", "../")) and not is_link:
        bases = [rel_dir]
    else:
        bases = ["", rel_dir] if is_link else [""]
    out = []
    for base in bases:
        p = posixpath.normpath(posixpath.join(base, word))
        if p not in (".", "..") and not p.startswith("../") and p not in out:
            out.append(p)
    return out


def references(rel: str, line: str) -> list[tuple[str, bool]]:
    """Các từ trông như đường dẫn trong backtick hoặc đích link Markdown của một dòng (chưa resolve), kèm cờ
    "là đích link"."""
    words = []
    for m in BACKTICK_RE.finditer(line):
        words.extend((w, False) for w in m.group(1).split())
    for m in MD_LINK_RE.finditer(line):
        words.append((m.group(1), True))
    out = []
    for w, is_link in words:
        c = _clean_word(w)
        if c:
            out.append((c, is_link))
    return out


def _template_only_refs(root: Path, manifest: dict, files: list[str], classes: dict[str, str | None],
                        exempt: set[str]) -> list[str]:
    tonly = {f for f in files if classes[f] == "template_only"} - exempt
    if not tonly:
        return []
    problems = []
    for rel in files:
        cls = classes[rel]
        if cls not in ("sync", "seed") or not _is_text(rel):
            continue
        text = _read_text(Path(root) / rel)
        if text is None:
            continue
        lines = seed_lines_in_app(rel, text) if cls == "seed" else enumerate(text.splitlines(), start=1)
        rel_dir = posixpath.dirname(rel)
        for no, line in lines:
            hits = []
            for word, is_link in references(rel, line):
                for cand in _resolve(word, rel_dir, is_link):
                    if cand in tonly and cand not in hits:
                        hits.append(cand)
            for target in hits:
                problems.append(f"{rel}:{no}: nhắc {target} — file lớp template_only, không có ở app")
    return problems


# ---------------------------------------------------------------- CHANGELOG của template (luật f + lệnh đồng bộ)

CHANGELOG_FILE = "CHANGELOG.md"
UNRELEASED_TITLE = "Chưa phát hành"
MANUAL_HEADING = "### Việc phải làm tay khi lên bản này"
MANUAL_FROM = (0, 4, 0)     # mục từ bản này trở lên bắt buộc có tiểu mục việc tay (v0.1.0–v0.3.0 được miễn)
VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
SECTION_RE = re.compile(r"^## (?P<title>\S.*?)\s*$")


def version_key(tag: str | None) -> tuple[int, int, int] | None:
    """`vX.Y.Z` ⇒ (X, Y, Z) để so theo SỐ (`v0.10.0` > `v0.9.0`); dạng khác ⇒ None."""
    m = VERSION_RE.match(tag or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def changelog_sections(text: str) -> list[dict]:
    """Các mục `## …` của CHANGELOG: `{"line", "title", "tag", "version", "manual"}`. Tiêu đề mục bản là
    `## vX.Y.Z — YYYY-MM-DD` (`tag` = `vX.Y.Z`, `version` = bộ số); `## Chưa phát hành` có `tag`/`version` = None.
    `manual` = các dòng dưới tiểu mục `### Việc phải làm tay khi lên bản này` (tới tiêu đề `##`/`###` kế tiếp, bỏ dòng
    trống đầu/cuối), None khi mục không có tiểu mục đó."""
    out: list[dict] = []
    cur: dict | None = None
    collecting = False
    for no, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        m = SECTION_RE.match(line)
        if m:
            title = m.group("title")
            tag = title.split()[0]
            ver = version_key(tag)
            cur = {"line": no, "title": title, "tag": tag if ver else None, "version": ver, "manual": None}
            out.append(cur)
            collecting = False
            continue
        if cur is None:
            continue
        if line.rstrip() == MANUAL_HEADING:
            cur["manual"] = []
            collecting = True
            continue
        if line.startswith("### ") or line.startswith("# "):
            collecting = False
            continue
        if collecting:
            cur["manual"].append(line.rstrip())
    for sec in out:
        lines = sec["manual"]
        if lines is not None:
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
    return out


def changelog_problems(text: str) -> list[str]:
    """Luật (f): mục `## Chưa phát hành` (nếu có) và mọi mục bản từ v0.4.0 phải có tiểu mục việc tay."""
    problems = []
    for sec in changelog_sections(text):
        need = sec["title"] == UNRELEASED_TITLE or (sec["version"] is not None and sec["version"] >= MANUAL_FROM)
        if need and sec["manual"] is None:
            problems.append(f"{CHANGELOG_FILE}:{sec['line']}: mục \"## {sec['title']}\" thiếu tiểu mục "
                            f"\"{MANUAL_HEADING}\" (lệnh đồng bộ in tiểu mục này cho app; không có gì thì ghi \"- Không có.\")")
    return problems


# ---------------------------------------------------------------- check

def check(root: Path, *, staged: bool = False) -> list[str]:
    """Danh sách vi phạm của luật (a)–(e) (rỗng = sạch). Manifest hỏng ⇒ ManifestError. `staged=True` (pre-commit):
    danh sách file lấy từ index git đang commit (`hook_index`)."""
    root = Path(root)
    manifest = load(root)
    files = tracked(root, staged=staged)
    classes = {f: classify(manifest, f) for f in files}
    problems = []
    # (a)
    for f in files:
        if classes[f] is None:
            problems.append(f"{f}: chưa thuộc lớp nào — thêm vào {MANIFEST_FILE} (sync / seed / template_only)")
    # (b)
    for cls in CLASSES:
        for entry in manifest[cls]["paths"]:
            if not any(_matches(entry, f) for f in files):
                problems.append(f"{MANIFEST_FILE}: mục \"{entry}\" ([{cls}]) không khớp file track nào")
    # (c)
    od = manifest["seed"].get("overlay_dir")
    targets = overlay_targets(root, manifest, files)
    known = set(files)
    for t in targets:
        if t in known and classes[t] != "template_only":
            problems.append(f"{od}/{t}: đè lên {t} đang thuộc lớp {classes[t] or '(chưa phân lớp)'}"
                            " — thư mục gieo chỉ được đè file template_only hoặc tạo file mới")
    # (d)
    problems.extend(_template_only_refs(root, manifest, files, classes, set(targets)))
    # (e)
    for f in files:
        if classes[f] == "seed":
            text = _read_text(root / f)
            if text is not None:
                problems.extend(template_block_problems(f, text))
    # (f) — CHANGELOG của TEMPLATE (lớp template_only; ở app thì CHANGELOG.md là release notes của app, không soi)
    if CHANGELOG_FILE in known and classes[CHANGELOG_FILE] == "template_only":
        text = _read_text(root / CHANGELOG_FILE)
        if text is not None:
            problems.extend(changelog_problems(text))
    return problems


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=str(Path(__file__).resolve().parents[2]),
                        help="gốc repo (mặc định suy từ vị trí script)")
    ap = argparse.ArgumentParser(description="Ba lớp sở hữu file (template.manifest.toml) + cổng mọi file có lớp")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_check = sub.add_parser("check", parents=[common], help="kiểm manifest (rc 0 sạch · 1 vi phạm · 2 hỏng)")
    p_check.add_argument("--staged", action="store_true",
                         help="đọc index git đang commit (pre-commit: tôn trọng GIT_INDEX_FILE của hook)")
    p_cls = sub.add_parser("classify", parents=[common], help="in lớp của từng đường dẫn")
    p_cls.add_argument("paths", nargs="+")
    p_app = sub.add_parser("is-app", parents=[common],
                           help="core.lock có được track (HEAD hoặc index)? in app/template; rc 0 app · 1 template · 2 "
                                "không phải repo git")
    p_app.add_argument("--staged", action="store_true", help="xét index git đang commit (pre-commit)")
    p_list = sub.add_parser("list", parents=[common], help="in các file track thuộc một lớp")
    p_list.add_argument("klass", metavar="lớp", choices=CLASSES)
    args = ap.parse_args(argv)
    root = Path(args.root)
    try:
        if args.cmd == "check":
            if is_app(root, staged=args.staged):
                # Có core.lock ⇔ đây là app: mục template_only không khớp gì, file riêng của app không có lớp —
                # luật của cổng này chỉ đúng ở template. Cổng của app là sync_core.py check.
                print("manifest: đây là app — cổng manifest chỉ áp ở template; dùng tools/template/sync_core.py check")
                return 0
            problems = check(root, staged=args.staged)
            for p in problems:
                print(p)
            if problems:
                print(f"manifest: {len(problems)} vi phạm", file=sys.stderr)
                return 1
            print("manifest: OK")
            return 0
        if args.cmd == "is-app":
            app = is_app(root, staged=args.staged)
            if app is None:
                print(f"FAIL: {root}: không phải repo git — không biết core.lock có được track không", file=sys.stderr)
                return 2
            print("app" if app else "template")
            return 0 if app else 1
        manifest = load(root)
        if args.cmd == "classify":
            rc = 0
            for rel in args.paths:
                cls = classify(manifest, rel)
                if cls is None:
                    rc = 1
                print(f"{cls or '(chưa phân lớp)'}\t{rel}")
            return rc
        for f in tracked(root):
            if classify(manifest, f) == args.klass:
                print(f)
        return 0
    except ManifestError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
