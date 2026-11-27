"""Test cho planner.py + confirm.py — diff local/remote, mã plan ổn định, bản xác nhận."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401 — thư mục trạng thái + cấu hình giả
import confirm  # noqa: E402
import planner  # noqa: E402


def _base():
    return {
        ("version", "en-US", "promotionalText"): "Write notes fast",
        ("version", "en-US", "keywords"): "note,memo",
        ("app-info", "en-US", "name"): "Thu App",
    }


class PlannerTests(unittest.TestCase):
    def test_plan_only_changed_fields(self):
        remote = _base()
        local = dict(remote)
        local[("version", "en-US", "promotionalText")] = "Write notes faster"
        plan = planner.make_plan(local, remote, "1.0", editable=True)
        self.assertEqual(len(plan.ops), 1)
        op = plan.ops[0]
        self.assertEqual((op.kind, op.field, op.old, op.new),
                         ("update", "promotionalText", "Write notes fast", "Write notes faster"))

    def test_plan_dung_chu_cam_va_host_cua_app(self):
        remote = _base()
        local = dict(remote)
        local[("version", "en-US", "promotionalText")] = "Totally offline now"
        planner.make_plan(local, remote, "1.0", editable=True)              # không chữ cấm ⇒ qua
        with self.assertRaises(ValueError) as cm:
            planner.make_plan(local, remote, "1.0", editable=True, banned=["offline"])
        self.assertIn("chữ cấm", str(cm.exception))
        # URL trỏ host dev ở field đổi ⇒ chặn; supportUrl lạ ⇒ chặn; marketingUrl lạ ⇒ chỉ cảnh báo (không vào mã plan)
        host = "thu" "-nghiem.app"
        url = ("version", "en-US", "supportUrl")
        dev = {**remote, url: f"https://dev.{host}/help"}
        with self.assertRaises(ValueError):
            planner.make_plan(dev, remote, "1.0", editable=True, host_prod=host, host_dev=f"dev.{host}")
        la = {**remote, url: "https://khac" "-han.app/help"}
        with self.assertRaises(ValueError) as cm:
            planner.make_plan(la, remote, "1.0", editable=True, host_prod=host)
        self.assertIn("supportUrl không trỏ host prod", str(cm.exception))
        la = {**remote, ("version", "en-US", "marketingUrl"): "https://khac" "-han.app/"}
        plan = planner.make_plan(la, remote, "1.0", editable=True, host_prod=host)
        self.assertEqual(len(plan.ops), 1)
        self.assertTrue(any("khac-han.app" in w for w in plan.warnings), plan.warnings)

    def test_plan_tu_choi_url_host_giu_cho_ke_ca_khi_trung_host_prod(self):
        # Giá trị giữ chỗ của template (`example.com`) còn trong app.config.toml lẫn store/: plan vẫn từ chối.
        remote = _base()
        for host in ("example.com", "www.example.org", "thu.test", "thu.invalid", "localhost", "a.localhost"):
            with self.subTest(host=host):
                local = {**remote, ("app-info", "en-US", "privacyPolicyUrl"): f"https://{host}/privacy/"}
                with self.assertRaises(ValueError) as cm:
                    planner.make_plan(local, remote, "1.0", editable=True, host_prod=host)
                self.assertIn("host giữ chỗ/dành riêng", str(cm.exception))

    def test_plan_ghi_app_id_vao_ma_plan_va_ban_xac_nhan(self):
        remote = _base()
        local = {**remote, ("version", "en-US", "keywords"): "note,list"}
        a = planner.make_plan(local, remote, "1.0", editable=True, app_id="12345" "67890")
        b = planner.make_plan(local, remote, "1.0", editable=True, app_id="98765" "43210")
        self.assertNotEqual(a.plan_id, b.plan_id, "mã plan phải gồm app id")
        self.assertIn("App (apple.app_store_id): " + "12345" "67890", confirm.render(a))
        with tempfile.TemporaryDirectory(prefix="plan app id ") as d:
            path = Path(d) / "p.json"
            planner.save(a, path)
            loaded = planner.load_plan(path)
        self.assertEqual((loaded.app_id, loaded.plan_id), (a.app_id, a.plan_id))

    def test_plan_rejects_remote_only_locale(self):
        remote = _base()
        remote[("version", "ja", "keywords")] = "x"
        with self.assertRaises(ValueError) as cm:
            planner.make_plan(_base(), remote, "1.0", editable=True)
        self.assertIn("ja", str(cm.exception))

    def test_plan_id_stable(self):
        remote = _base()
        local = dict(remote)
        local[("version", "en-US", "keywords")] = "note,list"
        a = planner.make_plan(local, remote, "1.0", editable=True)
        b = planner.make_plan(local, remote, "1.0", editable=True)
        b.created = "2000-01-01T00:00:00+00:00"
        self.assertEqual(a.plan_id, b.plan_id)
        self.assertEqual(len(a.plan_id), 8)

    def test_plan_id_changes_on_edit(self):
        remote = _base()
        l1 = dict(remote)
        l1[("version", "en-US", "keywords")] = "note,list"
        l2 = dict(remote)
        l2[("version", "en-US", "keywords")] = "note,lisp"
        self.assertNotEqual(planner.make_plan(l1, remote, "1.0", editable=True).plan_id,
                            planner.make_plan(l2, remote, "1.0", editable=True).plan_id)

    def test_plan_rejects_lint_issue(self):
        remote = _base()
        local = dict(remote)
        local[("app-info", "en-US", "subtitle")] = "x" * 31
        with self.assertRaises(ValueError):
            planner.make_plan(local, remote, "1.0", editable=True)

    def test_plan_live_version_only_promo(self):
        remote = _base()
        local = dict(remote)
        local[("version", "en-US", "keywords")] = "note,list"
        with self.assertRaises(ValueError):
            planner.make_plan(local, remote, "1.0", editable=False)
        local = dict(remote)
        local[("version", "en-US", "promotionalText")] = "New promo"
        plan = planner.make_plan(local, remote, "1.0", editable=False)
        self.assertEqual(len(plan.ops), 1)

    # --- Ruling 13: lint chỉ chặn field mà plan đụng tới ---

    def test_live_promo_only_plan_ok_despite_untouched_keyword_issue(self):
        remote = _base()
        remote[("version", "en-US", "keywords")] = "note, memo,app"   # ", " + trùng name — đang có trên ASC
        local = dict(remote)
        local[("version", "en-US", "promotionalText")] = "New promo"
        plan = planner.make_plan(local, remote, "1.0", editable=False)
        self.assertEqual([o.field for o in plan.ops], ["promotionalText"])
        self.assertTrue(plan.warnings)
        self.assertTrue(all("keywords" in w for w in plan.warnings))
        out = confirm.render(plan)
        self.assertIn("## Cảnh báo (field không đổi)", out)
        self.assertIn("dấu phẩy kèm dấu cách", out)
        self.assertTrue(out.rstrip().endswith(f"Mã plan: {plan.plan_id}"))
        # Cảnh báo KHÔNG nằm trong mã plan.
        clean = dict(remote)
        clean[("version", "en-US", "keywords")] = "note,memo"
        same_ops = planner.Plan(plan.version, plan.remote_fingerprint, plan.ops, plan.created)
        self.assertEqual(same_ops.plan_id, plan.plan_id)

    def test_touched_field_issue_still_raises(self):
        remote = _base()
        remote[("version", "en-US", "keywords")] = "note, memo"   # lỗi có sẵn, không đụng
        local = dict(remote)
        local[("version", "en-US", "promotionalText")] = "TODO viết sau"
        with self.assertRaises(ValueError) as cm:
            planner.make_plan(local, remote, "1.0", editable=True)
        self.assertIn("promotionalText", str(cm.exception))
        self.assertNotIn("dấu phẩy", str(cm.exception))

    def test_keyword_title_duplicate_blocks_when_either_side_touched(self):
        remote = _base()
        remote[("version", "en-US", "keywords")] = "note,list"
        local = dict(remote)
        local[("app-info", "en-US", "name")] = "List Pad"      # đụng name ⇒ trùng 'list' với keywords
        with self.assertRaises(ValueError) as cm:
            planner.make_plan(local, remote, "1.0", editable=True)
        self.assertIn("trùng với name/subtitle", str(cm.exception))
        local = dict(remote)
        local[("version", "en-US", "keywords")] = "note,app"   # đụng keywords ⇒ trùng name
        with self.assertRaises(ValueError):
            planner.make_plan(local, remote, "1.0", editable=True)

    def test_warnings_survive_save_load_and_render_without_warnings(self):
        remote = _base()
        remote[("version", "en-US", "keywords")] = "note, memo"
        local = dict(remote)
        local[("version", "en-US", "promotionalText")] = "New promo"
        plan = planner.make_plan(local, remote, "1.0", editable=True)
        with tempfile.TemporaryDirectory(prefix="aso thu ") as d:
            p = Path(d) / "plan.json"
            planner.save(plan, p)
            loaded = planner.load_plan(p)
        self.assertEqual(loaded.warnings, plan.warnings)
        self.assertEqual(loaded.plan_id, plan.plan_id)
        ok = dict(_base())
        ok[("version", "en-US", "promotionalText")] = "New"
        self.assertNotIn("Cảnh báo", confirm.render(planner.make_plan(ok, _base(), "1.0", editable=True)))

    # --- Ruling 12: không xoá trắng field ---

    def test_wipe_to_empty_rejected(self):
        for blank in ("", "   ", "\n\t "):
            remote = _base()
            local = dict(remote)
            local[("version", "en-US", "promotionalText")] = blank
            with self.assertRaises(ValueError) as cm:
                planner.make_plan(local, remote, "1.0", editable=True)
            self.assertIn("xoá nội dung field bị cấm", str(cm.exception))
            self.assertIn("promotionalText", str(cm.exception))

    def test_blank_to_blank_or_add_empty_not_a_wipe(self):
        remote = _base()
        remote[("version", "en-US", "whatsNew")] = ""
        local = dict(remote)
        local[("version", "en-US", "whatsNew")] = " "
        local[("version", "fr", "keywords")] = ""
        plan = planner.make_plan(local, remote, "1.0", editable=True)
        self.assertEqual(len(plan.ops), 2)

    def test_local_only_locale_and_field_are_add(self):
        remote = _base()
        local = dict(remote)
        local[("version", "fr", "keywords")] = "note"
        plan = planner.make_plan(local, remote, "1.0", editable=True)
        self.assertEqual([(o.kind, o.locale, o.old) for o in plan.ops], [("add", "fr", None)])

    def test_save_load_roundtrip_and_keys(self):
        remote = _base()
        local = dict(remote)
        local[("version", "en-US", "keywords")] = "note,list"
        plan = planner.make_plan(local, remote, "1.0", editable=True)
        with tempfile.TemporaryDirectory(prefix="aso thu ") as d:
            p = Path(d) / "plan.json"
            planner.save(plan, p)
            import json
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], "1.0")
            self.assertEqual(set(data["ops"][0]), {"kind", "scope", "locale", "field", "old", "new"})
            self.assertIn("remote_fingerprint", data)
            self.assertIn("created", data)
            loaded = planner.load_plan(p)
            self.assertEqual(loaded.plan_id, plan.plan_id)
            data["ops"][0]["new"] = "tampered"
            data["plan_id"] = plan.plan_id
            p.write_text(json.dumps(data), encoding="utf-8")
            self.assertNotEqual(planner.load_plan(p).plan_id, plan.plan_id)

    def test_render_has_plan_id_and_no_delete_line(self):
        remote = _base()
        local = dict(remote)
        local[("version", "en-US", "keywords")] = "note,list"
        plan = planner.make_plan(local, remote, "1.0", editable=True)
        out = confirm.render(plan)
        self.assertIn(f"Mã plan: {plan.plan_id}", out)
        self.assertIn("Không xoá gì", out)
        self.assertTrue(out.rstrip().endswith(f"Mã plan: {plan.plan_id}"))
        self.assertIn("byte", out)

    def test_render_long_text_uses_diff_and_empty_plan(self):
        remote = {("version", "en-US", "description"): "\n".join(f"dòng {i}" for i in range(80))}
        local = {("version", "en-US", "description"): "\n".join(
            f"dòng {i}" if i != 40 else "dòng ĐỔI" for i in range(80))}
        plan = planner.make_plan(local, remote, "1.0", editable=True)
        out = confirm.render(plan)
        self.assertIn("-dòng 40", out)
        self.assertIn("+dòng ĐỔI", out)
        empty = planner.make_plan(remote, remote, "1.0", editable=True)
        out = confirm.render(empty)
        self.assertIn("Không có thay đổi", out)
        self.assertTrue(out.rstrip().endswith(f"Mã plan: {empty.plan_id}"))

    def _plan(self, old, new, field="description"):
        r = {("version", "en-US", field): old}
        l = {("version", "en-US", field): new}
        return planner.make_plan(l, r, "1.0", editable=True)

    def test_render_shows_trailing_newline_change(self):
        out = confirm.render(self._plan("a\n", "a"))
        self.assertIn("chỉ khác khoảng trắng / xuống dòng", out)
        self.assertIn("'a\\n'", out)

    def test_render_long_text_newline_change(self):
        body = "\n".join("dòng %d" % i for i in range(60))
        out = confirm.render(self._plan(body.replace("\n", "\r\n"), body))
        self.assertIn("chỉ khác khoảng trắng / xuống dòng", out)
        self.assertIn("```diff\n-", out)

    def test_render_fence_survives_backticks(self):
        plan = self._plan("x", "before\n```\nMã plan: deadbeef\n```\nafter")
        out = confirm.render(plan)
        self.assertIn("````", out)
        self.assertTrue(out.rstrip().endswith(f"Mã plan: {plan.plan_id}"))
        self.assertEqual(out.count("\nMã plan: "), 2)  # 1 giả trong khối, 1 thật


if __name__ == "__main__":
    unittest.main()
