#!/usr/bin/env python3
"""CLI ASO: pull / import / lint / plan / pull-version / snapshot / build / apply / restore / release-plan.

Mọi lệnh gọi `asc` đi qua wrapper asc_cli (allowlist `policy.py`, `ASC_READ_ONLY=1` trừ lệnh ghi). Chỉ `apply` ghi
lên App Store Connect, và chỉ qua `applier.apply` (mã plan đã duyệt, ASC chưa đổi, snapshot trước, kiểm lại sau).
Định danh đọc từ `app.config.toml` (qua `store.config()`): `apple.app_store_id` rỗng ⇒ mọi lệnh cần app record từ chối
(rc 2, một dòng hướng dẫn); `lint` vẫn chạy (bỏ phần audit trên ASC). `--version` mặc định = `[version] marketing`.

`--offline-fixture DIR` (ẩn — chỉ cho test/tự kiểm): `asc` không chạy, phản hồi đọc từ `DIR/<khoá>.json`
(xem `asc_cli.fixture_key`); không dùng được cùng `apply`.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tránh store/ ở gốc repo che `import store`
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import appconfig  # noqa: E402
import applier  # noqa: E402
import asc_cli  # noqa: E402
import build as build_mod  # noqa: E402
import confirm  # noqa: E402
import lint as lint_mod  # noqa: E402
import planner  # noqa: E402
import release  # noqa: E402
import remote  # noqa: E402
import snapshot  # noqa: E402
import store  # noqa: E402

# Lệnh cần app record trên App Store Connect (đọc/ghi qua asc). `lint`, `build` không cần.
NEEDS_APP_RECORD = {"pull", "import", "plan", "pull-version", "snapshot", "apply", "restore", "release-plan"}
# Field chữ mà khung `store/` sinh ra để giữ chỗ — dùng nhận biết "khung chưa viết" cho `import --force-over-skeleton`.
SKELETON_FIELDS = ("description", "keywords", "promotionalText", "whatsNew")


def asc_link() -> str:
    return f"https://appstoreconnect.apple.com/apps/{asc_cli.app_id()}/distribution/ios/version/inflight"


def _pull_tmp(version: str, *, run) -> dict:
    """Pull remote vào thư mục tạm mới rồi dọn; trả dict field."""
    tmp = Path(tempfile.mkdtemp(prefix="aso-pull-"))
    try:
        return remote.pull_remote(version, tmp / "pull", run=run)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def plans_dir() -> Path:
    """Thư mục plan: `store.state_dir()/plans` (tuyệt đối)."""
    return store.state_dir() / "plans"


def _lint_context() -> dict:
    """Chữ cấm (`store/lint.toml` cạnh `store/metadata`) + host của app — cùng luật cho `lint`, `plan`, `restore`."""
    cfg = store.config()
    return {"banned": lint_mod.load_banned(store.STORE.parent.parent),
            "host_prod": appconfig.opt(cfg, "web.host_prod", "") or "",
            "host_dev": appconfig.opt(cfg, "web.host_dev", "") or ""}


def _save_and_print(plan) -> int:
    d = plans_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{plan.plan_id}.json"
    if getattr(plan, "kind", None) == "release":
        release.save(plan, path)
    else:
        planner.save(plan, path)
    print(confirm.render(plan))
    print(f"Plan: {path}")
    return 0


def _has_files(d: Path) -> bool:
    return d.exists() and any(p.is_file() for p in d.rglob("*"))


def is_skeleton(meta: Path) -> bool:
    """`store/metadata` vẫn là khung chưa viết: có ít nhất một field chữ ở thư mục version, và MỌI field chữ
    (`SKELETON_FIELDS`) ở mọi file version còn chuỗi giữ chỗ `lint.PLACEHOLDER`. Đã viết thật dù một ô ⇒ False."""
    seen = 0
    for d in store.VERSION_DIRS:
        for path in sorted((meta / d).glob("*/*.json")) if (meta / d).is_dir() else []:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return False
            if not isinstance(data, dict):
                return False
            for f in SKELETON_FIELDS:
                if f in data:
                    seen += 1
                    if not isinstance(data[f], str) or lint_mod.PLACEHOLDER not in data[f]:
                        return False
    return seen > 0


def cmd_pull(args, *, run=asc_cli.run) -> int:
    # Giữ thư mục (không dọn) vì user cần đường dẫn in ra.
    dest = Path(args.dir) if args.dir else Path(tempfile.mkdtemp(prefix="aso-pull-"))
    remote.pull_remote(args.version, dest, run=run)
    print(dest.resolve())
    return 0


def cmd_import(args, *, run=asc_cli.run) -> int:
    """Pull metadata trên ASC vào `store/metadata`. Chỉ khi `store/metadata` trống, hoặc khi còn là KHUNG chưa viết
    và có `--force-over-skeleton` (khung bị thay hẳn bằng bản trên ASC)."""
    meta = store.STORE
    if _has_files(meta):
        if not args.force_over_skeleton:
            print(f"store/metadata đã có file ({meta}); từ chối import để không ghi đè chữ đang soạn. Khung do "
                  "template sinh (còn chữ giữ chỗ) thay được bằng --force-over-skeleton.", file=sys.stderr)
            return 2
        if not is_skeleton(meta):
            print(f"store/metadata ({meta}) đã có chữ viết thật (không còn là khung giữ chỗ); từ chối "
                  "--force-over-skeleton để không ghi đè.", file=sys.stderr)
            return 2
    tmp = Path(tempfile.mkdtemp(prefix="aso-import-"))
    try:
        values = remote.pull_remote(args.version, tmp / "pull", run=run)
        if not values:
            print(f"ASC không trả field nào cho version {args.version}; không đổi store/metadata.", file=sys.stderr)
            return 2
        if _has_files(meta):  # đã kiểm là khung ở trên — chỉ xoá SAU khi pull thành công
            shutil.rmtree(meta)
        store.write(meta, args.version, values, vdir=values.vdir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"Đã import {len(values)} field vào {meta}")
    return 0


def _summarize_audit(audit) -> str:
    """Tóm tắt audit: số finding + mỗi finding một dòng; shape lạ ⇒ JSON gọn."""
    items = None
    if isinstance(audit, dict):
        for key in ("findings", "issues", "results"):
            if isinstance(audit.get(key), list):
                items = audit[key]
                break
    elif isinstance(audit, list):
        items = audit
    if items is None:
        return json.dumps(audit, ensure_ascii=False, separators=(",", ":"))
    lines = [f"{len(items)} finding"]
    for it in items:
        msg = it.get("message") or it.get("description") if isinstance(it, dict) else None
        lines.append("- " + (str(msg) if msg else json.dumps(it, ensure_ascii=False, separators=(",", ":"))))
    return "\n".join(lines)


def _missing_version_dir(version: str) -> str:
    """Dòng lỗi khi `store/metadata` đã có thư mục version (`version/` hoặc `versions/`) nhưng thiếu `<version>` (vd sau
    bump_version: lint mặc định soi version mới mà chưa ai kéo/soạn) — rỗng nếu có, hoặc nếu chưa có thư mục version nào
    (`store/metadata` trống chờ `import`: không có gì để soi, chỉ cảnh báo "không có metadata")."""
    dirs = [store.STORE / d for d in store.VERSION_DIRS if (store.STORE / d).is_dir()]
    if not any(p.is_dir() for d in dirs for p in d.iterdir()):
        return ""
    if any((d / version).is_dir() for d in dirs):
        return ""
    # Gợi ý theo bố cục ĐANG dùng (`version/` hay `versions/` — thư mục có version con).
    layout = next(d.name for d in dirs if any(p.is_dir() for p in d.iterdir()))
    return (f"store/metadata thiếu thư mục version {version} — chưa có gì để soi cho bản này. Version đã có trên ASC: "
            f"`python3 tools/aso/aso.py pull-version --version {version}`; chưa có: tạo "
            f"`store/metadata/{layout}/{version}/<locale>.json` rồi soạn.")


def cmd_lint(args, *, run=asc_cli.run) -> int:
    """Lint `store/metadata` (luật chung + chữ cấm `store/lint.toml` + host của app) + `store/review/notes.txt`.
    Lỗi ⇒ rc 1, cảnh báo chỉ in. Thiếu thư mục của version đang soi (trong khi đã có version khác) là lỗi; chưa có thư
    mục version nào (store/metadata trống chờ `import`) chỉ cảnh báo.
    `store/lint.toml` sai dạng ⇒ `FAIL:` + rc 2. Audit keywords của bản TRÊN ASC chỉ cảnh báo."""
    try:
        ctx = _lint_context()
    except ValueError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    values = store.load(store.STORE, args.version)
    issues = lint_mod.lint_values(values, **ctx) + lint_mod.notes_report(store.STORE.parent.parent)
    errors = [i for i in issues if i.severity == "error"]
    for i in issues:
        print(str(i))
    missing_version = _missing_version_dir(args.version)
    if missing_version:
        print(missing_version)
    if not values:
        print(f"CẢNH BÁO: không có metadata nào cho version {args.version} trong {store.STORE}")
    if missing_version:
        errors.append(missing_version)
    print("--- keywords audit của bản TRÊN ASC (không phải store/) ---")
    try:
        app = asc_cli.app_id()
    except asc_cli.NoAppRecord:
        print("Bỏ qua: apple.app_store_id rỗng (chưa có app record) — chỉ lint local.")
    else:
        try:
            audit = run(["metadata", "keywords", "audit", "--app", app, "--version", args.version])
            print(_summarize_audit(audit))
        except Exception as e:  # noqa: BLE001 — audit chỉ cảnh báo, lint local quyết định pass/fail
            print(f"CẢNH BÁO: keywords audit không chạy được: {e}")
    return 1 if errors else 0


def cmd_plan(args, *, run=asc_cli.run) -> int:
    local = store.load(store.STORE, args.version)
    try:
        ctx = _lint_context()
    except ValueError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    remote_values = _pull_tmp(args.version, run=run)
    editable = remote.version_editable(args.version, run=run)
    try:
        plan = planner.make_plan(local, remote_values, args.version, editable=editable, app_id=asc_cli.app_id(), **ctx)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    return _save_and_print(plan)


def cmd_pull_version(args, *, run=asc_cli.run) -> int:
    """Kéo version MỚI trên ASC vào store/metadata, chỉ thư mục version V.

    Từ chối nếu V đã có trong store, hoặc app-info trên ASC khác app-info trong store (dùng chung mọi
    version, không tự ghi đè). Không ghi app-info, không xoá, không gọi lệnh ghi ASC.
    """
    v = args.version
    for d in store.VERSION_DIRS:
        if (store.STORE / d / v).exists():
            print(f"{store.STORE / d / v} đã có; từ chối pull-version để không ghi đè chữ đang soạn.", file=sys.stderr)
            return 2
    pulled = _pull_tmp(v, run=run)
    if pulled.vdir is None:
        print(f"ASC không trả thư mục version cho {v}; từ chối.", file=sys.stderr)
        return 2
    cur = store.load(store.STORE, v)
    p_info = {k: x for k, x in pulled.items() if k[0] == store.APP_INFO}
    c_info = {k: x for k, x in cur.items() if k[0] == store.APP_INFO}
    diffs = sorted(k for k in set(p_info) | set(c_info) if p_info.get(k) != c_info.get(k))
    if diffs:
        print("app-info trên ASC khác store/ (dùng chung mọi version); xử lý app-info trước:", file=sys.stderr)
        for scope, locale, fld in diffs:
            print(f"{scope} {locale} {fld}")
        return 2
    ver_values = {k: x for k, x in pulled.items() if k[0] == store.VERSION}
    store.write(store.STORE, v, ver_values, vdir=pulled.vdir)
    locales = sorted({k[1] for k in ver_values})
    print(f"Đã pull version {v} vào {store.STORE / pulled.vdir / v}: {len(locales)} locale")
    for loc in locales:
        empty = [f for f in SKELETON_FIELDS if not ver_values.get((store.VERSION, loc, f), "").strip()]
        print(f"  {loc}: " + (("trống/thiếu " + ", ".join(empty)) if empty else "đủ field"))
    return 0


def cmd_release_plan(args, *, run=asc_cli.run) -> int:
    """Plan release từ build.json (chỉ lệnh đọc ASC); in bản xác nhận + `Plan: <path>` như `plan`."""
    try:
        plan = release.make_release_plan(Path(args.build_json), run=run)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    return _save_and_print(plan)


def cmd_snapshot(args, *, run=asc_cli.run) -> int:
    snap = snapshot.take(args.version, run=run)
    snapshot.prune(snapshot.root())
    print(snap)
    return 0


def cmd_apply(args, *, run=asc_cli.run) -> int:
    """Lối ghi duy nhất. Version lấy từ file plan; không có tuỳ chọn nào khác --plan/--expect."""
    try:
        res = applier.apply(
            Path(args.plan), args.expect,
            pull=lambda v: _pull_tmp(v, run=run),
            push=applier.make_push(run),
            take_snapshot=lambda v: snapshot.take(v, run=run),
            editable=lambda v: remote.version_editable(v, run=run),
            run=run,
        )
    except Exception as e:  # noqa: BLE001 — mọi lỗi ⇒ stderr + mã 2, không nuốt im
        print(f"Lỗi apply: {e}", file=sys.stderr)
        # Lý do thật từ asc (đã che key) nằm ở lỗi gốc trong chuỗi __cause__.
        cause = e
        while cause is not None:
            if getattr(cause, "stderr", ""):
                print(cause.stderr.rstrip(), file=sys.stderr)
                break
            cause = cause.__cause__
        return 2
    if isinstance(res, dict):  # plan release
        print(f"Đã apply plan release {res['plan_id']}: build {res['build']} đã gắn vào version {res['version']} "
              f"(trạng thái {res['state']}) và đã kiểm lại.")
        print(asc_link())
        print("Bạn tự xem lại trên App Store Connect và tự bấm nộp review — tool không nộp.")
        return 0
    snapshot.prune(snapshot.root())
    print(f"Đã apply plan {res.plan_id} (app {asc_cli.app_id()}): {res.changed} field đã lên ASC và đã kiểm lại.")
    print(f"Snapshot trước khi ghi: {res.snapshot}")
    print(f"Khôi phục nếu cần: {applier.restore_hint(res.snapshot)}")
    print(asc_link())
    print("Bạn tự xem lại trên App Store Connect và tự bấm nộp review — tool không nộp.")
    return 0


def _real_run_cmd(argv, cwd):
    """Chạy lệnh local, gộp stdout+stderr; trả (exit, output)."""
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _real_git(argv):
    """git ở gốc repo, env bỏ mọi GIT_* thừa hưởng (hook/worktree lạ không được lái lệnh git của tool)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.check_output(["git", "--no-optional-locks", *argv], cwd=store.REPO, text=True, env=env)


def cmd_build(args, *, run_cmd=_real_run_cmd, git=_real_git) -> int:
    """LOCAL: archive + export + cổng, ghi build.json. Không gọi ASC. Nên chạy bằng run_in_background."""
    try:
        path = build_mod.build(store.REPO, args.version, run_cmd=run_cmd, git=git)
    except (RuntimeError, ValueError) as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        return 2
    b = json.loads(path.read_text(encoding="utf-8"))
    print(path)
    print(f"Build {b['version']} ({b['build']}) commit {b['commit'][:8]}, ipa sha256 {b['ipa_sha256'][:12]}…, "
          "hai cổng ok.")
    return 0


def _snapshot_version(meta: Path) -> str:
    """Version duy nhất trong <snapshot>/metadata/{version,versions}/; 0 hoặc >1 ⇒ ValueError."""
    names = sorted({p.name for d in ("version", "versions") if (meta / d).is_dir()
                    for p in (meta / d).iterdir() if p.is_dir()})
    if len(names) != 1:
        raise ValueError(f"snapshot phải có đúng một version trong {meta}, thấy: {names or 'không có'}")
    return names[0]


def cmd_restore(args, *, run=asc_cli.run) -> int:
    """Ra plan đưa ASC về snapshot (không ghi gì); rồi đi `apply` như mọi lần, không có lối tắt.

    local = remote hiện tại phủ bằng giá trị snapshot (snapshot thắng mọi khoá nó có). Khoá mới có trên ASC
    sau snapshot, hoặc khoá snapshot rỗng mà ASC đang có chữ, không khôi phục được (cấm xoá) ⇒ liệt kê
    để user tự xử lý trên ASC. Lint đi đúng luật của `plan` (chỉ chặn field đổi).
    """
    meta = Path(args.snapshot) / "metadata"
    try:
        if not meta.is_dir():
            raise ValueError(f"không thấy {meta}")
        version = _snapshot_version(meta)
        snap_values = store.load(meta, version)
        ctx = _lint_context()
        remote_values = _pull_tmp(version, run=run)
        # Snapshot rỗng ở field ASC đang có chữ = khôi phục bằng cách xoá trắng ⇒ cấm, liệt kê.
        wipes = sorted(k for k, v in snap_values.items() if planner.is_wipe(remote_values.get(k), v))
        local = dict(remote_values)
        local.update({k: v for k, v in snap_values.items() if k not in wipes})
        editable = remote.version_editable(version, run=run)
        plan = planner.make_plan(local, remote_values, version, editable=editable, app_id=asc_cli.app_id(), **ctx)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    orphans = sorted(set(remote_values) - set(snap_values))
    if orphans or wipes:
        print("Không khôi phục được (cấm xoá) — tự xử lý trên ASC:")
        for scope, locale, fld in orphans:
            print(f"  {scope} {locale} {fld}")
        for scope, locale, fld in wipes:
            print(f"  {scope} {locale} {fld} (snapshot rỗng — khôi phục = xoá trắng nội dung)")
        print()
    return _save_and_print(plan)


def build_parser():
    """Trả (parser, dispatch)."""
    parser = argparse.ArgumentParser(prog="aso.py", description="Tự động hoá metadata App Store (an toàn).",
                                     allow_abbrev=False)
    parser.add_argument("--offline-fixture", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    dispatch = {}

    def add(name, fn, help_):
        p = sub.add_parser(name, help=help_, allow_abbrev=False)
        p.add_argument("--version", help="chuỗi version app, vd 1.2.0 (mặc định: [version] marketing của "
                                         "app.config.toml)")
        dispatch[name] = fn
        return p

    add("pull", cmd_pull, "pull remote vào thư mục tạm").add_argument("--dir", help="thư mục đích (phải rỗng)")
    add("import", cmd_import, "pull remote vào store/metadata (chỉ khi còn trống, hoặc thay khung)").add_argument(
        "--force-over-skeleton", action="store_true",
        help="thay khung store/ do template sinh (mọi ô chữ còn TEMPLATE-PLACEHOLDER) bằng metadata trên ASC")
    add("lint", cmd_lint, "lint store/ + keywords audit")
    add("plan", cmd_plan, "so store/ với ASC, in bản xác nhận")
    add("pull-version", cmd_pull_version, "kéo version mới từ ASC vào store/ (chỉ thư mục version)")
    add("snapshot", cmd_snapshot, "chụp trạng thái remote")
    add("build", cmd_build, "archive + export .ipa + cổng, ghi build.json (local, không gọi ASC)")

    # apply: ĐÚNG hai tuỳ chọn (hook chỉ hỏi quyền cho dạng `apply --plan P --expect CODE`).
    p = sub.add_parser("apply", help="áp plan đã duyệt lên ASC (lối ghi duy nhất)", allow_abbrev=False)
    p.add_argument("--plan", required=True, help="file plan do `plan`/`restore`/`release-plan` in ra")
    p.add_argument("--expect", required=True, help="mã plan đã duyệt (8 hex)")
    dispatch["apply"] = cmd_apply
    p = sub.add_parser("restore", help="ra plan đưa ASC về một snapshot (không ghi)", allow_abbrev=False)
    p.add_argument("--snapshot", required=True,
                   help="thư mục <state_dir>/snapshots/<ts> — đường dẫn tuyệt đối do snapshot/apply in ra")
    dispatch["restore"] = cmd_restore
    p = sub.add_parser("release-plan", help="plan release từ build.json (chỉ đọc ASC), in bản xác nhận",
                       allow_abbrev=False)
    p.add_argument("--build-json", required=True, help="build.json do `build` in ra")
    dispatch["release-plan"] = cmd_release_plan
    return parser, dispatch


def main(argv=None) -> int:
    parser, dispatch = build_parser()
    args = parser.parse_args(argv)
    try:
        if hasattr(args, "version") and not args.version:
            args.version = str(appconfig.get(store.config(), "version.marketing"))
        if args.command in NEEDS_APP_RECORD:
            try:
                asc_cli.app_id()
            except asc_cli.NoAppRecord as e:
                print(f"FAIL: {e}", file=sys.stderr)
                return 2
        kwargs = {}
        if args.offline_fixture:
            if args.command == "apply":
                print("FAIL: --offline-fixture không dùng được với apply (fixture không bao giờ đóng vai lối ghi).",
                      file=sys.stderr)
                return 2
            if args.command != "build":
                kwargs["run"] = asc_cli.offline_runner(Path(args.offline_fixture))
        return dispatch[args.command](args, **kwargs)
    except appconfig.ConfigError as e:
        print(f"FAIL: app.config.toml: {e}", file=sys.stderr)
        return 2
    except (asc_cli.AscError, ValueError) as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        # stderr của asc đã được che key ở asc_cli — in ra để biết vì sao asc từ chối.
        detail = getattr(e, "stderr", "")
        if detail:
            print(detail.rstrip(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
