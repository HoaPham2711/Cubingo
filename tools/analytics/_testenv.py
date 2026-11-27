"""Môi trường test của tools/analytics — mọi file test_*.py import module này ĐẦU TIÊN.

- `IOS_APP_FACTORY_CONFIG` và `ANALYTICS_OUT` LUÔN là thư mục tạm (đường dẫn có dấu cách): test không đọc
  `~/.config`, không ghi `.temp/` của repo. Biến khoá/định danh của nguồn (`ASC_CONFIG`, `GA4_KEY_FILE`, …) bị xoá.
- `_shared.load_cfg` trả cấu hình GIẢ (`FAKE_CFG`, giá trị ghép chuỗi): test xanh như nhau ở template và ở app sinh ra.
- Không gọi mạng: mọi lệnh kéo nhận `fetch` giả (`Resp`) hoặc dừng trước khi cần mạng.
"""
import atexit
import copy
import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FAKE_BUNDLE = "dev.thu" "-nghiem.ThuApp"
FAKE_PROPERTY = "12345" "6789"
FAKE_BQ = "thu-nghiem" "-proj"
FAKE_CFG = {
    "app": {"slug": "thu-app", "display_name": "Thu App", "display_name_internal": "Thu App Dev"},
    "bundle": {"store": FAKE_BUNDLE, "internal": FAKE_BUNDLE + ".internal"},
    "apple": {"team_id": "ABCDE" "12345", "app_store_id": "12345" "67890"},
    "version": {"marketing": "1.2.3", "build": "7"},
    "analytics": {"ga4_property": FAKE_PROPERTY, "bq_project": FAKE_BQ},
}
ENV_KEYS = ("ASC_CONFIG", "ASC_KEY_FILE", "GA4_KEY_FILE", "GA4_PROPERTY_ID", "GA4_BQ_PROJECT", "GA4_BQ_DATASET",
            "GA4_BQ_LOCATION", "CRASH_WATCH_FILE", "WEB_ADMIN_TOKEN_FILE")

for _k in ("IOS_APP_FACTORY_CONFIG", "ANALYTICS_OUT"):
    os.environ[_k] = tempfile.mkdtemp(prefix="analytics test " + _k.lower() + " ")
    atexit.register(shutil.rmtree, os.environ[_k], True)
for _k in ENV_KEYS:
    os.environ.pop(_k, None)

import _shared  # noqa: E402

_shared.load_cfg = lambda: copy.deepcopy(FAKE_CFG)

import crash_watch  # noqa: E402

# Danh sách theo dõi riêng của app (`tools/app/crash_watch.json`) không được lọt vào test: trỏ tới file không tồn tại.
crash_watch.APP_WATCH_FILE = Path(os.environ["ANALYTICS_OUT"]) / "khong-co-app-watch.json"


def cfg(**doi) -> dict:
    """Bản sao FAKE_CFG, `doi` dạng {"analytics.ga4_property": ""} ghi đè khoá chấm."""
    c = copy.deepcopy(FAKE_CFG)
    for dotted, value in doi.items():
        sec, key = dotted.split(".", 1)
        c.setdefault(sec, {})[key] = value
    return c


def use_config(tc, c: dict) -> None:
    p = mock.patch.object(_shared, "load_cfg", lambda: copy.deepcopy(c))
    p.start()
    tc.addCleanup(p.stop)


def tmpdir(tc, prefix="analytics tmp ") -> Path:
    d = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
    tc.addCleanup(shutil.rmtree, d, True)
    return d


def isolate(tc) -> tuple[Path, Path]:
    """Cho riêng test `tc`: thư mục cấu hình + gốc đầu ra mới. Trả (config_dir của app giả, gốc đầu ra)."""
    conf, out = tmpdir(tc, "analytics conf "), tmpdir(tc, "analytics out ")
    p = mock.patch.dict(os.environ, {"IOS_APP_FACTORY_CONFIG": str(conf), "ANALYTICS_OUT": str(out)})
    p.start()
    tc.addCleanup(p.stop)
    app_conf = conf / FAKE_CFG["app"]["slug"]
    app_conf.mkdir(parents=True)
    return app_conf, out


def set_env(tc, **env) -> None:
    p = mock.patch.dict(os.environ, env)
    p.start()
    tc.addCleanup(p.stop)


class Resp:
    """Phản hồi giả kiểu `requests.Response`."""

    def __init__(self, status=200, json_body=None, content=b""):
        import json as _json
        self.status_code = status
        self._json = json_body
        self.content = content if json_body is None else _json.dumps(json_body).encode()
        self.text = self.content.decode("utf-8", "replace")

    def json(self):
        if self._json is None:
            raise ValueError("không phải JSON")
        return self._json


def run(main, argv, **kw):
    """Chạy `main(argv, **kw)` → (rc, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv, **kw)
    return rc, out.getvalue(), err.getvalue()
