#!/usr/bin/env python3
"""Lint: tập product id trong file `.storekit` phải khớp `[purchases] product_ids` của app.config.toml.

    python3 tools/release/check_storekit.py            # gốc repo suy từ vị trí script
    python3 tools/release/check_storekit.py --root DIR # gốc khác (test)

Vì sao: id phải khớp TUYỆT ĐỐI ba nơi — cấu hình app (`AppConfig.productIDs` → `LiveStoreClient`), file
`.storekit` CỦA APP (`appconfig.STOREKIT_CONFIG`: paywall khi Run từ Xcode + store giả của route preview mà SmokeTests
đối chiếu) và App Store Connect. Lệch một ký tự thì
`Product.products` trả rỗng: triệu chứng giống hệt lỗi code, và chỉ lộ ra lúc chạy. Lint này bắt hai nơi đầu
(App Store Connect nằm ngoài repo). Kèm: tên subscription group trong file phải là `purchases.subscription_group`
(nếu cấu hình có khoá đó).

Phạm vi: CHỈ file `.storekit` của app. Fixture của lõi (`CoreTests/Purchases/CoreProducts.storekit`, id `test.pro.*`
cho `LiveStoreClientTests`) cố ý KHÔNG khớp cấu hình app nên nằm ngoài lint — không phải ngoại lệ đặc cách: lint vốn
chỉ đọc đúng một đường dẫn, không quét `*.storekit`.

Exit code:
  0  khớp (`OK`), hoặc `features.paywall = false` (`SKIP` — app miễn phí, không cần file `.storekit`)
  1  lệch id / lệch tên group / file `.storekit` thiếu, không phải JSON hoặc sai hình — in `FAIL: <lý do>`
  2  app.config.toml hỏng — in `FAIL: <lý do>`
Không bao giờ in traceback.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "common"))
import appconfig  # noqa: E402


class StoreKitFileError(Exception):
    """File `.storekit` thiếu / hỏng / sai hình."""


def _ids_in(entries, where: str) -> list[str]:
    if not isinstance(entries, list):
        raise StoreKitFileError(f"'{where}' phải là danh sách")
    ids = []
    for e in entries:
        pid = e.get("productID") if isinstance(e, dict) else None
        if not isinstance(pid, str) or not pid:
            raise StoreKitFileError(f"một mục trong '{where}' thiếu 'productID'")
        ids.append(pid)
    return ids


def read_storekit(path: Path) -> tuple[list[str], list[str]]:
    """(mọi product id, tên các subscription group) trong file `.storekit`."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise StoreKitFileError(f"không thấy {path} (features.paywall = true thì app phải có file này)")
    except (OSError, UnicodeDecodeError) as e:
        raise StoreKitFileError(f"không đọc được {path}: {e}")
    except json.JSONDecodeError as e:
        raise StoreKitFileError(f"{path} không phải JSON hợp lệ: {e}")
    if not isinstance(data, dict):
        raise StoreKitFileError(f"{path}: gốc phải là object JSON")
    ids = _ids_in(data.get("products", []), "products")
    ids += _ids_in(data.get("nonRenewingSubscriptions", []), "nonRenewingSubscriptions")
    groups = data.get("subscriptionGroups", [])
    if not isinstance(groups, list):
        raise StoreKitFileError("'subscriptionGroups' phải là danh sách")
    names = []
    for g in groups:
        if not isinstance(g, dict):
            raise StoreKitFileError("một mục trong 'subscriptionGroups' không phải object")
        names.append(str(g.get("name", "")))
        ids += _ids_in(g.get("subscriptions", []), "subscriptionGroups[].subscriptions")
    return ids, names


def check(root: Path) -> tuple[int, str]:
    try:
        cfg = appconfig.load(root)
        paywall = appconfig.feature(cfg, "features.paywall")
    except appconfig.ConfigError as e:
        return 2, f"FAIL: {e}"
    if not paywall:
        return 0, "SKIP: features.paywall = false — app miễn phí, không đối chiếu file .storekit"
    want = appconfig.opt(cfg, "purchases.product_ids", [])
    group = appconfig.opt(cfg, "purchases.subscription_group", "")
    path = root / appconfig.STOREKIT_CONFIG
    try:
        have, group_names = read_storekit(path)
    except StoreKitFileError as e:
        return 1, f"FAIL: {e}"
    problems = []
    dup = sorted({i for i in have if have.count(i) > 1})
    if dup:
        problems.append(f"id lặp trong {appconfig.STOREKIT_CONFIG}: {', '.join(dup)}")
    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    if missing:
        problems.append(f"id có trong purchases.product_ids nhưng THIẾU trong {appconfig.STOREKIT_CONFIG}: "
                        f"{', '.join(missing)}")
    if extra:
        problems.append(f"id có trong {appconfig.STOREKIT_CONFIG} nhưng KHÔNG có trong purchases.product_ids: "
                        f"{', '.join(extra)}")
    if group and group_names and any(n != group for n in group_names):
        problems.append(f"subscription group trong {appconfig.STOREKIT_CONFIG} là {', '.join(group_names)} — "
                        f"purchases.subscription_group = {group!r}")
    if problems:
        return 1, "FAIL: " + "\nFAIL: ".join(problems)
    return 0, f"OK: {len(have)} product id trong {appconfig.STOREKIT_CONFIG} khớp purchases.product_ids"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT, help="gốc repo (mặc định: suy từ vị trí script)")
    a = ap.parse_args(argv)
    rc, msg = check(a.root)
    print(msg, file=sys.stderr if rc else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
