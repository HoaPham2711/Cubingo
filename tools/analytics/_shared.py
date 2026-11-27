"""Phần dùng chung của các lệnh kéo số trong tools/analytics: cấu hình, khoá, phụ thuộc ngoài, thư mục đầu ra.

- Định danh (bundle id, GA4 property, project BigQuery) đọc từ `app.config.toml` qua `tools/common/appconfig.py`;
  biến môi trường cùng tên với nguồn (`GA4_PROPERTY_ID`, `GA4_BQ_PROJECT`, …) thắng cấu hình.
- Khoá nằm NGOÀI repo, ở `appconfig.config_dir(cfg)` (`asc.json`, `analytics-reader.json`) hoặc đường dẫn trong biến
  môi trường. Không bao giờ in nội dung khoá; thông báo lỗi chỉ nêu đường dẫn mong đợi.
- Phụ thuộc ngoài stdlib (`requirements.txt`) chỉ import trong hàm; thiếu ⇒ `Refuse` một dòng hướng dẫn cài, rc 2.
- Đầu ra: `<gốc>/<nguồn>/<YYYY-MM-DD>/`, gốc = `$ANALYTICS_OUT` nếu đặt (test trỏ vào thư mục tạm), không thì
  `<repo>/.temp/analytics` (đã gitignore).
"""
from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import appconfig  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
INSTALL_HINT = "FAIL: cần cài: python3 -m pip install -r tools/analytics/requirements.txt"


class Refuse(Exception):
    """Dừng có chủ đích: in đúng một dòng (thông điệp) ra stderr, rc 2. Không traceback."""


def load_cfg() -> dict:
    """Cấu hình app (`app.config.toml`). Test thay hàm này bằng cấu hình giả."""
    return appconfig.load(REPO)


def require(*modules: str) -> None:
    """Import thử từng module; thiếu cái nào ⇒ Refuse(INSTALL_HINT)."""
    for name in modules:
        try:
            importlib.import_module(name)
        except ImportError:
            raise Refuse(INSTALL_HINT) from None


def env_or(name: str, value: str) -> str:
    """Biến môi trường `name` nếu đặt và khác rỗng, không thì `value`."""
    v = os.environ.get(name, "")
    return v if v else value


def path_from_env(name: str, default: Path) -> Path:
    v = os.environ.get(name, "")
    return Path(v).expanduser() if v else default


def out_root() -> Path:
    v = os.environ.get("ANALYTICS_OUT", "")
    return Path(v).expanduser() if v else REPO / ".temp" / "analytics"


def run_dir(source: str, explicit: Path | None = None, today: dt.date | None = None) -> Path:
    """Thư mục đầu ra của một lần kéo; tạo nếu chưa có."""
    d = explicit or out_root() / source / (today or dt.date.today()).isoformat()
    d.mkdir(parents=True, exist_ok=True)
    return d


def show(path: Path) -> str:
    return str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)


def ga4_property(cfg: dict) -> str:
    """GA4 property id: `$GA4_PROPERTY_ID` thắng `[analytics] ga4_property`; cả hai rỗng ⇒ Refuse."""
    prop = env_or("GA4_PROPERTY_ID", str(appconfig.opt(cfg, "analytics.ga4_property", "") or ""))
    if not prop:
        raise Refuse("FAIL: chưa có GA4 property — đặt [analytics] ga4_property trong app.config.toml "
                     "(hoặc biến GA4_PROPERTY_ID)")
    return prop


def ga4_key_file(cfg: dict) -> Path:
    """File service account (role Viewer GA4 + BigQuery): `$GA4_KEY_FILE` hoặc `<config_dir>/analytics-reader.json`.
    Chỉ kiểm có file — KHÔNG đọc nội dung ở đây."""
    key = path_from_env("GA4_KEY_FILE", appconfig.config_dir(cfg) / "analytics-reader.json")
    if not key.is_file():
        raise Refuse(f"FAIL: thiếu file service account: {key} — đặt file JSON của service account (role Viewer) "
                     f"ở đó hoặc trỏ GA4_KEY_FILE tới nó")
    return key


def google_session(key_file: Path, scopes: list[str]):
    """Phiên HTTP đã xác thực bằng service account (google-auth). Lỗi đọc/parse khoá ⇒ Refuse không kèm nội dung."""
    require("requests", "google.auth", "google.oauth2")
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    try:
        creds = service_account.Credentials.from_service_account_file(str(key_file), scopes=scopes)
    except Exception:  # noqa: BLE001 — thông điệp của thư viện có thể trích nội dung khoá
        raise Refuse(f"FAIL: không đọc được service account ở {key_file} — kiểm đúng file JSON key") from None
    return AuthorizedSession(creds)


def session_fetch(session):
    """`fetch(method, url, **kw)` từ một phiên kiểu requests."""
    def fetch(method, url, **kw):
        kw.setdefault("timeout", 120)
        return session.request(method, url, **kw)
    return fetch


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def run_main(fn, *args, **kw) -> int:
    """Chạy `fn`; Refuse ⇒ in một dòng ra stderr, rc 2."""
    try:
        return fn(*args, **kw)
    except Refuse as e:
        print(str(e), file=sys.stderr)
        return 2


# ---------- API admin của web (`web/api`, Bearer ADMIN_TOKEN) ----------

class _HttpResp:
    """Phản hồi tối thiểu kiểu `requests.Response` cho `http_fetch` (chỉ stdlib)."""

    def __init__(self, status: int, body: bytes):
        self.status_code = status
        self.content = body
        self.text = body.decode("utf-8", "replace")

    def json(self):
        return json.loads(self.text)


def http_fetch(method: str, url: str, **kw):
    """`fetch(method, url, headers=…, timeout=…)` thật bằng urllib — không cần `requests`.

    KHÔNG theo chuyển hướng: urllib mặc định gửi lại MỌI header (kể cả `Authorization: Bearer <token admin>`) tới đích
    3xx, khác host cũng vậy ⇒ `web.host_prod` sai (apex → www, trang đỗ tên miền) làm lộ token. 3xx ⇒ Refuse một dòng."""
    import urllib.error
    import urllib.request

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None  # urllib ném HTTPError với mã 3xx thay vì đi tiếp

    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, method=method, headers=kw.get("headers") or {})
    try:
        with opener.open(req, timeout=kw.get("timeout", 60)) as r:  # noqa: S310 — https do appconfig dựng
            return _HttpResp(r.status, r.read())
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:
            raise Refuse(f"FAIL: API web trả chuyển hướng HTTP {e.code} — không theo (token admin không được gửi tới host "
                         "khác); đặt web.host_prod đúng host phục vụ /api/") from None
        return _HttpResp(e.code, e.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Refuse(f"FAIL: không gọi được API web ({type(e).__name__}) — kiểm mạng và web.host_prod") from None


def web_api_on(cfg: dict) -> bool:
    """App có API web ⇔ `features.web_api` (Ruling 11: tắt ⇒ chỉ site, không có `/api/*` để kéo số)."""
    return appconfig.feature(cfg, "features.web_api")


def web_admin(cfg: dict) -> tuple[str | None, str | None, Path]:
    """(host, token, đường dẫn file token). host rỗng/token thiếu ⇒ None. Token đọc từ `$WEB_ADMIN_TOKEN_FILE` hoặc
    `<config_dir>/web-admin-token`; nội dung KHÔNG bao giờ được in/ghi ra đâu cả."""
    host = str(appconfig.opt(cfg, "web.host_prod", "") or "") or None
    path = path_from_env("WEB_ADMIN_TOKEN_FILE", appconfig.config_dir(cfg) / "web-admin-token")
    token = None
    if path.is_file():
        token = path.read_text(encoding="utf-8").strip() or None
    return host, token, path


def admin_get(fetch, host: str, token: str, token_file: Path, path: str, params: dict | None = None) -> dict:
    """GET `https://<host>/api/v1/admin/<path>` → JSON. 401 ⇒ Refuse (token sai), 429 ⇒ Refuse (IP bị khoá),
    lỗi khác ⇒ Refuse kèm mã HTTP. Thông điệp chỉ nêu đường dẫn file token, không bao giờ nội dung."""
    import urllib.parse
    url = f"https://{host}/api/v1/admin/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    r = fetch("GET", url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if r.status_code == 401:
        raise Refuse(f"FAIL: API web từ chối token (HTTP 401) — đặt đúng ADMIN_TOKEN vào {token_file}")
    if r.status_code == 429:
        raise Refuse("FAIL: API web khoá IP này (HTTP 429, quá nhiều lần sai token) — đợi khoảng 1 giờ rồi thử lại")
    if r.status_code != 200:
        raise AdminError(r.status_code)
    try:
        return r.json()
    except ValueError:
        raise AdminError(r.status_code) from None


class AdminError(Exception):
    """Phản hồi admin không dùng được (không phải 401/429); `.status` là mã HTTP."""

    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.status = status


# Server giữ số web + sự kiện gói 400 ngày (web/api/src/cron.ts RETAIN_DAYS) và kẹp /admin/stats ở 400.
SERVER_RETAIN_DAYS = 400


def retained_days(s: str) -> int:
    """Kiểu argparse cho `--days` của số kéo qua API web: 1..SERVER_RETAIN_DAYS (vượt ⇒ lỗi, rc 2 — không ghi số ngày
    mà server không có)."""
    import argparse
    n = positive_int(s)
    if n > SERVER_RETAIN_DAYS:
        raise argparse.ArgumentTypeError(f"tối đa {SERVER_RETAIN_DAYS} (server chỉ giữ {SERVER_RETAIN_DAYS} ngày): {s!r}")
    return n


def positive_int(s: str) -> int:
    """Kiểu argparse: số nguyên ≥ 1 (sai ⇒ argparse báo lỗi, rc 2)."""
    import argparse
    try:
        n = int(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"phải là số nguyên ≥ 1: {s!r}") from None
    if n < 1:
        raise argparse.ArgumentTypeError(f"phải là số nguyên ≥ 1: {s!r}")
    return n
