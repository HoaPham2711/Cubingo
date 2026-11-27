"""Test cho web/tools/check_site.py — repo tạm, không đụng repo thật (trừ một test CHỈ ĐỌC cây thật)."""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import check_site  # noqa: E402
from webtest_kit import CONFIG, make_repo, page, write  # noqa: E402

PUB = "web/site/public/"
PRIVACY_ALL = page("privacy", '<section data-feature="paywall">p</section>\n<section data-feature="web_api">w</section>\n'
                              '<section data-feature="purchase_records">r</section>\n'
                              '<section data-feature="apple_ads">a</section>')
SCRIPT = '<script type="module" src="/m.js"></script>'
# Cấu hình "đã điền thật" cho đường --release: host/e-mail không thuộc tên miền dành riêng (example.com, *.test…).
REAL = CONFIG.replace('host_prod = "example.com"', 'host_prod = "demo-site.net"').replace(
    'host_dev = "dev.example.com"', 'host_dev = "dev.demo-site.net"').replace("help@example.com", "help@demo-site.net")


def tat(*switches):
    text = CONFIG
    for s in switches:
        text = text.replace(f"{s} = true", f"{s} = false")
    return text


class CheckSiteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.n = 0

    def repo(self, config=CONFIG, privacy=PRIVACY_ALL, extra=None):
        self.n += 1
        base = self.base / str(self.n)
        base.mkdir()
        files = {PUB + "index.html": page("home", SCRIPT), PUB + "privacy/index.html": privacy,
                 PUB + "terms/index.html": page("terms"), PUB + "support/index.html": page("support")}
        files.update(extra or {})
        return make_repo(base, files, config)

    def test_site_dung_qua(self):
        self.assertEqual(check_site.check(self.repo()), ([], []))
        self.assertEqual(check_site.main(["--root", str(self.repo(config=REAL)), "--release"]), 0)

    def test_release_tu_choi_host_va_email_giu_cho(self):
        # Host/e-mail dành riêng (RFC 2606/6761) chỉ là giá trị giữ chỗ: lỗi với --release, im khi không.
        root = self.repo()
        self.assertEqual(check_site.check(root), ([], []))
        errors, _ = check_site.check(root, release=True)
        self.assertTrue(any("web.host_prod" in e and "example.com" in e for e in errors), errors)
        self.assertTrue(any("support.email" in e for e in errors), errors)
        for host in ("app.test", "shop.invalid", "localhost", "a.example.org"):
            cfg = REAL.replace('host_prod = "demo-site.net"', f'host_prod = "{host}"')
            errors, _ = check_site.check(self.repo(config=cfg), release=True)
            self.assertTrue(any("web.host_prod" in e for e in errors), (host, errors))

    def test_release_canonical_va_mailto_phai_khop_cau_hinh(self):
        good = page("s", '<link rel="canonical" href="https://demo-site.net/support/">\n'
                         '<a href="mailto:help@demo-site.net">mail</a>')
        self.assertEqual(check_site.check(self.repo(config=REAL, extra={PUB + "support/index.html": good}),
                                          release=True), ([], []))
        stale = good.replace("https://demo-site.net/", "https://old-site.net/").replace("help@demo-site.net", "old@demo-site.net")
        root = self.repo(config=REAL, extra={PUB + "support/index.html": stale})
        errors, _ = check_site.check(root, release=True)
        self.assertTrue(any("canonical" in e and "old-site.net" in e for e in errors), errors)
        self.assertTrue(any("mailto" in e and "old@demo-site.net" in e for e in errors), errors)
        self.assertEqual(check_site.check(root)[0], [])

    def test_thieu_trang_bat_bien_bi_bao(self):
        root = self.repo()
        (root / PUB / "terms/index.html").unlink()
        errors, _ = check_site.check(root)
        self.assertTrue(any("terms/index.html" in e for e in errors), errors)
        self.assertEqual(check_site.main(["--root", str(root)]), 1)

    def test_check_site_placeholder_loi_khi_release(self):
        root = self.repo(extra={PUB + "support/index.html": page("s", "<p>TEMPLATE-PLACEHOLDER: FAQ</p>")})
        errors, warnings = check_site.check(root)
        self.assertEqual(errors, [])
        self.assertTrue(any("support/index.html" in w and "TEMPLATE-PLACEHOLDER" in w for w in warnings), warnings)
        self.assertEqual(check_site.main(["--root", str(root)]), 0)
        errors, _ = check_site.check(root, release=True)
        self.assertTrue(any("support/index.html" in e for e in errors), errors)
        self.assertEqual(check_site.main(["--root", str(root), "--release"]), 1)

    def test_check_site_privacy_lech_cong_tac(self):
        # Công tắc tắt mà trang còn khối ⇒ lỗi.
        errors, _ = check_site.check(self.repo(config=tat("paywall")))
        self.assertTrue(any('"paywall"' in e for e in errors), errors)
        # Công tắc bật mà trang thiếu khối ⇒ lỗi.
        thieu = PRIVACY_ALL.replace('<section data-feature="apple_ads">a</section>', "")
        errors, _ = check_site.check(self.repo(privacy=thieu))
        self.assertTrue(any("apple_ads" in e for e in errors), errors)
        # Khớp sau khi cắt ⇒ qua.
        self.assertEqual(check_site.check(self.repo(config=tat("apple_ads"), privacy=thieu))[0], [])
        # Giá trị lạ ⇒ lỗi.
        la = PRIVACY_ALL.replace("</body>", '<p data-feature="khac">x</p>\n</body>')
        errors, _ = check_site.check(self.repo(privacy=la))
        self.assertTrue(any("khac" in e for e in errors), errors)

    def test_check_site_khoi_mua_hang_server_theo_ca_hai_cong_tac(self):
        # paywall + web_api bật ⇒ server lưu thông báo mua hàng ⇒ privacy PHẢI có phần purchase_records.
        thieu = PRIVACY_ALL.replace('<section data-feature="purchase_records">r</section>', "")
        errors, _ = check_site.check(self.repo(privacy=thieu))
        self.assertTrue(any("purchase_records" in e for e in errors), errors)
        # Chỉ một công tắc bật ⇒ server không lưu gì ⇒ phần đó KHÔNG được có.
        chi_paywall = PRIVACY_ALL.replace('<section data-feature="web_api">w</section>', "")
        errors, _ = check_site.check(self.repo(config=tat("web_api"), privacy=chi_paywall.replace(SCRIPT, "")))
        self.assertTrue(any("purchase_records" in e for e in errors), errors)
        ok = chi_paywall.replace('<section data-feature="purchase_records">r</section>', "")
        self.assertEqual(check_site.check(self.repo(config=tat("web_api"), privacy=ok,
                                                    extra={PUB + "index.html": page("home")}))[0], [])

    def test_check_site_m_js_khi_tat_web_api(self):
        privacy = PRIVACY_ALL.replace('<section data-feature="web_api">w</section>', "").replace(
            '<section data-feature="purchase_records">r</section>', "")
        root = self.repo(config=tat("web_api"), privacy=privacy)
        errors, _ = check_site.check(root)
        self.assertTrue(any("m.js" in e and "index.html" in e for e in errors), errors)
        write(root, PUB + "index.html", page("home"))
        self.assertEqual(check_site.check(root)[0], [])

    def test_dau_khoi_va_bien_gieo_con_sot_bi_bao(self):
        root = self.repo(extra={PUB + "terms/index.html": page("t", "<!-- feature:paywall:begin -->\n<p>$display_name</p>")})
        errors, _ = check_site.check(root)
        self.assertTrue(any("feature:" in e and "sync_core.py" in e for e in errors), errors)  # gợi ý tool đúng
        self.assertTrue(any("$display_name" in e for e in errors), errors)

    def test_khong_co_web_thi_bo_qua(self):
        base = self.base / "rong"
        base.mkdir()
        self.assertEqual(check_site.main(["--root", str(make_repo(base, {}))]), 0)

    def test_site_cua_repo_nay_qua_khong_release(self):
        # CHỈ ĐỌC cây thật: trang gieo của repo này phải qua cổng (placeholder chỉ là cảnh báo khi không --release).
        if not (REPO / PUB).is_dir():
            self.skipTest("repo không có web/site/public")
        self.assertEqual(check_site.check(REPO)[0], [])


if __name__ == "__main__":
    unittest.main()
