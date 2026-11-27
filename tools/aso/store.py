"""Nguồn sự thật metadata của repo, đúng bố cục `asc metadata pull` ghi ra.

    <root>/app-info/<locale>.json
    <root>/version/<versionString>/<locale>.json

Tài liệu `asc` mâu thuẫn giữa `version/` và `versions/`: `load` nhận cả hai
(có cả hai ⇒ ValueError) và báo lại tên đã thấy (`Metadata.vdir`); `write` ghi `version/` trừ khi
truyền `vdir` — applier dựng thư mục push đúng tên mà `asc metadata pull` vừa ghi.
Cấm: `default.json`, giá trị `null`, giá trị không phải chuỗi.

Hai mức đường dẫn:
- `load`/`write` nhận `root` = thư mục metadata (`<repo>/store/metadata`, hoặc thư mục `asc metadata pull` ghi ra);
- `metadata_dir`/`load_app_info`/`load_version`/`locales_on_disk` nhận `root` = GỐC repo (app) cho tiện gọi từ lint, CLI.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import appconfig  # noqa: E402

# Gốc repo = hai cấp trên tools/aso/ (lớp đồng bộ: giống nhau ở mọi app).
REPO = Path(__file__).resolve().parents[2]
STORE = REPO / "store" / "metadata"


def config() -> dict:
    """`app.config.toml` của repo này (đọc + kiểm mỗi lần gọi, không cache).

    Mọi định danh của công cụ ASO (App Store id, slug ⇒ thư mục trạng thái/khoá, team, version) đi qua đây.
    Test thay hàm này bằng cấu hình giả (`_testenv`)."""
    return appconfig.load(REPO)


def state_dir(cfg: dict | None = None) -> Path:
    """Thư mục trạng thái tuyệt đối của ASO cho app này = `appconfig.state_dir(cfg, "aso")`.

    `~/Library/Application Support/ios-app-factory/<slug>/aso` (ghi đè gốc bằng `$IOS_APP_FACTORY_STATE` — test luôn
    đặt). Bên trong: `snapshots/`, `plans/`, `builds/`, `applied.jsonl`, `asc-cwd/`. Tính lại mỗi lần gọi."""
    cfg = config() if cfg is None else cfg
    return appconfig.state_dir(cfg, "aso").expanduser().resolve()

# (scope, locale, field); scope ∈ {"app-info", "version"}
Field = tuple[str, str, str]

APP_INFO = "app-info"
VERSION = "version"
VERSION_DIRS = ("version", "versions")


class Metadata(dict):
    """dict field → chuỗi, kèm `vdir`: tên thư mục version đã thấy khi load ("version"/"versions"),
    None nếu không có thư mục version nào."""

    def __init__(self, values=(), vdir=None):
        super().__init__(values)
        if vdir not in (None, *VERSION_DIRS):
            raise ValueError(f"tên thư mục version lạ: {vdir}")
        self.vdir = vdir


def _version_dir(root: Path, version: str):
    """Trả về thư mục version tồn tại (version/ hoặc versions/), hoặc None."""
    found = [root / d / version for d in VERSION_DIRS if (root / d / version).is_dir()]
    if len(found) > 1:
        raise ValueError(f"cả version/ và versions/ cùng có {version} — mơ hồ")
    return found[0] if found else None


def _read_dir(directory: Path, scope: str, out: dict) -> None:
    for path in sorted(directory.glob("*.json")):
        locale = path.stem
        if locale == "default":
            raise ValueError(f"cấm default.json: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: gốc JSON phải là object")
        for key, value in data.items():
            if value is None:
                raise ValueError(f"{path}: {key} = null (cấm xoá bằng null)")
            if not isinstance(value, str):
                raise ValueError(f"{path}: {key} không phải chuỗi")
            out[(scope, locale, key)] = value


def load(root: Path, version: str) -> Metadata:
    """Đọc toàn bộ field chuỗi của app-info và version `version`; `.vdir` = tên thư mục version đã thấy."""
    root = Path(root)
    out: dict[Field, str] = {}
    if (root / "app-info").is_dir():
        _read_dir(root / "app-info", APP_INFO, out)
    vdir = _version_dir(root, version)
    if vdir is not None:
        _read_dir(vdir, VERSION, out)
    return Metadata(out, vdir.parent.name if vdir is not None else None)


def write(root: Path, version: str, values: dict[Field, str], *, vdir: str | None = None) -> None:
    """Ghi JSON UTF-8, khoá sắp xếp, indent 2, `\\n` cuối (diff git ổn định).

    `vdir` = tên thư mục version ("version" mặc định, hoặc "versions").
    """
    vdir = vdir or VERSION
    if vdir not in VERSION_DIRS:
        raise ValueError(f"tên thư mục version lạ: {vdir}")
    root = Path(root)
    files: dict[Path, dict[str, str]] = {}
    for (scope, locale, field), value in values.items():
        if locale == "default":
            raise ValueError("cấm default.json")
        if not isinstance(value, str):
            raise ValueError(f"{scope}/{locale}/{field}: không phải chuỗi")
        if scope == APP_INFO:
            path = root / "app-info" / f"{locale}.json"
        elif scope == VERSION:
            path = root / vdir / version / f"{locale}.json"
        else:
            raise ValueError(f"scope lạ: {scope}")
        files.setdefault(path, {})[field] = value
    for path, data in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- tiện ích theo GỐC repo

def metadata_dir(root: Path) -> Path:
    """`<root>/store/metadata` — nơi `asc metadata pull` ghi, nơi người sửa chữ."""
    return Path(root) / "store" / "metadata"


def load_app_info(root: Path, locale: str) -> dict:
    """Field của `app-info/<locale>.json` (rỗng nếu file không có). Cùng luật `load`: không null, chỉ chuỗi."""
    out: dict[Field, str] = {}
    path = metadata_dir(root) / "app-info"
    if (path / f"{locale}.json").is_file() or locale == "default":
        _read_one(path, locale, APP_INFO, out)
    return {field: value for (_s, _l, field), value in out.items()}


def load_version(root: Path, version: str, locale: str) -> dict:
    """Field của `version[s]/<version>/<locale>.json`. Có cả `version/` lẫn `versions/` ⇒ ValueError (như `load`)."""
    vdir = _version_dir(metadata_dir(root), version)
    out: dict[Field, str] = {}
    if vdir is not None and ((vdir / f"{locale}.json").is_file() or locale == "default"):
        _read_one(vdir, locale, VERSION, out)
    return {field: value for (_s, _l, field), value in out.items()}


def locales_on_disk(root: Path, version: str) -> list[str]:
    """Locale có file ở app-info HOẶC ở thư mục version `version`, sắp xếp. `default` ⇒ ValueError."""
    base = metadata_dir(root)
    found: set[str] = set()
    dirs = [base / "app-info"]
    vdir = _version_dir(base, version)
    if vdir is not None:
        dirs.append(vdir)
    for d in dirs:
        if d.is_dir():
            for path in d.glob("*.json"):
                if path.stem == "default":
                    raise ValueError(f"cấm default.json: {path}")
                found.add(path.stem)
    return sorted(found)


def _read_one(directory: Path, locale: str, scope: str, out: dict) -> None:
    """Đọc đúng một file locale bằng cùng luật kiểm của `_read_dir`."""
    if locale == "default":
        raise ValueError(f"cấm default.json: {directory / 'default.json'}")
    path = directory / f"{locale}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: gốc JSON phải là object")
    for key, value in data.items():
        if value is None:
            raise ValueError(f"{path}: {key} = null (cấm xoá bằng null)")
        if not isinstance(value, str):
            raise ValueError(f"{path}: {key} không phải chuỗi")
        out[(scope, locale, key)] = value
