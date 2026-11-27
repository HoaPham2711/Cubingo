"""Snapshot trạng thái remote trước khi apply: <state_dir>/snapshots/<UTC>/metadata + fingerprint.txt."""
from __future__ import annotations

import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asc_cli  # noqa: E402
import planner  # noqa: E402
import remote as remote_mod  # noqa: E402
import store  # noqa: E402

TS_FORMAT = "%Y%m%dT%H%M%SZ"


def root() -> Path:
    """Thư mục chứa snapshot: `store.state_dir()/snapshots` (tuyệt đối)."""
    return store.state_dir() / "snapshots"


def take(version: str, *, run: Callable[..., Any] = asc_cli.run, now: datetime | None = None) -> Path:
    """Pull remote vào <root()>/<ts>/metadata, ghi fingerprint.txt. Lỗi ⇒ xoá thư mục dở rồi raise."""
    now = now or datetime.now(timezone.utc)
    snap = root() / now.strftime(TS_FORMAT)
    if snap.exists():
        # Hai lần take cùng một giây: không bao giờ đụng/xoá snapshot cũ (bản phục hồi).
        raise FileExistsError(f"snapshot {snap.name} đã tồn tại; đợi sang giây sau rồi thử lại")
    try:
        values = remote_mod.pull_remote(version, snap / "metadata", run=run)
        (snap / "fingerprint.txt").write_text(planner.fingerprint(values) + "\n", encoding="utf-8")
    except BaseException:
        shutil.rmtree(snap, ignore_errors=True)
        raise
    return snap


def _parse(name: str) -> datetime | None:
    try:
        return datetime.strptime(name, TS_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def prune(root: Path, keep: int = 10, keep_days: int = 30, *, now: datetime | None = None) -> list[Path]:
    """Xoá bản nằm ngoài `keep` bản mới nhất VÀ cũ hơn `keep_days` ngày; trả danh sách đã xoá."""
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    if not root.is_dir():
        return []
    snaps = sorted(((t, p) for p in root.iterdir() if p.is_dir() and (t := _parse(p.name))),
                   key=lambda x: x[0], reverse=True)
    cutoff = now - timedelta(days=keep_days)
    removed = []
    for t, p in snaps[keep:]:
        if t < cutoff:
            shutil.rmtree(p)
            removed.append(p)
    return removed
