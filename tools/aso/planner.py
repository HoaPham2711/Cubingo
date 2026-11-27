"""Planner: so store/ (local) với ASC (remote) thành Plan có mã ngắn ổn định."""
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint as lint_mod  # noqa: E402

Field = tuple  # (scope, locale, field)


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def fingerprint(remote: dict) -> str:
    """SHA-256 của trạng thái remote (JSON chuẩn hoá, khoá sắp xếp)."""
    rows = sorted([list(k), v] for k, v in remote.items())
    return hashlib.sha256(_canon(rows).encode("utf-8")).hexdigest()


@dataclass
class Op:
    kind: Literal["add", "update"]
    scope: str
    locale: str
    field: str
    old: str | None
    new: str


@dataclass
class Plan:
    version: str
    remote_fingerprint: str
    ops: list[Op] = field(default_factory=list)
    created: str = ""
    # Lint thấy ở field KHÔNG đổi (Ruling 13): chỉ hiển thị, không chặn, KHÔNG nằm trong plan_id.
    warnings: list[str] = field(default_factory=list)
    # `apple.app_store_id` của app lúc plan: nằm trong mã plan, hiện ở bản xác nhận; `apply` từ chối plan của app khác.
    app_id: str = ""

    @property
    def plan_id(self) -> str:
        """8 ký tự hex đầu của SHA-256 nội dung (gồm `app_id`; không gồm `created`, `warnings`); luôn tính lại."""
        body = {
            "app_id": self.app_id,
            "version": self.version,
            "remote_fingerprint": self.remote_fingerprint,
            "ops": [asdict(o) for o in self.ops],
        }
        return hashlib.sha256(_canon(body).encode("utf-8")).hexdigest()[:8]


def _locales(values: dict) -> dict[str, set]:
    out: dict[str, set] = {}
    for scope, locale, _f in values:
        out.setdefault(scope, set()).add(locale)
    return out


def is_blank(value) -> bool:
    """Rỗng hoặc chỉ khoảng trắng (None cũng tính là rỗng)."""
    return value is None or not value.strip()


def is_wipe(old, new) -> bool:
    """Op biến một field đang có chữ thành rỗng/chỉ khoảng trắng — cấm (Ruling 12)."""
    return not is_blank(old) and is_blank(new)


def _issue_line(i) -> str:
    return f"  - [{i.locale}] {i.field}: {i.message}"


def make_plan(local: dict, remote: dict, version: str, *, editable: bool,
              banned=(), host_prod: str = "", host_dev: str = "", app_id: str = "") -> Plan:
    """So local/remote thành Plan. Lint (`lint.lint_values` với chữ cấm + host của app) chặn LỖI ở field plan đụng
    tới; lỗi ở field không đổi và mọi cảnh báo chỉ vào `warnings` (không nằm trong mã plan). `app_id` = App Store id
    của app đang plan (ghi vào plan + mã plan)."""
    local_loc, remote_loc = _locales(local), _locales(remote)
    for scope, locales in sorted(remote_loc.items()):
        missing = locales - local_loc.get(scope, set())
        if missing:
            raise ValueError(
                f"store/ thiếu locale {', '.join(sorted(missing))} (scope {scope}) đang có trên ASC; "
                "không xoá locale — hãy bổ sung vào store/")
    ops = []
    for key in sorted(local):
        scope, locale, fld = key
        new = local[key]
        if key in remote:
            if remote[key] != new:
                ops.append(Op("update", scope, locale, fld, remote[key], new))
        else:
            ops.append(Op("add", scope, locale, fld, None, new))

    wipes = [o for o in ops if is_wipe(o.old, o.new)]
    if wipes:
        keys = ", ".join(f"[{o.locale}] {o.field}" for o in wipes)
        raise ValueError(f"xoá nội dung field bị cấm — tự xử lý trên ASC: {keys}")

    # Lint chỉ chặn lỗi ở field plan đụng tới (hoặc khoá liên quan, vd name/subtitle ↔ keywords);
    # lỗi có sẵn ở field không đổi ⇒ cảnh báo (vd version đang bán, chỉ đổi promo).
    op_keys = {(o.scope, o.locale, o.field) for o in ops}
    blocking, warnings = [], []
    for i in lint_mod.lint_values(local, banned=banned, host_prod=host_prod, host_dev=host_dev):
        touched = (i.scope, i.locale, i.field) in op_keys or any(r in op_keys for r in i.related)
        (blocking if touched and i.severity == "error" else warnings).append(i)
    if blocking:
        raise ValueError("lint không qua:\n" + "\n".join(_issue_line(i) for i in blocking))

    if not editable:
        bad = sorted({o.field for o in ops if o.field != "promotionalText"})
        if bad:
            raise ValueError(
                f"version {version} không sửa được (đang bán / chờ duyệt): chỉ đổi được promotionalText, "
                f"nhưng plan có đổi {', '.join(bad)}")

    return Plan(version, fingerprint(remote), ops,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                [_issue_line(i).strip()[2:] for i in warnings], app_id)


def save(plan: Plan, path: Path) -> None:
    data = {
        "app_id": plan.app_id,
        "version": plan.version,
        "plan_id": plan.plan_id,
        "remote_fingerprint": plan.remote_fingerprint,
        "created": plan.created,
        "ops": [asdict(o) for o in plan.ops],
        "warnings": list(plan.warnings),
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_plan(path: Path):
    """Đọc plan; `plan_id` trên đĩa không được tin — luôn tính lại từ nội dung.

    `"kind": "release"` ⇒ ReleasePlan; không có `kind` ⇒ Plan metadata; kind khác ⇒ ValueError."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "kind" in data:
        if data["kind"] != "release":
            raise ValueError(f"loại plan không biết: {data['kind']!r}")
        import release  # import muộn: release.py import planner
        return release.from_dict(data)
    ops = [Op(**o) for o in data["ops"]]
    return Plan(data["version"], data["remote_fingerprint"], ops, data.get("created", ""),
                [str(w) for w in data.get("warnings", [])], str(data.get("app_id", "")))
