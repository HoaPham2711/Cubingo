#!/usr/bin/env python3
"""Kéo nhánh `develop` LOCAL lên khớp `origin/develop` — chạy sau khi merge PR (nhà máy agent).

Sau `gh pr merge`, GitHub có commit mới nhưng `develop` local (thường đang checkout ở checkout chính
của repo) vẫn cũ ⇒ worktree mới rẽ từ develop cũ, phiên khác đọc code cũ. Script này:

1. `git fetch origin develop`.
2. Tìm worktree đang checkout `develop` (`git worktree list --porcelain`):
   - có ⇒ `git -C <worktree> merge --ff-only origin/develop`. Git tự từ chối nếu thay đổi chưa commit
     đụng file được cập nhật — KHÔNG stash, KHÔNG reset: báo lại để user xử lý.
   - không ⇒ `git fetch origin develop:develop` (cập nhật ref, chỉ fast-forward).
3. develop local có commit chưa push (lệch nhánh) ⇒ không fast-forward được ⇒ báo, không ép.

Chỉ fast-forward, không bao giờ làm mất việc. In một dòng `SYNC-DEVELOP <trạng thái>: …`.
Mã thoát: 0 = đã khớp/đã cập nhật, 1 = không cập nhật được (lý do ở stdout).

    python3 tools/dev/sync_develop.py [--repo <đường dẫn bất kỳ trong repo>] [--branch develop]
Test: python3 -m unittest tools/dev/test_sync_develop.py
"""
import argparse
import subprocess
import sys
from pathlib import Path


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def worktree_for_branch(repo, branch):
    """Đường dẫn worktree đang checkout `branch`, hoặc None."""
    r = git(repo, "worktree", "list", "--porcelain")
    if r.returncode != 0:
        return None
    path = None
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line == f"branch refs/heads/{branch}" and path:
            return Path(path)
    return None


def rev(repo, ref):
    r = git(repo, "rev-parse", "--verify", "--quiet", ref)
    return r.stdout.strip() if r.returncode == 0 else None


def sync(repo, branch="develop", remote="origin"):
    """Trả (ok: bool, thông điệp)."""
    f = git(repo, "fetch", "--quiet", remote, branch)
    if f.returncode != 0:
        return False, f"fetch {remote}/{branch} lỗi: {f.stderr.strip()}"
    remote_sha = rev(repo, f"refs/remotes/{remote}/{branch}")
    local_sha = rev(repo, f"refs/heads/{branch}")
    if remote_sha is None:
        return False, f"không thấy {remote}/{branch}"
    if local_sha == remote_sha:
        return True, f"{branch} đã khớp {remote}/{branch} ({remote_sha[:8]})"
    if local_sha and git(repo, "merge-base", "--is-ancestor", local_sha, remote_sha).returncode != 0:
        return False, (f"{branch} local có commit chưa có trên {remote} (lệch nhánh) — không fast-forward được; "
                       f"tự xử lý (push hoặc merge) rồi chạy lại")
    wt = worktree_for_branch(repo, branch)
    if wt is not None:
        m = git(wt, "merge", "--ff-only", "--quiet", f"refs/remotes/{remote}/{branch}")
        if m.returncode != 0:
            err = (m.stderr or m.stdout).strip().splitlines()
            return False, (f"{branch} đang checkout ở {wt} nhưng không fast-forward được (thường do thay đổi chưa "
                           f"commit đụng file vừa cập nhật — không stash/reset hộ): {' '.join(err[:3])}")
        return True, f"{branch} ở {wt}: {(local_sha or '')[:8]} → {remote_sha[:8]}"
    u = git(repo, "fetch", "--quiet", remote, f"{branch}:{branch}")
    if u.returncode != 0:
        return False, f"cập nhật ref {branch} lỗi: {u.stderr.strip()}"
    return True, f"{branch} (ref, không checkout ở đâu): {(local_sha or 'mới')[:8]} → {remote_sha[:8]}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--branch", default="develop")
    a = ap.parse_args(argv)
    ok, msg = sync(Path(a.repo), a.branch)
    print(f"SYNC-DEVELOP {'OK' if ok else 'FAIL'}: {msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
