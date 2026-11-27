#!/usr/bin/env python3
"""Test khoá thiếu / phụ thuộc thiếu: một dòng hướng dẫn, rc 2, không traceback, không in nội dung khoá.

Không có khoá thật nào: file khoá là file tạm chứa chuỗi canh gác; gói ngoài bị che hoặc thay bằng module giả
qua `sys.modules`, nên test chạy được cả khi máy không cài requirements.txt.
Chạy: `python3 -m unittest discover -s tools/analytics -p "test_*.py"`.
"""
import _testenv  # noqa: F401  (đầu tiên)

import json
import sys
import types
import unittest
from unittest import mock

import _shared
import asc_pull
import crash_pull
import ga4_pull

GOI_NGOAI = ("jwt", "cryptography", "requests", "google", "google.auth", "google.auth.transport",
             "google.auth.transport.requests", "google.oauth2", "google.oauth2.service_account")
CANH_GAC = "BI-MAT-KHONG-DUOC-IN-" + "7f3a"


def che_goi_ngoai(tc):
    """Giả lập máy chưa cài requirements.txt: import các gói ngoài ném ImportError."""
    p = mock.patch.dict(sys.modules, {name: None for name in GOI_NGOAI})
    p.start()
    tc.addCleanup(p.stop)


def goi_gia_nem_loi_kem_noi_dung(tc):
    """Gói ngoài 'có cài' nhưng thư viện ném lỗi TRÍCH nội dung khoá (như vài bản PyJWT/google-auth làm)."""
    def nem(*a, **k):
        raise ValueError(f"khoá hỏng: {CANH_GAC}")
    jwt = types.ModuleType("jwt")
    jwt.encode = nem
    requests = types.ModuleType("requests")

    class Session:
        def request(self, *a, **k):
            tc.fail("không được gọi mạng")
    requests.Session = Session
    sa = types.ModuleType("google.oauth2.service_account")
    sa.Credentials = types.SimpleNamespace(from_service_account_file=nem)
    treq = types.ModuleType("google.auth.transport.requests")
    treq.AuthorizedSession = lambda creds: tc.fail("không được tạo phiên")
    mods = {"jwt": jwt, "cryptography": types.ModuleType("cryptography"), "requests": requests,
            "google": types.ModuleType("google"), "google.auth": types.ModuleType("google.auth"),
            "google.auth.transport": types.ModuleType("google.auth.transport"),
            "google.auth.transport.requests": treq, "google.oauth2": types.ModuleType("google.oauth2"),
            "google.oauth2.service_account": sa}
    mods["google.oauth2"].service_account = sa
    p = mock.patch.dict(sys.modules, mods)
    p.start()
    tc.addCleanup(p.stop)


def asc_san_sang(tc, conf, key_exists=True):
    (conf / "asc.json").write_text(encoding="utf-8", data=json.dumps({"key_id": "KEY" "TEST01", "issuer_id": "I", "vendor_number": "1"}))
    key = _testenv.tmpdir(tc) / "AuthKey thu.p8"
    if key_exists:
        key.write_text(encoding="utf-8", data=CANH_GAC)
    _testenv.set_env(tc, ASC_KEY_FILE=str(key))
    return key


def ga4_khoa(tc, conf, exists=True):
    key = conf / "analytics-reader.json"
    if exists:
        key.write_text(encoding="utf-8", data=CANH_GAC)
    return key


class ThieuKhoa(unittest.TestCase):
    def assertMotDong(self, rc, so, se):
        self.assertEqual(rc, 2, so + se)
        self.assertEqual(se.count("\n"), 1, se)
        self.assertTrue(se.startswith("FAIL: "), se)
        self.assertNotIn("Traceback", so + se)
        self.assertNotIn(CANH_GAC, so + se)

    def test_thieu_khoa_mot_dong_huong_dan_khong_in_noi_dung_khoa(self):
        conf, _ = _testenv.isolate(self)
        # ASC: thiếu .p8 ⇒ nêu đường dẫn mong đợi
        key = asc_san_sang(self, conf, key_exists=False)
        rc, so, se = _testenv.run(asc_pull.main, [])
        self.assertMotDong(rc, so, se)
        self.assertIn(str(key), se)
        # GA4 + BigQuery: thiếu service account ⇒ nêu <config_dir>/analytics-reader.json
        for main in (ga4_pull.main, crash_pull.main):
            rc, so, se = _testenv.run(main, [])
            self.assertMotDong(rc, so, se)
            self.assertIn(str(conf / "analytics-reader.json"), se)
        # Có file khoá nhưng thư viện ném lỗi kèm nội dung khoá ⇒ vẫn một dòng, không lộ nội dung
        asc_san_sang(self, conf)
        ga4_khoa(self, conf)
        goi_gia_nem_loi_kem_noi_dung(self)
        for main in (asc_pull.main, ga4_pull.main, crash_pull.main):
            rc, so, se = _testenv.run(main, [])
            self.assertMotDong(rc, so, se)
            self.assertIn("AuthKey thu.p8" if main is asc_pull.main else "analytics-reader.json", se)


def goi_gia_ghi_lai(tc, ghi):
    """Gói ngoài giả GHI LẠI lời gọi: jwt.encode (payload/key/thuật toán/header), requests.Session.request,
    service_account.Credentials.from_service_account_file (đường dẫn + scopes), AuthorizedSession."""
    def encode(payload, key, algorithm=None, headers=None):
        ghi.setdefault("jwt", []).append({"payload": payload, "key": key, "algorithm": algorithm, "headers": headers})
        return "token-gia"

    class Session:
        def request(self, method, url, **kw):
            ghi.setdefault("http", []).append((method, url, kw))
            return _testenv.Resp(404, json_body={"errors": []})

    def from_file(path, scopes=None):
        ghi.setdefault("sa", []).append({"path": path, "scopes": scopes})
        return "creds-gia"

    class AuthorizedSession(Session):
        def __init__(self, creds):
            ghi.setdefault("creds", []).append(creds)

    jwt = types.ModuleType("jwt")
    jwt.encode = encode
    requests = types.ModuleType("requests")
    requests.Session = Session
    sa = types.ModuleType("google.oauth2.service_account")
    sa.Credentials = types.SimpleNamespace(from_service_account_file=from_file)
    treq = types.ModuleType("google.auth.transport.requests")
    treq.AuthorizedSession = AuthorizedSession
    oauth2 = types.ModuleType("google.oauth2")
    oauth2.service_account = sa
    mods = {"jwt": jwt, "cryptography": types.ModuleType("cryptography"), "requests": requests,
            "google": types.ModuleType("google"), "google.auth": types.ModuleType("google.auth"),
            "google.auth.transport": types.ModuleType("google.auth.transport"),
            "google.auth.transport.requests": treq, "google.oauth2": oauth2, "google.oauth2.service_account": sa}
    p = mock.patch.dict(sys.modules, mods)
    p.start()
    tc.addCleanup(p.stop)


class KyToken(unittest.TestCase):
    def test_claim_jwt_app_store_connect(self):
        conf, _ = _testenv.isolate(self)
        key = asc_san_sang(self, conf)
        ghi = {}
        goi_gia_ghi_lai(self, ghi)
        rc, so, se = _testenv.run(asc_pull.main, ["--days", "1"])
        self.assertEqual(rc, 0, se)
        self.assertTrue(ghi["jwt"])
        tok = ghi["jwt"][0]
        p = tok["payload"]
        self.assertEqual(p["aud"], "appstoreconnect-v1")
        self.assertEqual(p["iss"], "I")
        self.assertGreater(p["exp"], p["iat"])
        self.assertLessEqual(p["exp"] - p["iat"], 1200)  # Apple từ chối token sống > 20 phút
        self.assertEqual(tok["algorithm"], "ES256")
        self.assertEqual(tok["headers"]["kid"], "KEY" "TEST01")
        self.assertEqual(tok["key"], key.read_text(encoding="utf-8"))  # file giả, không phải khoá thật
        api = [h for h in ghi["http"] if h[1].startswith(asc_pull.API)]
        self.assertTrue(api)
        self.assertTrue(all(h[2]["headers"]["Authorization"] == "Bearer token-gia" for h in api))

    def test_service_account_dung_file_va_scope(self):
        conf, _ = _testenv.isolate(self)
        key = ga4_khoa(self, conf)
        ghi = {}
        goi_gia_ghi_lai(self, ghi)
        _testenv.run(ga4_pull.main, ["--days", "1"])
        _testenv.run(crash_pull.main, [])
        self.assertEqual(ghi["sa"], [
            {"path": str(key), "scopes": ["https://www.googleapis.com/auth/analytics.readonly"]},
            {"path": str(key), "scopes": ["https://www.googleapis.com/auth/bigquery"]}])
        self.assertEqual(ghi["creds"], ["creds-gia", "creds-gia"])
        self.assertTrue(all("Authorization" not in (h[2].get("headers") or {}) for h in ghi["http"]))


class ThieuPhuThuoc(unittest.TestCase):
    def test_thieu_phu_thuoc_huong_dan_cai(self):
        conf, _ = _testenv.isolate(self)
        asc_san_sang(self, conf)
        ga4_khoa(self, conf)
        che_goi_ngoai(self)
        for main in (asc_pull.main, ga4_pull.main, crash_pull.main):
            rc, so, se = _testenv.run(main, [])
            self.assertEqual(rc, 2, main.__module__)
            self.assertEqual(se, _shared.INSTALL_HINT + "\n")
            self.assertEqual(_shared.INSTALL_HINT,
                             "FAIL: cần cài: python3 -m pip install -r tools/analytics/requirements.txt")

    def test_requirements_ghim_dung_bon_goi(self):
        text = (_shared.REPO / "tools" / "analytics" / "requirements.txt").read_text(encoding="utf-8")
        pins = sorted(line.split("==")[0] for line in text.splitlines() if line and not line.startswith("#"))
        self.assertEqual(pins, ["PyJWT", "cryptography", "google-auth", "requests"])
        self.assertTrue(all("==" in line for line in text.splitlines() if line and not line.startswith("#")))

    def test_import_module_khong_can_goi_ngoai(self):
        che_goi_ngoai(self)
        import importlib
        for name in ("asc_pull", "ga4_pull", "crash_pull", "crash_watch", "retention", "digest"):
            sys.modules.pop(name, None)
            importlib.import_module(name)  # import đầu file chỉ dùng stdlib


if __name__ == "__main__":
    unittest.main()
