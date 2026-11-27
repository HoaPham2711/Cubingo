"""Build local: archive + export .ipa App Store, chạy cổng phát hành, ghi build.json.

KHÔNG gọi App Store Connect (không dùng asc_cli). Chỉ chạy lệnh local qua `run_cmd` tiêm vào, git qua `git` tiêm vào —
test chỉ kiểm argv dựng ra, không bao giờ chạy xcodebuild thật.

Định danh/bố cục không viết cứng: project/scheme/target là hằng bố cục của `appconfig` (`PROJECT`, `PROJ_DIR`,
`STORE_SCHEME` = cấu hình Release + bundle id Store, `APP_TARGET`); version/build đọc `[version]` của `app.config.toml`
(Info.plist chỉ có `$(APP_MARKETING_VERSION)`, giá trị thật đến từ `Identity.xcconfig` sinh ra); team ⇐ `apple.team_id`.
Như `tools/release/bump_version.sh`: build từ nhánh `main`, cây sạch, HEAD mang tag `v<marketing>`.
"""
from __future__ import annotations

import hashlib
import json
import plistlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import appconfig  # noqa: E402
import store  # noqa: E402

RELEASE_BRANCH = "main"


def config_version(cfg: dict) -> tuple[str, str]:
    """(marketing, build) từ `[version]` của cấu hình."""
    return str(appconfig.get(cfg, "version.marketing")), str(appconfig.get(cfg, "version.build"))


def preflight(repo: Path, version: str, *, git, cfg: dict) -> str:
    """Kiểm checkout đúng để ra bản; trả commit SHA. Sai ⇒ ValueError (chưa chạy lệnh build nào)."""
    marketing, _number = config_version(cfg)
    if marketing != version:
        raise ValueError(f"app.config.toml có version.marketing = {marketing}, không phải {version}")
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if branch != RELEASE_BRANCH:
        raise ValueError(f"phải build từ nhánh {RELEASE_BRANCH} (đang ở {branch})")
    if git(["status", "--porcelain"]).strip():
        raise ValueError("cây làm việc chưa sạch (git status --porcelain khác rỗng)")
    try:
        tag = git(["describe", "--exact-match", "--tags", "HEAD"]).strip()
    except Exception:  # noqa: BLE001 — không có tag ở HEAD
        tag = ""
    if tag != f"v{version}":
        raise ValueError(f"HEAD phải có tag v{version} (thấy: {tag or 'không có tag'})")
    stale = appconfig.stale_generated(repo, cfg)
    if stale:
        raise ValueError(f"file sinh từ app.config.toml lệch/thiếu: {', '.join(stale)} — chạy "
                         "`python3 tools/common/appconfig.py render` rồi commit")
    return git(["rev-parse", "HEAD"]).strip()


def export_options(path: Path, team_id: str) -> None:
    path.write_bytes(plistlib.dumps({
        "method": "app-store-connect", "teamID": team_id, "signingStyle": "automatic",
        "uploadSymbols": True, "destination": "export"}))


def _step(run_cmd, argv, cwd) -> None:
    code, out = run_cmd(argv, cwd)
    if code != 0:
        tail = "\n".join(str(out).splitlines()[-40:])
        raise RuntimeError(f"lệnh lỗi (exit {code}): {' '.join(argv)}\n{tail}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _vb(plist: dict) -> tuple[str, str]:
    return str(plist.get("CFBundleShortVersionString")), str(plist.get("CFBundleVersion"))


def build(repo: Path, version: str, *, run_cmd, git, cfg: dict | None = None) -> Path:
    """Archive → export → cổng → build.json; trả đường dẫn build.json.

    Làm trong `<dir>.partial/`, chỉ đổi tên thành `<dir>` sau khi build.json đã ghi ⇒ lần lỗi không để lại
    thư mục cuối; `.partial` cũ (không bao giờ có build.json) tự bị xoá khi thử lại.
    """
    repo = Path(repo)
    cfg = store.config() if cfg is None else cfg
    commit = preflight(repo, version, git=git, cfg=cfg)
    want = config_version(cfg)
    number = want[1]
    d = store.state_dir(cfg) / "builds" / f"{version}-{number}"
    if d.exists():
        raise ValueError(f"{d} đã có (build.json đã ghi) — không ghi đè (xoá tay nếu muốn build lại)")
    work = d.with_name(d.name + ".partial")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    archive, export = work / f"{appconfig.APP_TARGET}.xcarchive", work / "export"
    plist = work / "ExportOptions.plist"
    export_options(plist, str(appconfig.get(cfg, "apple.team_id")))
    _step(run_cmd, ["xcodegen", "generate"], repo / appconfig.PROJ_DIR)
    _step(run_cmd, ["xcodebuild", "archive", "-project", appconfig.PROJECT, "-scheme", appconfig.STORE_SCHEME,
                    "-configuration", "Release", "-destination", "generic/platform=iOS",
                    "-archivePath", str(archive)], repo)
    apps = sorted((archive / "Products" / "Applications").glob("*.app"))
    if len(apps) != 1:
        raise RuntimeError(f"cần đúng một .app trong xcarchive, thấy {len(apps)}")
    app_vb = _vb(plistlib.loads((apps[0] / "Info.plist").read_bytes()))
    if app_vb != want:
        raise RuntimeError(f"Info.plist trong xcarchive lệch: {app_vb}, mong {want} (theo [version] của "
                           "app.config.toml)")
    _step(run_cmd, ["xcodebuild", "-exportArchive", "-archivePath", str(archive), "-exportPath", str(export),
                    "-exportOptionsPlist", str(plist), "-allowProvisioningUpdates"], repo)
    _step(run_cmd, ["./tools/release/verify_release_clean.sh", str(archive)], repo)
    _step(run_cmd, ["python3", "tools/i18n/verify_catalog.py", "--check"], repo)
    ipas = sorted(export.glob("*.ipa"))
    if len(ipas) != 1:
        raise RuntimeError(f"cần đúng một .ipa trong {export}, thấy {len(ipas)}")
    final_ipa = d.resolve() / "export" / ipas[0].name  # đường dẫn SAU khi đổi tên
    (work / "build.json").write_text(json.dumps({
        "version": version, "build": number, "commit": commit, "ipa": str(final_ipa),
        "ipa_sha256": _sha256(ipas[0]),
        "gates": {"verify_release_clean": "ok", "verify_catalog": "ok"},
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds")}, indent=2) + "\n",
        encoding="utf-8")
    work.rename(d)
    return d / "build.json"
