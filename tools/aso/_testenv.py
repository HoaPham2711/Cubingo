"""Môi trường test của công cụ ASO — mọi file test_*.py import module này ĐẦU TIÊN.

- `IOS_APP_FACTORY_STATE` / `IOS_APP_FACTORY_CONFIG` / `IOS_APP_FACTORY_BIN` LUÔN là thư mục tạm (đường dẫn có dấu
  cách): test không bao giờ đụng `~/Library/Application Support`, `~/.config` hay `~/.local/share`.
- `store.config` trả cấu hình GIẢ (`FAKE_CFG`): App Store id, slug, team… ghép chuỗi, không phải định danh thật nào,
  nên test xanh như nhau ở template và ở mọi app sinh ra (không phụ thuộc `app.config.toml` của repo).
"""
import atexit
import copy
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

FAKE_APP_ID = "12345" "67890"
FAKE_TEAM = "ABCDE" "12345"
FAKE_HOST = "thu" "-nghiem.app"
FAKE_CFG = {
    "app": {"slug": "thu-app", "display_name": "Thu App", "display_name_internal": "Thu App Dev"},
    "bundle": {"store": "dev.thu" "-nghiem.ThuApp", "internal": "dev.thu" "-nghiem.ThuApp.internal"},
    "apple": {"team_id": FAKE_TEAM, "app_store_id": FAKE_APP_ID},
    "version": {"marketing": "1.2.3", "build": "7"},
    "web": {"host_prod": FAKE_HOST, "host_dev": "dev." + FAKE_HOST},
    "store": {"locales": ["en-US"]},
}

# Mặc định cho cả tiến trình test (kể cả test quên gọi isolate).
for _k in ("IOS_APP_FACTORY_STATE", "IOS_APP_FACTORY_CONFIG", "IOS_APP_FACTORY_BIN"):
    os.environ[_k] = tempfile.mkdtemp(prefix="aso test " + _k[16:].lower() + " ")
    atexit.register(shutil.rmtree, os.environ[_k], True)
os.environ.pop("ASO_CONFIG", None)
os.environ.pop("ASC_KEY_FILE", None)

import store  # noqa: E402

store.config = lambda: copy.deepcopy(FAKE_CFG)


def cfg(**doi) -> dict:
    """Bản sao FAKE_CFG, `doi` dạng {"apple.app_store_id": ""} ghi đè khoá chấm."""
    c = copy.deepcopy(FAKE_CFG)
    for dotted, value in doi.items():
        sec, key = dotted.split(".", 1)
        c.setdefault(sec, {})[key] = value
    return c


def use_config(tc, c: dict) -> None:
    """Cho riêng test `tc`: `store.config()` trả `c`."""
    p = mock.patch.object(store, "config", lambda: copy.deepcopy(c))
    p.start()
    tc.addCleanup(p.stop)


def isolate(tc) -> Path:
    """Đặt `IOS_APP_FACTORY_STATE` = thư mục tạm mới cho riêng test `tc`; trả thư mục trạng thái ASO tương ứng
    (`<tạm>/<slug>/aso`, đã resolve)."""
    d = Path(tempfile.mkdtemp(prefix="aso state ")).resolve()
    tc.addCleanup(shutil.rmtree, d, True)
    p = mock.patch.dict(os.environ, {"IOS_APP_FACTORY_STATE": str(d)})
    p.start()
    tc.addCleanup(p.stop)
    return store.state_dir()
