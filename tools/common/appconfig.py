#!/usr/bin/env python3
"""Loader cho app.config.toml — nguồn duy nhất của định danh app.

Mọi tool khác import module này thay vì chép literal định danh:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
    import appconfig

CLI:
    appconfig.py get <khoá>            in giá trị (vd bundle.store; store.locales in danh sách cách nhau bằng dấu phẩy)
    appconfig.py state-dir <tool>      in thư mục trạng thái của tool cho app này (không tạo thư mục)
    appconfig.py config-dir            in thư mục cấu hình/khoá của app này (không tạo thư mục)
    appconfig.py render                ghi AppHost/Config/Identity.xcconfig + Features.generated.yml
                                       + AppHost/AppHost/PrivacyInfo.xcprivacy (khi có mẫu PRIVACY_TEMPLATE)
                                       + Entitlements.generated.yml + AppHost/AppHost/AppHost.entitlements
                                       + web/api/wrangler.jsonc + web/site/wrangler.jsonc (khi web.host_prod có giá trị)
    appconfig.py check                 rc 1 nếu một file sinh ra đã cũ so với config
    appconfig.py fixture-plist --out D ghi GoogleService-Info-{Prod,Dev}.plist vào D
Lỗi cấu hình ⇒ `FAIL: <thông báo>` ra stderr, rc 2, không traceback.

Lược đồ CHẶT (`SCHEMA`): section/khoá không có trong lược đồ bị từ chối (khoá gõ sai như `[web] hostprod`
không được âm thầm thành rỗng). Thêm khoá mới = thêm vào `SCHEMA` cùng lúc với `app.config.toml`.
"""
from __future__ import annotations

import sys

# Chặn MỘT chỗ cho mọi tool (tomllib có từ 3.11): Python cũ của macOS (/usr/bin/python3 = 3.9) phải nhận
# một dòng FAIL rõ ràng, không phải traceback ModuleNotFoundError. Áp cho cả import lẫn CLI.
if sys.version_info < (3, 11):
    sys.stderr.write(f"FAIL: cần Python ≥ 3.11 (đang chạy {sys.version_info[0]}.{sys.version_info[1]})\n")
    raise SystemExit(2)

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import plistlib  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import tomllib  # noqa: E402
from pathlib import Path  # noqa: E402

# --- Hằng số bố cục repo (không phải định danh) ---
PROJ_DIR = "AppHost"
PROJECT = "AppHost/AppHost.xcodeproj"
# Thư mục nguồn/test của app. `Core/` + `CoreTests/` nằm NGOÀI AppHost/ (lõi dùng chung); `CoreOptional/` +
# `CoreOptionalTests/` là các khối tuỳ chọn (chỉ biên dịch khi công tắc bật — xem OPTIONAL_BLOCKS). Tool lặp qua các
# root này phải chịu được root ngoài AppHost/ và root VẮNG MẶT (template chưa có / app đã xoá khối).
SRC_ROOTS = ("AppHost/AppHost/", "Core/", "CoreOptional/")
TEST_ROOTS = ("AppHost/AppHostTests/", "CoreTests/", "CoreOptionalTests/")
APP_TARGET = "AppHost"
TEST_TARGET = "AppHostTests"
UITEST_TARGET = "AppHostUITests"
SCHEME = "AppHost"
UISHOTS_SCHEME = "AppHost-UIShots"
STORE_SCHEME = "AppHost-Store"
STOREKIT_SCHEME = "AppHost-StoreKitTests"
# Scheme chỉ build Core/ một mình (static library không ship) — cổng biên "lõi không biết app".
CORE_ONLY_SCHEME = "CoreOnly"
XCCONFIG = "AppHost/Config/Identity.xcconfig"
# Spec XcodeGen sinh ra, `project.yml` include — nơi khối tuỳ chọn theo công tắc được nối vào target.
FEATURES_YML = "AppHost/Config/Features.generated.yml"
WHATS_NEW_CATALOG = "AppHost/AppHost/WhatsNew/WhatsNewCatalog.swift"
# Cấu hình StoreKit local: resource của test bundle + tuỳ chọn Run của scheme AppHost, KHÔNG nằm trong .app.
# Do app sở hữu (không sinh từ cấu hình); tools/release/check_storekit.py giữ id khớp `[purchases] product_ids`.
STOREKIT_CONFIG = "AppHost/StoreKitConfig/Products.storekit"
CONFIG_FILE = "app.config.toml"

XCCONFIG_HEADER = ("// SINH TỰ ĐỘNG từ app.config.toml — không sửa tay. "
                   "Chạy: python3 tools/common/appconfig.py render\n")
FEATURES_YML_HEADER = ("# SINH TỰ ĐỘNG từ app.config.toml — không sửa tay. "
                       "Chạy: python3 tools/common/appconfig.py render\n"
                       "# AppHost/project.yml include file này; mảng sources/dependencies ở đây được nối thêm vào target.\n")

_REQUIRED = (
    "app.slug", "app.display_name", "app.display_name_internal",
    "bundle.store", "bundle.internal", "apple.team_id",
    "version.marketing", "version.build",
)
# Lược đồ chặt: đúng các section/khoá có trong app.config.toml của template. Khoá tuỳ chọn được phép VẮNG,
# không được LẠ. Test `test_luoc_do_khop_dung_config_cua_template` giữ hai nơi khớp nhau.
SCHEMA: dict[str, tuple[str, ...]] = {
    "app": ("slug", "display_name", "display_name_internal"),
    "bundle": ("store", "internal"),
    "apple": ("team_id", "app_store_id"),
    "version": ("marketing", "build"),
    "web": ("host_prod", "host_dev", "app_paths", "external_site"),
    "cloudflare": ("d1_prod", "d1_dev"),
    "firebase": ("app_check_prod", "app_check_dev"),
    "support": ("email",),
    "features": ("paywall", "web_api", "apple_ads"),
    "purchases": ("product_ids", "subscription_group"),
    "store": ("locales",),
    "analytics": ("ga4_property", "bq_project"),
    "i18n": ("languages",),
}
# Mọi regex dùng `fullmatch` (không neo `^…$`: `$` của `re.match` nhận cả "…\n").
_RE_SLUG = re.compile(r"[a-z][a-z0-9-]{1,30}")
_RE_BUNDLE = re.compile(r"[A-Za-z0-9.-]+")
_RE_TEAM = re.compile(r"[A-Z0-9]{10}")
_RE_MARKETING = re.compile(r"\d+\.\d+\.\d+")
_RE_BUILD = re.compile(r"\d+")
# Hostname trần: chữ, số, '.', '-' — không scheme, không '/', không cổng, không khoảng trắng.
_RE_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?")
_WEB_KEYS = ("web.host_prod", "web.host_dev")
# Id D1 do `wrangler d1 create` in ra (UUID) — chấp nhận chữ, số, '-' để không chặn định dạng đổi sau này.
_RE_D1_ID = re.compile(r"[A-Za-z0-9-]+")
# Audience App Check: "<projectId>:<projectNumber>" (projectNumber là SỐ, không phải id chữ).
_RE_APP_CHECK = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]:\d+")
_RE_APP_PATH_BAD = re.compile(r"[?#\s]")
_RE_APP_STORE_ID = re.compile(r"\d*")
# Email đơn giản dạng x@y.z — đủ chặn gõ nhầm và ký tự phá xcconfig ('//', '$(', khoảng trắng).
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# Id sản phẩm StoreKit: không khoảng trắng (APP_PRODUCT_IDS nối bằng dấu cách).
_RE_PRODUCT_ID = re.compile(r"[A-Za-z0-9._-]+")
# Locale App Store Connect: `ll`, `ll-RR` (vùng) hoặc `ll-Ssss` (chữ viết) — vd en-US, vi, ja, fr-CA, zh-Hans, pt-BR.
_RE_LOCALE = re.compile(r"[a-z]{2,3}(?:-(?:[A-Z]{2}|[A-Z][a-z]{3}))?")
DEFAULT_STORE_LOCALES = ("en-US",)
_RE_GA4_PROPERTY = re.compile(r"\d*")
# Project id GCP: 6–30 ký tự, chữ thường/số/'-', bắt đầu bằng chữ, không kết thúc bằng '-'.
_RE_GCP_PROJECT = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]")
_RE_TOOL = re.compile(r"[a-z0-9][a-z0-9_-]*")
_FEATURE_KEYS = ("features.paywall", "features.web_api", "features.apple_ads")

# Khối tuỳ chọn: thư mục nguồn + test chỉ đưa vào target khi công tắc bật (Features.generated.yml). Đường dẫn
# `src`/`tests` tính từ gốc repo; file sinh ra nằm ở AppHost/Config/ và XcodeGen tính đường dẫn trong file `include` theo CHÍNH file đó (đã thử với
# XcodeGen 2.44: `../CoreOptional` báo thiếu thư mục AppHost/CoreOptional) nên viết `../../` + đường dẫn.
# `flag` là cờ biên dịch Swift — CHỈ dùng trong AppHost/ (tools/common/lint_feature_flag.py canh). `products` là
# product của package `Firebase` đã ghim trong project.yml (không thêm package thứ hai).
OPTIONAL_BLOCKS = (
    {"feature": "features.web_api", "flag": "FEATURE_WEB_API",
     "src": "CoreOptional/WebAPI", "tests": "CoreOptionalTests/WebAPI", "products": ("FirebaseAppCheck",)},
)

# Privacy manifest sinh theo công tắc: `render` cắt từ mẫu PRIVACY_TEMPLATE (lớp gieo — app sửa mẫu, không sửa file
# sinh ra) các khối `<!-- feature:<công tắc>:begin -->` … `<!-- feature:<công tắc>:end -->` của công tắc TẮT, bỏ dòng
# dấu của công tắc BẬT, giữ nguyên mọi dòng khác (kể cả comment XML). Mẫu VẮNG ở gốc repo ⇒ manifest không do
# `render` quản (app tự giữ tay) — cổng 7 của verify_release_clean.sh vẫn đối chiếu bản build với công tắc.
PRIVACY_TEMPLATE = "AppHost/Config/PrivacyInfo.template.xcprivacy"
PRIVACY_MANIFEST = "AppHost/AppHost/PrivacyInfo.xcprivacy"
# Công tắc ↔ khoá Info.plist (project.yml đặt từ APP_FEATURE_*) ↔ kiểu dữ liệu chỉ khối đó khai. MỘT nguồn: cổng 7
# đọc bảng này để đối chiếu `.app`; test giữ nó khớp đúng các khối trong mẫu.
PRIVACY_BLOCKS = (
    {"switch": "paywall", "info_key": "FeaturePaywall",
     "types": ("NSPrivacyCollectedDataTypePurchaseHistory",)},
    {"switch": "web_api", "info_key": "FeatureWebAPI",
     "types": ("NSPrivacyCollectedDataTypeCustomerSupport", "NSPrivacyCollectedDataTypeEmailAddress")},
    {"switch": "apple_ads", "info_key": "FeatureAppleAds",
     "types": ("NSPrivacyCollectedDataTypeAdvertisingData",)},
)
# Entitlement associated-domains (Universal Link): có đúng khi `web.host_prod` khác rỗng, giá trị theo build setting
# `APP_WEB_HOST` (Debug/Internal = host dev, Release = host prod — project.yml). XcodeGen không đặt điều kiện được cho
# thuộc tính entitlement và GHI ĐÈ file `.entitlements` từ `entitlements.properties` mỗi lần `xcodegen generate` ⇒
# `render` sinh fragment ENTITLEMENTS_YML (project.yml include, XcodeGen gộp `properties` với khai báo của project.yml —
# app thêm khả năng khác ở đó) VÀ ghi chính file ENTITLEMENTS đúng byte XcodeGen sẽ ghi (khoá khác của file giữ nguyên) —
# `check`/pre-commit bắt lệch ngay cả khi chưa chạy xcodegen. Cổng 10 của verify_release_clean.sh soi bản đã ký.
ENTITLEMENTS = "AppHost/AppHost/AppHost.entitlements"
ENTITLEMENTS_YML = "AppHost/Config/Entitlements.generated.yml"
# Chỉ quản hai file trên khi `project.yml` của gốc include fragment (app sinh từ bản cũ chưa có dòng include: XcodeGen
# không đọc fragment và ghi đè entitlements về bản không có khoá ⇒ quản thì `check` đỏ mãi; repo giả của test: không có).
PROJECT_YML = "AppHost/project.yml"
# Đúng MỘT mục danh sách YAML (không phải chuỗi con — comment nhắc đường dẫn không được tính là đã include).
_RE_ENTITLEMENTS_INCLUDE = re.compile(r"^\s*-\s*Config/Entitlements\.generated\.yml\s*$", re.M)
ASSOCIATED_DOMAINS_KEY = "com.apple.developer.associated-domains"
APPLINKS_ENTRY = "applinks:$(APP_WEB_HOST)"
# Dòng chú thích `render` chèn ngay sau dòng DOCTYPE của manifest sinh ra (mẫu không mang nó — sửa mẫu là đúng chỗ).
PRIVACY_GENERATED_HEADER = (f"<!-- SINH bởi `python3 tools/common/appconfig.py render` từ {PRIVACY_TEMPLATE} theo [features] "
                            "của app.config.toml — KHÔNG sửa tay: sửa mẫu rồi render. -->")
_RE_FEATURE_MARK = re.compile(r"^[ \t]*<!--[ \t]*feature:([a-z_]+):(begin|end)[ \t]*-->[ \t]*$")
_RE_FEATURE_TOKEN = re.compile(r"feature:[A-Za-z0-9_-]*:(?:begin|end)\b")
# Gốc repo chứa CHÍNH file này (tools/common/appconfig.py) — nơi đọc mẫu khi không có gốc nào được truyền.
_TOOL_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(Exception):
    """Lỗi cấu hình; thông báo luôn nêu tên khoá."""


def repo_root(start: Path | None = None) -> Path:
    """Gốc working tree chứa `start` (đúng cả với git worktree)."""
    start = Path(start) if start is not None else Path.cwd()
    try:
        r = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
    except OSError as e:
        raise ConfigError(f"không chạy được git: {e}")
    if r.returncode != 0:
        raise ConfigError(f"{start} không nằm trong repo git")
    return Path(r.stdout.strip())


def get(cfg: dict, dotted: str):
    """Lấy giá trị theo khoá chấm, vd `bundle.store`."""
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise ConfigError(f"khoá không tồn tại: {dotted}")
        cur = cur[part]
    return cur


def _check_display(cfg: dict, key: str) -> str:
    v = get(cfg, key)
    if not isinstance(v, str) or not v.strip():
        raise ConfigError(f"{key} phải là chuỗi không rỗng")
    if v != v.strip():
        # xcconfig cắt khoảng trắng đầu/cuối ⇒ tên trên máy khác tên trong config.
        raise ConfigError(f"{key} không được có khoảng trắng đầu/cuối: {v!r}")
    if "\n" in v or "\r" in v or "//" in v or "$(" in v or "${" in v:
        # '//' mở comment xcconfig; '$(' / '${' là tham chiếu biến build setting.
        raise ConfigError(f"{key} không được chứa xuống dòng, '//', '$(' hay '${{'")
    return v


def _check_match(cfg: dict, key: str, rx: re.Pattern, hint: str) -> str:
    v = get(cfg, key)
    if not isinstance(v, str) or not rx.fullmatch(v):
        raise ConfigError(f"{key} sai dạng ({hint}): {v!r}")
    return v


def _check_schema(cfg: dict) -> None:
    for section, body in cfg.items():
        if section not in SCHEMA:
            raise ConfigError(f"section lạ: [{section}] (cho phép: {', '.join(SCHEMA)})")
        if not isinstance(body, dict):
            raise ConfigError(f"{section} phải là section [{section}], không phải giá trị")
        for key in body:
            if key not in SCHEMA[section]:
                raise ConfigError(f"khoá lạ: {section}.{key} (section [{section}] chỉ có: "
                                  f"{', '.join(SCHEMA[section])})")


def _check_web(cfg: dict) -> None:
    for key in _WEB_KEYS:
        try:
            v = get(cfg, key)
        except ConfigError:
            continue  # web.* tuỳ chọn
        if not isinstance(v, str) or (v != "" and not _RE_HOST.fullmatch(v)):
            raise ConfigError(f"{key} phải rỗng hoặc là hostname trần (chữ, số, '.', '-'; "
                              f"không scheme, không '/', không khoảng trắng): {v!r}")


def web_external_site(cfg: dict) -> bool:
    """`[web] external_site` — site của app ở ngoài repo (không dùng `web/site/public/`); vắng ⇒ false. True ⇒ cổng 16 của
    verify_release_clean.sh in SKIP thấy rõ thay vì đòi `check_site.py --release`; false mà có host nhưng thiếu site ⇒ FAIL."""
    v = opt(cfg, "web.external_site", False)
    if not isinstance(v, bool):
        raise ConfigError(f"web.external_site phải là true hoặc false: {v!r}")
    return v


def web_app_paths(cfg: dict) -> list[str]:
    """`[web] app_paths` — đường dẫn mở app (AASA `components`); vắng ⇒ []. Mỗi phần tử bắt đầu "/", không chứa
    "?", "#" hay khoảng trắng; sai ⇒ ConfigError nêu tên khoá."""
    v = opt(cfg, "web.app_paths", [])
    if not isinstance(v, list):
        raise ConfigError(f"web.app_paths phải là danh sách chuỗi bắt đầu bằng '/': {v!r}")
    for p in v:
        if not isinstance(p, str) or not p.startswith("/") or _RE_APP_PATH_BAD.search(p):
            raise ConfigError(f"web.app_paths có phần tử sai (phải bắt đầu bằng '/', không chứa '?', '#', "
                              f"khoảng trắng): {p!r}")
    return list(v)


def _check_cloud(cfg: dict) -> None:
    for key, rx, hint in (("cloudflare.d1_prod", _RE_D1_ID, "chữ, số, '-'"),
                          ("cloudflare.d1_dev", _RE_D1_ID, "chữ, số, '-'"),
                          ("firebase.app_check_prod", _RE_APP_CHECK, "<projectId>:<projectNumber>"),
                          ("firebase.app_check_dev", _RE_APP_CHECK, "<projectId>:<projectNumber>")):
        v = opt(cfg, key, "")
        if not isinstance(v, str) or (v != "" and not rx.fullmatch(v)):
            raise ConfigError(f"{key} phải rỗng hoặc đúng dạng ({hint}): {v!r}")


def opt(cfg: dict, key: str, default):
    """Giá trị khoá tuỳ chọn; vắng ⇒ `default`. API công khai (tools/release/check_storekit.py dùng)."""
    try:
        return get(cfg, key)
    except ConfigError:
        return default


def feature(cfg: dict, key: str) -> bool:
    """Cờ tính năng (vắng ⇒ tắt); không phải bool ⇒ lỗi nêu tên khoá. API công khai."""
    v = opt(cfg, key, False)
    if not isinstance(v, bool):
        raise ConfigError(f"{key} phải là true hoặc false: {v!r}")
    return v


def _check_features(cfg: dict) -> None:
    for key in _FEATURE_KEYS:
        feature(cfg, key)
    store_id = opt(cfg, "apple.app_store_id", "")
    if not isinstance(store_id, str) or not _RE_APP_STORE_ID.fullmatch(store_id):
        raise ConfigError(f"apple.app_store_id phải rỗng hoặc chỉ chữ số: {store_id!r}")
    email = opt(cfg, "support.email", "")
    if not isinstance(email, str) or (email != "" and not _RE_EMAIL.fullmatch(email)):
        raise ConfigError(f"support.email phải rỗng hoặc dạng x@y.z: {email!r}")
    ids = opt(cfg, "purchases.product_ids", [])
    if not isinstance(ids, list) or not all(isinstance(i, str) and _RE_PRODUCT_ID.fullmatch(i) for i in ids):
        raise ConfigError(f"purchases.product_ids phải là danh sách chuỗi không khoảng trắng "
                          f"(chữ, số, '.', '_', '-'): {ids!r}")
    if feature(cfg, "features.paywall") and not ids:
        raise ConfigError("purchases.product_ids không được rỗng khi features.paywall = true")
    # Cả hai công tắc cần host web: web_api gọi API ở đó; paywall bắt buộc link Điều khoản/Quyền riêng tư
    # (https://<host>/terms|privacy/ — Guideline 3.1.2). Debug/Internal dùng host_dev, Release dùng host_prod ⇒ cần cả
    # hai. Bắt ở đây (mọi lần render/check/run_tests) thay vì để tới cổng 13 lúc archive.
    for cong_tac in ("features.web_api", "features.paywall"):
        if feature(cfg, cong_tac):
            for key in _WEB_KEYS:
                if opt(cfg, key, "") == "":
                    raise ConfigError(f"{key} không được rỗng khi {cong_tac} = true")


def store_locales(cfg: dict) -> list[str]:
    """`[store] locales` — danh sách locale App Store Connect của listing; vắng ⇒ ["en-US"].

    Khác `[i18n] languages` (ngôn ngữ UI của app). Dạng `ll`/`ll-RR`/`ll-Ssss`; rỗng, trùng (không phân biệt
    hoa/thường) hoặc sai dạng ⇒ ConfigError nêu tên khoá."""
    v = opt(cfg, "store.locales", list(DEFAULT_STORE_LOCALES))
    if not isinstance(v, list) or not v:
        raise ConfigError(f"store.locales phải là danh sách không rỗng các locale App Store Connect: {v!r}")
    seen: set[str] = set()
    for loc in v:
        if not isinstance(loc, str):
            raise ConfigError(f"store.locales có phần tử không phải chuỗi: {loc!r}")
        if loc.lower() in seen:  # trùng xét trước dạng: "en-US" và "EN-us" báo trùng, không báo sai dạng
            raise ConfigError(f"store.locales có locale trùng: {loc!r}")
        seen.add(loc.lower())
        if not _RE_LOCALE.fullmatch(loc):
            raise ConfigError(f"store.locales có locale sai dạng (ll, ll-RR hoặc ll-Ssss, vd en-US, vi, zh-Hans): {loc!r}")
    return list(v)


def primary_locale(cfg: dict) -> str:
    """Locale chính của listing = phần tử đầu của `store_locales`."""
    return store_locales(cfg)[0]


def _check_analytics(cfg: dict) -> None:
    ga4 = opt(cfg, "analytics.ga4_property", "")
    if not isinstance(ga4, str) or not _RE_GA4_PROPERTY.fullmatch(ga4):
        raise ConfigError(f"analytics.ga4_property phải rỗng hoặc chỉ chữ số: {ga4!r}")
    bq = opt(cfg, "analytics.bq_project", "")
    if not isinstance(bq, str) or (bq != "" and not _RE_GCP_PROJECT.fullmatch(bq)):
        raise ConfigError(f"analytics.bq_project phải rỗng hoặc là id project GCP (chữ thường, số, '-'; "
                          f"6–30 ký tự): {bq!r}")


def state_dir(cfg: dict, tool: str) -> Path:
    """Thư mục trạng thái của `tool` cho app này — CHỈ tính đường dẫn, không tạo thư mục.

    `$IOS_APP_FACTORY_STATE` đặt ⇒ `<đó>/<slug>/<tool>`; không ⇒
    `~/Library/Application Support/ios-app-factory/<slug>/<tool>`. Slug nằm trong đường dẫn để nhiều app
    trên một máy không đè trạng thái của nhau."""
    if not isinstance(tool, str) or not _RE_TOOL.fullmatch(tool):
        raise ConfigError(f"tên tool sai dạng (a-z, 0-9, '-', '_'): {tool!r}")
    env = os.environ.get("IOS_APP_FACTORY_STATE")
    base = Path(env) if env else Path.home() / "Library" / "Application Support" / "ios-app-factory"
    return base / get(cfg, "app.slug") / tool


def config_dir(cfg: dict) -> Path:
    """Thư mục cấu hình/khoá của app này — CHỈ tính đường dẫn, không tạo thư mục.

    `$IOS_APP_FACTORY_CONFIG` đặt ⇒ `<đó>/<slug>`; không ⇒ `~/.config/ios-app-factory/<slug>`."""
    env = os.environ.get("IOS_APP_FACTORY_CONFIG")
    base = Path(env) if env else Path.home() / ".config" / "ios-app-factory"
    return base / get(cfg, "app.slug")


def shared_bin_dir() -> Path:
    """Thư mục binary dùng chung cả máy — CHỈ tính đường dẫn, không tạo thư mục.

    `$IOS_APP_FACTORY_BIN` đặt ⇒ dùng nguyên văn; không ⇒ `~/.local/share/ios-app-factory`."""
    env = os.environ.get("IOS_APP_FACTORY_BIN")
    return Path(env) if env else Path.home() / ".local" / "share" / "ios-app-factory"


def seed_variables(cfg: dict, *, template_tag: str, date: str) -> dict[str, str]:
    """Bộ biến thay vào file gieo (`$display_name`, `$host_prod`, …) — định nghĩa MỘT lần ở đây.

    `new_app.py` dùng nó với cấu hình ứng viên của app mới; lệnh nhận file gieo mới ở app dùng lại với cấu hình của app.
    `host_prod` rỗng khi `web.host_prod` vắng/rỗng (app không có web); `support_email`, `app_store_id` rỗng khi vắng."""
    host = opt(cfg, "web.host_prod", "")
    return {
        "display_name": get(cfg, "app.display_name"),
        "slug": get(cfg, "app.slug"),
        "bundle_id": get(cfg, "bundle.store"),
        "host_prod": host if isinstance(host, str) else "",
        "support_email": opt(cfg, "support.email", "") or "",
        "app_store_id": opt(cfg, "apple.app_store_id", "") or "",
        "marketing_version": get(cfg, "version.marketing"),
        "primary_locale": primary_locale(cfg),
        "template_tag": template_tag,
        "date": date,
    }


def _validate(cfg: dict) -> None:
    _check_schema(cfg)
    for key in _REQUIRED:
        try:
            get(cfg, key)
        except ConfigError:
            raise ConfigError(f"thiếu khoá bắt buộc: {key}")
    _check_match(cfg, "app.slug", _RE_SLUG, "a-z, 0-9, '-', bắt đầu bằng chữ, 2-31 ký tự")
    store = _check_match(cfg, "bundle.store", _RE_BUNDLE, "chỉ chữ, số, '.', '-'")
    internal = _check_match(cfg, "bundle.internal", _RE_BUNDLE, "chỉ chữ, số, '.', '-'")
    if store == internal:
        raise ConfigError("bundle.internal phải khác bundle.store")
    _check_match(cfg, "apple.team_id", _RE_TEAM, "10 ký tự A-Z0-9")
    _check_match(cfg, "version.marketing", _RE_MARKETING, "dạng X.Y.Z")
    _check_match(cfg, "version.build", _RE_BUILD, "chỉ chữ số")
    name = _check_display(cfg, "app.display_name")
    name_int = _check_display(cfg, "app.display_name_internal")
    if name == name_int:
        raise ConfigError("app.display_name_internal phải khác app.display_name")
    _check_web(cfg)
    _check_features(cfg)
    # Có host prod ⇒ có entitlement `applinks:$(APP_WEB_HOST)`, mà Debug/Internal đặt APP_WEB_HOST = host dev: host dev
    # rỗng ⇒ mục `applinks:` trống ở bản dev. Kiểm SAU công tắc để lỗi của paywall/web_api (rõ lý do hơn) báo trước.
    if opt(cfg, "web.host_prod", "") != "" and opt(cfg, "web.host_dev", "") == "":
        raise ConfigError("web.host_dev không được rỗng khi web.host_prod có giá trị (Universal Link của bản "
                          "Debug/Internal: applinks:<host dev>)")
    web_app_paths(cfg)
    web_external_site(cfg)
    _check_cloud(cfg)
    store_locales(cfg)
    _check_analytics(cfg)


def load(root: Path | None = None) -> dict:
    """Đọc + kiểm app.config.toml ở gốc repo."""
    root = Path(root) if root is not None else repo_root()
    path = root / CONFIG_FILE
    try:
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"không thấy {path}")
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{CONFIG_FILE} không phải TOML hợp lệ: {e}")
    _validate(cfg)
    return cfg


def render_xcconfig(cfg: dict) -> str:
    rows = (
        ("APP_SLUG", "app.slug"),
        ("APP_DISPLAY_NAME_STORE", "app.display_name"),
        ("APP_DISPLAY_NAME_INTERNAL", "app.display_name_internal"),
        ("APP_BUNDLE_ID_STORE", "bundle.store"),
        ("APP_BUNDLE_ID_INTERNAL", "bundle.internal"),
        ("APP_TEAM_ID", "apple.team_id"),
        ("APP_MARKETING_VERSION", "version.marketing"),
        ("APP_BUILD_NUMBER", "version.build"),
        ("APP_WEB_HOST_PROD", "web.host_prod"),
        ("APP_WEB_HOST_DEV", "web.host_dev"),
        ("APP_STORE_ID", "apple.app_store_id"),
        ("APP_SUPPORT_EMAIL", "support.email"),
    )
    out = [XCCONFIG_HEADER]
    values = [(var, opt(cfg, key, "")) for var, key in rows]  # khoá tuỳ chọn vắng ⇒ rỗng
    values += [
        ("APP_FEATURE_PAYWALL", "YES" if feature(cfg, "features.paywall") else "NO"),
        ("APP_FEATURE_APPLE_ADS", "YES" if feature(cfg, "features.apple_ads") else "NO"),
        ("APP_FEATURE_WEB_API", "YES" if feature(cfg, "features.web_api") else "NO"),
        ("APP_PRODUCT_IDS", " ".join(opt(cfg, "purchases.product_ids", []))),
    ]
    for var, val in values:
        out.append(f"{var} = {val}\n" if val != "" else f"{var} =\n")
    return "".join(out)


def render_features_yml(cfg: dict) -> str:
    """Spec XcodeGen cho các khối tuỳ chọn đang bật (`OPTIONAL_BLOCKS`), hoặc `{}` khi không khối nào bật.

    project.yml `include` file này; XcodeGen nối mảng `sources`/`dependencies` vào target và gộp `settings`.
    Cờ biên dịch đi vào CẢ AppHost lẫn AppHostTests, ở dạng `$(inherited) <CỜ>` để giữ DEBUG/INTERNAL của project."""
    blocks = [b for b in OPTIONAL_BLOCKS if feature(cfg, b["feature"])]
    if not blocks:
        return FEATURES_YML_HEADER + "{}\n"
    conditions = '"$(inherited) ' + " ".join(b["flag"] for b in blocks) + '"'
    settings = ["    settings:", "      base:", f"        SWIFT_ACTIVE_COMPILATION_CONDITIONS: {conditions}"]
    out = ["targets:", f"  {APP_TARGET}:", "    sources:"]
    out += [f"      - path: ../../{b['src']}" for b in blocks]
    products = [p for b in blocks for p in b["products"]]
    if products:
        out.append("    dependencies:")
        for p in dict.fromkeys(products):
            out += ["      - package: Firebase", f"        product: {p}"]
    out += settings
    out += [f"  {TEST_TARGET}:", "    sources:"]
    out += [f"      - path: ../../{b['tests']}" for b in blocks]
    out += settings
    return FEATURES_YML_HEADER + "\n".join(out) + "\n"


def disabled_block_roots(cfg: dict) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(thư mục nguồn, thư mục test) của các khối tuỳ chọn đang TẮT — kết thúc bằng `/`.

    Tool đi qua nguồn/test (run_tests.py) dùng để bỏ file không nằm trong build: chọn test của khối tắt thì
    xcodebuild báo "không chạy" (xanh giả), còn file nguồn của nó không hề được biên dịch."""
    off = [b for b in OPTIONAL_BLOCKS if not feature(cfg, b["feature"])]
    return tuple(b["src"] + "/" for b in off), tuple(b["tests"] + "/" for b in off)


def cut_feature_blocks(text: str, on: dict[str, bool], source: str = PRIVACY_TEMPLATE) -> str:
    """Cắt khối `<!-- feature:<công tắc>:begin -->` … `:end -->` theo `on` (công tắc → bật?). `source` = tên file nêu
    trong thông báo lỗi (mặc định mẫu privacy manifest; trang web gieo truyền đường dẫn của trang).

    Công tắc bật ⇒ chỉ bỏ hai dòng dấu; tắt ⇒ bỏ cả khối. Dấu chiếm trọn một dòng; dấu dính chữ, công tắc lạ, lồng
    nhau, không cặp ⇒ ConfigError nêu số dòng (1-based). Các dòng khác giữ nguyên từng byte (kể cả dòng trống cuối)."""
    kept: list[str] = []
    open_sw, opened = None, 0
    for no, line in enumerate(text.split("\n"), 1):
        m = _RE_FEATURE_MARK.match(line)
        if m is None:
            if _RE_FEATURE_TOKEN.search(line) and line.endswith("\r"):
                raise ConfigError(f"{source} dòng {no}: mẫu dùng xuống dòng CRLF (Windows) — lưu lại bằng LF "
                                  "(dấu feature chỉ nhận dòng kết thúc bằng LF)")
            if _RE_FEATURE_TOKEN.search(line):
                raise ConfigError(f"{source} dòng {no}: dấu feature phải chiếm trọn một dòng "
                                  f"`<!-- feature:<công tắc>:begin|end -->`: {line.strip()}")
            if open_sw is None or on[open_sw]:
                kept.append(line)
            continue
        sw, kind = m.groups()
        if sw not in on:
            raise ConfigError(f"{source} dòng {no}: công tắc lạ '{sw}' (có: {', '.join(on)})")
        if kind == "begin":
            if open_sw is not None:
                raise ConfigError(f"{source} dòng {no}: khối '{sw}' lồng trong khối '{open_sw}' "
                                  f"mở ở dòng {opened}")
            open_sw, opened = sw, no
        else:
            if open_sw != sw:
                raise ConfigError(f"{source} dòng {no}: `feature:{sw}:end` không cặp")
            open_sw = None
    if open_sw is not None:
        raise ConfigError(f"{source} dòng {opened}: `feature:{open_sw}:begin` không có dấu đóng")
    return "\n".join(kept)


# Trang web gieo (`web/site/public/**`, lớp seed): `new_app` (và lệnh nhận file gieo mới) cắt khối
# `<!-- feature:<công tắc>:begin|end -->` theo công tắc của app — cùng cú pháp với mẫu privacy manifest. Ngoài ba công
# tắc `[features]` còn `app_store` = app đã có `apple.app_store_id` (link App Store trên landing) và `purchase_records` =
# `paywall` VÀ `web_api` (API lưu App Store Server Notifications ⇒ trang privacy phải nói server giữ gì, bao lâu).
WEB_SEED_PREFIX = "web/site/public/"
WEB_SEED_SUFFIXES = (".html", ".txt", ".xml")


def web_seed_switches(cfg: dict) -> dict[str, bool]:
    """Công tắc cắt khối của trang web gieo."""
    on = {b["switch"]: feature(cfg, "features." + b["switch"]) for b in PRIVACY_BLOCKS}
    on["app_store"] = opt(cfg, "apple.app_store_id", "") not in ("", None)
    on["purchase_records"] = on["paywall"] and on["web_api"]
    return on


def render_web_seed(cfg: dict, rel: str, text: str) -> str:
    """Nội dung file gieo `rel` (đã thay biến) sau khi cắt khối feature theo cấu hình; file ngoài WEB_SEED_PREFIX hoặc
    không phải trang text (`.html`/`.txt`/`.xml`) ⇒ trả nguyên. Dấu sai ⇒ ConfigError nêu `rel` và số dòng."""
    if not rel.startswith(WEB_SEED_PREFIX) or not rel.endswith(WEB_SEED_SUFFIXES):
        return text
    return cut_feature_blocks(text, web_seed_switches(cfg), source=rel)


def render_privacy_manifest(cfg: dict, template: bytes | str | None = None) -> bytes:
    """Privacy manifest của app theo công tắc `[features]`, cắt từ mẫu PRIVACY_TEMPLATE.

    `template` vắng ⇒ đọc mẫu ở repo chứa chính file này. Dòng PRIVACY_GENERATED_HEADER được chèn ngay sau dòng
    `<!DOCTYPE` (không có ⇒ sau dòng `<?xml`, không có nữa ⇒ đầu file). Kết quả phải là plist hợp lệ (không thì ConfigError)."""
    if template is None:
        template = (_TOOL_ROOT / PRIVACY_TEMPLATE).read_bytes()
    text = template.decode("utf-8") if isinstance(template, bytes) else template
    on = {b["switch"]: feature(cfg, "features." + b["switch"]) for b in PRIVACY_BLOCKS}
    lines = cut_feature_blocks(text, on).split("\n")
    at = next((i + 1 for i, line in enumerate(lines) if line.lstrip().startswith("<!DOCTYPE")), None)
    if at is None:  # không DOCTYPE: sau dòng khai báo XML (comment không được đứng trước nó), không có thì đầu file
        at = 1 if lines and lines[0].startswith("<?xml") else 0
    lines.insert(at, PRIVACY_GENERATED_HEADER)
    out = "\n".join(lines).encode("utf-8")
    try:
        plistlib.loads(out)
    except Exception as e:  # plistlib ném nhiều kiểu lỗi (ExpatError, ValueError, InvalidFileException)
        raise ConfigError(f"{PRIVACY_TEMPLATE} sau khi cắt không còn là plist hợp lệ: {e}")
    return out


def has_app_links(cfg: dict) -> bool:
    """App có Universal Link ⇔ `web.host_prod` khác rỗng."""
    return opt(cfg, "web.host_prod", "") != ""


def render_entitlements_yml(cfg: dict) -> str:
    """Fragment XcodeGen: `entitlements.properties` của target app mang associated-domains khi có host; `{}` khi không."""
    header = FEATURES_YML_HEADER.splitlines(keepends=True)[0] + (
        "# AppHost/project.yml include file này; `entitlements.properties` ở đây gộp với khai báo của project.yml.\n")
    if not has_app_links(cfg):
        return header + "{}\n"
    return header + "\n".join([
        "targets:", f"  {APP_TARGET}:", "    entitlements:", "      properties:",
        f'        {ASSOCIATED_DOMAINS_KEY}: ["{APPLINKS_ENTRY}"]']) + "\n"


def includes_entitlements_fragment(root: Path) -> bool:
    """`AppHost/project.yml` ở `root` có mục `include` trỏ ENTITLEMENTS_YML (khớp nguyên dòng danh sách YAML)."""
    proj = Path(root) / PROJECT_YML
    return proj.is_file() and bool(_RE_ENTITLEMENTS_INCLUDE.search(proj.read_text(encoding="utf-8")))


def render_entitlements(cfg: dict, existing: bytes | None = None) -> str:
    """Entitlements của app: `existing` (file hiện có; vắng ⇒ dict rỗng) với khoá ASSOCIATED_DOMAINS_KEY đặt thành
    [APPLINKS_ENTRY] khi `web.host_prod` khác rỗng, gỡ khi rỗng. Khoá khác giữ nguyên. `existing` không phải plist
    dict ⇒ ConfigError."""
    ents: dict = {}
    if existing:
        try:
            ents = plistlib.loads(existing)
        except Exception as e:  # plistlib ném nhiều kiểu lỗi
            raise ConfigError(f"{ENTITLEMENTS} không phải plist hợp lệ: {e}")
        if not isinstance(ents, dict):
            raise ConfigError(f"{ENTITLEMENTS} phải là plist dạng dict")
    if has_app_links(cfg):
        ents[ASSOCIATED_DOMAINS_KEY] = [APPLINKS_ENTRY]
    else:
        ents.pop(ASSOCIATED_DOMAINS_KEY, None)
    return plistlib.dumps(ents).decode("utf-8")


WRANGLER_API = "web/api/wrangler.jsonc"
WRANGLER_SITE = "web/site/wrangler.jsonc"
WRANGLER_HEADER = ("// SINH bởi `python3 tools/common/appconfig.py render` từ app.config.toml — không sửa tay "
                   "(sửa app.config.toml rồi render).\n")
WRANGLER_COMPAT_DATE = "2026-08-22"
D1_TODO = "TODO-d1-id"
API_CRONS = ["17 3 * * *"]


# Host giữ chỗ/dành riêng (RFC 2606/6761): không bao giờ là site/e-mail thật của app — cổng ra bản (check_site --release)
# từ chối. Cùng luật với lint metadata Store.
RESERVED_DOMAINS = ("example.com", "example.net", "example.org")
RESERVED_TLDS = ("example", "test", "invalid", "localhost")


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


def has_web(cfg: dict) -> bool:
    """App có web ⇔ `web.host_prod` khác rỗng (không có ⇒ không sinh `web/*/wrangler.jsonc`)."""
    return opt(cfg, "web.host_prod", "") != ""


def web_warnings(cfg: dict) -> list[str]:
    """Việc tay còn thiếu của web (một dòng mỗi việc) — `check` in ra stderr, không làm rc đỏ."""
    if not has_web(cfg):
        return []
    out = []
    # web_api tắt ⇒ app không có API (deploy chỉ site) ⇒ D1 / App Check không cần (Ruling 11).
    if feature(cfg, "features.web_api"):
        missing = [k for k in ("cloudflare.d1_prod", "cloudflare.d1_dev") if opt(cfg, k, "") == ""]
        if missing:
            out.append(f"{' + '.join(missing)} còn rỗng — wrangler.jsonc dùng \"{D1_TODO}\"; dán database_id sau "
                       "`wrangler d1 create` (deploy từ chối tới lúc đó)")
        missing = [k for k in ("firebase.app_check_prod", "firebase.app_check_dev") if opt(cfg, k, "") == ""]
        if missing:
            out.append(f"{' + '.join(missing)} còn rỗng khi features.web_api = true — điền "
                       "\"<projectId>:<projectNumber>\" (App Check của API; deploy từ chối tới lúc đó)")
    return out


def _wrangler_json(body: dict) -> str:
    return WRANGLER_HEADER + json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def _api_env(cfg: dict, *, dev: bool) -> dict:
    slug = get(cfg, "app.slug")
    host = get(cfg, "web.host_dev" if dev else "web.host_prod")
    d1 = opt(cfg, "cloudflare.d1_dev" if dev else "cloudflare.d1_prod", "") or D1_TODO
    body = {
        "name": f"{slug}-api" + ("-dev" if dev else ""),
        "d1_databases": [{"binding": "DB", "database_name": slug + ("-dev" if dev else ""),
                          "database_id": d1, "migrations_dir": "migrations"}],
        "triggers": {"crons": list(API_CRONS)},
        "vars": {
            # App Store Server Notifications LUÔN mang bundle Store (bản ghi App Store Connect) — kể cả Sandbox
            # (TestFlight, App Review, sandbox tester, "Send Test Notification") đi về API dev. Bản .internal không có
            # bản ghi trên App Store Connect ⇒ CẢ HAI môi trường lọc theo bundle Store (chỉ AASA dùng bundle .internal ở dev).
            "ASSN_BUNDLE_ID": get(cfg, "bundle.store"),
            "ASSN_ENVIRONMENTS": "Sandbox" if dev else "Production",
            "APP_CHECK_PROJECTS": opt(cfg, "firebase.app_check_dev" if dev else "firebase.app_check_prod", ""),
            "APP_CHECK_REQUIRED": "0" if dev else "1",
            "PUBLIC_ORIGIN": f"https://{host}",
        },
    }
    return body


def render_wrangler_api(cfg: dict) -> str:
    """`web/api/wrangler.jsonc`: Worker API (Hono + D1) của app; `env.dev` lặp đủ binding (wrangler không kế thừa)."""
    body = {
        "name": None, "main": "src/index.ts", "compatibility_date": WRANGLER_COMPAT_DATE,
        "compatibility_flags": ["nodejs_compat"], "workers_dev": False, "preview_urls": False,
    }
    prod = _api_env(cfg, dev=False)
    body.update(prod)
    body["env"] = {"dev": _api_env(cfg, dev=True)}
    return _wrangler_json(body)


def _site_env(cfg: dict, *, dev: bool) -> dict:
    slug = get(cfg, "app.slug")
    ids = f"{get(cfg, 'apple.team_id')}.{get(cfg, 'bundle.internal' if dev else 'bundle.store')}"
    body: dict = {"name": f"{slug}-site" + ("-dev" if dev else "")}
    if dev:
        body["routes"] = [{"pattern": get(cfg, "web.host_dev"), "custom_domain": True}]
    # Prod: Worker chỉ chạy trước asset ở hai tiền tố nó phục vụ. Dev: chạy trước MỌI đường dẫn — asset tĩnh khớp đường
    # dẫn được phục vụ THẲNG, không qua Worker, nên chỉ như vậy `X-Robots-Tag: noindex` (NOINDEX=1) mới tới được trang HTML.
    first: list[str] | bool = True if dev else ["/.well-known/*", "/api/*"]
    # `not_found_handling: "404-page"`: đường dẫn không có asset ⇒ phục vụ public/404.html (mã 404) thay vì 404 trống.
    body["assets"] = {"directory": "public", "binding": "ASSETS", "run_worker_first": first,
                      "not_found_handling": "404-page"}
    body["vars"] = {"APP_IDS": ids, "APP_PATHS": json.dumps(web_app_paths(cfg)), "NOINDEX": "1" if dev else "0"}
    if feature(cfg, "features.web_api"):
        body["services"] = [{"binding": "API", "service": f"{slug}-api" + ("-dev" if dev else "")}]
    return body


def render_wrangler_site(cfg: dict) -> str:
    """`web/site/wrangler.jsonc`: site tĩnh + Worker nhỏ (AASA, noindex dev, chuyển `/api/*` khi có API).
    `services` chỉ khi `features.web_api`; prod không có `routes` (custom domain gắn tay)."""
    # workers_dev/preview_urls tắt như API: không bản sao `<slug>-site[-dev].<account>.workers.dev` (bản đó cũng chuyển
    # `/api/*`, kể cả admin, và feedback dev mở) — chỉ host của app (prod: custom domain gắn tay; dev: `routes`).
    body = {"main": "src/worker.ts", "compatibility_date": WRANGLER_COMPAT_DATE, "workers_dev": False,
            "preview_urls": False}
    body = {"name": None, **body}
    body.update(_site_env(cfg, dev=False))
    body["env"] = {"dev": _site_env(cfg, dev=True)}
    return _wrangler_json(body)


def _generated(cfg: dict, root: Path | None = None) -> tuple[tuple[str, str], ...]:
    """(đường dẫn tương đối, nội dung) của mọi file `render` sinh ra ở gốc `root` (vắng ⇒ repo chứa file này).

    Privacy manifest chỉ có mặt khi gốc đó có mẫu PRIVACY_TEMPLATE. Fragment + file entitlements chỉ khi PROJECT_YML của
    gốc include fragment; entitlements dựng từ file đang có (chỉ khoá associated-domains do `render` quản)."""
    base = Path(root if root is not None else _TOOL_ROOT)
    out = [(XCCONFIG, render_xcconfig(cfg)), (FEATURES_YML, render_features_yml(cfg))]
    tpl = base / PRIVACY_TEMPLATE
    if tpl.is_file():
        out.append((PRIVACY_MANIFEST, render_privacy_manifest(cfg, tpl.read_bytes()).decode("utf-8")))
    if includes_entitlements_fragment(base):
        out.append((ENTITLEMENTS_YML, render_entitlements_yml(cfg)))
        ents = base / ENTITLEMENTS
        out.append((ENTITLEMENTS, render_entitlements(cfg, ents.read_bytes() if ents.is_file() else None)))
    if has_web(cfg):
        out.append((WRANGLER_API, render_wrangler_api(cfg)))
        out.append((WRANGLER_SITE, render_wrangler_site(cfg)))
    return tuple(out)


def generated_files(cfg: dict, root: Path | None = None) -> tuple[tuple[str, str], ...]:
    """API công khai của `_generated`: (đường dẫn, nội dung) mọi file `render` sẽ ghi ở `root` theo `cfg` —
    `sync_core.py sync --adopt-new-seed` dùng để tạo file sinh MỚI (vd `web/*/wrangler.jsonc`) cho app."""
    return _generated(cfg, root)


def _write_if_changed(path: Path, new: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == new:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, encoding="utf-8")
    return True


def write_xcconfig(root: Path, cfg: dict) -> bool:
    """Ghi xcconfig; True nếu nội dung file đổi."""
    return _write_if_changed(Path(root) / XCCONFIG, render_xcconfig(cfg))


def is_xcconfig_fresh(root: Path, cfg: dict) -> bool:
    path = Path(root) / XCCONFIG
    return path.exists() and path.read_text(encoding="utf-8") == render_xcconfig(cfg)


def stale_generated(root: Path, cfg: dict) -> list[str]:
    """Các file sinh ra (đường dẫn tương đối) đang thiếu hoặc lệch so với config."""
    out = []
    for rel, new in _generated(cfg, root):
        path = Path(root) / rel
        if not (path.exists() and path.read_text(encoding="utf-8") == new):
            out.append(rel)
    return out


def write_generated(root: Path, cfg: dict) -> bool:
    """Ghi mọi file sinh ra (xcconfig, Features.generated.yml, privacy manifest nếu có mẫu, entitlements); True nếu có
    file đổi."""
    changed = [_write_if_changed(Path(root) / rel, new) for rel, new in _generated(cfg, root)]
    return any(changed)


def is_generated_fresh(root: Path, cfg: dict) -> bool:
    return not stale_generated(root, cfg)


# Dấu nhận biết plist fixture — cổng release (verify_release_clean.sh) đọc hai hằng số này và từ chối plist
# fixture trừ khi ALLOW_FIXTURE_PLIST=1 (chỉ selfcheck đặt). Plist thật do Firebase console sinh không có khoá này.
FIXTURE_MARK_KEY = "FACTORY_FIXTURE_PLIST"
FIXTURE_API_KEY = "FIXTURE-NOT-A-REAL-KEY"


def fixture_plist(cfg: dict, config_name: str) -> bytes:
    """GoogleService-Info giả cho build không có file thật; Release ⇒ id Store."""
    bundle = get(cfg, "bundle.store" if config_name == "Release" else "bundle.internal")
    return plistlib.dumps({
        FIXTURE_MARK_KEY: True,
        "BUNDLE_ID": bundle,
        "PROJECT_ID": "fixture-" + get(cfg, "app.slug"),
        "API_KEY": FIXTURE_API_KEY,
        "GOOGLE_APP_ID": "1:123456789:ios:abcdef0123456789",
        "GCM_SENDER_ID": "123456789",
    })


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="appconfig")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get")
    g.add_argument("key")
    sub.add_parser("render")
    sub.add_parser("check")
    sd = sub.add_parser("state-dir")
    sd.add_argument("tool")
    sub.add_parser("config-dir")
    f = sub.add_parser("fixture-plist")
    f.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    try:
        root = repo_root()
        cfg = load(root)
        if args.cmd == "get":
            if args.key == "store.locales":
                print(",".join(store_locales(cfg)))
            else:
                print(get(cfg, args.key))
        elif args.cmd == "state-dir":
            print(state_dir(cfg, args.tool))
        elif args.cmd == "config-dir":
            print(config_dir(cfg))
        elif args.cmd == "render":
            for rel, new in _generated(cfg, root):
                changed = _write_if_changed(root / rel, new)
                print(("Đã ghi " if changed else "Không đổi: ") + rel)
        elif args.cmd == "check":
            stale = stale_generated(root, cfg)
            if stale:
                print(f"FAIL: {', '.join(stale)} đã cũ — chạy: python3 tools/common/appconfig.py render",
                      file=sys.stderr)
                return 1
            print("OK: file sinh ra (" + ", ".join(rel for rel, _ in _generated(cfg, root))
                  + ") khớp app.config.toml")
            for w in web_warnings(cfg):
                print(f"WARN: {w}", file=sys.stderr)
            if has_app_links(cfg) and (root / PROJECT_YML).is_file() and not includes_entitlements_fragment(root):
                # App sinh từ bản cũ: chưa có dòng include ⇒ bản build KHÔNG có associated-domains (cổng 10 đỏ ở archive).
                print(f"NOTE: web.host_prod có giá trị nhưng {PROJECT_YML} chưa include "
                      f"{ENTITLEMENTS_YML.removeprefix(PROJ_DIR + '/')} — Universal Link chưa có trong bản build; thêm "
                      f"dòng `  - {ENTITLEMENTS_YML.removeprefix(PROJ_DIR + '/')}` vào `include:` rồi render + "
                      f"xcodegen generate", file=sys.stderr)
        else:
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / "GoogleService-Info-Prod.plist").write_bytes(fixture_plist(cfg, "Release"))
            (out / "GoogleService-Info-Dev.plist").write_bytes(fixture_plist(cfg, "Debug"))
        return 0
    except ConfigError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
