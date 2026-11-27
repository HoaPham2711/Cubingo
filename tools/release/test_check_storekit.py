"""Test cho check_storekit.py: tập id trong file `.storekit` phải khớp `[purchases] product_ids`.

Mỗi test dựng một gốc tạm (app.config.toml + AppHost/StoreKitConfig/Products.storekit) rồi chạy script thật với
`--root`. Chạy: python3 -m unittest tools/release/test_check_storekit.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check_storekit.py"
sys.path.insert(0, str(HERE.parent / "common"))
import appconfig  # noqa: E402

CONFIG = """\
[app]
slug = "sample"
display_name = "Sample"
display_name_internal = "Sample Dev"

[bundle]
store = "com.example.sample"
internal = "com.example.sample.internal"

[apple]
team_id = "0000000000"

[version]
marketing = "0.1.0"
build = "1"

[web]
host_prod = "example.com"
host_dev = "dev.example.com"

[features]
paywall = {paywall}

[purchases]
product_ids = {ids}
subscription_group = "pro"
"""


def storekit(subs=("a.monthly", "a.yearly"), products=("a.lifetime",), group="pro", non_renewing=()):
    def sub(pid, period):
        return {"productID": pid, "recurringSubscriptionPeriod": period, "type": "RecurringSubscription",
                "displayPrice": "1.99", "familyShareable": False, "groupNumber": 1, "internalID": pid,
                "localizations": [], "referenceName": pid, "subscriptionGroupID": "1"}
    return {
        "identifier": "TEST",
        "nonRenewingSubscriptions": [{"productID": p, "type": "NonRenewingSubscription"} for p in non_renewing],
        "products": [{"productID": p, "type": "NonConsumable", "displayPrice": "9.99"} for p in products],
        "settings": {},
        "subscriptionGroups": [{"id": "1", "name": group, "localizations": [],
                                "subscriptions": [sub(p, "P1M") for p in subs]}] if subs else [],
        "version": {"major": 3, "minor": 0},
    }


class CheckStoreKitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "gốc có dấu cách"
        self.root.mkdir()

    def setup(self, ids=("a.monthly", "a.yearly", "a.lifetime"), paywall=True, sk=None, raw=None):
        cfg = CONFIG.format(paywall="true" if paywall else "false", ids=json.dumps(list(ids)))
        (self.root / appconfig.CONFIG_FILE).write_text(cfg, encoding="utf-8")
        path = self.root / appconfig.STOREKIT_CONFIG
        path.parent.mkdir(parents=True, exist_ok=True)
        if raw is not None:
            path.write_text(raw, encoding="utf-8")
        elif sk is not False:
            path.write_text(json.dumps(sk if sk is not None else storekit(), indent=2), encoding="utf-8")

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                              capture_output=True, text=True)

    def assertFail(self, r, rc, *needles):
        self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
        self.assertIn("FAIL:", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        for n in needles:
            self.assertIn(n, r.stderr)

    def test_khop_rc0(self):
        self.setup()
        r = self.run_cli()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)

    def test_thu_tu_khac_van_khop(self):
        self.setup(ids=("a.lifetime", "a.yearly", "a.monthly"))
        self.assertEqual(self.run_cli().returncode, 0)

    def test_cau_hinh_co_ma_storekit_thieu_id_rc1(self):
        self.setup(sk=storekit(products=()))
        self.assertFail(self.run_cli(), 1, "a.lifetime")

    def test_storekit_thua_id_rc1(self):
        self.setup(ids=("a.monthly", "a.yearly"))
        self.assertFail(self.run_cli(), 1, "a.lifetime")

    def test_id_non_renewing_cung_duoc_dem(self):
        self.setup(sk=storekit(non_renewing=("a.season",)))
        self.assertFail(self.run_cli(), 1, "a.season")

    def test_paywall_tat_skip(self):
        self.setup(ids=(), paywall=False, sk=False)
        r = self.run_cli()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("SKIP", r.stdout)

    def test_thieu_file_storekit_rc1(self):
        self.setup(sk=False)
        self.assertFail(self.run_cli(), 1, "Products.storekit")

    def test_storekit_khong_phai_json_rc1(self):
        self.setup(raw="{ không phải json")
        self.assertFail(self.run_cli(), 1, "JSON")

    def test_storekit_sai_hinh_rc1(self):
        self.setup(raw='{"products": "x"}')
        self.assertFail(self.run_cli(), 1)

    def test_ten_nhom_subscription_lech_rc1(self):
        self.setup(sk=storekit(group="khac"))
        self.assertFail(self.run_cli(), 1, "subscription_group", "khac")

    def test_cau_hinh_hong_rc2(self):
        self.setup()
        (self.root / appconfig.CONFIG_FILE).write_text("[app\n", encoding="utf-8")
        self.assertFail(self.run_cli(), 2)

    def test_mac_dinh_doc_repo_that_tu_vi_tri_script(self):
        # Không truyền --root, chạy từ thư mục khác: script tự tìm gốc theo vị trí của nó.
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=self._tmp.name)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
