"""Applier: đường code DUY NHẤT ghi lên ASC (spec §6.2, §8).

Thứ tự bắt buộc của `apply`:
  1. đọc plan, mã tính lại phải == mã user đã duyệt (`expect`);
  2. pull remote, fingerprint phải == lúc plan; có op ngoài promotionalText ⇒ kiểm lại version sửa được;
  3. snapshot (lỗi ⇒ dừng, không push);
  4. dựng thư mục tạm = remote vừa pull + đúng các op của plan (KHÔNG đọc store/), cùng tên thư mục
     version (`version/`/`versions/`) mà pull vừa thấy, push;
  5. pull lại, mỗi op phải đã lên đúng `new`;
  6. nối một dòng vào ledger `<state_dir>/applied.jsonl`.
Plan release (`kind: "release"`): sau bước 1 rẽ sang `release.apply_release` (không snapshot/push metadata),
ledger cùng file qua `_record_release`. Loại plan khác (vd plan ảnh/CPP — template chưa mang) ⇒ `planner.load_plan`
từ chối ở bước 1, không có lối ghi nào.
"""
from __future__ import annotations

import json
import shlex
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asc_cli  # noqa: E402
import planner  # noqa: E402
import store  # noqa: E402



def ledger_path() -> Path:
    """Ledger mọi lần push: `store.state_dir()/applied.jsonl` (tuyệt đối)."""
    return store.state_dir() / "applied.jsonl"


@dataclass
class ApplyResult:
    plan_id: str
    snapshot: Path
    changed: int


def make_push(run: Callable[..., Any] = asc_cli.run) -> Callable[[Path, str], Any]:
    """Hàm push thật: `metadata push` đúng argv đã chốt, write=True (policy chỉ cho đúng lệnh này ghi)."""
    def push(directory: Path, version: str):
        return run(["metadata", "push", "--app", asc_cli.app_id(), "--version", version,
                    "--dir", str(directory)], write=True)
    return push


def restore_hint(snap: Path) -> str:
    """Lệnh restore dán được: đường dẫn state dir có dấu cách ("Application Support") ⇒ quote."""
    return f"python3 tools/aso/aso.py restore --snapshot {shlex.quote(str(snap))}"


def _merge(remote: dict, plan: planner.Plan) -> dict:
    """remote + đúng các op của plan; tự kiểm chỉ khác remote ở khoá của op, không mất khoá nào."""
    merged = dict(remote)
    op_keys = set()
    for o in plan.ops:
        key = (o.scope, o.locale, o.field)
        if key in op_keys:
            raise RuntimeError(f"plan có hai op cùng khoá {key}")
        op_keys.add(key)
        if o.kind == "update":
            if remote.get(key) != o.old:
                raise RuntimeError(f"op update {key}: giá trị cũ trên ASC không khớp plan")
        elif o.kind == "add":
            if key in remote:
                raise RuntimeError(f"op add {key}: khoá đã có trên ASC")
        else:
            raise RuntimeError(f"op lạ: {o.kind}")
        if not isinstance(o.new, str):
            raise RuntimeError(f"op {key}: giá trị mới không phải chuỗi")
        if planner.is_wipe(remote.get(key), o.new):
            raise RuntimeError(f"op {key}: xoá nội dung field bị cấm — tự xử lý trên ASC")
        merged[key] = o.new
    missing = set(remote) - set(merged)
    if missing:
        raise RuntimeError(f"thư mục push thiếu khoá đang có trên ASC: {sorted(missing)}")
    diff = {k for k in merged if merged[k] != remote.get(k)}
    if diff != op_keys:
        raise RuntimeError(f"thư mục push khác remote ngoài các op của plan: {sorted(diff ^ op_keys)}")
    return merged


def _append_ledger(plan: planner.Plan, snap: Path, status: str) -> None:
    """Một dòng cho MỌI lần push đã chạy; status ∈ ok | unverified | mismatch | push_failed."""
    ledger = ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "plan_id": plan.plan_id,
        "version": plan.version,
        "snapshot": str(snap),
        "ops": len(plan.ops),
        "status": status,
    }
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def _record(plan: planner.Plan, snap: Path, status: str) -> None:
    """Ghi ledger, KHÔNG BAO GIỜ che lỗi gốc: OSError ⇒ cảnh báo stderr rồi đi tiếp
    (nhánh lỗi vẫn raise RuntimeError gốc kèm snapshot + lệnh restore; nhánh ok vẫn trả thành công)."""
    try:
        _append_ledger(plan, snap, status)
    except OSError as e:
        print(f"CẢNH BÁO: không ghi được ledger {ledger_path()} (plan {plan.plan_id}, status {status}, "
              f"snapshot {snap}): {e}", file=sys.stderr)


def _record_release(plan, status: str, extra: dict) -> None:
    """Dòng ledger cho plan release (cùng applied.jsonl); status ∈ ok | upload_failed | wait_failed | build_invalid |
    create_failed | attach_failed | verify_failed. OSError ⇒ cảnh báo stderr, không che lỗi gốc (như `_record`)."""
    line = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "plan_id": plan.plan_id, "kind": "release", "version": plan.version, "build": plan.build,
        "status": status, **extra,
    }
    try:
        ledger = ledger_path()
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"CẢNH BÁO: không ghi được ledger {ledger_path()} (plan release {plan.plan_id}, status {status}): {e}",
              file=sys.stderr)


def _recovery(snap: Path) -> str:
    return f"Snapshot trước khi ghi: {snap}. Khôi phục: {restore_hint(snap)} (ra plan để duyệt, rồi apply như thường)"


def _diff_lines(expected: dict, actual: dict) -> list[str]:
    """Các khoá mà `actual` khác `expected` (thiếu, thừa, khác giá trị), mỗi khoá một dòng ngắn."""
    out = []
    for key in sorted(set(expected) | set(actual)):
        if expected.get(key) != actual.get(key):
            got = actual.get(key)
            shown = "<không có>" if got is None else repr(got[:80])
            out.append(f"{' '.join(key)} = {shown}")
    return out


def apply(plan_path: Path, expect: str, *,
          pull: Callable[[str], dict],
          push: Callable[[Path, str], Any],
          take_snapshot: Callable[[str], Path],
          editable: Callable[[str], bool],
          run: Callable[..., Any] = asc_cli.run):
    """Trả ApplyResult (plan metadata) hoặc dict kết quả (plan release)."""
    # Áp plan đã duyệt lên ASC. Mọi bước kiểm hỏng ⇒ raise TRƯỚC khi ghi (trừ bước 5: kiểm sau ghi).
    # (1) Mã plan tính lại từ nội dung, không tin mã ghi trong file.
    plan = planner.load_plan(Path(plan_path))
    if plan.plan_id != expect:
        raise ValueError(f"plan đã đổi (mã hiện tại {plan.plan_id}, đã duyệt {expect}) — làm plan mới")
    if getattr(plan, "kind", None) == "release":
        # Plan release: không snapshot/push metadata — chạy đúng các bước đã duyệt.
        import release  # import muộn: release.py import applier
        return release.apply_release(plan, run=run)
    current_app = asc_cli.app_id()
    if plan.app_id != current_app:
        raise ValueError(f"plan làm cho app {plan.app_id or '(không ghi)'}, app hiện tại là {current_app} — "
                         "làm plan mới trong đúng repo app")
    if not plan.ops:
        raise ValueError("plan không có thay đổi nào — không có gì để apply")

    # (2) ASC phải y như lúc plan.
    remote = pull(plan.version)
    if not isinstance(remote, store.Metadata):
        raise RuntimeError("pull không báo bố cục thư mục version (version/ hay versions/) — không push")
    if planner.fingerprint(remote) != plan.remote_fingerprint:
        raise RuntimeError("ASC đã đổi từ lúc plan — làm plan mới")
    if any(o.field != "promotionalText" for o in plan.ops) and not editable(plan.version):
        raise RuntimeError(f"version {plan.version} không còn sửa được (đang bán / chờ duyệt): "
                           "chỉ đổi được promotionalText — làm plan mới")
    merged = _merge(remote, plan)  # kiểm trước snapshot: plan lỗi thì không tốn snapshot

    # (3) Snapshot lỗi ⇒ exception bay ra, không push. Snapshot phải chụp đúng trạng thái đã plan.
    snap = Path(take_snapshot(plan.version))
    try:
        snap_fp = (snap / "fingerprint.txt").read_text(encoding="utf-8").strip()
    except OSError as e:
        raise RuntimeError(f"không đọc được fingerprint của snapshot {snap}: {e} — không push") from e
    if snap_fp != plan.remote_fingerprint:
        raise RuntimeError(f"ASC đổi trong lúc chụp snapshot — làm plan mới (snapshot {snap})")

    # (4) Push đúng thứ đã duyệt: CHỈ các field của op (giá trị lấy từ `merged`), không gì từ store/.
    # asc PATCH mọi field có trong file locale, và version đang bán từ chối mọi field ngoài promotionalText
    # (gặp thật 2026-10-29) ⇒ không đưa field không đổi vào. Field/locale vắng mặt = giữ nguyên trên ASC
    # (không --allow-deletes nên asc không xoá); bước (5) vẫn so khớp tuyệt đối toàn bộ.
    push_values = {(o.scope, o.locale, o.field): merged[(o.scope, o.locale, o.field)] for o in plan.ops}
    tmp = Path(tempfile.mkdtemp(prefix="aso-push-"))
    try:
        try:
            # Đúng tên thư mục version mà `metadata pull` vừa ghi (asc mâu thuẫn version/ ↔ versions/).
            store.write(tmp, plan.version, push_values, vdir=remote.vdir)
            # Thư mục một scope có mặt ⇒ asc quản MỌI locale của scope đó, locale vắng bị coi là xoá
            # (asc từ chối khi không --allow-deletes — gặp thật 2026-10-29); file `{}` cũng bị từ chối
            # ("at least one … field is required"). ⇒ mỗi locale không có op mang đúng MỘT field với giá trị y hệt
            # ASC: asc so khác trước khi gọi API nên locale không khác gì thì không PATCH. Scope không op: bỏ hẳn.
            op_locales = {(o.scope, o.locale) for o in plan.ops}
            keep = {}
            for scope in {o.scope for o in plan.ops}:
                prefer = "name" if scope == store.APP_INFO else "promotionalText"
                for locale in {loc for (s, loc, _f) in remote if s == scope}:
                    if (scope, locale) in op_locales:
                        continue
                    fields = sorted(f for (s, loc, f) in remote if (s, loc) == (scope, locale))
                    field = prefer if prefer in fields else fields[0]
                    keep[(scope, locale, field)] = remote[(scope, locale, field)]
            store.write(tmp, plan.version, keep, vdir=remote.vdir)
        except Exception as e:
            raise RuntimeError(f"dựng thư mục push lỗi (CHƯA ghi gì lên ASC): {e}") from e
        try:
            push(tmp, plan.version)
        except Exception as e:
            # Push có thể đã ghi một phần ⇒ luôn chỉ đường khôi phục.
            _record(plan, snap, "push_failed")
            raise RuntimeError(f"push lỗi (ASC có thể đã bị ghi một phần): {e}. {_recovery(snap)}") from e
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # (5) Kiểm lại trên ASC: phải đúng y `merged` — mọi khoá, mọi giá trị, không thừa khoá.
    try:
        after = pull(plan.version)
    except Exception as e:
        _record(plan, snap, "unverified")
        raise RuntimeError(f"ĐÃ push lên ASC nhưng pull kiểm lại lỗi: {e} — chưa xác minh được. "
                           f"{_recovery(snap)}") from e
    if after != merged:
        _record(plan, snap, "mismatch")
        lines = "\n".join(f"  - {d}" for d in _diff_lines(merged, after))
        raise RuntimeError(f"sau push, ASC khác thứ đã duyệt ở:\n{lines}\n{_recovery(snap)}")

    # (6) Ledger.
    _record(plan, snap, "ok")
    return ApplyResult(plan.plan_id, snap, len(plan.ops))
