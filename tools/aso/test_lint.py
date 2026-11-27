"""Test cho lint.py — giới hạn App Store, keywords theo byte, chữ giữ chỗ, chữ cấm của app, URL theo host."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint as aso_lint  # noqa: E402

# Cấu hình giả của một app thử (host ghép chuỗi, không phải định danh thật nào).
HOST = "ghi-chu" + "-thu.app"
CONFIG = f"""\
[app]
slug = "ghi-chu"
display_name = "Ghi Chu"
display_name_internal = "Ghi Chu Dev"

[bundle]
store = "dev.thu-nghiem.GhiChu"
internal = "dev.thu-nghiem.GhiChu.internal"

[apple]
team_id = "ABCDE12345"
app_store_id = ""

[version]
marketing = "1.0.0"
build = "1"

[web]
host_prod = "{HOST}"
host_dev = "dev.{HOST}"

[support]
email = "hotro@{HOST}"

[features]
paywall = false
web_api = false
apple_ads = false

[purchases]
product_ids = []
subscription_group = "pro"

[store]
locales = ["en-US", "vi"]

[analytics]
ga4_property = ""
bq_project = ""

[i18n]
languages = ["en"]
"""

# Một bản metadata "viết thật" hợp lệ (không chữ giữ chỗ).
THAT = {
    "app-info/en-US.json": {"name": "Ghi Chu", "subtitle": "Quick notes", "privacyPolicyUrl": f"https://{HOST}/privacy/"},
    "version/1.0.0/en-US.json": {
        "description": "Write notes fast.", "keywords": "memo,jot,pad", "marketingUrl": f"https://{HOST}/",
        "promotionalText": "Fresh and quick.", "supportUrl": f"https://{HOST}/support/", "whatsNew": "First release."},
}


class LintTests(unittest.TestCase):
    def repo(self, files=None, config=CONFIG):
        d = tempfile.TemporaryDirectory(prefix="kho lint ")
        self.addCleanup(d.cleanup)
        root = Path(d.name)
        (root / "app.config.toml").write_text(config, encoding="utf-8")
        for rel, data in (THAT if files is None else files).items():
            p = root / "store" / "metadata" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return root

    def lint(self, root, banned=()):
        return aso_lint.lint(root, "1.0.0", banned=list(banned))

    def sua(self, scope_file, **doi):
        """THAT với `doi` ghi đè vào một file."""
        files = json.loads(json.dumps(THAT))
        files[scope_file].update(doi)
        return files

    def test_khung_sinh_ra_bi_lint_tu_choi_vi_chu_giu_cho(self):
        files = {
            "app-info/en-US.json": {"name": "Ghi Chu", "subtitle": "", "privacyPolicyUrl": f"https://{HOST}/privacy/"},
            "version/1.0.0/en-US.json": {
                "description": f"{aso_lint.PLACEHOLDER} — describe the app here.", "keywords": aso_lint.PLACEHOLDER,
                "marketingUrl": f"https://{HOST}/", "promotionalText": f"{aso_lint.PLACEHOLDER} — x",
                "supportUrl": f"https://{HOST}/support/", "whatsNew": f"{aso_lint.PLACEHOLDER} — y"},
        }
        loi = self.lint(self.repo(files))
        self.assertEqual(len(loi), 4, loi)
        self.assertTrue(all(aso_lint.PLACEHOLDER in x for x in loi), loi)

    def test_dien_chu_that_thi_lint_xanh(self):
        root = self.repo()
        self.assertEqual(self.lint(root), [])
        self.assertEqual([i for i in aso_lint.lint_report(root, "1.0.0", banned=[]) if i.severity == "error"], [])

    def test_keywords_dem_byte_utf8(self):
        kw = ("間取り図" * 9)[:34]
        self.assertEqual(len(kw), 34)
        self.assertEqual(len(kw.encode("utf-8")), 102)
        loi = self.lint(self.repo(self.sua("version/1.0.0/en-US.json", keywords=kw)))
        self.assertTrue([x for x in loi if "keywords" in x and "byte" in x], loi)
        # tiếng Việt có dấu: 34 ký tự nhưng > 100 byte
        vi = "ưỡ" * 20 + "ab"
        self.assertLessEqual(len(vi), 100)
        self.assertGreater(len(vi.encode("utf-8")), 100)
        self.assertTrue(self.lint(self.repo(self.sua("version/1.0.0/en-US.json", keywords=vi))))
        # đúng 100 byte ASCII thì xanh
        self.assertEqual(self.lint(self.repo(self.sua("version/1.0.0/en-US.json", keywords="a" * 100))), [])

    def test_qua_gioi_han_ky_tu(self):
        for scope_file, field, limit in (("app-info/en-US.json", "name", 30), ("app-info/en-US.json", "subtitle", 30),
                                         ("version/1.0.0/en-US.json", "promotionalText", 170),
                                         ("version/1.0.0/en-US.json", "description", 4000),
                                         ("version/1.0.0/en-US.json", "whatsNew", 4000)):
            with self.subTest(field=field):
                dung = self.repo(self.sua(scope_file, **{field: "x" * limit}))
                self.assertEqual(self.lint(dung), [])
                loi = self.lint(self.repo(self.sua(scope_file, **{field: "x" * (limit + 1)})))
                self.assertEqual(len(loi), 1, loi)
                self.assertIn(f"vượt giới hạn {limit}", loi[0])
        # đếm ký tự Unicode, không đếm byte: 30 chữ có dấu vẫn đạt
        self.assertEqual(self.lint(self.repo(self.sua("app-info/en-US.json", name="ễ" * 30))), [])

    def test_url_host_dev_bi_tu_choi(self):
        loi = self.lint(self.repo(self.sua("version/1.0.0/en-US.json", supportUrl=f"https://dev.{HOST}/support/")))
        self.assertEqual(len(loi), 1, loi)
        self.assertIn("host dev", loi[0])
        # URL nằm trong văn xuôi cũng bị bắt
        loi2 = self.lint(self.repo(self.sua("version/1.0.0/en-US.json", description=f"See https://dev.{HOST}/x for more.")))
        self.assertTrue([x for x in loi2 if "host dev" in x], loi2)

    def test_url_thieu_host_hoac_con_bien_la_loi_ke_ca_khi_khong_khai_host(self):
        khong_host = CONFIG.replace(f'host_prod = "{HOST}"', 'host_prod = ""').replace(
            f'host_dev = "dev.{HOST}"', 'host_dev = ""')
        for url in ("https:///privacy/", "https://$host_prod/privacy/", f"https://{HOST}/$slug/"):
            for config in (CONFIG, khong_host):
                with self.subTest(url=url, co_host=config is CONFIG):
                    root = self.repo(self.sua("app-info/en-US.json", privacyPolicyUrl=url), config=config)
                    loi = self.lint(root)
                    self.assertEqual(len(loi), 1, loi)
                    self.assertIn("thiếu host hoặc còn biến", loi[0])
        # không khai host + URL bình thường ⇒ không lỗi, không cảnh báo
        root = self.repo(config=khong_host)
        self.assertEqual(aso_lint.lint_report(root, "1.0.0", banned=[]), [])

    def test_url_khac_host_prod_chi_canh_bao(self):
        # marketingUrl / URL trong văn xuôi trỏ host khác: chỉ cảnh báo
        la = "nguoi" + "-la.app"
        root = self.repo(self.sua("version/1.0.0/en-US.json", marketingUrl=f"https://{la}/help"))
        self.assertEqual(self.lint(root), [], "cảnh báo không làm lint đỏ")
        warn = [i for i in aso_lint.lint_report(root, "1.0.0", banned=[]) if i.severity == "warning"]
        self.assertEqual(len(warn), 1)
        self.assertIn(la, warn[0].message)

    def test_privacy_va_support_khac_host_prod_la_loi(self):
        la = "nguoi" + "-la.app"
        for scope_file, field in (("app-info/en-US.json", "privacyPolicyUrl"), ("version/1.0.0/en-US.json", "supportUrl")):
            with self.subTest(field=field):
                loi = self.lint(self.repo(self.sua(scope_file, **{field: f"https://{la}/x"})))
                self.assertEqual(len(loi), 1, loi)
                self.assertIn(f"{field} không trỏ host prod ({HOST})", loi[0])
                # www.<host_prod> là cùng site: không lỗi, không cảnh báo
                root = self.repo(self.sua(scope_file, **{field: f"https://www.{HOST}/x"}))
                self.assertEqual(aso_lint.lint_report(root, "1.0.0", banned=[]), [])
                # tên miền con khác (không phải www) vẫn là lỗi
                self.assertEqual(len(self.lint(self.repo(self.sua(scope_file, **{field: f"https://help.{HOST}/x"})))), 1)
        # chiều ngược lại: host_prod = www.<host của URL>
        config = CONFIG.replace(f'host_prod = "{HOST}"', f'host_prod = "www.{HOST}"')
        self.assertEqual(aso_lint.lint_report(self.repo(config=config), "1.0.0", banned=[]), [])

    def test_url_host_giu_cho_la_loi_ke_ca_khi_la_host_prod(self):
        # Template để `web.host_prod = "example.com"`: app giữ nguyên ⇒ URL khung sinh ra phải đỏ, không chỉ cảnh báo.
        for host in ("example.com", "www.example.com", "example.net", "a.example.org", "thu.example", "thu.test",
                     "thu.invalid", "localhost", "thu.localhost", "EXAMPLE.COM"):
            config = CONFIG.replace(f'host_prod = "{HOST}"', f'host_prod = "{host}"').replace(
                f'host_dev = "dev.{HOST}"', f'host_dev = "dev.{host}"')
            for scope_file, field in (("app-info/en-US.json", "privacyPolicyUrl"),
                                      ("version/1.0.0/en-US.json", "marketingUrl")):
                with self.subTest(host=host, field=field):
                    files = self.sua(scope_file, **{field: f"https://{host}/x"})
                    loi = self.lint(self.repo(files, config=config))
                    self.assertTrue([x for x in loi if "host giữ chỗ/dành riêng" in x and field in x], loi)
        # host thật trùng tên một phần không bị bắt
        for host in ("example.community", "myexample.com", "test.app", "invalid.dev"):
            with self.subTest(host=host):
                self.assertFalse(aso_lint.is_reserved_host(host))

    def test_notes_apple_review_giu_cho_qua_dai_xuong_dong_la_loi(self):
        root = self.repo()
        notes = root / "store" / "review" / "notes.txt"
        self.assertEqual(self.lint(root), [], "không có notes.txt ⇒ không soi")
        notes.parent.mkdir(parents=True)
        notes.write_text(f"{aso_lint.PLACEHOLDER} — write the notes here.", encoding="utf-8")
        loi = self.lint(root)
        self.assertEqual(len(loi), 1, loi)
        self.assertIn("review/notes.txt", loi[0])
        self.assertIn(aso_lint.PLACEHOLDER, loi[0])
        # dài quá quy ước 384 / xuống dòng cuối: chỉ CẢNH BÁO (ô của Apple nhận dài hơn) — lint không đỏ
        def warns():
            return [str(i) for i in aso_lint.lint_report(root, "1.0.0", banned=[]) if i.severity == "warning"]
        notes.write_text("Open the app and tap New.\n", encoding="utf-8")
        self.assertEqual(self.lint(root), [])
        self.assertTrue([x for x in warns() if "xuống dòng cuối" in x], warns())
        notes.write_text("x" * 385, encoding="utf-8")
        self.assertEqual(self.lint(root), [])
        self.assertTrue([x for x in warns() if "quy ước 384" in x], warns())
        notes.write_text("ễ" * 384, encoding="utf-8")
        self.assertEqual(aso_lint.lint_report(root, "1.0.0", banned=[]), [])

    def test_chu_cam_doc_tu_lint_toml(self):
        root = self.repo(self.sua("version/1.0.0/en-US.json", description="Works Ngoại Tuyến, no sign-in."))
        self.assertEqual(aso_lint.load_banned(root), [], "không có store/lint.toml ⇒ không cấm gì")
        self.assertEqual(self.lint(root, aso_lint.load_banned(root)), [])
        (root / "store" / "lint.toml").write_text('banned = ["ngoại tuyến", "no sign-in"]\n', encoding="utf-8")
        cam = aso_lint.load_banned(root)
        self.assertEqual(cam, ["ngoại tuyến", "no sign-in"])
        loi = self.lint(root, cam)
        self.assertEqual(len(loi), 2, loi)       # không phân biệt hoa/thường
        # lõi không mang từ cấm sẵn
        self.assertEqual(aso_lint.lint_values({("version", "en-US", "description"): "offline"}), [])

    def test_lint_toml_sai_dang_bi_tu_choi(self):
        root = self.repo()
        (root / "store" / "lint.toml").write_text('banned = "offline"\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            aso_lint.load_banned(root)
        (root / "store" / "lint.toml").write_text("banned = [\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            aso_lint.load_banned(root)

    def test_version_va_versions_cung_luc_loi(self):
        root = self.repo()
        p = root / "store" / "metadata" / "versions" / "1.0.0"
        p.mkdir(parents=True)
        (p / "en-US.json").write_text(json.dumps(THAT["version/1.0.0/en-US.json"]), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.lint(root)

    def test_keywords_dau_phay_cach_va_trung_tieu_de(self):
        loi = self.lint(self.repo(self.sua("version/1.0.0/en-US.json", keywords="memo, jot")))
        self.assertTrue([x for x in loi if "dấu cách" in x], loi)
        loi2 = self.lint(self.repo(self.sua("version/1.0.0/en-US.json", keywords="quick,memo")))
        self.assertTrue([x for x in loi2 if "'quick'" in x], loi2)
        # locale khác không bị ảnh hưởng bởi name/subtitle của en-US
        files = self.sua("version/1.0.0/en-US.json")
        files["version/1.0.0/vi.json"] = {"keywords": "quick"}
        self.assertFalse([x for x in self.lint(self.repo(files)) if "vi/" in x])

    def test_todo_tbd_lorem_nhung_khong_bat_tu_chua_chung(self):
        for chu in ("Mô tả TODO sau", "tbd", "Lorem ipsum"):
            with self.subTest(chu=chu):
                self.assertTrue(self.lint(self.repo(self.sua("version/1.0.0/en-US.json", description=chu))))
        self.assertEqual(self.lint(self.repo(self.sua("version/1.0.0/en-US.json", description="mastodon"))), [])

    def test_hang_so_giu_dung_hop_dong(self):
        self.assertEqual(aso_lint.LIMITS, {"name": 30, "subtitle": 30, "promotionalText": 170,
                                           "description": 4000, "whatsNew": 4000})
        self.assertEqual(aso_lint.KEYWORDS_BYTES, 100)
        self.assertEqual(aso_lint.PLACEHOLDER, "TEMPLATE-PLACEHOLDER")


if __name__ == "__main__":
    unittest.main()
