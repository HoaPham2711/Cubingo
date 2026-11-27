"""Plan release: upload build, tạo version (nếu chưa có), gắn build — qua cùng cổng duyệt với plan metadata."""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import applier  # noqa: E402 — ledger chung applied.jsonl (applier không import release ở top-level)
import asc_cli  # noqa: E402
import planner  # noqa: E402
import remote  # noqa: E402

KIND = "release"

STEP_LABELS = {
    "upload_build": "Upload file .ipa lên App Store Connect (TestFlight) và chờ xử lý xong",
    "create_version": "Tạo version mới trên App Store Connect",
    "attach_build": "Gắn build vừa upload vào version",
}


@dataclass
class Step:
    action: Literal["upload_build", "create_version", "attach_build"]


@dataclass
class ReleasePlan:
    version: str
    build: str
    commit: str
    ipa: str
    ipa_sha256: str
    gates: dict
    remote_fingerprint: str
    ops: list[Step] = field(default_factory=list)
    created: str = ""
    kind: str = KIND
    # True = build đã có trên ASC (lần chạy trước upload xong) ⇒ plan chỉ còn create/attach, không upload.
    resume: bool = False
    # Trạng thái ASC lúc plan, để bản xác nhận nói rõ người đang duyệt cái gì (None = chưa có).
    observed: dict = field(default_factory=lambda: {"version_state": None, "build_state": None})

    @property
    def plan_id(self) -> str:
        """8 hex đầu SHA-256 của mọi trường trừ `created` (kèm `kind`); luôn tính lại."""
        body = {
            "kind": self.kind, "version": self.version, "build": self.build, "commit": self.commit,
            "ipa": self.ipa, "ipa_sha256": self.ipa_sha256, "gates": self.gates,
            "remote_fingerprint": self.remote_fingerprint, "resume": self.resume,
            "observed": self.observed, "ops": [asdict(o) for o in self.ops],
        }
        return hashlib.sha256(planner._canon(body).encode("utf-8")).hexdigest()[:8]


def _data(env: Any) -> list:
    if isinstance(env, dict) and isinstance(env.get("data"), list):
        return env["data"]
    return []


def remote_state(version: str, build: str, *, run: Callable[..., Any] = asc_cli.run) -> dict:
    """Chỉ lệnh ĐỌC: trạng thái version (None nếu chưa có), build đã có trên ASC chưa, và các version IOS
    KHÁC đang ở trạng thái sửa được (ASC không cho tạo version mới khi còn một bản như vậy)."""
    # Không lọc --version: cần thấy cả bản khác đang sửa được. Lọc versionString trong code.
    vers = run(["versions", "list", "--app", asc_cli.app_id(), "--platform", "IOS", "--paginate"])
    matches = []
    other_editable = []
    for item in _data(vers):
        attrs = item.get("attributes", {}) if isinstance(item, dict) else {}
        if attrs.get("platform", "IOS") != "IOS":
            continue
        if attrs.get("versionString") != version:
            other = remote.state_from_attributes(attrs)
            if other in remote.EDITABLE_STATES:
                other_editable.append([str(attrs.get("versionString")), other])
            continue
        matches.append(attrs)
    if len(matches) > 1:
        raise ValueError(f"có {len(matches)} version khớp {version} trên ASC — không đoán, kiểm tra tay")
    state = None
    attached = None
    if matches:
        state = remote.state_from_attributes(matches[0])
        if state is None:
            raise ValueError(f"version {version} có trên ASC nhưng không đọc được trạng thái")
        view = run(["versions", "view", "--app", asc_cli.app_id(), "--version", version, "--include", "build"])
        attached = _attached_build(view)[0]
    # --processing-state all: mặc định asc có thể chỉ trả build VALID ⇒ bỏ sót build PROCESSING/FAILED
    # của lần chạy trước (phát hiện resume sai). Lọc số build trong code.
    builds = run(["builds", "list", "--app", asc_cli.app_id(), "--version", version, "--platform", "IOS",
                  "--processing-state", "all"])
    same = [b.get("attributes", {}) for b in _data(builds)
            if str(b.get("attributes", {}).get("version")) == str(build)]
    if len(same) > 1:
        raise ValueError(f"có {len(same)} build số {build} trên ASC — không đoán, kiểm tra tay")
    return {"version_state": state, "attached_build": attached, "build_exists": bool(same),
            "build_state": same[0].get("processingState") if same else None,
            "other_editable": sorted(other_editable)}


def _fingerprint(state: dict) -> str:
    return hashlib.sha256(planner._canon(state).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_release_plan(build_json: Path, *, run: Callable[..., Any] = asc_cli.run) -> ReleasePlan:
    b = json.loads(Path(build_json).read_text(encoding="utf-8"))
    bad = sorted(k for k, v in (b.get("gates") or {}).items() if v != "ok")
    if bad or not b.get("gates"):
        raise ValueError(f"cổng chưa qua: {', '.join(bad) or 'build.json không có gates'}")
    ipa = Path(b["ipa"])
    version, build = b["version"], str(b["build"])
    st = remote_state(version, build, run=run)
    vs = st["version_state"]
    if vs is not None and vs not in remote.EDITABLE_STATES:
        raise ValueError(f"version {version} đang ở trạng thái {vs} (đang bán / chờ duyệt) — không thêm build")
    resume = st["build_exists"]
    if resume:
        # Lần chạy trước đã upload xong (hoặc upload "lỗi" nhưng thật ra đã lên) ⇒ chỉ plan phần còn lại.
        if st["build_state"] != "VALID":
            raise ValueError(f"build {build} đã có trên ASC nhưng processingState = "
                             f"{st['build_state'] or 'không rõ'} (chưa VALID) — đợi xử lý xong rồi chạy lại")
        if vs is None:
            actions = ["create_version", "attach_build"]
        elif st["attached_build"] is None:
            actions = ["attach_build"]
        elif str(st["attached_build"]) == build:
            raise ValueError(f"bản {version} đã gắn build {build} — không còn gì để làm")
        else:
            raise ValueError(f"bản {version} đang gắn build {st['attached_build']}, khác build {build} "
                             "đã upload — không tự thay, xử lý tay trên ASC")
    elif vs is None:
        actions = ["upload_build", "create_version", "attach_build"]
    elif st["attached_build"] is not None:
        # attach-build sẽ THAY build đang gắn — tool không thay (render nói "Không xoá gì").
        raise ValueError(f"bản {version} đang gắn build {st['attached_build']} — gỡ build trên ASC trước "
                         "nếu muốn thay; tool không thay build")
    else:
        actions = ["upload_build", "attach_build"]
    if "create_version" in actions and st["other_editable"]:
        x, xs = st["other_editable"][0]
        raise ValueError(f"bản {x} đang ở {xs} — ASC không cho tạo version mới; xử lý bản {x} trên ASC trước")
    if not resume:
        # Chỉ plan có upload mới cần .ipa thật; plan resume ghi ipa/sha theo build.json, không đọc file.
        try:
            actual = _sha256_file(ipa)
        except OSError as e:
            raise ValueError(f"không đọc được file .ipa ({ipa}): {type(e).__name__}") from None
        if actual != b["ipa_sha256"]:
            raise ValueError(f"SHA-256 của .ipa không khớp build.json (build.json {b['ipa_sha256'][:12]}…, "
                             f"thực {actual[:12]}…)")
    return ReleasePlan(version, build, b["commit"], str(ipa), b["ipa_sha256"], dict(b["gates"]), _fingerprint(st),
                       [Step(a) for a in actions],
                       datetime.now(timezone.utc).isoformat(timespec="seconds"), resume=resume,
                       observed={"version_state": vs, "build_state": st["build_state"]})


def to_dict(plan: ReleasePlan) -> dict:
    return {
        "kind": KIND, "version": plan.version, "build": plan.build, "commit": plan.commit,
        "ipa": plan.ipa, "ipa_sha256": plan.ipa_sha256, "gates": plan.gates,
        "plan_id": plan.plan_id, "remote_fingerprint": plan.remote_fingerprint,
        "created": plan.created, "resume": plan.resume, "observed": plan.observed,
        "ops": [asdict(o) for o in plan.ops],
    }


_TOP_KEYS = {"kind", "version", "build", "commit", "ipa", "ipa_sha256", "gates", "plan_id",
             "remote_fingerprint", "created", "resume", "observed", "ops"}
_ACTIONS = ("upload_build", "create_version", "attach_build")
# Thứ tự hợp lệ theo `resume`: plan mới luôn upload; plan resume KHÔNG BAO GIỜ upload.
_ORDERS = {False: (["upload_build", "create_version", "attach_build"], ["upload_build", "attach_build"]),
           True: (["create_version", "attach_build"], ["attach_build"])}


def from_dict(data: dict) -> ReleasePlan:
    """Đọc chặt (fail-closed): khoá lạ, action lạ, thứ tự bước lạ, cổng != ok ⇒ ValueError.

    plan_id trên đĩa không được tin — property tính lại từ nội dung."""
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise ValueError(f"plan release có khoá lạ: {', '.join(sorted(unknown))}")
    ops = data.get("ops")
    if not isinstance(ops, list):
        raise ValueError("plan release thiếu ops")
    for o in ops:
        if not isinstance(o, dict) or set(o) != {"action"}:
            raise ValueError(f"bước không hợp lệ trong plan release: {o!r}")
        if o["action"] not in _ACTIONS:
            raise ValueError(f"action lạ trong plan release: {o['action']!r}")
    resume = data.get("resume")
    if not isinstance(resume, bool):
        raise ValueError("plan release thiếu/sai trường resume (phải true/false)")
    if [o["action"] for o in ops] not in _ORDERS[resume]:
        raise ValueError("thứ tự bước plan release không hợp lệ")
    gates = data.get("gates")
    if not isinstance(gates, dict) or not gates or any(v != "ok" for v in gates.values()):
        raise ValueError("plan release có cổng chưa qua (gates phải đủ và đều ok)")
    observed = data.get("observed")
    if (not isinstance(observed, dict) or set(observed) != {"version_state", "build_state"}
            or any(v is not None and not isinstance(v, str) for v in observed.values())):
        raise ValueError("plan release thiếu/sai trường observed")
    try:
        return ReleasePlan(data["version"], str(data["build"]), data["commit"], data["ipa"],
                           data["ipa_sha256"], dict(gates), data["remote_fingerprint"],
                           [Step(o["action"]) for o in ops], data.get("created", ""), resume=resume,
                           observed=dict(observed))
    except KeyError as e:
        raise ValueError(f"plan release thiếu trường {e}") from None


def save(plan: ReleasePlan, path: Path) -> None:
    Path(path).write_text(json.dumps(to_dict(plan), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render(plan: ReleasePlan) -> str:
    out = [f"# Bản xác nhận release — version {plan.version} (build {plan.build})", "",
           "## Tóm tắt", "",
           f"- Version: {plan.version}", f"- Build: {plan.build}", f"- Commit: {plan.commit}",
           f"- File .ipa: {plan.ipa}", f"- SHA-256 .ipa: {plan.ipa_sha256[:12]}…", "",
           "## Trạng thái trên ASC lúc plan", ""]
    vs = plan.observed.get("version_state")
    if vs is None:
        out.append(f"- version {plan.version} chưa có — sẽ tạo (release type MANUAL: Apple duyệt xong bạn tự "
                   "bấm phát hành)")
    else:
        out.append(f"- version {plan.version} đã có, {vs}")
    if plan.resume:
        out.append(f"- build {plan.build} trên ASC: {plan.observed.get('build_state') or 'không rõ'}")
    out += ["", "## Các bước (theo thứ tự)", ""]
    if plan.resume:
        out[-2:-2] = [f"Tiếp tục bản dở: build {plan.build} đã có trên ASC (không upload lại)", ""]

    def label(action: str) -> str:
        if plan.resume and action == "attach_build":
            return f"Gắn build {plan.build} (đã có trên ASC)"
        return STEP_LABELS[action]
    out += [f"{i}. {label(o.action)}" for i, o in enumerate(plan.ops, 1)]
    out += ["", "## Xoá / thay", "", "**Không xoá gì**", "",
            "## Cổng đã qua", ""]
    out += [f"- {k}: {v}" for k, v in sorted(plan.gates.items())]
    out += ["", "Plan này KHÔNG nộp review và KHÔNG phát hành — bước đó do người làm trên ASC.", "",
            f"Mã plan: {plan.plan_id}"]
    return "\n".join(out) + "\n"


# ---------- thực thi plan release (chỉ được gọi từ applier.apply sau khi kiểm mã plan) ----------

# Status ledger: ok | upload_failed | wait_failed | build_invalid | create_failed | attach_failed | verify_failed.
_FAIL_STATUS = {"upload_build": "upload_failed", "create_version": "create_failed",
                "attach_build": "attach_failed"}


def _progress(plan: ReleasePlan, completed: list[str], status: str = "") -> str:
    """Câu nói rõ phần nào đã xong, phần nào chưa, và cách làm tiếp (không xoá gì)."""
    done = ", ".join(completed) or "chưa bước nào"
    left = ", ".join(o.action for o in plan.ops if o.action not in completed) or "không còn"
    out = f"Đã xong: {done}. Chưa làm: {left}. Tool KHÔNG xoá/hoàn tác gì trên ASC. "
    if status == "upload_failed":
        out += (f"Build {plan.build} CÓ THỂ đã lên ASC dù báo lỗi (vd timeout đường truyền) — `release-plan` "
                "sẽ tự phát hiện và chỉ plan các bước còn lại. ")
    elif status in ("build_invalid", "wait_failed"):
        out += f"Đợi build {plan.build} xử lý xong (VALID) trên ASC rồi mới chạy lại. "
    return out + ("Chạy lại `python3 tools/aso/aso.py release-plan --build-json <build.json>` để làm plan mới — "
                  "plan kế tiếp tự phát hiện build/version đã có và chỉ còn các bước chưa xong.")


def _attached_build(view: Any) -> tuple[str | None, str | None]:
    """(số build, id build) đang gắn vào version theo `versions view --include build`.

    `relationships.build.data` = null ⇒ chưa gắn (None, None), KHÔNG lấy `included` bù. Có id ⇒ phải khớp
    đúng một build trong `included`. Không có relationships.build ⇒ `included` có 0 build = chưa gắn, 1 = nó.
    Còn lại (shape lạ, nhiều build, id không thấy, thiếu số) ⇒ ValueError — không đoán."""
    if not isinstance(view, dict) or not isinstance(view.get("data"), dict):
        raise ValueError("versions view trả shape lạ — không đọc được build đang gắn")
    inc = [i for i in (view.get("included") or []) if isinstance(i, dict) and i.get("type") == "builds"]
    rels = view["data"].get("relationships")
    if rels is None:
        rels = {}
    elif not isinstance(rels, dict):
        raise ValueError("relationships lạ (không phải object) — không đọc được build đang gắn")
    if "build" in rels:
        rel_obj = rels["build"]
        if not isinstance(rel_obj, dict) or "data" not in rel_obj:
            raise ValueError("relationships.build không có data — không đọc được build đang gắn")
        rel = rel_obj["data"]
        if rel is None:
            return None, None
        if not isinstance(rel, dict):
            raise ValueError("relationships.build.data lạ — không đọc được build đang gắn")
        if isinstance(rel.get("attributes"), dict) and rel["attributes"].get("version") is not None:
            return str(rel["attributes"]["version"]), rel.get("id")
        inc = [i for i in inc if rel.get("id") is not None and i.get("id") == rel["id"]]
        if len(inc) != 1:
            raise ValueError("không tìm thấy build đang gắn trong included")
    elif not inc:
        return None, None
    if len(inc) != 1:
        raise ValueError(f"included có {len(inc)} build — không đoán build đang gắn")
    ver = (inc[0].get("attributes") or {}).get("version")
    if ver is None:
        raise ValueError("build đang gắn không có số build")
    return str(ver), inc[0].get("id")


def apply_release(plan: ReleasePlan, *, run: Callable[..., Any] = asc_cli.run) -> dict:
    """Thực thi plan release đã duyệt. Thứ tự: ASC chưa đổi → .ipa chưa đổi → các bước → kiểm lại → ledger.

    Không bao giờ xoá/hoàn tác, không nộp review, không phát hành. Hỏng giữa chừng ⇒ ledger + RuntimeError
    nói rõ bước nào đã xong."""
    A = asc_cli.app_id()
    if [o.action for o in plan.ops] not in _ORDERS[plan.resume]:  # from_dict đã chặn; phòng thủ
        raise RuntimeError("thứ tự bước plan release không hợp lệ với resume — CHƯA ghi gì")
    # (1) ASC phải y như lúc plan (chỉ lệnh đọc).
    try:
        st = remote_state(plan.version, plan.build, run=run)
    except ValueError as e:
        raise RuntimeError(f"không đọc được trạng thái ASC: {e} — CHƯA ghi gì") from e
    if _fingerprint(st) != plan.remote_fingerprint:
        raise RuntimeError("ASC đã đổi — làm plan release mới (CHƯA ghi gì)")
    # (2) .ipa phải đúng file đã duyệt. Plan resume không upload ⇒ không cần (và không đọc) .ipa.
    if not plan.resume:
        try:
            actual = _sha256_file(Path(plan.ipa))
        except OSError as e:
            raise RuntimeError(f"không đọc được .ipa ({plan.ipa}): {type(e).__name__} — CHƯA ghi gì") from e
        if actual != plan.ipa_sha256:
            raise RuntimeError(f"SHA-256 .ipa đã đổi từ lúc plan (plan {plan.ipa_sha256[:12]}…, thực "
                               f"{actual[:12]}…) — CHƯA ghi gì, build lại rồi làm plan mới")

    completed: list[str] = []

    def write(action: str, argv: list[str]) -> Any:
        try:
            return run(argv, write=True)
        except Exception as e:
            status = _FAIL_STATUS[action]
            applier._record_release(plan, status, {"completed": list(completed)})
            raise RuntimeError(f"bước {action} lỗi: {e}. {_progress(plan, completed, status)}") from e

    # (3)–(5) Các bước theo đúng thứ tự plan (from_dict đã kiểm thứ tự hợp lệ).
    for step in plan.ops:
        if step.action == "upload_build":
            write("upload_build", ["builds", "upload", "--app", A, "--ipa", plan.ipa])
            completed.append("upload_build")  # build ĐÃ lên ASC từ đây, dù chờ xử lý có hỏng
            try:
                waited = run(["builds", "wait", "--app", A, "--build-number", plan.build, "--version",
                              plan.version, "--platform", "IOS", "--timeout", "45m"], write=False)
            except Exception as e:  # noqa: BLE001 — không xác nhận được VALID ⇒ dừng
                applier._record_release(plan, "wait_failed", {"completed": list(completed)})
                raise RuntimeError(f"build {plan.build} đã upload nhưng chờ xử lý lỗi: {e} — DỪNG, không tạo "
                                   f"version/gắn build. {_progress(plan, completed, 'wait_failed')}") from e
            ps = remote._find_key(waited, "processingState")
            if ps != "VALID":
                applier._record_release(plan, "build_invalid",
                                        {"completed": list(completed), "processing_state": ps})
                raise RuntimeError(f"build {plan.build} đã upload nhưng chưa VALID (processingState = "
                                   f"{ps or 'không có trong kết quả'}) — DỪNG, không tạo version/gắn build. "
                                   f"{_progress(plan, completed, 'build_invalid')}")
            continue
        elif step.action == "create_version":
            write("create_version", ["versions", "create", "--app", A, "--version", plan.version,
                                     "--platform", "IOS", "--release-type", "MANUAL"])
        elif step.action == "attach_build":
            write("attach_build", ["versions", "attach-build", "--app", A, "--version", plan.version,
                                   "--build-number", plan.build])
        else:  # from_dict đã chặn; phòng thủ
            raise RuntimeError(f"bước lạ: {step.action}")
        completed.append(step.action)

    # (6) Kiểm lại: version gắn đúng build và vẫn ở trạng thái sửa được.
    try:
        view = run(["versions", "view", "--app", A, "--version", plan.version, "--include", "build"], write=False)
    except Exception as e:  # noqa: BLE001
        applier._record_release(plan, "verify_failed", {"completed": list(completed)})
        raise RuntimeError(f"đã chạy xong các bước nhưng đọc kiểm lại lỗi: {e} — tự kiểm trên ASC. "
                           f"{_progress(plan, completed)}") from e
    data = view.get("data") if isinstance(view, dict) else None
    attrs = data.get("attributes") if isinstance(data, dict) else None
    state = remote.state_from_attributes(attrs) if isinstance(attrs, dict) else None
    try:
        got_build, build_id = _attached_build(view)
    except ValueError:
        got_build, build_id = None, None
    if got_build != plan.build or state not in remote.EDITABLE_STATES:
        applier._record_release(plan, "verify_failed",
                                {"completed": list(completed), "attached_build": got_build, "state": state})
        raise RuntimeError(f"kiểm lại sai: version {plan.version} đang gắn build {got_build or '?'} "
                           f"(cần {plan.build}), trạng thái {state or '?'} — tự kiểm trên ASC. "
                           f"{_progress(plan, completed)}")
    version_id = data.get("id")
    # (7) Ledger.
    applier._record_release(plan, "ok", {"build_id": build_id, "version_id": version_id, "state": state})
    return {"plan_id": plan.plan_id, "version": plan.version, "build": plan.build,
            "build_id": build_id, "version_id": version_id, "state": state}
