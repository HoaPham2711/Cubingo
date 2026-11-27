#!/usr/bin/env python3
"""Kéo báo cáo App Store Connect (Sales, Subscription, Analytics Reports) về TSV.

Chạy:
    python3 tools/analytics/asc_pull.py                  # 60 ngày gần nhất
    python3 tools/analytics/asc_pull.py --days 30
    python3 tools/analytics/asc_pull.py --create-analytics-request   # một lần, cần key role Admin

Kết quả: .temp/analytics/asc/<ngày chạy>/ (hoặc `$ANALYTICS_OUT/asc/<ngày>/`, hoặc `--out`).

Cấu hình (ngoài repo): `$ASC_CONFIG` hoặc `<config_dir>/asc.json` = {key_id, issuer_id, vendor_number}
(`config_dir` = `appconfig.config_dir`, theo `app.slug`). Bundle id lấy từ `app.config.toml` (`bundle.store`).
File key: `$ASC_KEY_FILE` hoặc `~/.appstoreconnect/private_keys/AuthKey_<key_id>.p8`, role Sales and Reports.
Script KHÔNG BAO GIỜ in nội dung key hay token. Cần gói ở requirements.txt (PyJWT, cryptography, requests).
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shared  # noqa: E402
from _shared import Refuse  # noqa: E402

API = "https://api.appstoreconnect.apple.com"

# (tên file, reportType, reportSubType, các version thử lần lượt)
DAILY_REPORTS = [
    ("sales", "SALES", "SUMMARY", ["1_1", "1_0"]),
    ("subscription_events", "SUBSCRIPTION_EVENT", "SUMMARY", ["1_4", "1_3"]),
    ("subscriptions", "SUBSCRIPTION", "SUMMARY", ["1_4", "1_3"]),
]

# Analytics Reports chung cho phân tích sản phẩm (khớp theo tên, bỏ qua cái nào không có).
ANALYTICS_REPORTS = [
    "App Store Discovery and Engagement Standard",
    "App Store Discovery and Engagement Detailed",  # có cột Campaign (mã ct của link App Store)
    "App Downloads Standard",
    "App Downloads Detailed",  # có Source Info + Campaign
    "App Store Installation and Deletion Standard",
    "App Sessions Standard",
    "App Store Purchases Standard",
    "App Crashes",
]

VENDOR_HINT = ("lấy Vendor # ở App Store Connect › Payments and Financial Reports (góc trên trái) rồi thêm "
               '"vendor_number" vào')


def load_asc_config(cfg: dict) -> tuple[dict, Path]:
    """asc.json → {key_id, issuer_id, vendor_number}; thiếu file/khoá ⇒ Refuse một dòng nêu đường dẫn."""
    path = _shared.path_from_env("ASC_CONFIG", _shared.appconfig.config_dir(cfg) / "asc.json")
    if not path.is_file():
        raise Refuse(f"FAIL: thiếu cấu hình App Store Connect: {path} — tạo file JSON "
                     '{"key_id", "issuer_id", "vendor_number"} (key role Sales and Reports) hoặc trỏ ASC_CONFIG tới nó')
    try:
        creds = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Refuse(f"FAIL: {path} không phải JSON hợp lệ") from None
    if not isinstance(creds, dict):
        raise Refuse(f"FAIL: {path} phải là một object JSON")
    for k in ("key_id", "issuer_id"):
        if not creds.get(k):
            raise Refuse(f"FAIL: {path} thiếu \"{k}\" (xem trang Users and Access › Integrations của App Store Connect)")
    if not creds.get("vendor_number"):
        raise Refuse(f"FAIL: {path} thiếu \"vendor_number\" — {VENDOR_HINT} {path.name}")
    return creds, path


def key_file(creds: dict) -> Path:
    """File .p8 — chỉ kiểm tồn tại, không đọc ở đây."""
    default = Path(f"~/.appstoreconnect/private_keys/AuthKey_{creds['key_id']}.p8").expanduser()
    p = _shared.path_from_env("ASC_KEY_FILE", default)
    if not p.is_file():
        raise Refuse(f"FAIL: thiếu file key App Store Connect: {p} — tải AuthKey_<key_id>.p8 về đó "
                     f"(chmod 600) hoặc trỏ ASC_KEY_FILE tới nó")
    return p


def default_fetch(creds: dict, key_path: Path):
    """`fetch(method, url, **kw)` thật: requests + JWT ES256 (sống 15 phút, làm mới trước khi hết hạn).
    Chỉ gắn token cho URL của API ASC — URL tải segment đã ký sẵn thì không."""
    _shared.require("jwt", "cryptography", "requests")
    import jwt
    import requests

    http = requests.Session()
    state = {"token": None, "exp": 0}

    def token():
        if time.time() > state["exp"] - 60:
            now = int(time.time())
            try:
                key = key_path.read_text(encoding="utf-8")
                state["token"] = jwt.encode(
                    {"iss": creds["issuer_id"], "iat": now, "exp": now + 900, "aud": "appstoreconnect-v1"},
                    key, algorithm="ES256", headers={"kid": creds["key_id"], "typ": "JWT"})
            except Exception:  # noqa: BLE001 — thông điệp thư viện có thể trích nội dung key
                raise Refuse(f"FAIL: không ký được token App Store Connect bằng {key_path} — kiểm file .p8 "
                             f"khớp key_id/issuer_id trong asc.json") from None
            state["exp"] = now + 900
        return state["token"]

    def fetch(method, url, **kw):
        kw.setdefault("timeout", 120)
        if url.startswith(API):
            kw["headers"] = {"Authorization": f"Bearer {token()}"} | (kw.get("headers") or {})
        return http.request(method, url, **kw)
    return fetch


class Client:
    def __init__(self, fetch):
        self.fetch = fetch

    def get(self, path, params=None, accept="application/json"):
        url = path if path.startswith("http") else API + path
        for attempt in range(4):
            r = self.fetch("GET", url, params=params, headers={"Accept": accept})
            if r.status_code != 429:
                return r
            time.sleep(5 * (attempt + 1))
        return r

    def post(self, path, body):
        return self.fetch("POST", API + path, json=body)

    def pages(self, path, params=None):
        """Duyệt hết phân trang của một endpoint danh sách."""
        while path:
            r = self.get(path, params)
            if r.status_code != 200:
                raise RuntimeError(f"{path}: HTTP {r.status_code} {r.text[:400]}")
            doc = r.json()
            yield from doc.get("data", [])
            path, params = doc.get("links", {}).get("next"), None


def gunzip_text(content: bytes) -> str:
    try:
        return gzip.decompress(content).decode("utf-8")
    except OSError:
        return content.decode("utf-8")


def pull_daily(client, vendor, out, days, today=None):
    """Báo cáo Sales/Subscription theo ngày → gộp một file TSV mỗi loại (thêm cột report_date đầu dòng)."""
    today = today or dt.date.today()
    for name, rtype, subtype, versions in DAILY_REPORTS:
        header, lines, got, version, r = None, [], 0, None, None
        span = 3 if name == "subscriptions" else days  # Subscription summary là ảnh chụp trạng thái
        for i in range(1, span + 1):
            day = (today - dt.timedelta(days=i)).isoformat()
            for v in ([version] if version else versions):
                r = client.get("/v1/salesReports", {
                    "filter[frequency]": "DAILY", "filter[reportType]": rtype,
                    "filter[reportSubType]": subtype, "filter[vendorNumber]": vendor,
                    "filter[reportDate]": day, "filter[version]": v,
                }, accept="application/a-gzip")
                if r.status_code == 200:
                    version = v
                    break
                if r.status_code == 404:  # ngày không có giao dịch / chưa có báo cáo
                    break
            if r.status_code == 200:
                text = gunzip_text(r.content).strip("\n")
                if not text.strip():
                    continue  # 200 mà thân rỗng: coi như ngày không có báo cáo (không lấy "" làm header)
                rows = text.split("\n")
                if header is None:
                    header = "report_date\t" + rows[0]
                lines += [f"{day}\t{row}" for row in rows[1:] if row.strip()]
                got += 1
            elif r.status_code == 400:
                # Apple trả "Invalid vendor number" cho báo cáo Subscription khi tài khoản CHƯA có giao dịch
                # subscription nào (Sales cùng vendor number vẫn chạy) → bỏ loại này thôi.
                try:
                    detail = (r.json().get("errors") or [{}])[0].get("detail", r.text[:200])
                except ValueError:
                    detail = r.text[:200]
                print(f"  --   {name}: Apple từ chối ({detail}) — bỏ qua loại báo cáo này")
                break
            elif r.status_code != 404:
                print(f"  LỖI  {name} {day}: HTTP {r.status_code} {r.text[:300]}")
                if r.status_code in (401, 403):
                    return False
        if header:
            (out / f"{name}.tsv").write_text("\n".join([header] + lines) + "\n", encoding="utf-8")
        print(f"  ok   {name}: {got}/{span} ngày có dữ liệu, {len(lines)} dòng"
              + (f" (version {version})" if version else ""))
    return True


def find_app(client, bundle_id):
    r = client.get("/v1/apps", {"filter[bundleId]": bundle_id, "fields[apps]": "name,bundleId"})
    if r.status_code != 200:
        print(f"  LỖI  tra app: HTTP {r.status_code} {r.text[:300]}")
        return None
    data = [a for a in r.json().get("data", []) if a["attributes"]["bundleId"] == bundle_id]
    return data[0]["id"] if data else None


def unique_lines(lines):
    """Bỏ dòng trùng hoàn toàn, giữ thứ tự: Apple gửi lại cùng số liệu ở nhiều instance `processingDate`."""
    return list(dict.fromkeys(lines))


def pull_analytics(client, app_id, out, days, create, today=None):
    """Analytics Reports: impression/product page view/download/session/crash theo ngày."""
    reqs = list(client.pages(f"/v1/apps/{app_id}/analyticsReportRequests", {"filter[accessType]": "ONGOING"}))
    reqs = [r for r in reqs if not r["attributes"].get("stoppedDueToInactivity")]
    if not reqs:
        if not create:
            print("  --   Analytics Reports: chưa có report request ONGOING. Tạo một lần bằng key "
                  "role Admin: asc_pull.py --create-analytics-request")
            return
        r = client.post("/v1/analyticsReportRequests", {"data": {
            "type": "analyticsReportRequests", "attributes": {"accessType": "ONGOING"},
            "relationships": {"app": {"data": {"type": "apps", "id": app_id}}}}})
        if r.status_code != 201:
            print(f"  LỖI  tạo report request: HTTP {r.status_code} {r.text[:400]}")
            return
        print("  ok   đã tạo report request ONGOING — Apple cần 1–2 ngày để sinh báo cáo đầu tiên.")
        return

    since = ((today or dt.date.today()) - dt.timedelta(days=days)).isoformat()
    adir = out / "analytics"
    adir.mkdir(exist_ok=True)
    reports = {r["attributes"]["name"]: r["id"]
               for r in client.pages(f"/v1/analyticsReportRequests/{reqs[0]['id']}/reports")}
    (adir / "_available_reports.json").write_text(json.dumps(sorted(reports), indent=1), encoding="utf-8")
    for name in ANALYTICS_REPORTS:
        if name not in reports:
            print(f"  --   analytics '{name}': chưa có")
            continue
        header, lines, n = None, [], 0
        for inst in client.pages(f"/v1/analyticsReports/{reports[name]}/instances", {"filter[granularity]": "DAILY"}):
            if inst["attributes"]["processingDate"] < since:
                continue
            for seg in client.pages(f"/v1/analyticsReportInstances/{inst['id']}/segments"):
                # URL tải đã ký sẵn — fetch thật KHÔNG gắn token ASC cho URL ngoài API.
                d = client.fetch("GET", seg["attributes"]["url"], timeout=300)
                if d.status_code != 200:
                    print(f"  LỖI  tải segment '{name}': HTTP {d.status_code}")
                    continue
                text = gunzip_text(d.content).strip("\n")
                if not text.strip():
                    continue
                rows = text.split("\n")
                header = header or rows[0]
                lines += [row for row in rows[1:] if row.strip()]
            n += 1
        lines = unique_lines(lines)
        if header:
            fname = name.lower().replace(" ", "_") + ".tsv"
            (adir / fname).write_text("\n".join([header] + lines) + "\n", encoding="utf-8")
        print(f"  ok   analytics '{name}': {n} ngày, {len(lines)} dòng")


def _main(argv, fetch):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--create-analytics-request", action="store_true",
                    help="tạo report request ONGOING (một lần, cần key role Admin)")
    ap.add_argument("--out", type=Path, default=None, help="thư mục đầu ra (mặc định <gốc>/asc/<ngày>)")
    args = ap.parse_args(argv)

    cfg = _shared.load_cfg()
    bundle_id = _shared.appconfig.get(cfg, "bundle.store")
    creds, _ = load_asc_config(cfg)
    if fetch is None:
        fetch = default_fetch(creds, key_file(creds))
    client = Client(fetch)
    out = _shared.run_dir("asc", args.out)

    if not args.create_analytics_request:
        if not pull_daily(client, creds["vendor_number"], out, args.days):
            print("  --   bỏ qua phần Sales/Subscription còn lại (xem lỗi ở trên)")
    app_id = find_app(client, bundle_id)
    if app_id:
        try:
            pull_analytics(client, app_id, out, args.days, args.create_analytics_request)
        except RuntimeError as e:
            print(f"  LỖI  Analytics Reports: {e}")
    else:
        print(f"  --   không tra được app {bundle_id} bằng key này (bỏ qua Analytics Reports)")
    print(f"\nĐã ghi vào {_shared.show(out)}")
    return 0


def main(argv=None, *, fetch=None) -> int:
    """`fetch(method, url, **kw) -> response kiểu requests` tiêm được (test); None ⇒ HTTP thật có JWT."""
    return _shared.run_main(_main, argv, fetch)


if __name__ == "__main__":
    sys.exit(main())
