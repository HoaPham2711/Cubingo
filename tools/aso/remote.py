"""Đọc trạng thái remote (ASC) qua wrapper `asc_cli`: pull metadata, kiểm version sửa được."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asc_cli  # noqa: E402
import store  # noqa: E402

# Trạng thái version cho phép sửa mọi field (spec: Ruling 4).
EDITABLE_STATES = {"PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED"}


# Version đang bán trên App Store: appVersionState = READY_FOR_DISTRIBUTION (asc 5.17.1 thật),
# appStoreState cũ = READY_FOR_SALE.
LIVE_STATES = {"READY_FOR_DISTRIBUTION", "READY_FOR_SALE"}


def pull_remote(version: str, dest: Path, *, run: Callable[..., Any] = asc_cli.run) -> store.Metadata:
    """Pull metadata vào thư mục `dest` MỚI/RỖNG (không dùng --force), bỏ default.json, rồi load.

    `default.json` chỉ là bản dự phòng suy ra, không phải locale thật ⇒ xoá trước khi load.
    Trả `store.Metadata`: `.vdir` = tên thư mục version asc vừa ghi ("version" hay "versions").
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        raise ValueError(f"thư mục pull phải rỗng: {dest}")
    run(["metadata", "pull", "--app", asc_cli.app_id(), "--version", version, "--dir", str(dest)])
    for stray in dest.rglob("default.json"):
        stray.unlink()
    return store.load(dest, version)


def _find_key(obj: Any, key: str):
    """Tìm giá trị của `key` ở độ sâu bất kỳ; không thấy ⇒ None."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        children = obj.values()
    elif isinstance(obj, list):
        children = obj
    else:
        return None
    for child in children:
        found = _find_key(child, key)
        if found is not None:
            return found
    return None


def state_from_attributes(attrs: dict) -> str | None:
    """Trạng thái version từ `attributes`: appVersionState, thiếu thì appStoreState, không có ⇒ None."""
    return attrs.get("appVersionState") or attrs.get("appStoreState") or None


def version_state(version: str, *, run: Callable[..., Any] = asc_cli.run) -> str | None:
    """Trạng thái version từ `versions view --include build`; thiếu/shape lạ ⇒ None.

    asc 5.17.1: KHÔNG có `--include` thì `versions view` in summary rút gọn (id, versionString, platform,
    state…) — không có `data.attributes`. Vì vậy luôn xin envelope (`--include build`, như release.py) và
    đọc `data.attributes`; vẫn nhận shape rút gọn (`state` ở gốc hoặc dưới `data`) phòng asc đổi lại."""
    data = run(["versions", "view", "--app", asc_cli.app_id(), "--version", version, "--include", "build"])
    if not isinstance(data, dict):
        return None
    inner = data.get("data")
    if isinstance(inner, dict):
        attrs = inner.get("attributes")
        if isinstance(attrs, dict):
            state = state_from_attributes(attrs)
            if isinstance(state, str) and state:
                return state
        if isinstance(inner.get("state"), str) and inner["state"]:
            return inner["state"]
    if isinstance(data.get("state"), str) and data["state"]:
        return data["state"]
    return None


def version_editable(version: str, *, run: Callable[..., Any] = asc_cli.run) -> bool:
    """True nếu trạng thái thuộc EDITABLE_STATES; không đọc được trạng thái ⇒ False (an toàn)."""
    return version_state(version, run=run) in EDITABLE_STATES
