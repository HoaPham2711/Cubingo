#!/usr/bin/env python3
""""Phá code → test PHẢI đỏ" một cách AN TOÀN cho verifier (memory test-green-does-not-mean-test-guards).

    python3 tools/factory/mutate.py --file <đường dẫn> --find "<chuỗi gốc>" --replace "<chuỗi phá>" \
        [--kill-pattern "<regex trong output chứng tỏ TEST đỏ>"] -- <lệnh test…>
    python3 tools/factory/mutate.py --recover          # khôi phục mọi file còn dở (sau khi bị kill -9)

Sao lưu file → thay ĐÚNG MỘT lần --find → chạy lệnh test → KHÔI PHỤC → kiểm sha256 trùng bản gốc. Không dùng
git stash/checkout (stash dùng chung giữa các worktree; checkout xoá thay đổi chưa commit của thợ).

An toàn (factory-review 2026-11-06 bắt 4 lỗi ở bản đầu):
- Khoá `flock` theo đường dẫn file: hai mutate song song trên CÙNG file ⇒ cái sau từ chối (exit 2) thay vì khôi
  phục về bản đã bị cái trước phá.
- Bản ghi khôi phục trên đĩa (`$TMPDIR/factory-mutate/<băm>/`) viết TRƯỚC khi phá; SIGTERM/SIGHUP/SIGINT ⇒ khôi
  phục rồi thoát; kể cả SIGKILL, lần chạy sau (hoặc `--recover`) tự khôi phục trước khi làm gì khác.
- Không coi mọi rc≠0 là "test đỏ": rc 3 (`[false-green]` của run_tests.py), 124 (timeout), lỗi build/cú pháp ⇒
  `MUTATION INCONCLUSIVE`. Có `--kill-pattern` ⇒ chỉ KILLED khi output khớp mẫu đó.

Dòng cuối stdout: `MUTATION KILLED` / `MUTATION SURVIVED` / `MUTATION INCONCLUSIVE`.
Exit: 0 killed, 1 survived, 2 lỗi dùng/khoá/khôi phục, 4 inconclusive.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

STATE_ROOT = Path(os.environ.get("FACTORY_MUTATE_STATE") or Path(tempfile.gettempdir()) / "factory-mutate")
INCONCLUSIVE_RC = {3, 124}
INCONCLUSIVE_OUT = re.compile(r"\[false-green\]|\*\* BUILD FAILED \*\*|BUILD FAILED|SyntaxError|IndentationError|"
                              r"error: compile|Testing cancelled|xcodebuild: error", re.I)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def state_dir(f: Path) -> Path:
    return STATE_ROOT / hashlib.sha1(str(f.resolve()).encode()).hexdigest()[:16]


def clear_record(d: Path) -> None:
    """Xoá bản ghi khôi phục — KHÔNG xoá thư mục (file `lock` đang được flock giữ; review vòng 2)."""
    for name in ("meta.json", "orig"):
        (d / name).unlink(missing_ok=True)


def restore_pending(d: Path) -> str | None:
    """Có bản ghi dở ⇒ khôi phục bản gốc NẾU file hiện tại đúng là bản đã bị phá (sha khớp `mutated`).
    File đã đổi sau đó (thợ sửa thật sau lần bị kill -9) ⇒ KHÔNG đè, báo lỗi, giữ bản gốc để người quyết.
    Trả đường dẫn đã khôi phục (hoặc None khi không có gì dở)."""
    meta = d / "meta.json"
    if not meta.exists():
        return None
    info = json.loads(meta.read_text(encoding="utf-8"))
    target, orig = Path(info["path"]), d / "orig"
    cur = sha(target) if target.exists() else None
    if cur == info["sha"]:  # đã là bản gốc (bị kill sau khi khôi phục xong)
        clear_record(d)
        return None
    if cur != info.get("mutated"):
        raise RuntimeError(f"{target} đã đổi sau lần mutate bị ngắt — KHÔNG tự đè. Bản gốc trước khi phá: {orig}; "
                           f"so sánh rồi tự quyết, xong xoá {meta}")
    shutil.copy2(orig, target)
    if sha(target) != info["sha"]:
        raise RuntimeError(f"khôi phục {target} lệch sha — bản gốc còn ở {orig}")
    clear_record(d)
    return str(target)


def recover_all() -> int:
    n = bad = 0
    for d in sorted(STATE_ROOT.glob("*")) if STATE_ROOT.exists() else []:
        lock = open(d / "lock", "a+")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"[mutate] {d.name}: đang có mutate chạy, bỏ qua")
            continue
        try:
            p = restore_pending(d)
        except RuntimeError as e:
            print(f"mutate.py: {e}", file=sys.stderr)
            bad += 1
            continue
        if p:
            n += 1
            print(f"[mutate] đã khôi phục {p}")
    print(f"[mutate] recover: {n} file" + (f", {bad} file cần người quyết" if bad else ""))
    return 2 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--file")
    ap.add_argument("--find")
    ap.add_argument("--replace")
    ap.add_argument("--kill-pattern", help="regex trong output chứng tỏ test ĐỎ (VD 'FAILED|failures=')")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--recover", action="store_true")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    if a.recover:
        return recover_all()
    if not (a.file and a.find is not None and a.replace is not None):
        print("mutate.py: cần --file, --find, --replace", file=sys.stderr)
        return 2
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not cmd:
        print("mutate.py: thiếu lệnh test sau --", file=sys.stderr)
        return 2
    f = Path(a.file)
    if not f.is_file():
        print(f"mutate.py: không có file {f}", file=sys.stderr)
        return 2

    d = state_dir(f)
    d.mkdir(parents=True, exist_ok=True)
    lock = open(d / "lock", "a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"mutate.py: đang có mutate khác trên {f} — chờ nó xong (không chạy song song cùng file)", file=sys.stderr)
        return 2
    try:
        prev = restore_pending(d)  # lần trước bị kill -9 giữa chừng
    except RuntimeError as e:
        print(f"mutate.py: {e}", file=sys.stderr)
        return 2
    if prev:
        print(f"[mutate] phát hiện lần chạy dở trước — đã khôi phục {prev}")

    text = f.read_text(encoding="utf-8")
    n = text.count(a.find)
    if n != 1:
        print(f"mutate.py: --find phải xuất hiện đúng 1 lần (thấy {n}) — dùng chuỗi dài hơn", file=sys.stderr)
        return 2
    orig_sha = sha(f)
    new_text = text.replace(a.find, a.replace, 1)
    mutated_sha = hashlib.sha256(new_text.encode("utf-8")).hexdigest()
    shutil.copy2(f, d / "orig")
    (d / "meta.json").write_text(json.dumps({"path": str(f.resolve()), "sha": orig_sha, "mutated": mutated_sha}),
                                 encoding="utf-8")

    child: list[subprocess.Popen] = []

    def kill_group(sig=signal.SIGKILL):
        for c in child:
            if c.poll() is None:
                try:
                    os.killpg(c.pid, sig)  # cả cháu (xcodebuild/simctl) — con chạy ở session riêng
                except (ProcessLookupError, PermissionError):
                    c.kill()

    def on_signal(signum, _frame):
        kill_group(signal.SIGTERM)
        try:
            restore_pending(d)
            sys.stderr.write(f"[mutate] tín hiệu {signum}: đã khôi phục {f}\n")
        finally:
            os._exit(128 + signum)

    old = {s: signal.signal(s, on_signal) for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
    rc, out = None, []
    try:
        f.write_text(new_text, encoding="utf-8")
        print(f"[mutate] {f}: thay 1 chỗ, chạy: {' '.join(cmd)}", flush=True)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                             start_new_session=True)
        child.append(p)

        def pump():  # đọc output ở luồng riêng: vòng đọc không được chặn --timeout (review vòng 2)
            for line in p.stdout:
                sys.stdout.write(line)
                out.append(line)

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        try:
            rc = p.wait(timeout=a.timeout)
        except subprocess.TimeoutExpired:
            kill_group()
            p.wait()
            rc = 124
        reader.join(timeout=5)
    finally:
        try:
            restore_pending(d)
        except RuntimeError as e:
            print(f"mutate.py: KHÔI PHỤC LỖI — {e}", file=sys.stderr)
            return 2
        for s, h in old.items():
            signal.signal(s, h)
    if sha(f) != orig_sha:
        print(f"mutate.py: KHÔI PHỤC LỖI — sha {f} lệch bản gốc", file=sys.stderr)
        return 2
    print(f"[mutate] đã khôi phục {f} (sha256 khớp bản gốc); lệnh test rc={rc}")
    blob = "".join(out)
    if rc == 0:
        print("MUTATION SURVIVED — test vẫn xanh khi code bị phá: test KHÔNG gác bất biến này")
        return 1
    if rc in INCONCLUSIVE_RC or INCONCLUSIVE_OUT.search(blob) or (a.kill_pattern and not re.search(a.kill_pattern, blob)):
        why = ("rc=%s" % rc) if rc in INCONCLUSIVE_RC else ("output không khớp --kill-pattern" if a.kill_pattern
                                                              and not re.search(a.kill_pattern, blob) else "lỗi build/cú pháp/false-green trong output")
        print(f"MUTATION INCONCLUSIVE — {why}: không chứng minh được test đỏ vì đúng bất biến (chọn phép phá khác)")
        return 4
    print("MUTATION KILLED — test đỏ khi code bị phá: test có gác")
    return 0


if __name__ == "__main__":
    sys.exit(main())
