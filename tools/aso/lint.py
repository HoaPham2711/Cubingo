"""Lint metadata App Store: giới hạn, keywords theo byte, chữ giữ chỗ, chữ cấm của app, URL theo host.

Luật chung (đúng ở mọi app): độ dài theo ký tự Unicode (`LIMITS`), keywords ≤ 100 BYTE UTF-8, keywords không có ", ",
từ khoá không trùng name/subtitle cùng locale, không còn `todo|tbd|lorem|TEMPLATE-PLACEHOLDER`, URL thiếu host hoặc còn
`$` (biến gieo chưa thay) là lỗi kể cả khi app không khai host, URL trỏ host giữ chỗ/dành riêng (`example.com|net|org`
và tên miền con, `*.example`, `*.test`, `*.invalid`, `localhost`, `*.localhost` — RFC 2606/6761) là lỗi kể cả khi đó
chính là `web.host_prod` (giá trị giữ chỗ của template), URL trỏ host dev là lỗi; `privacyPolicyUrl`/`supportUrl` không
trỏ `web.host_prod` (hay `www.` của nó, hai chiều) là lỗi (khi app có khai host), URL khác không trỏ host prod chỉ là
cảnh báo.
`store/review/notes.txt` (notes cho Apple Review, người dán tay): còn chữ giữ chỗ là lỗi; dài quá 384 ký tự (quy ước của
template cho notes ngắn, không phải giới hạn của Apple) hoặc có xuống dòng cuối chỉ là cảnh báo (`lint_notes`).
Danh sách chữ cấm là của APP: `store/lint.toml` (`banned = [...]`), lõi không mang sẵn từ nào.
"""
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import store  # noqa: E402
import appconfig  # noqa: E402

# Giới hạn theo số ký tự
LIMITS = {"name": 30, "subtitle": 30, "promotionalText": 170, "description": 4000, "whatsNew": 4000}
KEYWORDS_BYTES = 100  # keywords tính theo byte UTF-8

# Chuỗi của khung `store/` do template sinh: còn thấy là lint đỏ cho tới khi người viết chữ thật.
PLACEHOLDER = "TEMPLATE-PLACEHOLDER"

# Field URL App Store dùng làm trang của chính app: lệch host prod là LỖI (field URL khác chỉ cảnh báo).
OWN_HOST_FIELDS = ("privacyPolicyUrl", "supportUrl")
# Host giữ chỗ/dành riêng (RFC 2606/6761): không bao giờ là site thật của app.
RESERVED_DOMAINS = ("example.com", "example.net", "example.org")
RESERVED_TLDS = ("example", "test", "invalid", "localhost")
# Notes cho Apple Review (ô App Review Information › Notes) — đường dẫn tương đối từ gốc repo.
REVIEW_NOTES = Path("store") / "review" / "notes.txt"
# Quy ước của template (notes ngắn, dễ đọc khi duyệt) — ô của Apple nhận dài hơn nhiều ⇒ vượt chỉ cảnh báo.
REVIEW_NOTES_MAX = 384

_PLACEHOLDER = re.compile(r"\b(todo|tbd|lorem)\b|" + re.escape(PLACEHOLDER), re.IGNORECASE)
_WORD = re.compile(r"\w+")
_URL = re.compile(r"https?://[^\s\"'<>)\]]+", re.IGNORECASE)


@dataclass
class Issue:
    locale: str
    field: str
    message: str
    scope: str = ""
    # Khoá khác cùng gây ra lỗi (vd name/subtitle mà keywords trùng từ) — đụng khoá này cũng tính là đụng lỗi.
    related: tuple = ()
    severity: str = "error"          # "error" ⇒ lint đỏ · "warning" ⇒ chỉ báo

    def __str__(self) -> str:
        where = "/".join(x for x in (self.scope, self.locale, self.field) if x)
        tag = "cảnh báo: " if self.severity == "warning" else ""
        return f"{tag}{where}: {self.message}"


def _words(s: str) -> list[str]:
    return _WORD.findall(s.lower())


def load_banned(root: Path) -> list[str]:
    """Chữ cấm của app từ `<root>/store/lint.toml` (`banned = [...]`). Không có file ⇒ rỗng; sai dạng ⇒ ValueError."""
    path = Path(root) / "store" / "lint.toml"
    if not path.is_file():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"{path}: không phải TOML hợp lệ: {e}")
    banned = data.get("banned", [])
    if not isinstance(banned, list) or not all(isinstance(x, str) for x in banned):
        raise ValueError(f"{path}: banned phải là danh sách chuỗi")
    return list(banned)


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_reserved_host(host: str) -> bool:
    """Host giữ chỗ/dành riêng: `example.com|net|org` (+ tên miền con), TLD `example|test|invalid|localhost`, `localhost`."""
    h = host.lower().rstrip(".")
    if not h:
        return False
    if h.rsplit(".", 1)[-1] in RESERVED_TLDS:
        return True
    return any(h == d or h.endswith("." + d) for d in RESERVED_DOMAINS)


def same_site(host: str, host_prod: str) -> bool:
    """`host` là site của app: trùng `host_prod`, hoặc khác nhau đúng tiền tố `www.` (hai chiều)."""
    h, p = host.lower().rstrip("."), host_prod.lower().rstrip(".")
    return h == p or h == "www." + p or p == "www." + h


def lint_notes(text: str) -> list[Issue]:
    """Soi nội dung `store/review/notes.txt`: chữ giữ chỗ ⇒ lỗi; quá `REVIEW_NOTES_MAX` ký tự (quy ước của template)
    hoặc xuống dòng cuối ⇒ cảnh báo."""
    issues: list[Issue] = []

    def add(message, severity="error"):
        issues.append(Issue("", "notes.txt", message, "review", severity=severity))
    m = _PLACEHOLDER.search(text)
    if m:
        add(f"còn chữ giữ chỗ '{m.group(0)}' — viết notes cho Apple Review của bản này")
    if len(text) > REVIEW_NOTES_MAX:
        add(f"dài {len(text)} ký tự, quá quy ước {REVIEW_NOTES_MAX} ký tự của template cho notes ngắn "
            "(ô của Apple nhận dài hơn)", "warning")
    if text.endswith(("\n", "\r")):
        add("có xuống dòng cuối (người dán tay sẽ dán cả nó) — nên bỏ", "warning")
    return issues


def notes_report(root: Path) -> list[Issue]:
    """`lint_notes` của `<root>/store/review/notes.txt`; không có file ⇒ rỗng (app không giữ notes ở repo)."""
    path = Path(root) / REVIEW_NOTES
    if not path.is_file():
        return []
    return lint_notes(path.read_text(encoding="utf-8"))


def lint_values(values: dict, *, banned=(), host_prod: str = "", host_dev: str = "") -> list[Issue]:
    """Soi `values` {(scope, locale, field): chuỗi}. Trả mọi Issue (lỗi lẫn cảnh báo)."""
    issues: list[Issue] = []
    title_words: dict[str, set] = {}  # locale -> từ trong name/subtitle
    title_keys: dict[str, list] = {}  # locale -> khoá name/subtitle
    for key, value in sorted(values.items()):
        _scope, locale, field = key
        if field in ("name", "subtitle"):
            title_words.setdefault(locale, set()).update(_words(value))
            title_keys.setdefault(locale, []).append(key)
    host_prod, host_dev = host_prod.lower(), host_dev.lower()

    for (scope, locale, field), value in sorted(values.items()):
        def add(message, related=(), severity="error"):
            issues.append(Issue(locale, field, message, scope, tuple(related), severity))
        limit = LIMITS.get(field)
        if limit is not None and len(value) > limit:
            add(f"{field} dài {len(value)} ký tự, vượt giới hạn {limit}")
        if field == "keywords":
            size = len(value.encode("utf-8"))
            if size > KEYWORDS_BYTES:
                add(f"keywords {size} byte, vượt giới hạn {KEYWORDS_BYTES} byte")
            if ", " in value:
                add("keywords có dấu phẩy kèm dấu cách (lãng phí byte)")
            seen = set()
            for phrase in value.split(","):
                for w in _words(phrase):
                    if len(w) >= 2 and w in title_words.get(locale, ()) and w not in seen:
                        seen.add(w)
                        add(f"từ khoá '{w}' trùng với name/subtitle", title_keys.get(locale, ()))
        folded = value.casefold()
        for term in banned:
            if term and term.casefold() in folded:
                add(f"chứa chữ cấm '{term}'")
        m = _PLACEHOLDER.search(value)
        if m:
            add(f"còn chữ giữ chỗ '{m.group(0)}'")
        for url in _URL.findall(value):
            host = _host(url)
            if "$" in url or not host:
                # Khung sinh ra khi `web.host_prod` rỗng (`https:///privacy/`) hoặc biến gieo chưa thay: luôn là lỗi,
                # kể cả khi app không khai host nào.
                add(f"URL thiếu host hoặc còn biến chưa thay: {url}")
            elif is_reserved_host(host):
                # Giá trị giữ chỗ của template (`example.com`) hoặc host thử: đẩy lên App Store là sai, kể cả khi
                # `web.host_prod` vẫn còn chính giá trị đó.
                add(f"URL trỏ host giữ chỗ/dành riêng ({host}) — đặt `web.host_prod` thật trong app.config.toml "
                    f"rồi sửa URL trong store/metadata: {url}")
            elif host_dev and host == host_dev:
                add(f"URL trỏ host dev ({host}): {url}")
            elif host_prod and not same_site(host, host_prod):
                if field in OWN_HOST_FIELDS:
                    add(f"{field} không trỏ host prod ({host_prod}): {url}")
                else:
                    add(f"URL không trỏ host prod ({host_prod}): {url}", severity="warning")
    return issues


def lint_report(root: Path, version: str, *, banned=None, cfg: dict | None = None) -> list[Issue]:
    """Đọc `store/metadata` của repo `root` + host từ `app.config.toml` rồi soi. `banned=None` ⇒ đọc `store/lint.toml`."""
    root = Path(root)
    cfg = appconfig.load(root) if cfg is None else cfg
    values = store.load(store.metadata_dir(root), version)
    if banned is None:
        banned = load_banned(root)
    return lint_values(values, banned=banned,
                       host_prod=appconfig.opt(cfg, "web.host_prod", ""),
                       host_dev=appconfig.opt(cfg, "web.host_dev", "")) + notes_report(root)


def lint(root: Path, version: str, *, banned: list[str], cfg: dict | None = None) -> list[str]:
    """Các LỖI (mỗi lỗi một dòng); rỗng = xanh. Cảnh báo không vào đây — lấy qua `lint_report` (`severity`)."""
    return [str(i) for i in lint_report(root, version, banned=banned, cfg=cfg) if i.severity == "error"]
