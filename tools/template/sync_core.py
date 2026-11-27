#!/usr/bin/env python3
"""`core.lock` của app + cổng "file lớp đồng bộ không lệch template".

    python3 tools/template/sync_core.py check [--staged] [--root R]   # rc 0 khớp · 1 lệch · 2 không có/hỏng core.lock
    python3 tools/template/sync_core.py status [--root R]             # in tag, commit, nguồn, số file
    python3 tools/template/sync_core.py sync --to <tag> [--source <đường dẫn | url>] [--dry-run] [--adopt-new-seed] [--root R]
                                                                      # rc 0 xong / không đổi · 1 từ chối · 2 tham số / lock hỏng

`sync` (CHỈ chạy trong app — template (có new_app.py của template được track trong tools/template) hay repo không track `core.lock` ⇒ rc 2)
là lối DUY NHẤT để file lớp đồng bộ đổi ở app. Điều kiện vào: `git status --porcelain` rỗng, `check` sạch, `.temp/`
bị git ignore (không thì rc 1, không ghi gì). Nguồn mặc định = `template.source` của lock (`--source` thay cho lần chạy
này, lock giữ nguồn cũ). Lấy cây NGUYÊN BẢN ở tag (repo cục bộ: `git archive`; URL: `git clone --depth 1 --branch`) vào
`.temp/core-sync/.fetch-*`, danh sách file theo git; phân lớp theo manifest CỦA CÂY MỚI:
  * thêm / sửa — file lớp sync của cây mới (lock mới ghim mọi file đó);
  * xoá — chỉ file ĐÃ GHIM ở `synced` cũ mà cây mới không còn xếp sync và không chuyển sang seed (file của app nằm dưới
    thư mục sync — vd `docs/lessons-learned/app/` lớp seed lồng trong thư mục sync — không bao giờ bị xoá);
  * nay do app sở hữu — đã ghim, nay lớp seed: giữ file, bỏ khỏi `synced`;
  * xung đột — lớp sync ở cây mới, app đã có thứ ở đó mà lock cũ không ghim; hoặc file app đang track mà manifest
    mới xếp lớp sync dù template không ship (thư mục nay do template sở hữu) ⇒ rc 1, liệt kê, không ghi gì;
  * file gieo đổi — digest seed ở cây mới khác `seeded` cũ ⇒ chép bản mới ra `.temp/core-sync/<tag>/<đường dẫn>` để so
    tay (ở lại cho người), cập nhật `seeded`; không đụng file của app. File gieo do `appconfig.py render` của cây mới
    sinh (xcconfig, Features.generated.yml, privacy manifest, entitlements — `generated_paths`) không bao giờ được báo ở
    đây: bản trong template sinh theo cấu hình của template, app tự render;
  * nhận file gieo mới (CHỈ với `--adopt-new-seed`) — khoá `seeded` của cây mới chưa từng có trong lock cũ (khoá giữ chỗ
    `$primary_locale`… mà new_app ghi là "đã gieo", không bao giờ nhận lại), trừ file sinh, Swift, tính năng mẫu, và
    metadata MẪU `store/metadata/` khi thư mục gieo mang khung: dựng bản app như new_app (`render_seed`: biến từ
    `app.config.toml` CỦA APP qua `appconfig.seed_variables` của cây mới, thay trong đường dẫn + nội dung file thư mục
    gieo, nhân locale, cắt khối `template:`). Đích chưa track và trống ⇒ tạo, báo "(đã tạo ở app)", không chép ra .temp/;
    đã track ⇒ không đụng (như cũ); chưa track mà có thứ trên đĩa ⇒ xung đột, rc 1, không ghi gì. `seeded` vẫn ghi
    digest BẢN NGUYÊN. Không cờ ⇒ hành vi cũ + MỘT dòng gợi ý cờ khi có file như vậy (sau khi áp, lock đã ghi chúng vào
    `seeded`: muốn nhận thì khôi phục NGAY sau sync, trước `render`/sửa tay — lệnh khôi phục bỏ mọi thay đổi chưa commit —
    rồi chạy lại với cờ; dòng gợi ý in sẵn lệnh).
    `appconfig.py` CỦA CÂY MỚI được nạp và chạy trong tiến trình này (`seed_variables`, `generated_paths`): tag đích phải
    là nguồn tin được (template của chính bạn), như mọi code lõi sắp đồng bộ vào app.
Áp: chép file mới vào `.temp/core-sync/.staging-*` (cùng ổ đĩa), xoá file `delete` + thư mục rỗng TRƯỚC (chỗ của
chúng có thể là chỗ của file mới: template đổi tên hoa/thường, file ↔ thư mục — chỗ chỉ bị chính file template ghim và
đang xoá chiếm thì không phải xung đột), `os.replace` từng file (giữ bit thực thi theo digest) rồi từng file gieo nhận
mới (cũng dựng sẵn trong thư mục tạm), gỡ khỏi index tên cũ của
file đổi tên hoa/thường, ghi `core.lock` SAU CÙNG. Lỗi giữa chừng ⇒ in lệnh khôi phục, rc 1, lock không đổi. Cuối cùng
in tóm tắt, file gieo đổi, các tiểu mục "Việc phải làm tay khi lên bản này" của CHANGELOG của template (cây mới) cho các
bản trong (cũ, mới], và các lệnh tiếp theo. Không tự commit. Tag đích cũ hơn bản đang đứng ⇒ in cảnh báo rồi vẫn làm.

`core.lock` chỉ có ở APP (do lệnh tạo app ghi, được track; có nó ⇔ "đây là app", không có ⇔ "đây là template").
Nó ghim bản template mà app đang đứng và digest (`manifest.digest`: sha256 + "+x" khi có bit thực thi của chủ) của:
  * `synced` — mọi file lớp `sync`: app phải giữ giống hệt từng byte; muốn đổi thì sửa ở template, tag, rồi đồng bộ
    (`sync_core.py sync --to <tag>`) — không có lối "chấp nhận lệch";
  * `seeded` — mọi file lớp `seed` NGUYÊN BẢN trong template lúc gieo (trước khi cắt khối, trước khi thay biến; file lấy
    từ thư mục gieo thì là digest của file trong thư mục gieo) — để lần đồng bộ sau so được với bản nguyên của tag mới.
    Cổng `check` KHÔNG soi file seed: chúng thuộc app.

Lược đồ (JSON, khoá sắp xếp, thụt 2, UTF-8 không thoát ký tự, có xuống dòng cuối):

    { "schema": 1,
      "template": { "source": "<url hoặc đường dẫn>", "tag": "v0.4.0" | null, "commit": "<sha đầy đủ>" },
      "synced": { "<đường dẫn>": "<digest>" },
      "seeded": { "<đường dẫn>": "<digest>" } }

Khoá lạ, sai kiểu, đường dẫn tuyệt đối / thoát gốc (`..`) / không chuẩn, digest sai dạng ⇒ `LockError` (CLI rc 2).

`check` in mỗi file lệch một dòng `M <đường dẫn>` (nội dung/bit thực thi khác, hoặc đã thành symlink / thư mục /
nằm dưới một thư mục symlink), `D <đường dẫn>` (mất) hay `A <đường dẫn>` (file mới, đang track / trong index, mà manifest
của app xếp lớp sync nhưng lock không ghim — file của app phải nằm ngoài thư mục template sở hữu). So từng byte — không
chuẩn hoá CRLF/LF.

"Đây là app" = `core.lock` được TRACK (HEAD hoặc index — `manifest.is_app`), không phải "có file trên đĩa": app xoá /
`git rm` lock thì `check` rc 2 kèm lệnh khôi phục, không lặng lẽ thành "template".
`check --staged` (pre-commit) so nội dung trong INDEX với `core.lock` cũng đọc từ index: commit do lệnh đồng bộ tạo
(file + lock cùng stage) qua. Index là index git ĐANG commit: `GIT_INDEX_FILE` của hook được giữ khi nó thuộc chính repo
`--root` (`manifest.hook_index` — `git commit -a` dựng index tạm, `.git/index` lúc đó là nội dung cũ); mọi biến
`GIT_*` khác bị gỡ, `--no-optional-locks`.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import html
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest as mf  # noqa: E402  (phân lớp + digest dùng chung)

LOCK = "core.lock"
SCHEMA = 1
GUIDANCE = "File này do template sở hữu — sửa ở template rồi chạy tools/template/sync_core.py sync --to <tag>"
GUIDANCE_ADDED = ("File mới nằm trong thư mục do template sở hữu — chuyển nó sang chỗ của app (vd AppHost/…, tools/app/…,"
                  " docs/lessons-learned/app/…) hoặc thêm nó vào template")
# Nơi app chuyển file của nó tới khi đụng thư mục template sở hữu — KHÔNG nêu một thư mục cụ thể có thể chính là
# thư mục đang xung đột; nêu quy tắc.
APP_PLACE = ("một thư mục app sở hữu khác (đường dẫn template.manifest.toml của bản đích không xếp lớp sync: không khai,"
             " hoặc lớp gieo — vd dưới AppHost/)")
TOP_KEYS = {"schema", "template", "synced", "seeded"}
TEMPLATE_KEYS = {"source", "tag", "commit"}
DIGEST_RE = re.compile(r"^[0-9a-f]{64}(\+x)?$")
COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class LockError(Exception):
    """`core.lock` thiếu (khi cần) / hỏng / sai lược đồ, hoặc không đọc được repo (CLI rc 2)."""


# ---------------------------------------------------------------- lược đồ

def _check_path(section: str, rel) -> str:
    if not isinstance(rel, str) or not rel:
        raise LockError(f"{section}: đường dẫn phải là chuỗi khác rỗng, gặp {rel!r}")
    parts = rel.split("/")
    if (rel.startswith("/") or "\\" in rel or "\0" in rel or re.match(r"^[A-Za-z]:", rel)
            or any(p in ("", ".", "..") for p in parts)):
        raise LockError(f"{section}: \"{rel}\" phải là đường dẫn tương đối chuẩn trong gốc (không '/', '..', '.', '\\')")
    # Không bao giờ ghim / ghi vào thư mục git (ổ không phân biệt hoa thường: `.GIT/` cũng là `.git/`).
    if any(p.casefold() == ".git" for p in parts):
        raise LockError(f"{section}: \"{rel}\" nằm trong thư mục .git — từ chối")
    if rel.casefold() == LOCK.casefold():
        raise LockError(f"{section}: {LOCK} không tự ghim chính nó")
    return rel


def validate(data) -> dict:
    """Kiểm lược đồ của dict đã đọc từ JSON; trả chính nó. Sai ⇒ LockError."""
    if not isinstance(data, dict):
        raise LockError(f"{LOCK} phải là một object JSON")
    if set(data) != TOP_KEYS:
        extra, missing = set(data) - TOP_KEYS, TOP_KEYS - set(data)
        msg = []
        if extra:
            msg.append("khoá lạ " + ", ".join(sorted(extra)))
        if missing:
            msg.append("thiếu " + ", ".join(sorted(missing)))
        raise LockError(f"{LOCK}: " + "; ".join(msg))
    if isinstance(data["schema"], bool) or data["schema"] != SCHEMA:
        raise LockError(f"{LOCK}: schema phải là {SCHEMA}, gặp {data['schema']!r}")
    tpl = data["template"]
    if not isinstance(tpl, dict) or set(tpl) != TEMPLATE_KEYS:
        raise LockError(f"{LOCK}: template phải là object có đúng các khoá {', '.join(sorted(TEMPLATE_KEYS))}")
    if not isinstance(tpl["source"], str) or not tpl["source"]:
        raise LockError(f"{LOCK}: template.source phải là chuỗi khác rỗng")
    if tpl["tag"] is not None and (not isinstance(tpl["tag"], str) or not tpl["tag"]):
        raise LockError(f"{LOCK}: template.tag phải là chuỗi khác rỗng hoặc null")
    if not isinstance(tpl["commit"], str) or not COMMIT_RE.match(tpl["commit"]):
        raise LockError(f"{LOCK}: template.commit phải là sha đầy đủ (hex thường), gặp {tpl['commit']!r}")
    for section in ("synced", "seeded"):
        table = data[section]
        if not isinstance(table, dict):
            raise LockError(f"{LOCK}: {section} phải là object đường dẫn → digest")
        for rel, dig in table.items():
            _check_path(section, rel)
            if not isinstance(dig, str) or not DIGEST_RE.match(dig):
                raise LockError(f"{section}: digest của \"{rel}\" sai dạng (sha256 hex [+x]), gặp {dig!r}")
    both = set(data["synced"]) & set(data["seeded"])
    if both:
        raise LockError(f"{LOCK}: đường dẫn ở cả synced lẫn seeded: {', '.join(sorted(both))}")
    return data


def _parse(raw: bytes, where: str) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise LockError(f"{where}: không phải JSON UTF-8 hợp lệ: {e}") from None
    return validate(data)


def lock_text(lock: dict) -> str:
    """Bytes chuẩn của core.lock (dạng chuỗi): khoá sắp xếp, thụt 2, không thoát ký tự không-ASCII, xuống dòng cuối."""
    return json.dumps(lock, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def read_lock(root: Path) -> dict | None:
    """Đọc + kiểm `core.lock` ở gốc (working tree). Thiếu ⇒ None; hỏng / sai lược đồ / là symlink ⇒ LockError."""
    path = Path(root) / LOCK
    if not os.path.lexists(path):
        return None
    if path.is_symlink() or not path.is_file():
        raise LockError(f"{path}: không phải file thường")
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise LockError(f"không đọc được {path}: {e.strerror or e}") from None
    return _parse(raw, LOCK)


def write_lock(root: Path, lock: dict) -> None:
    """Ghi `core.lock` ở gốc (kiểm lược đồ trước; ghi file tạm rồi thay nguyên khối). Đích là symlink/thư mục ⇒ LockError."""
    validate(lock)
    path = Path(root) / LOCK
    if os.path.lexists(path) and (path.is_symlink() or not path.is_file()):
        raise LockError(f"{path}: không phải file thường — không ghi đè")
    tmp = path.with_name(LOCK + ".tmp")
    if os.path.lexists(tmp):
        raise LockError(f"{tmp}: đã tồn tại — xoá tay rồi chạy lại")
    with open(tmp, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(lock_text(lock))
    os.replace(tmp, path)


# ---------------------------------------------------------------- dựng lock

def _walk(tree: Path):
    """(đường dẫn tương đối, Path, là symlink) của mọi file/symlink trong cây trên đĩa, bỏ `.git` ở gốc."""
    for dirpath, dirnames, filenames in os.walk(tree, followlinks=False):
        rel_dir = os.path.relpath(dirpath, tree)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
        if not rel_dir and ".git" in dirnames:
            dirnames.remove(".git")
        for name in list(dirnames):
            p = Path(dirpath) / name
            if p.is_symlink():
                dirnames.remove(name)
                yield (f"{rel_dir}/{name}" if rel_dir else name), p, True
        for name in filenames:
            if not rel_dir and name == ".git":
                continue
            p = Path(dirpath) / name
            yield (f"{rel_dir}/{name}" if rel_dir else name), p, p.is_symlink()


def _digest(p: Path, rel: str) -> str:
    try:
        return mf.digest(p)
    except (mf.ManifestError, OSError) as e:
        raise LockError(f"{rel}: không băm được ({e})") from None


def _git_files(tree: Path) -> list[str] | None:
    """`git ls-files` của `tree` khi nó là GỐC một work tree git; không phải ⇒ None."""
    try:
        r = mf._git(tree, "rev-parse", "--show-toplevel")
    except OSError:
        return None
    if r.returncode != 0:
        return None
    top = r.stdout.decode("utf-8", "surrogateescape").strip()
    if os.path.realpath(top) != os.path.realpath(tree):
        return None
    return mf.tracked(tree)


def _listed(tree: Path, files: list[str]):
    for rel in files:
        if rel == LOCK:
            continue
        _check_path("files", rel)
        p = tree / rel
        if not os.path.lexists(p):
            raise LockError(f"{rel}: có trong danh sách file nhưng không có trong cây {tree}")
        yield rel, p, p.is_symlink()


def build_lock(tree: Path, manifest: dict, *, source: str, tag: str | None, commit: str,
               files: list[str] | None = None) -> dict:
    """Dựng nội dung core.lock từ cây template NGUYÊN BẢN (bản xuất ở tag, chưa áp gì):
    `synced` = digest mọi file lớp sync; `seeded` = digest mọi file lớp seed như template ship, riêng đường dẫn là đích
    của `overlay_dir` thì là digest của file trong thư mục gieo. File lớp sync/seed là symlink ⇒ LockError.

    Ghim file NÀO là việc của git, không phải của đĩa: `files` (đường dẫn tương đối đúng như git gọi tên — vd
    `git ls-tree -r -z --name-only <ref>` của template) ⇒ đúng các file đó; `files=None` mà `tree` là gốc work tree git ⇒
    `git ls-files`; chỉ thư mục thường (test) mới đi đĩa. Nhờ vậy file bị ignore (`__pycache__/`, `.DS_Store`) không bị
    ghim, và tên ghim là dạng git lưu (NFC) chứ không phải dạng trên đĩa (macOS có thể NFD)."""
    tree = Path(tree)
    if files is None:
        files = _git_files(tree)
    entries = _walk(tree) if files is None else _listed(tree, files)
    od = manifest["seed"].get("overlay_dir")
    prefix = od + "/" if od else None
    synced: dict[str, str] = {}
    seeded: dict[str, str] = {}
    overlay: dict[str, str] = {}
    for rel, p, is_link in entries:
        if rel == LOCK:
            continue
        if prefix and rel.startswith(prefix):
            target = rel[len(prefix):]
            if is_link or not p.is_file():
                raise LockError(f"{rel}: file gieo là symlink / không phải file thường")
            overlay[target] = _digest(p, rel)
            continue
        cls = mf.classify(manifest, rel)
        if cls not in ("sync", "seed"):
            continue
        if is_link:
            raise LockError(f"{rel}: file lớp {cls} là symlink — không ghim được")
        if not p.is_file():
            raise LockError(f"{rel}: file lớp {cls} không phải file thường — không ghim được")
        (synced if cls == "sync" else seeded)[rel] = _digest(p, rel)
    for target, dig in overlay.items():
        synced.pop(target, None)
        seeded[target] = dig
    lock = {
        "schema": SCHEMA,
        "template": {"source": source, "tag": tag, "commit": commit},
        "synced": dict(sorted(synced.items())),
        "seeded": dict(sorted(seeded.items())),
    }
    return validate(lock)


# ---------------------------------------------------------------- lệch

def _added(manifest: dict, files, synced: dict) -> list[tuple[str, str]]:
    """Luật A: file (track / trong index) mà manifest CỦA APP xếp lớp sync nhưng lock không ghim — app thêm file vào
    thư mục template sở hữu (vd `Core/…`, `.githooks/pre-push`) là đổi hành vi lõi mà không cổng nào thấy."""
    return [("A", rel) for rel in files
            if rel != LOCK and rel not in synced and mf.classify(manifest, rel) == "sync"]


def _sorted_lines(items) -> list[str]:
    return [f"{letter} {rel}" for letter, rel in sorted(items, key=lambda t: (t[1], t[0]))]


def _drift_tree(root: Path, synced: dict) -> list[str]:
    out = []
    for rel, want in sorted(synced.items()):
        cur = root
        bad = None
        parts = rel.split("/")
        for i, part in enumerate(parts):
            cur = cur / part
            try:
                st = os.lstat(cur)
            except FileNotFoundError:
                bad = "D"
                break
            except NotADirectoryError:      # một thư mục cha đã thành file
                bad = "D"
                break
            if stat.S_ISLNK(st.st_mode):
                bad = "M"                   # symlink (chính file hoặc thư mục cha) — không còn là file template
                break
            if i < len(parts) - 1 and not stat.S_ISDIR(st.st_mode):
                bad = "D"
                break
            if i == len(parts) - 1 and not stat.S_ISREG(st.st_mode):
                bad = "M"                   # thành thư mục / FIFO / file đặc biệt — không mở (FIFO treo)
        if bad is None:
            try:
                got = mf.digest(cur)
            except (mf.ManifestError, OSError):
                got = None
            if got != want:
                bad = "M"
        if bad:
            out.append((bad, rel))
    return out


def _index(root: Path) -> tuple[dict[str, tuple[str, str]], dict]:
    """(đường dẫn → (mode, blob sha)) của index git đang commit + env đã dùng."""
    try:
        env = mf.git_env(root, staged=True)
    except mf.ManifestError as e:
        raise LockError(str(e)) from None
    try:
        r = mf._git(root, "ls-files", "-s", "-z", env=env)
    except OSError as e:
        raise LockError(f"không chạy được git: {e}") from None
    if r.returncode != 0:
        raise LockError(f"{root}: không đọc được index git ({r.stderr.decode('utf-8', 'replace').strip()})")
    entries: dict[str, tuple[str, str]] = {}
    for rec in r.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if not rec:
            continue
        meta, path = rec.split("\t", 1)
        mode, sha, stage = meta.split()
        if stage != "0":
            entries[path] = ("conflict", sha)
        else:
            entries[path] = (mode, sha)
    return entries, env


def _blobs(root: Path, env: dict, shas: list[str]) -> dict[str, bytes]:
    """Nội dung các blob (một lần `git cat-file --batch`)."""
    uniq = sorted(set(shas))
    if not uniq:
        return {}
    r = mf._git(root, "cat-file", "--batch", env=env, stdin=("\n".join(uniq) + "\n").encode())
    if r.returncode != 0:
        raise LockError(f"git cat-file lỗi: {r.stderr.decode('utf-8', 'replace').strip()}")
    out, data, pos = {}, r.stdout, 0
    for _ in uniq:
        nl = data.index(b"\n", pos)
        head = data[pos:nl].decode().split()
        if len(head) < 3 or head[1] != "blob":
            raise LockError(f"git cat-file: không đọc được blob {head[0] if head else '?'}")
        size = int(head[2])
        out[head[0]] = data[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
    return out


RESTORE = f"khôi phục: git restore --staged --worktree {LOCK}"


def _drift_index(root: Path) -> list[str]:
    entries, env = _index(root)
    lock_entry = entries.get(LOCK)
    if lock_entry is None:
        if mf.is_app(root, staged=True):
            raise LockError(f"{LOCK} đã bị gỡ khỏi commit này nhưng HEAD có nó — đây là app, lock phải ở lại ({RESTORE})")
        raise LockError(f"không có {LOCK} trong index của {root} — đây là template (lock chỉ có ở app)")
    if lock_entry[0] not in ("100644", "100755"):
        raise LockError(f"{LOCK} trong index không phải file thường")
    man_entry = entries.get(mf.MANIFEST_FILE)
    if man_entry is None or man_entry[0] not in ("100644", "100755"):
        raise LockError(f"{mf.MANIFEST_FILE} không có (hoặc không phải file thường) trong index — không phân lớp được"
                        f" (file lớp đồng bộ; khôi phục bằng git restore --staged --worktree {mf.MANIFEST_FILE})")
    raw = _blobs(root, env, [lock_entry[1], man_entry[1]])
    lock = _parse(raw[lock_entry[1]], f"{LOCK} (index)")
    try:
        manifest = mf.parse(raw[man_entry[1]])
    except mf.ManifestError as e:
        raise LockError(f"{mf.MANIFEST_FILE} (index): {e}") from None
    synced = lock["synced"]
    regular = {rel: entries[rel] for rel in synced if rel in entries and entries[rel][0] in ("100644", "100755")}
    contents = _blobs(root, env, [sha for _, sha in regular.values()])
    paths = sorted(entries)
    out = []
    for rel, want in sorted(synced.items()):
        e = entries.get(rel)
        if e is None:
            # Không còn file ở đúng đường dẫn; có mục bên dưới ⇒ nó đã thành thư mục.
            under = rel + "/"
            out.append(("M" if any(p.startswith(under) for p in paths) else "D", rel))
            continue
        if rel not in regular:
            out.append(("M", rel))         # symlink (120000), submodule (160000), xung đột merge
            continue
        mode, sha = regular[rel]
        got = hashlib.sha256(contents[sha]).hexdigest() + ("+x" if mode == "100755" else "")
        if got != want:
            out.append(("M", rel))
    out.extend(_added(manifest, paths, synced))
    return _sorted_lines(out)


def drift(root: Path, *, staged: bool = False) -> list[str]:
    """Các file lệch core.lock, sắp theo đường dẫn: `M` (file ghim bị sửa/thay), `D` (file ghim mất), `A` (file mới mà
    manifest của app xếp lớp sync nhưng lock không ghim). Rỗng = khớp. Hỏng lock / manifest ⇒ LockError; thiếu lock mà
    nó vẫn được track (`manifest.is_app`) ⇒ LockError "lock bị gỡ" kèm lệnh khôi phục.
    `staged=True`: file, lock và manifest đều đọc từ index git đang commit. Working tree: M/D soi đĩa; A xét file ĐANG
    TRACK (git là nguồn sự thật — file chưa add thì chưa tính); gốc không phải repo git ⇒ bỏ luật A."""
    root = Path(root)
    if staged:
        return _drift_index(root)
    lock = read_lock(root)
    if lock is None:
        app = mf.is_app(root)
        if app:
            raise LockError(f"{LOCK} đã bị xoá khỏi working tree nhưng vẫn được track — đây là app ({RESTORE})")
        if app is None:
            raise LockError(f"không có {LOCK} ở {root} (không phải repo git — quyết định theo file trên đĩa)")
        raise LockError(f"không có {LOCK} ở {root} — đây là template (lock chỉ có ở app)")
    out = _drift_tree(root, lock["synced"])
    try:
        manifest = mf.load(root)
    except mf.ManifestError as e:
        raise LockError(str(e)) from None
    try:
        files = mf.tracked(root)
    except mf.ManifestError:
        files = []
    # Working tree soi ĐĨA: file còn track nhưng không còn là file trên đĩa (lệnh đồng bộ vừa xoá nó, hay thay bằng thư
    # mục; chưa `git add -A`) không phải "file mới" — index (staged) vẫn thấy nó cho tới khi được gỡ.
    files = [f for f in files
             if os.path.lexists(root / f) and (os.path.islink(root / f) or not os.path.isdir(root / f))]
    out.extend(_added(manifest, files, lock["synced"]))
    return _sorted_lines(out)


# ---------------------------------------------------------------- đồng bộ: kéo lõi lên tag mới

TEMPLATE_MARKER = "tools/template/new_app.py"   # trong HEAD ⇔ đây là TEMPLATE (`_is_template` = `repo_kind` của pre-commit)
WORK_DIR = ".temp/core-sync"                    # git-ignore; bản gieo mới để so tay nằm ở WORK_DIR/<tag>/
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_replace = os.replace                           # điểm tiêm lỗi cho test (lỗi giữa chừng ⇒ lock không đổi)


class SyncRefused(Exception):
    """Đồng bộ bị từ chối trước khi ghi gì (CLI rc 1)."""


class TreeUnusable(SyncRefused):
    """Bản tool này không dùng được cây template mới (manifest / lược đồ core.lock mới hơn) — đường ra: chạy tool CỦA
    BẢN MỚI với `--root <app>` (`bootstrap_hint`)."""


class SyncError(Exception):
    """Lỗi giữa lúc áp — app có thể đã đổi một phần, core.lock CHƯA đổi; thông điệp kèm lệnh khôi phục (CLI rc 1)."""


@dataclass
class SyncPlan:
    """Kết quả so cây template mới với `core.lock` hiện tại của app (đường dẫn đã sắp xếp)."""
    add: list[str]            # file lớp sync mới — chưa có ở app
    update: list[str]         # file lớp sync đã ghim, nội dung/bit thực thi đổi
    delete: list[str]         # đã ghim, không còn lớp sync ở cây mới và không chuyển sang seed ⇒ xoá khỏi app
    released: list[str]       # đã ghim, nay lớp seed ⇒ giữ file, bỏ khỏi `synced` ("nay do app sở hữu")
    conflicts: list[str]      # lớp sync ở cây mới, app đã có thứ ở đường dẫn đó mà lock cũ không ghim ⇒ từ chối
    seed_changed: list[str]   # file lớp seed mà digest ở cây mới khác `seeded` cũ ⇒ chép ra WORK_DIR/<tag>/ để so tay
    synced: dict[str, str]    # `synced` của lock mới
    seeded: dict[str, str]    # `seeded` của lock mới
    sources: dict[str, str]   # file seed → đường dẫn nguồn trong cây mới (đích của thư mục gieo: file trong thư mục gieo)
    manifest: dict            # manifest của cây mới
    # đường dẫn xung đột → ("app" | "seed", thứ đang chiếm chỗ): "app" = file của app (không lớp / lớp khác) nằm ở chỗ
    # template nay sở hữu; "seed" = chính đường dẫn đó trước là lớp gieo (bản của app), nay là lớp đồng bộ; "dir" = file
    # app track nằm trong thư mục manifest mới xếp lớp sync mà template không ship.
    conflict_reasons: dict[str, tuple[str, str]] = field(default_factory=dict)
    # file gieo do `appconfig.py render` của cây mới sinh ở app — không báo đổi, không bao giờ nhận vào app
    generated: set[str] = field(default_factory=set)

    def changes_files(self) -> bool:
        return bool(self.add or self.update or self.delete)


# Danh sách file (theo git) của các cây đã lấy bằng fetch_template — Ruling 9: danh sách file của cây mới là của git,
# không đi đĩa. plan_sync tra ở đây khi không được truyền `files=`.
_FETCHED: dict[str, list[str]] = {}


def _is_url(source: str) -> bool:
    return "://" in source or bool(re.match(r"^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+:", source))


def public_source(source: str) -> str:
    """Nguồn template để IN / GHI vào core.lock: bỏ thông tin đăng nhập của URL dạng `scheme://…` — http(s) bỏ cả
    userinfo (`https://user:token@host/…` ⇒ `https://host/…`, token hay nằm ở phần user), scheme khác chỉ bỏ mật khẩu
    (`ssh://git:pw@host/…` ⇒ `ssh://git@host/…`). Dạng scp `git@host:org/repo.git` và đường dẫn cục bộ giữ nguyên.
    (new_app.py — lớp chỉ-template — có bản sao vì nó nhập sync_core.py của cây ở `--ref`, có thể cũ hơn.)"""
    if "://" not in source:
        return source
    scheme, rest = source.split("://", 1)
    cut = min([i for i in (rest.find(ch) for ch in "/?#") if i != -1] or [len(rest)])
    netloc, tail = rest[:cut], rest[cut:]
    if "@" not in netloc:
        return source
    user, host = netloc.rsplit("@", 1)
    if scheme.lower() in ("http", "https"):
        keep = ""
    else:
        keep = user.split(":", 1)[0] + "@"
    return f"{scheme}://{keep}{host}{tail}"


def _check_tag(tag: str) -> str:
    if not isinstance(tag, str) or not TAG_RE.match(tag):
        raise LockError(f"tag {tag!r} sai dạng (chữ, số, '.', '_', '+', '-'; không bắt đầu bằng '-')")
    return tag


def _export(repo: Path, commit: str, into: Path) -> list[str]:
    """`git archive <commit>` của `repo` bung vào `into`; trả danh sách file của git (`ls-tree -r -z --name-only`)."""
    r = mf._git(repo, "ls-tree", "-r", "-z", "--name-only", commit)
    if r.returncode != 0:
        raise SyncRefused(f"git ls-tree {commit[:12]} lỗi: {r.stderr.decode('utf-8', 'replace').strip()}")
    names = [n for n in r.stdout.decode("utf-8", "surrogateescape").split("\0") if n]
    archive = subprocess.Popen(["git", "--no-optional-locks", "-C", str(repo), "archive", "--format=tar", commit],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=mf._clean_env())
    tar = subprocess.run(["tar", "-xf", "-", "-C", str(into)], stdin=archive.stdout, capture_output=True)
    archive.stdout.close()
    err = archive.stderr.read().decode("utf-8", "replace")
    if archive.wait() != 0 or tar.returncode != 0:
        raise SyncRefused(f"git archive | tar lỗi: {err.strip()} {tar.stderr.decode('utf-8', 'replace').strip()}")
    return names


def _resolve_tag(repo: Path, tag: str) -> str:
    r = mf._git(repo, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}")
    if r.returncode != 0:
        raise SyncRefused(f"tag {tag} không có ở nguồn template {repo}")
    return r.stdout.decode().strip()


def fetch_template(source: str, tag: str, into: Path) -> str:
    """Lấy cây template NGUYÊN BẢN ở `tag` vào thư mục `into` (chưa có hoặc rỗng); trả commit đầy đủ.
    Đường dẫn cục bộ là repo git (thường hoặc bare) ⇒ `git archive <tag>`; URL ⇒ `git clone --depth 1 --branch <tag>`
    vào thư mục tạm của hệ thống (xoá ngay sau đó) rồi như trên. Danh sách file của git được nhớ cho plan_sync.
    Nguồn không đọc được / tag không có ⇒ SyncRefused."""
    _check_tag(tag)
    into = Path(into)
    if os.path.lexists(into):
        if into.is_symlink() or not into.is_dir() or any(os.scandir(into)):
            raise SyncRefused(f"{into}: phải là thư mục chưa có hoặc rỗng")
    else:
        into.mkdir(parents=True)
    clone_dir = None
    try:
        if _is_url(source):
            clone_dir = Path(tempfile.mkdtemp(prefix="core-sync-clone-"))
            r = subprocess.run(["git", "--no-optional-locks", "clone", "-q", "--depth", "1", "--no-checkout",
                                "--branch", tag, "--", source, str(clone_dir / "repo")],
                               capture_output=True, env=mf._clean_env())
            if r.returncode != 0:
                raise SyncRefused(f"không clone được {public_source(source)} ở tag {tag}: "
                                  f"{r.stderr.decode('utf-8', 'replace').strip()}")
            repo = clone_dir / "repo"
        else:
            repo = Path(os.path.abspath(source))
            if not repo.is_dir():
                raise SyncRefused(f"nguồn template {source} không phải thư mục / URL đọc được")
            r = mf._git(repo, "rev-parse", "--git-dir")
            if r.returncode != 0:
                raise SyncRefused(f"nguồn template {source} không phải repo git")
        commit = _resolve_tag(repo, tag)
        names = _export(repo, commit, into)
    except OSError as e:
        raise SyncRefused(f"không đọc được nguồn template {public_source(source)}: {e}") from None
    finally:
        if clone_dir is not None:
            shutil.rmtree(clone_dir, ignore_errors=True)
    _FETCHED[os.path.realpath(into)] = names
    return commit


def _inode(path: Path) -> tuple[int, int] | None:
    try:
        st = os.lstat(path)
    except OSError:
        return None
    return (st.st_dev, st.st_ino) if stat.S_ISREG(st.st_mode) else None


def _subtree_blocker(root: Path, top: Path, gone: set) -> str | None:
    """Thư mục `top` chỉ chứa file template ghim và đang xoá (`gone`: inode)? Có thứ khác (file của app, chưa track,
    bị ignore, symlink) ⇒ trả đường dẫn của thứ đó; không ⇒ None."""
    for dirpath, dirnames, filenames in os.walk(top, followlinks=False):
        for name in dirnames:
            if os.path.islink(os.path.join(dirpath, name)):
                return os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if _inode(p) not in gone:
                return str(p.relative_to(root)).replace(os.sep, "/")
    return None


def _blocker(root: Path, rel: str, gone: set) -> str | None:
    """Thứ đang chiếm chỗ của `rel` ở app (đường dẫn tương đối của nó), hoặc None khi chỗ trống — hay chỉ bị chiếm bởi
    file mà TEMPLATE đã ghim và đang xoá (`gone`: inode các file đó): cùng file khác hoa/thường (ổ không phân biệt hoa
    thường), một thành phần cha là file ghim đang xoá (file → thư mục), hay một thư mục chỉ gồm file ghim đang xoá
    (thư mục → file)."""
    cur = root
    parts = rel.split("/")
    for i, part in enumerate(parts):
        cur = cur / part
        here = "/".join(parts[:i + 1])
        try:
            st = os.lstat(cur)
        except FileNotFoundError:
            return None
        except NotADirectoryError:
            return here
        last = i == len(parts) - 1
        if stat.S_ISLNK(st.st_mode):
            return here
        if stat.S_ISREG(st.st_mode):
            # file ghim đang xoá: chính nó (khác hoa/thường) hay một cha của đường dẫn mới — sau khi xoá thì chỗ trống
            return None if (st.st_dev, st.st_ino) in gone else here
        if not stat.S_ISDIR(st.st_mode):
            return here
        if last:
            return _subtree_blocker(root, cur, gone)
    return None


SCHEMA_LINE_RE = re.compile(r"^SCHEMA = (\d+)\s*(?:#.*)?$", re.M)


def incoming_lock_schema(new_tree: Path) -> int | None:
    """Lược đồ core.lock mà `sync_core.py` CỦA CÂY MỚI ghi — đọc dòng `SCHEMA = <n>` ở đầu dòng của file đó (không
    chạy nó). Không có file / không thấy dòng ⇒ None (không biết; khi đó chỉ manifest được kiểm)."""
    f = Path(new_tree) / "tools/template/sync_core.py"
    try:
        if f.is_symlink() or not f.is_file():
            return None
        m = SCHEMA_LINE_RE.search(f.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return int(m.group(1)) if m else None


def bootstrap_hint(root: Path, src: str, to: str) -> str:
    """Lệnh chạy tool của BẢN MỚI trên app (`--root`) — tool đó nhập manifest.py của chính nó nên đọc được cây mới."""
    app, tag = shlex.quote(str(root)), shlex.quote(to)
    if _is_url(src):
        return ("Chạy sync_core.py của bản mới trên app:\n"
                f"  git clone -q --depth 1 --branch {tag} {shlex.quote(public_source(src))} <thư mục tạm>\n"
                f"  python3 <thư mục tạm>/tools/template/sync_core.py sync --root {app} --to {tag}"
                f" --source {shlex.quote(public_source(src))}\n"
                "(xong thì xoá thư mục tạm)")
    tool = shlex.quote(str(Path(os.path.abspath(src)) / "tools/template/sync_core.py"))
    return ("Chạy sync_core.py của bản mới trên app (checkout của template phải đứng ở "
            f"{to} hoặc mới hơn — `git -C {shlex.quote(src)} checkout {tag}` nếu cần):\n"
            f"  python3 {tool} sync --root {app} --to {tag} --source {shlex.quote(src)}")


def plan_sync(root: Path, new_tree: Path, files: list[str] | None = None) -> SyncPlan:
    """So cây template mới (`new_tree`, bản xuất nguyên bản ở tag đích) với `core.lock` của app. Lớp lấy theo manifest
    CỦA CÂY MỚI. `files` = danh sách file của git cho cây đó (mặc định: cái fetch_template đã nhớ). Không ghi gì."""
    root, new_tree = Path(root), Path(new_tree)
    old = read_lock(root)
    if old is None:
        raise LockError(f"không có {LOCK} ở {root}")
    if files is None:
        files = _FETCHED.get(os.path.realpath(new_tree))
        if files is None:
            raise LockError(f"không biết danh sách file (theo git) của {new_tree} — lấy cây bằng fetch_template")
    incoming = incoming_lock_schema(new_tree)
    if incoming is not None and incoming > SCHEMA:
        raise TreeUnusable(f"cây template mới dùng {LOCK} lược đồ {incoming}, bản sync_core.py này chỉ hiểu tới {SCHEMA}")
    try:
        manifest = mf.load(new_tree)
        fresh = build_lock(new_tree, manifest, source="-", tag=None, commit="0" * 40, files=files)
    except (mf.ManifestError, LockError) as e:
        raise TreeUnusable(f"cây template mới không dùng được: {e}") from None
    new_synced, new_seeded = fresh["synced"], fresh["seeded"]
    od = manifest["seed"].get("overlay_dir")
    targets = set(mf.overlay_targets(new_tree, manifest, files))
    sources = {p: (f"{od}/{p}" if p in targets else p) for p in new_seeded}
    old_synced, old_seeded = old["synced"], old["seeded"]
    delete, released = [], []
    for p in old_synced:
        if p in new_synced:
            continue
        if p in new_seeded or mf.classify(manifest, p) == "seed":
            released.append(p)
        else:
            delete.append(p)
    # Chỗ bị chiếm bởi chính file template ghim và đang xoá không phải xung đột (đổi tên hoa/thường, file ↔ thư mục).
    gone = {ino for ino in (_inode(root / p) for p in delete) if ino is not None}
    add, conflicts, reasons = [], [], {}
    for p in new_synced:
        if p in old_synced:
            continue
        who = _blocker(root, p, gone)
        if who is None:
            add.append(p)
        else:
            conflicts.append(p)
            reasons[p] = ("seed" if p in old_seeded and who == p else "app", who)
    # File app đang track mà manifest MỚI xếp lớp sync nhưng template không ship (và không phải file ghim đang xoá):
    # thư mục của nó nay do template sở hữu ⇒ sau đồng bộ `check` sẽ báo `A` và hook chặn commit — từ chối ngay.
    shipped, gone_paths = set(new_synced), set(delete)
    for p in mf.tracked(root):
        if p in shipped or p in gone_paths or p in old_synced or mf.classify(manifest, p) != "sync":
            continue
        conflicts.append(p)
        reasons[p] = ("dir", p)
    update = [p for p in new_synced if p in old_synced and new_synced[p] != old_synced[p]]
    # File gieo mà app tự sinh bằng `appconfig.py render` (xcconfig, Features.generated.yml, privacy manifest,
    # entitlements…): bản trong template là bản sinh theo cấu hình CỦA TEMPLATE — so tay với nó vô nghĩa, app chạy render.
    # Không báo "file gieo đổi", không chép ra .temp/, không bao giờ nhận vào app; `seeded` vẫn ghi digest bản nguyên.
    generated = generated_paths(new_tree)
    seed_changed = [p for p, dig in new_seeded.items()
                    if dig != old_seeded.get(p, old_synced.get(p)) and p not in generated]
    return SyncPlan(add=sorted(add), update=sorted(update), delete=sorted(delete), released=sorted(released),
                    conflicts=sorted(conflicts), seed_changed=sorted(seed_changed), synced=new_synced,
                    seeded=new_seeded, sources=sources, manifest=manifest, conflict_reasons=reasons,
                    generated=generated)


# ---------------------------------------------------------------- nhận file gieo mới (`--adopt-new-seed`)

APPCONFIG_REL = "tools/common/appconfig.py"
# Hằng đường dẫn file do `appconfig.py render` sinh (đọc từ appconfig của CÂY MỚI; hằng nào vắng thì bỏ qua).
GENERATED_CONSTS = ("XCCONFIG", "FEATURES_YML", "PRIVACY_MANIFEST", "ENTITLEMENTS_YML", "ENTITLEMENTS", "WRANGLER_API",
                    "WRANGLER_SITE")
# Metadata MẪU của template (giống `STORE_SAMPLE_DIR` của new_app.py — test_new_app gác hai bên khớp): khi thư mục gieo
# mang khung metadata thì bản mẫu không bao giờ tới app (new_app bỏ nó; adopt cũng bỏ).
STORE_SAMPLE_DIR = "store/metadata/"
# Không nhận: mã Swift (file gieo mới thường cần sửa ở file gieo ĐÃ CÓ — vd AppShellView — mà đồng bộ không bao giờ sửa
# ⇒ build gãy) và tính năng mẫu (app đã gỡ mẫu không được hồi sinh nó). Chúng ở lại dạng "(mới ở template)" để so tay.
NOT_ADOPTED_DIRS = ("AppHost/AppHost/Features/Sample/", "AppHost/AppHostTests/Sample/")
NOT_ADOPTED_SUFFIXES = (".swift",)


def _load_module(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"không nạp được {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return mod


def _tree_appconfig(new_tree: Path):
    """Module `appconfig.py` CỦA CÂY MỚI (một nguồn của bộ biến gieo — Ruling 2), hoặc None khi cây không có."""
    p = Path(new_tree) / APPCONFIG_REL
    if p.is_symlink() or not p.is_file():
        return None
    try:
        return _load_module(f"_sync_core_appconfig_{abs(hash(os.path.realpath(p)))}", p)
    except (ImportError, SyntaxError, SystemExit, OSError):
        return None


def generated_paths(new_tree: Path) -> set[str]:
    """Đường dẫn file mà `appconfig.py render` (của cây mới) sinh ở app. Cây không có appconfig ⇒ rỗng."""
    ac = _tree_appconfig(new_tree)
    if ac is None:
        return set()
    return {v for v in (getattr(ac, n, None) for n in GENERATED_CONSTS) if isinstance(v, str) and v}


def _not_adopted(rel: str) -> bool:
    return rel.endswith(NOT_ADOPTED_SUFFIXES) or rel.startswith(NOT_ADOPTED_DIRS)


def new_seed_keys(plan: SyncPlan, old: dict) -> list[str]:
    """Khoá `seeded` của cây mới chưa từng có trong lock cũ (cả `seeded` lẫn `synced`) — ứng viên nhận vào app. Khoá đã
    có trong `seeded` cũ (kể cả khoá đường dẫn giữ chỗ `$primary_locale`… mà new_app ghi) KHÔNG BAO GIỜ là ứng viên:
    app đã được gieo (hoặc đã xoá) nó. Bỏ file sinh (render), metadata mẫu khi thư mục gieo mang khung, Swift, mẫu."""
    samples = set(store_sample_keys(plan))
    return sorted(key for key in plan.seeded
                  if not (key in old["seeded"] or key in old["synced"] or key in plan.generated or _not_adopted(key)
                          or key in samples))


def store_sample_keys(plan: SyncPlan) -> list[str]:
    """Metadata MẪU của template (`store/metadata/…` không qua thư mục gieo) khi thư mục gieo mang khung metadata — new_app
    bỏ chúng ở app mới; `--adopt-new-seed` không nhận và không chép chúng ra .temp/ (cùng đường dẫn với bản khung vừa tạo)."""
    if not any(src != key and key.startswith(STORE_SAMPLE_DIR) for key, src in plan.sources.items()):
        return []
    return sorted(k for k in plan.seeded if k.startswith(STORE_SAMPLE_DIR) and plan.sources.get(k, k) == k)


def render_seed(key: str, raw: bytes, *, overlay: bool, subs: dict, locales: list[str] | None, blocks_mod,
                web_cut=None) -> list[tuple[str, bytes]]:
    """Bản app của MỘT file gieo, đúng như new_app.apply_layers + cut_template_blocks + cut_web_feature_blocks làm: file
    trong thư mục gieo (`overlay`) ⇒ thay `$biến` trong ĐƯỜNG DẪN (`subs`) và trong NỘI DUNG (`.json`: giá trị escape
    JSON; file không phải UTF-8 giữ nguyên; `.html`/`.xml`: giá trị escape HTML), file `store/metadata/**/<locale
    chính>.json` nhân sang mọi locale khác của `locales`; file gieo thường giữ nội dung. Mọi file: cắt khối `template:`,
    rồi `web_cut(đường dẫn đích, nội dung)` (= `appconfig.render_web_seed` của cây mới với cấu hình CỦA APP — cắt khối
    `feature:` của trang web gieo; None ⇒ bỏ qua). Trả [(đường dẫn đích, bytes)]. Sai ⇒ SyncRefused."""
    import string
    final = string.Template(key).safe_substitute(subs) if overlay else key
    if overlay and "$" in final:
        raise SyncRefused(f"{key}: đường dẫn gieo còn biến chưa thay ({final}) — bộ biến của appconfig.seed_variables"
                          " không có biến đó")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is not None:
        if overlay:
            json_subs = {k: json.dumps(v, ensure_ascii=False)[1:-1] for k, v in subs.items()}
            markup_subs = {k: html.escape(str(v), quote=True) for k, v in subs.items()}
            text = string.Template(text).safe_substitute(
                json_subs if final.endswith(".json") else markup_subs if final.endswith((".html", ".xml")) else subs)
        style = blocks_mod.style_for(final)
        if style is not None and "template:" in text:
            try:
                text = blocks_mod.cut(text, "template", style)
            except blocks_mod.BlockError as e:
                raise SyncRefused(f"{key}: khối template: sai — {e}") from None
        if web_cut is not None:
            try:
                text = web_cut(final, text)
            except SyncRefused:
                raise
            except Exception as e:            # ConfigError của appconfig cây mới (dấu khối feature: sai)
                raise SyncRefused(f"{key}: khối feature: sai — {e}") from None
        data = text.encode("utf-8")
    else:
        data = raw
    finals = [final]
    primary = subs.get("primary_locale")
    if (overlay and locales and primary and final.startswith(STORE_SAMPLE_DIR)
            and final.endswith(f"/{primary}.json")):
        finals += [final[: -len(f"{primary}.json")] + f"{loc}.json" for loc in locales if loc != primary]
    return [(f, data) for f in finals]


@dataclass
class AdoptPlan:
    """File gieo mới sẽ được tạo ở app (`--adopt-new-seed`)."""
    files: dict[str, bytes]           # đường dẫn đích → nội dung đã thay biến + cắt khối
    modes: dict[str, bool]            # đường dẫn đích → có bit thực thi (theo digest bản nguyên)
    keys: list[str]                   # khoá `seeded` mà MỌI đích đều được tạo ⇒ không chép ra .temp/
    tracked: list[str]                # đích app đã track ⇒ không đụng (như cũ: chép bản nguyên ra .temp/)
    conflicts: dict[str, str]         # đích chưa track nhưng có thứ trên đĩa chiếm chỗ → thứ đó ⇒ từ chối


def plan_adopt(root: Path, new_tree: Path, plan: SyncPlan, old: dict, *, tag_label: str, date: str) -> AdoptPlan:
    """Kế hoạch nhận file gieo mới: biến lấy từ `app.config.toml` CỦA APP qua `appconfig.seed_variables` CỦA CÂY MỚI.
    "Chưa có ở app" = đích không track VÀ không có gì trên đĩa; có trên đĩa mà chưa track ⇒ xung đột; đã track ⇒ không
    đụng. Không ghi gì. Cấu hình hỏng / cây không có seed_variables ⇒ SyncRefused.

    Trang web gieo (`web/site/public/**`) còn được cắt khối `feature:` theo công tắc CỦA APP
    (`appconfig.render_web_seed` của cây mới — như new_app bước 4b). File SINH mới với app (khoá `seeded` mới thuộc
    `generated_paths`, vd hai `web/*/wrangler.jsonc` khi app nhận `web/`) không lấy bản của template: dựng bằng
    `appconfig.generated_files` của cây mới trên cấu hình CỦA APP (đúng thứ `appconfig.py render` sẽ ghi) — chỉ những file
    cấu hình của app thực sự sinh (vd không có `web.host_prod` ⇒ không có wrangler)."""
    root, new_tree = Path(root), Path(new_tree)
    keys = new_seed_keys(plan, old)
    gen_keys = sorted(k for k in plan.generated
                      if k in plan.seeded and k not in old["seeded"] and k not in old["synced"])
    out = AdoptPlan(files={}, modes={}, keys=[], tracked=[], conflicts={})
    if not keys and not gen_keys:
        return out
    ac = _tree_appconfig(new_tree)
    if ac is None or not hasattr(ac, "seed_variables"):
        raise SyncRefused(f"cây template mới không có {APPCONFIG_REL} với seed_variables — --adopt-new-seed cần tag có"
                          " bộ biến gieo")
    import tomllib
    try:
        with open(root / getattr(ac, "CONFIG_FILE", "app.config.toml"), "rb") as fh:
            cfg = tomllib.load(fh)
        subs = ac.seed_variables(cfg, template_tag=tag_label, date=date)
        locales = ac.store_locales(cfg) if hasattr(ac, "store_locales") else None
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise SyncRefused(f"không đọc được app.config.toml của app: {e}") from None
    except Exception as e:                    # ConfigError của appconfig cây mới (lớp riêng của module đó)
        raise SyncRefused(f"app.config.toml của app không dựng được biến gieo: {e}") from None
    web_cut = None
    if hasattr(ac, "render_web_seed"):
        def web_cut(final: str, text: str) -> str:
            return ac.render_web_seed(cfg, final, text)
    generated: dict[str, str] = {}
    if gen_keys and hasattr(ac, "generated_files"):
        try:
            generated = dict(ac.generated_files(cfg, root))
        except Exception as e:                # ConfigError của appconfig cây mới
            raise SyncRefused(f"app.config.toml của app không dựng được file sinh: {e}") from None
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import blocks as blocks_mod  # noqa: E402  (lớp đồng bộ, cạnh file này)
    tracked = set(mf.tracked(root))
    tracked_fold = {p.casefold(): p for p in tracked}
    gone = {ino for ino in (_inode(root / p) for p in plan.delete) if ino is not None}
    taken = {p.casefold() for p in plan.synced}
    for key in keys:
        src = new_tree / plan.sources.get(key, key)
        if src.is_symlink() or not src.is_file():
            raise SyncRefused(f"{plan.sources.get(key, key)}: file gieo không phải file thường trong cây mới")
        raw = src.read_bytes()
        if _digest(src, key) != plan.seeded[key]:
            raise SyncRefused(f"{key}: nội dung khác digest đã lập kế hoạch (cây template đổi trong lúc chạy?)")
        rendered = render_seed(key, raw, overlay=plan.sources.get(key, key) != key, subs=subs, locales=locales,
                               blocks_mod=blocks_mod, web_cut=web_cut)
        made = 0
        for final, data in rendered:
            try:
                _check_path("seed", final)
            except LockError as e:
                raise SyncRefused(str(e)) from None
            if final in tracked or final.casefold() in tracked_fold:
                out.tracked.append(final)
                continue
            who = _blocker(root, final, gone)
            if who is None and (final.casefold() in taken or final in out.files):
                who = final                    # trùng chỗ với file đồng bộ / file nhận khác
            if who is not None:
                out.conflicts[final] = who
                continue
            out.files[final] = data
            out.modes[final] = plan.seeded[key].endswith("+x")
            made += 1
        if made == len(rendered):
            out.keys.append(key)
    for key in gen_keys:
        if key not in generated:              # cấu hình của app không sinh file này (vd không có web)
            continue
        if key in tracked or key.casefold() in tracked_fold:
            continue                           # app đã có (vd tự render trước) — `render` lo phần còn lại
        who = _blocker(root, key, gone)
        if who is None and (key.casefold() in taken or key in out.files):
            who = key
        if who is not None:
            out.conflicts[key] = who
            continue
        out.files[key] = generated[key].encode("utf-8")
        out.modes[key] = False
        out.keys.append(key)
    out.tracked.sort()
    return out


def _dest(root: Path, rel: str, *, create: bool) -> Path:
    """Đường dẫn ghi/xoá trong app: không thành phần cha nào là symlink / file, không thoát gốc. `create` ⇒ tạo cha."""
    _check_path("sync", rel)
    cur = root
    for part in rel.split("/")[:-1]:
        cur = cur / part
        if os.path.islink(cur):
            raise SyncError(f"{rel}: thành phần {cur.relative_to(root)} là symlink — từ chối ghi qua nó")
        if os.path.lexists(cur):
            if not cur.is_dir():
                raise SyncError(f"{rel}: {cur.relative_to(root)} không phải thư mục")
        elif create:
            cur.mkdir()
    target = root / rel
    if os.path.islink(target) or (os.path.lexists(target) and not target.is_file()):
        raise SyncError(f"{rel}: đích là symlink / không phải file thường — từ chối")
    return target


def _copy_as(src: Path, dst: Path, want: str) -> None:
    """Chép `src` → `dst` với bit thực thi theo digest (`+x`), rồi khẳng định digest đúng `want`."""
    if os.path.islink(src) or not src.is_file():
        raise SyncError(f"{src}: không phải file thường trong cây template mới")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    umask = os.umask(0)
    os.umask(umask)
    os.chmod(dst, (0o777 if want.endswith("+x") else 0o666) & ~umask)
    got = mf.digest(dst)
    if got != want:
        raise SyncError(f"{src}: nội dung khác digest đã lập kế hoạch (cây template đổi trong lúc chạy?)")


def _prune_parents(root: Path, rel: str) -> None:
    cur = (root / rel).parent
    while cur != root:
        try:
            cur.rmdir()                    # chỉ xoá được thư mục rỗng
        except OSError:
            return
        cur = cur.parent


def _tag_dir(tag: str | None, commit: str) -> str:
    return tag if tag else commit[:12]


def _recovery(root: Path, added: list[str]) -> str:
    """Lệnh đưa app về đúng trước lúc đồng bộ (điều kiện vào: cây sạch ⇒ HEAD = index = working tree): gỡ file vừa
    thêm (chưa track), rồi lấy lại từ HEAD mọi file đã sửa / đã xoá, cả mục index lệnh đồng bộ đã gỡ (đổi tên hoa/thường)."""
    cmd = "git restore --staged --worktree -- ."
    if added:
        cmd = "git clean -fd -- " + " ".join(shlex.quote(p) for p in added) + " && " + cmd
    return f"cd {shlex.quote(str(root))} && {cmd}"


def _case_renames(plan: SyncPlan) -> list[str]:
    """File ghim đang xoá mà một file được ghi chỉ khác nó ở hoa/thường (đổi tên hoa/thường của template)."""
    written = {p.casefold(): p for p in plan.add}
    return sorted(d for d in plan.delete if d.casefold() in written and written[d.casefold()] != d)


def apply_sync(root: Path, new_tree: Path, plan: SyncPlan, *, source: str, tag: str | None, commit: str,
               adopt: AdoptPlan | None = None) -> None:
    """Áp kế hoạch: chép mọi file mới vào thư mục tạm TRONG repo (WORK_DIR/.staging-*), chép bản gieo mới ra
    WORK_DIR/<tag>/, rồi xoá file `delete` (và thư mục rỗng chúng để lại) TRƯỚC — chỗ chúng chiếm có thể là chỗ của file
    mới (đổi tên hoa/thường, file ↔ thư mục) —, `os.replace` từng file mới, rồi từng file gieo được nhận (`adopt`, cũng
    đã dựng sẵn trong thư mục tạm), gỡ khỏi index tên cũ của file đổi tên hoa/thường (ổ không phân biệt hoa thường: git
    không tự thấy), ghi `core.lock` SAU CÙNG. Không đụng file lớp seed ĐÃ CÓ của app. Lỗi giữa chừng ⇒ SyncError kèm
    lệnh khôi phục (`_recovery`, gồm cả file gieo vừa tạo); core.lock chưa đổi."""
    root, new_tree = Path(root), Path(new_tree)
    if plan.conflicts:
        raise SyncRefused("còn xung đột: " + ", ".join(plan.conflicts))
    if adopt is not None and adopt.conflicts:
        raise SyncRefused("còn xung đột file gieo: " + ", ".join(sorted(adopt.conflicts)))
    adopted = sorted(adopt.files) if adopt is not None else []
    lock = validate({"schema": SCHEMA, "template": {"source": source, "tag": tag, "commit": commit},
                     "synced": dict(sorted(plan.synced.items())), "seeded": dict(sorted(plan.seeded.items()))})
    temp = root / ".temp"
    work = root / WORK_DIR
    for p in (temp, work):
        if os.path.islink(p) or (os.path.lexists(p) and not p.is_dir()):
            raise SyncRefused(f"{p.relative_to(root)} là symlink / không phải thư mục — từ chối ghi vào đó")
    work.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=work))
    adopt_stage = Path(tempfile.mkdtemp(prefix=".staging-", dir=work))
    writes = sorted(plan.add + plan.update)
    touched = False
    try:
        try:
            for p in writes:
                _check_path("sync", p)
                _copy_as(new_tree / p, staging / p, plan.synced[p])
            for p in adopted:
                _check_path("seed", p)
                dst = adopt_stage / p
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(adopt.files[p])
                umask = os.umask(0)
                os.umask(umask)
                os.chmod(dst, (0o777 if adopt.modes.get(p) else 0o666) & ~umask)
            seed_dir = work / _tag_dir(tag, commit)
            for p in plan.seed_changed:
                _check_path("seed", p)
                _copy_as(new_tree / plan.sources[p], seed_dir / p, plan.seeded[p])
        except (OSError, mf.ManifestError, LockError) as e:
            raise SyncError(f"chuẩn bị file lỗi: {e} — app chưa bị đụng") from None
        try:
            for p in plan.delete:
                target = _dest(root, p, create=False)
                if os.path.lexists(target):
                    touched = True
                    target.unlink()
                    _prune_parents(root, p)
            for p in writes:
                target = _dest(root, p, create=True)
                touched = True
                _replace(staging / p, target)
            for p in adopted:
                target = _dest(root, p, create=True)
                if os.path.lexists(target):
                    raise SyncError(f"{p}: đã có thứ ở đích của file gieo mới (xuất hiện trong lúc chạy?) — không ghi đè")
                touched = True
                _replace(adopt_stage / p, target)
            renamed = _case_renames(plan)
            if renamed:
                r = mf._git(root, "rm", "-q", "--cached", "--ignore-unmatch", "--",
                            *(f":(literal){d}" for d in renamed))
                if r.returncode != 0:
                    raise SyncError(f"git rm --cached (tên cũ của file đổi hoa/thường) lỗi: "
                                    f"{r.stderr.decode('utf-8', 'replace').strip()}")
            write_lock(root, lock)
        except (OSError, SyncError, LockError) as e:
            if not touched:
                raise SyncError(f"{e} — app chưa bị đụng, {LOCK} không đổi") from None
            raise SyncError(f"lỗi giữa chừng: {e}\n{LOCK} CHƯA đổi; app đã đổi một phần. Khôi phục về trước lúc đồng bộ:\n"
                            f"  {_recovery(root, plan.add + adopted)}") from None
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(adopt_stage, ignore_errors=True)


def manual_steps(changelog: str, after: str | None, upto: str) -> str:
    """Các tiểu mục "Việc phải làm tay khi lên bản này" của mọi bản trong (after, upto] — so theo SỐ `vX.Y.Z`, tăng dần;
    `after` None (lock tạo từ ref không tag) hoặc không phải dạng `vX.Y.Z` ⇒ mọi bản tới `upto`. Mục `Chưa phát hành`
    không bao giờ được in (chưa có tag). Không có gì ⇒ chuỗi rỗng."""
    hi = mf.version_key(upto)
    if hi is None:
        return ""
    lo = mf.version_key(after) if after else None
    picked = []
    for sec in mf.changelog_sections(changelog):
        v = sec["version"]
        if v is None or v > hi or (lo is not None and v <= lo) or sec["manual"] is None:
            continue
        picked.append((v, sec["tag"], sec["manual"]))
    picked.sort(key=lambda t: t[0])
    return "\n\n".join(f"{tag}:\n" + "\n".join(lines) for _, tag, lines in picked)


def seed_notes(root: Path, old: dict, plan: SyncPlan, src: str, to: str, seed_dir: str, *, dry_run: bool) -> list[str]:
    """Dòng báo "file gieo đổi" — mỗi file một nhãn: "(đổi)" (app đã được gieo file này, template đổi bản nguyên),
    "(mới ở template)" (chưa từng gieo vào app), "(app không còn file này)" (đã gieo, app đã xoá — vd file mẫu sau
    remove_sample); nguồn là repo cục bộ ⇒ kèm lệnh `git -C <nguồn> diff <cũ>..<mới> -- <đường dẫn trong template>`
    (đích của thư mục gieo: đường dẫn trong thư mục gieo). Báo cáo thôi — không đổi file nào của app."""
    if not plan.seed_changed:
        return []
    tpl = old["template"]
    old_ref = tpl["tag"] or tpl["commit"]
    local = not _is_url(src)
    out = [f"  (bản chép là file NGUYÊN BẢN của template: chưa cắt khối template:/sample:, chưa thay biến $… — so tay"
           " rồi gộp phần nên lấy vào file của app)"]
    for p in plan.seed_changed:
        if p not in old["seeded"] and p not in old["synced"]:
            label = "(mới ở template)"
        elif not os.path.lexists(root / p):
            label = "(app không còn file này)"
        else:
            label = "(đổi)"
        line = f"  * {p}  {label}" if dry_run else f"  * {p}  {label}  →  {seed_dir}/{p}"
        out.append(line)
        if local:
            out.append(f"      git -C {shlex.quote(src)} diff {shlex.quote(old_ref)}..{shlex.quote(to)} -- "
                       f"{shlex.quote(plan.sources.get(p, p))}")
    return out


def _is_template(root: Path) -> bool:
    """Bản Python của `repo_kind` trong pre-commit: HEAD có ⇒ TEMPLATE khi dấu nằm trong HEAD (index không tính —
    stage dấu ở app không biến app thành template); HEAD chưa có ⇒ TEMPLATE khi dấu ở index VÀ core.lock chưa từng xuất
    hiện ở ref / reflog nào (git log lỗi ⇒ coi là app)."""
    if mf._git(root, "rev-parse", "--verify", "-q", "HEAD^{commit}").returncode == 0:
        return mf._git(root, "cat-file", "-e", f"HEAD:./{TEMPLATE_MARKER}").returncode == 0
    r = mf._git(root, "ls-files", "-z", "--", f":(literal){TEMPLATE_MARKER}")
    if TEMPLATE_MARKER not in r.stdout.decode("utf-8", "surrogateescape").split("\0"):
        return False
    seen = mf._git(root, "log", "-1", "--all", "--reflog", "--full-history", "--format=%H", "--", LOCK)
    return seen.returncode == 0 and not seen.stdout.strip()


def _label(tag: str | None, commit: str) -> str:
    return tag if tag else f"(commit {commit[:12]})"


def _git_root(root: Path) -> Path:
    r = mf._git(root, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        raise LockError(f"{root}: không phải repo git")
    top = Path(r.stdout.decode("utf-8", "surrogateescape").strip())
    if os.path.realpath(top) != os.path.realpath(root):
        raise LockError(f"--root {root} không phải gốc repo (gốc là {top})")
    return Path(os.path.realpath(root))


def _adopt_hint(root: Path, tree: Path, plan: SyncPlan, old: dict, to: str, commit: str, *, dry_run: bool) -> str | None:
    """MỘT dòng gợi ý `--adopt-new-seed` khi cây mới có file gieo mới mà app chưa có (không cờ). Không dựng được biến
    (cấu hình app hỏng…) ⇒ vẫn gợi ý khi có khoá ứng viên."""
    try:
        n = len(plan_adopt(root, tree, plan, old, tag_label=_label(to, commit),
                           date=datetime.date.today().isoformat()).files)
    except SyncRefused:
        n = len(new_seed_keys(plan, old))
    if not n:
        return None
    again = "chạy lại" if dry_run else (
        "NGAY sau sync này, trước `render`/sửa tay, chạy lệnh khôi phục — nó bỏ MỌI thay đổi chưa commit, kể cả sửa sau"
        f" sync — ({_recovery(root, plan.add)}) rồi chạy lại")
    return (f"Gợi ý: {n} file gieo mới ở {to} mà app chưa có (vd store/) — {again} với --adopt-new-seed để tạo chúng ở"
            " app (thay biến từ app.config.toml của app).")


def cmd_sync(root: Path, to: str, source: str | None, dry_run: bool, adopt_new_seed: bool = False) -> int:
    """`sync --to <tag>`: rc 0 xong / không có gì đổi · 1 bị từ chối hoặc lỗi giữa chừng · 2 tham số / core.lock hỏng.
    `adopt_new_seed` ⇒ file gieo MỚI ở tag đích mà app chưa có (`plan_adopt`) được tạo ở app, báo "(đã tạo ở app)"."""
    root = _git_root(Path(os.path.abspath(root)))
    if _is_template(root):
        raise LockError(f"{root} là TEMPLATE ({TEMPLATE_MARKER} được track) — sync chỉ chạy trong app")
    if not mf.is_app(root):
        raise LockError(f"{root} không track {LOCK} — sync chỉ chạy trong app sinh từ template")
    old = read_lock(root)
    if old is None:
        raise LockError(f"{LOCK} đã bị xoá khỏi working tree nhưng vẫn được track ({RESTORE})")
    _check_tag(to)
    st = mf._git(root, "status", "--porcelain")
    if st.returncode != 0 or st.stdout.strip():
        msg = st.stdout.decode("utf-8", "replace").rstrip() or st.stderr.decode("utf-8", "replace").strip()
        raise SyncRefused(f"cây chưa sạch — commit hoặc bỏ thay đổi trước khi đồng bộ:\n{msg}")
    lines = drift(root)
    if lines:
        raise SyncRefused("file lớp đồng bộ lệch core.lock — khôi phục trước (git restore …), lõi chỉ đổi qua đồng bộ:\n"
                          + "\n".join("  " + ln for ln in lines))
    if mf._git(root, "check-ignore", "-q", f"{WORK_DIR}/.probe").returncode != 0:
        raise SyncRefused(f"{WORK_DIR}/ không bị git ignore — thêm `.temp/` vào .gitignore rồi chạy lại")
    tpl = old["template"]
    src = source or tpl["source"]
    old_tag, old_label = tpl["tag"], _label(tpl["tag"], tpl["commit"])
    ko, kn = mf.version_key(old_tag), mf.version_key(to)
    if ko is not None and kn is not None and kn < ko:
        print(f"sync_core: CẢNH BÁO: {to} cũ hơn bản app đang đứng ({old_tag}) — đang hạ lõi xuống bản cũ")
    work = root / WORK_DIR
    for p in (root / ".temp", work):
        if os.path.islink(p) or (os.path.lexists(p) and not p.is_dir()):
            raise SyncRefused(f"{p.relative_to(root)} là symlink / không phải thư mục — từ chối")
    work.mkdir(parents=True, exist_ok=True)
    fetch_dir = Path(tempfile.mkdtemp(prefix=".fetch-", dir=work))
    try:
        tree = fetch_dir / "tree"
        commit = fetch_template(src, to, tree)
        try:
            plan = plan_sync(root, tree)
        except TreeUnusable as e:
            raise SyncRefused(f"{e}\n{bootstrap_hint(root, src, to)}") from None
        changelog = ""
        if mf.classify(plan.manifest, mf.CHANGELOG_FILE) == "template_only":
            cl = tree / mf.CHANGELOG_FILE
            if cl.is_file() and not cl.is_symlink():
                changelog = cl.read_text(encoding="utf-8", errors="replace")
        steps = manual_steps(changelog, old_tag, to)
        new_lock = {"schema": SCHEMA, "template": {"source": public_source(tpl["source"]), "tag": to, "commit": commit},
                    "synced": plan.synced, "seeded": plan.seeded}
        if lock_text(new_lock) == lock_text(old):
            print(f"sync_core: không có gì đổi — app đã đứng ở {to} ({commit[:12]})")
            return 0
        if plan.conflicts:
            print(f"sync_core: TỪ CHỐI — {len(plan.conflicts)} đường dẫn thuộc lớp đồng bộ của {to} đang bị chiếm ở app"
                  f" bởi thứ {LOCK} không ghim. Không ghi gì.", file=sys.stderr)
            for p in plan.conflicts:
                kind, who = plan.conflict_reasons.get(p, ("app", p))
                if kind == "seed":
                    print(f"  ! {p} — trước là lớp gieo (bản của app), nay template sở hữu (lớp đồng bộ): bản của app"
                          " sẽ bị thay bằng bản của template. Giữ lại thay đổi của bạn nếu cần (chép ra chỗ khác),"
                          f" git rm {shlex.quote(p)}, commit, rồi chạy lại.", file=sys.stderr)
                elif kind == "dir":
                    print(f"  ! {p} — file của app nằm trong thư mục mà ở {to} template sở hữu (lớp đồng bộ): chuyển"
                          f" {p} sang {APP_PLACE}, commit, rồi chạy lại.", file=sys.stderr)
                else:
                    where = "" if who == p else f" (bị chặn bởi {who})"
                    print(f"  ! {p}{where} — file của app nằm ở chỗ template nay sở hữu: chuyển/đổi tên file của app"
                          f" sang {APP_PLACE}, commit, rồi chạy lại.", file=sys.stderr)
            return 1
        adopt, hint = None, None
        if adopt_new_seed:
            adopt = plan_adopt(root, tree, plan, old, tag_label=_label(to, commit),
                               date=datetime.date.today().isoformat())
            if adopt.conflicts:
                print(f"sync_core: TỪ CHỐI — {len(adopt.conflicts)} file gieo mới của {to} có chỗ đang bị chiếm ở app"
                      " bởi thứ git không track. Không ghi gì.", file=sys.stderr)
                for p, who in sorted(adopt.conflicts.items()):
                    where = "" if who == p else f" (bị chặn bởi {who})"
                    print(f"  ! {p}{where} — chưa track nhưng đã có trên đĩa: xoá/chuyển nó đi, hoặc git add + commit"
                          " nếu đó là file của app (khi đó không nhận), rồi chạy lại.", file=sys.stderr)
                return 1
            # File được tạo ở app không chép bản nguyên ra .temp/ nữa — báo riêng "(đã tạo ở app)". Metadata mẫu của
            # template (bản khung vừa thay nó) cũng không: cùng đường dẫn, dễ nhầm với file vừa tạo.
            skip = set(adopt.keys) | set(store_sample_keys(plan))
            plan.seed_changed = [p for p in plan.seed_changed if p not in skip]
        else:
            hint = _adopt_hint(root, tree, plan, old, to, commit, dry_run=dry_run)
        head = "kế hoạch (--dry-run, không ghi gì)" if dry_run else "đồng bộ"
        print(f"sync_core: {head} lõi {old_label} → {to} ({commit[:12]}) từ {public_source(src)}")
        for mark, items, note in (("+", plan.add, "thêm"), ("~", plan.update, "sửa"), ("-", plan.delete, "xoá"),
                                  (">", plan.released, "nay do app sở hữu (chuyển sang lớp gieo — giữ file, bỏ khỏi "
                                                       f"{LOCK})")):
            for p in items:
                print(f"  {mark} {p}  ({note})")
        seed_dir = f"{WORK_DIR}/{_tag_dir(to, commit)}"
        notes = seed_notes(root, old, plan, src, to, seed_dir, dry_run=dry_run)
        adopted = sorted(adopt.files) if adopt is not None else []
        if dry_run:
            if adopted:
                print("File gieo mới — sẽ tạo ở app (thay biến từ app.config.toml của app, cắt khối template:):")
                print("\n".join(f"  * {p}  (sẽ tạo ở app)" for p in adopted))
            if notes:
                print(f"File gieo đổi ở template (sẽ chép bản mới ra {seed_dir}/ để so tay, app không bị đụng):")
                print("\n".join(notes))
            if hint:
                print(hint)
            return 0
        apply_sync(root, tree, plan, source=public_source(tpl["source"]), tag=to, commit=commit, adopt=adopt)
    finally:
        shutil.rmtree(fetch_dir, ignore_errors=True)
        _FETCHED.pop(os.path.realpath(fetch_dir / "tree"), None)
    print(f"sync_core: đã đồng bộ lõi {old_label} → {to}: {len(plan.add)} thêm, {len(plan.update)} sửa, "
          f"{len(plan.delete)} xoá, {len(plan.released)} nay do app sở hữu")
    if adopted:
        print("File gieo mới — đã tạo ở app (thay biến từ app.config.toml của app, cắt khối template:; đọc lại rồi sửa"
              " cho đúng app):")
        print("\n".join(f"  * {p}  (đã tạo ở app)" for p in adopted))
    if notes:
        print(f"File gieo đổi ở template — app KHÔNG bị đụng; bản mới để so tay ở {seed_dir}/:")
        print("\n".join(notes))
    if steps:
        print(f"Việc phải làm tay (CHANGELOG của template, {old_label} → {to}):")
        print("\n".join("  " + ln if ln else "" for ln in steps.splitlines()))
    else:
        print(f"Việc phải làm tay: CHANGELOG của template không ghi việc nào cho {old_label} → {to}.")
    if hint:
        print(hint)
    print("Bước tiếp theo:")
    print("  python3 tools/common/appconfig.py render")
    print("  (cd AppHost && xcodegen generate)")
    print("  python3 tools/dev/run_tests.py --full")
    print(f"  git add -A && git commit -m \"chore(core): đồng bộ lõi {old_label} → {to}\"")
    return 0


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=str(Path(__file__).resolve().parents[2]),
                        help="gốc repo app (mặc định suy từ vị trí script)")
    ap = argparse.ArgumentParser(description="core.lock của app: file lớp đồng bộ không được lệch template")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_check = sub.add_parser("check", parents=[common], help="rc 0 khớp · 1 lệch · 2 không có/hỏng core.lock")
    p_check.add_argument("--staged", action="store_true",
                         help="so nội dung trong index git đang commit (pre-commit) thay cho working tree")
    sub.add_parser("status", parents=[common], help="in tag, commit, nguồn, số file của core.lock")
    p_sync = sub.add_parser("sync", parents=[common],
                            help="kéo file lớp đồng bộ của template ở <tag> vào app (rc 0 xong · 1 từ chối · 2 tham số)")
    p_sync.add_argument("--to", required=True, metavar="TAG", help="tag template đích (vX.Y.Z)")
    p_sync.add_argument("--source", help="đường dẫn repo template hoặc URL (mặc định: template.source trong core.lock)")
    p_sync.add_argument("--dry-run", action="store_true", help="chỉ in kế hoạch, không ghi gì")
    p_sync.add_argument("--adopt-new-seed", action="store_true",
                        help="tạo ở app các file lớp gieo MỚI ở tag đích mà app chưa có (thay biến từ app.config.toml"
                             " của app, cắt khối template:)")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if args.cmd == "sync":
        try:
            return cmd_sync(root, args.to, args.source, args.dry_run, args.adopt_new_seed)
        except (SyncRefused, SyncError) as e:
            print(f"sync_core: TỪ CHỐI: {e}" if isinstance(e, SyncRefused) else f"sync_core: FAIL: {e}",
                  file=sys.stderr)
            return 1
        except (LockError, mf.ManifestError) as e:
            print(f"FAIL: {e}", file=sys.stderr)
            return 2
    try:
        if args.cmd == "check":
            lines = drift(root, staged=args.staged)
            for line in lines:
                print(line)
            if lines:
                print(f"sync_core: {len(lines)} file lớp đồng bộ lệch {LOCK}", file=sys.stderr)
                return 1
            print(f"sync_core: OK — file lớp đồng bộ khớp {LOCK}")
            return 0
        lock = read_lock(root)
        if lock is None:
            raise LockError(f"không có {LOCK} ở {root} — đây là template (lock chỉ có ở app)")
        tpl = lock["template"]
        print(f"tag: {tpl['tag'] if tpl['tag'] is not None else '(không tag)'}")
        print(f"commit: {tpl['commit']}")
        print(f"nguồn: {tpl['source']}")
        print(f"file đồng bộ: {len(lock['synced'])}")
        print(f"file gieo: {len(lock['seeded'])}")
        return 0
    except (LockError, mf.ManifestError) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
