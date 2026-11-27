"""Wrapper an toàn quanh CLI `asc` (ghim version).

- Kiểm policy (policy.check_asc_args) TRƯỚC khi chạy bất cứ thứ gì.
- Từ chối chạy nếu ASC_SHA256 (ghim) có giá trị mà SHA-256 của binary khác — kiểm TRƯỚC khi chạy
  binary lần nào (kể cả `asc version`); ghim rỗng ⇒ bỏ qua (install_asc.sh in giá trị để ghi vào).
- Từ chối chạy nếu `asc version` không khớp ASC_VERSION.
- Env sạch cho MỌI lần chạy (cả `asc version`): bỏ mọi ASC_* cũ, telemetry tắt; truyền key qua env
  (không keychain, không ghi ./.asc/).
- ASC_READ_ONLY=1 trừ khi write=True. Telemetry tắt. Luôn `--output json`.
- Không bao giờ in nội dung key/token; stderr của AscError đã lọc đường dẫn key và id.

Định danh đọc từ `app.config.toml` (qua `store.config()`), không viết cứng:
- App Store id ⇐ `apple.app_store_id` (`app_id()`; rỗng ⇒ `NoAppRecord` kèm hướng dẫn);
- binary ⇐ `appconfig.shared_bin_dir()/asc/<ASC_VERSION>/asc` (một bản cho cả máy, `install_asc.sh` cài);
- cấu hình khoá ⇐ `$ASO_CONFIG`, mặc định `appconfig.config_dir(cfg)/asc-listing.json` (theo slug);
- file `.p8` ⇐ `$ASC_KEY_FILE`, mặc định `~/.appstoreconnect/private_keys/AuthKey_<key_id>.p8`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import appconfig  # noqa: E402
import policy  # noqa: E402
import store  # noqa: E402

ASC_VERSION = (Path(__file__).resolve().parent / "ASC_VERSION").read_text().strip()
# SHA-256 ghim của binary (rỗng = chưa ghim; ghi sau khi user xác nhận giá trị install_asc.sh in ra).
ASC_SHA256 = (Path(__file__).resolve().parent / "ASC_SHA256").read_text().strip().lower()

NO_APP_RECORD = ("chưa có app record trên App Store Connect: tạo app trên ASC (tay) rồi ghi id số của nó vào "
                 "apple.app_store_id trong app.config.toml")

# Cache trong tiến trình: đường dẫn bin đã kiểm SHA-256 (nếu ghim) + version đạt.
_VERSION_OK: set[str] = set()


class AscError(Exception):
    def __init__(self, message: str, returncode: int | None = None, stderr: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class NoAppRecord(AscError):
    """`apple.app_store_id` rỗng — lệnh cần app record không chạy."""


def app_id(cfg: dict | None = None) -> str:
    """App Store id của app (`apple.app_store_id`); rỗng ⇒ NoAppRecord với hướng dẫn một dòng."""
    cfg = store.config() if cfg is None else cfg
    value = appconfig.opt(cfg, "apple.app_store_id", "")
    if not isinstance(value, str) or not value:
        raise NoAppRecord(NO_APP_RECORD)
    return value


def asc_bin() -> Path:
    """Đường dẫn binary `asc` ghim: `<shared_bin_dir>/asc/<ASC_VERSION>/asc` (dùng chung mọi app trên máy)."""
    return appconfig.shared_bin_dir().expanduser() / "asc" / ASC_VERSION / "asc"


def default_config(cfg: dict | None = None) -> Path:
    """Cấu hình khoá mặc định `{key_id, issuer_id}`: `<config_dir(cfg)>/asc-listing.json` (theo slug của app)."""
    cfg = store.config() if cfg is None else cfg
    return appconfig.config_dir(cfg).expanduser() / "asc-listing.json"


def _load_credentials() -> tuple[str, str, Path]:
    """Đọc key_id, issuer_id và đường dẫn .p8 (không đọc nội dung key)."""
    env_cfg = os.environ.get("ASO_CONFIG")
    cfg_path = Path(env_cfg).expanduser() if env_cfg else default_config()
    try:
        cfg = json.loads(cfg_path.read_text())
        key_id, issuer_id = cfg["key_id"], cfg["issuer_id"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise AscError(f"không đọc được cấu hình khoá ASC ({type(e).__name__}): tạo file JSON "
                       "{key_id, issuer_id} ở thư mục cấu hình của app hoặc trỏ $ASO_CONFIG tới nó") from None
    key_file = os.environ.get("ASC_KEY_FILE")
    key_path = (Path(key_file) if key_file
                else Path(f"~/.appstoreconnect/private_keys/AuthKey_{key_id}.p8")).expanduser()
    if not key_path.is_file():
        raise AscError("không thấy file key .p8")
    return key_id, issuer_id, key_path


def _redact(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "<redacted>")
    return text


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sanitized_env() -> dict[str, str]:
    """Env gốc bỏ mọi ASC_* và ASO_CONFIG, telemetry tắt — nền cho MỌI lần chạy binary."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("ASC_") and k != "ASO_CONFIG"}
    env.update({"ASC_TELEMETRY_DISABLED": "1", "DO_NOT_TRACK": "1"})
    return env


def _check_version(bin: Path) -> None:
    if str(bin) in _VERSION_OK:
        return
    pin = ASC_SHA256.strip().lower()
    if pin:
        try:
            actual = _sha256_file(bin)
        except OSError as e:
            raise AscError(f"không đọc được binary asc ({type(e).__name__}); chạy tools/aso/install_asc.sh") from None
        if actual != pin:
            raise AscError(f"SHA-256 của binary asc khác giá trị ghim trong tools/aso/ASC_SHA256 "
                           f"(ghim {pin[:12]}…, thực {actual[:12]}…) — không chạy")
    try:
        p = subprocess.run([str(bin), "version"], capture_output=True, text=True, timeout=30,
                           env=_sanitized_env())
    except OSError as e:
        raise AscError(f"không chạy được asc ({type(e).__name__}); chạy tools/aso/install_asc.sh") from None
    pattern = rf"(?<![\d.]){re.escape(ASC_VERSION)}(?![\d.])"
    if p.returncode != 0 or not re.search(pattern, p.stdout):
        raise AscError(f"asc lệch version (cần {ASC_VERSION}): {p.stdout.strip()[:80]!r}",
                       returncode=p.returncode)
    _VERSION_OK.add(str(bin))


def _build_env(write: bool, key_id: str, issuer_id: str, key_path: Path, app: str) -> dict[str, str]:
    env = _sanitized_env()
    env.update({
        "ASC_KEY_ID": key_id,
        "ASC_ISSUER_ID": issuer_id,
        "ASC_PRIVATE_KEY_PATH": str(key_path),
        "ASC_BYPASS_KEYCHAIN": "1",
        "ASC_APP_ID": app,
    })
    if not write:
        env["ASC_READ_ONLY"] = "1"
    return env


def run(args: list[str], *, write: bool = False, bin: Path | None = None) -> Any:
    """Chạy asc với args; trả JSON đã parse (stdout rỗng => None)."""
    policy.check_asc_args(args, write=write)
    app = app_id()  # chưa có app record ⇒ dừng trước khi chạy binary lần nào
    bin = Path(bin) if bin else asc_bin()
    _check_version(bin)
    key_id, issuer_id, key_path = _load_credentials()
    env = _build_env(write, key_id, issuer_id, key_path, app)
    full = list(args)
    if not any(a == "--output" or a.startswith("--output=") for a in full):
        full += ["--output", "json"]
    # asc ghi `.asc/reports/` vào cwd khi lỗi ⇒ chạy ở thư mục trạng thái, không phải worktree.
    cwd = store.state_dir() / "asc-cwd"
    cwd.mkdir(parents=True, exist_ok=True)
    p = subprocess.run([str(bin), *full], capture_output=True, text=True, env=env, cwd=str(cwd))
    secrets = [str(key_path), key_path.name, key_id, issuer_id]
    if p.returncode != 0:
        # asc để chi tiết lỗi từng localization ở stdout (JSON) — gộp vào để người đọc thấy lý do thật.
        detail = "\n".join(s for s in (p.stderr.strip(), p.stdout.strip()[:4000]) if s)
        raise AscError(f"asc thoát mã {p.returncode}", returncode=p.returncode,
                       stderr=_redact(detail, secrets))
    if not p.stdout.strip():
        return None
    try:
        return json.loads(p.stdout)
    except ValueError:
        raise AscError("stdout của asc không phải JSON", returncode=0,
                       stderr=_redact(p.stderr, secrets)) from None


# ---------- chạy giả từ fixture (`aso.py --offline-fixture DIR`) — không binary, không mạng ----------

_PATH_FLAGS = {"--dir": "DIR", "--ipa": "IPA"}
_UNSAFE = re.compile(r"[^A-Za-z0-9._=-]")


def fixture_key(args: list[str]) -> str:
    """Khoá CHUẨN HOÁ của một lệnh asc (argv sau tên binary, chưa có `--output json`) — tên file fixture không đuôi.

    Chuẩn hoá để một bộ fixture dùng được ở mọi app và mọi lần chạy:
    - giá trị sau `--app` ⇒ `APP` (App Store id khác nhau giữa các app);
    - giá trị sau `--dir` ⇒ `DIR`, sau `--ipa` ⇒ `IPA` (thư mục tạm/đường dẫn đổi mỗi lần);
    - mọi đối số khác là đường dẫn tuyệt đối ⇒ `PATH`;
    - nối các token bằng `_`; ký tự ngoài `[A-Za-z0-9._=-]` trong token ⇒ `-`.
    Ví dụ: `metadata pull --app 123 --version 0.1.0 --dir /tmp/x` ⇒ `metadata_pull_--app_APP_--version_0.1.0_--dir_DIR`.
    """
    out, prev = [], None
    for a in args:
        if prev == "--app":
            tok = "APP"
        elif prev in _PATH_FLAGS:
            tok = _PATH_FLAGS[prev]
        elif a.startswith("/"):
            tok = "PATH"
        else:
            tok = _UNSAFE.sub("-", a)
        out.append(tok)
        prev = a
    return "_".join(out)


def offline_runner(fixture_dir: Path):
    """`run` giả đọc phản hồi ghi sẵn: `<fixture_dir>/<fixture_key(args)>.json` dạng
    `{"response": <JSON asc in ra, có thể null>, "files": {"<đường dẫn tương đối>": <object JSON>}}`.

    `files` được ghi vào thư mục của `--dir` (như `asc metadata pull` thật). Vẫn đi qua `policy.check_asc_args`;
    lệnh ghi (`write=True`) ⇒ AscError (fixture không bao giờ đóng vai lối ghi). Thiếu fixture ⇒ AscError nêu khoá."""
    fixture_dir = Path(fixture_dir)

    def run(args: list[str], *, write: bool = False, bin: Path | None = None) -> Any:
        policy.check_asc_args(args, write=write)
        if write:
            raise AscError("chế độ fixture offline không chạy lệnh ghi")
        key = fixture_key(list(args))
        path = fixture_dir / f"{key}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise AscError(f"fixture offline thiếu lệnh: {key} (cần file {path})") from None
        except ValueError as e:
            raise AscError(f"fixture offline {path} không phải JSON: {e}") from None
        if not isinstance(data, dict) or set(data) - {"response", "files"}:
            raise AscError(f"fixture offline {path}: gốc phải là object chỉ có 'response' và 'files'")
        files = data.get("files") or {}
        if files:
            if "--dir" not in args or args.index("--dir") + 1 >= len(args):
                raise AscError(f"fixture offline {key}: có 'files' nhưng lệnh không có --dir")
            dest = Path(args[args.index("--dir") + 1])
            for rel, obj in files.items():
                target = (dest / rel).resolve()
                if dest.resolve() not in target.parents:
                    raise AscError(f"fixture offline {key}: đường dẫn ra ngoài --dir: {rel}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return data.get("response")
    return run
