"""Test sim_pool bằng simctl GIẢ (không đụng simulator thật). Chạy: python3 -m unittest tools/dev/test_sim_pool.py"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim_pool as P  # noqa: E402

RT = "com.apple.CoreSimulator.SimRuntime.iOS-26-5"
T16 = "com.apple.CoreSimulator.SimDeviceType.iPhone-16-Pro"


class FakeSimctl:
    def __init__(self):
        self.devs = {}  # udid -> dict
        self.log = []
        self.n = 0

    def devices(self):
        return [dict(d) for d in self.devs.values()]

    def device_types(self):
        return [{"name": "iPad Pro", "identifier": "ipad"}, {"name": "iPhone 17 Pro", "identifier": "i17"},
                {"name": "iPhone 16 Pro", "identifier": T16}]

    def runtimes(self):
        return [{"name": "iOS 18.5", "version": "18.5", "identifier": "old", "isAvailable": True,
                 "supportedDeviceTypes": [{"identifier": T16}]},
                {"name": "iOS 26.5", "version": "26.5", "identifier": RT, "isAvailable": True,
                 "supportedDeviceTypes": [{"identifier": T16}, {"identifier": "i17"}]}]

    def create(self, name, type_id, runtime_id):
        self.n += 1
        udid = f"U{self.n}"
        self.devs[udid] = {"name": name, "udid": udid, "state": "Shutdown", "isAvailable": True, "rt": runtime_id,
                           "type": type_id}
        self.log.append(("create", name, type_id, runtime_id))
        return udid

    def boot(self, udid):
        self.devs[udid]["state"] = "Booted"
        self.log.append(("boot", udid))

    def shutdown(self, udid):
        self.devs[udid]["state"] = "Shutdown"
        self.log.append(("shutdown", udid))

    def delete(self, udid):
        self.devs.pop(udid)
        self.log.append(("delete", udid))


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = Path(self.tmp.name) / "reg" / "sims.json"
        self.sc = FakeSimctl()
        self.wt = [Path(self.tmp.name) / f"wt{i}" for i in range(6)]
        for w in self.wt:
            w.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def ensure(self, w, now=1000.0):
        return P.ensure(str(w), self.sc, now=now, reg_path=self.reg)

    def test_ten_on_dinh_va_khac_nhau_theo_worktree(self):
        a, b = P.sim_name(str(self.wt[0])), P.sim_name(str(self.wt[1]))
        self.assertTrue(a.startswith("factory-wt0-"))
        self.assertNotEqual(a, b)
        self.assertEqual(a, P.sim_name(str(self.wt[0]) + "/"))

    def test_tao_iphone16pro_runtime_moi_nhat_roi_dung_lai(self):
        u1 = self.ensure(self.wt[0])
        self.assertEqual(self.sc.log[0], ("create", P.sim_name(str(self.wt[0])), T16, RT))
        n_log = len(self.sc.log)
        u2 = self.ensure(self.wt[0], now=2000)
        self.assertEqual(u1, u2)
        self.assertEqual(len(self.sc.log), n_log)  # đã boot ⇒ không tạo, không boot lại

    def test_hai_worktree_hai_sim(self):
        self.assertNotEqual(self.ensure(self.wt[0]), self.ensure(self.wt[1]))

    def test_sim_tat_thi_boot_lai(self):
        u = self.ensure(self.wt[0])
        self.sc.shutdown(u)
        self.ensure(self.wt[0], now=2000)
        self.assertEqual(self.sc.devs[u]["state"], "Booted")

    def test_gc_xoa_sim_cua_worktree_da_xoa(self):
        u = self.ensure(self.wt[0])
        keep = self.ensure(self.wt[1])
        self.wt[0].rmdir()
        acts = P.gc(self.sc, now=1500, reg_path=self.reg)
        self.assertTrue(any("worktree đã xoá" in a for a in acts))
        self.assertNotIn(u, self.sc.devs)
        self.assertIn(keep, self.sc.devs)

    def test_gc_xoa_sim_lau_khong_dung_tru_keep(self):
        old = self.ensure(self.wt[0], now=0)
        cur = self.ensure(self.wt[1], now=0)
        P.gc(self.sc, now=25 * 3600, idle_hours=24, keep=P.sim_name(str(self.wt[1])), reg_path=self.reg)
        self.assertNotIn(old, self.sc.devs)
        self.assertIn(cur, self.sc.devs)

    def test_gc_tat_bot_khi_qua_nhieu_sim_boot(self):
        us = [self.ensure(self.wt[i], now=100 + i) for i in range(5)]
        P.gc(self.sc, now=100 + 3600, max_booted=3, keep=P.sim_name(str(self.wt[4])), reg_path=self.reg)
        states = [self.sc.devs[u]["state"] for u in us]
        self.assertEqual(states, ["Shutdown", "Shutdown", "Booted", "Booted", "Booted"])  # tắt cái cũ nhất

    def test_gc_khong_tat_sim_vua_dung(self):
        # sim vừa bắt đầu một lượt test (có thể đang chạy L2 dài của phiên khác) không bị tắt dù quá trần
        us = [self.ensure(self.wt[i], now=100 + i) for i in range(5)]
        self.ensure(self.wt[0], now=3600)  # wt0 vừa dùng lại
        P.gc(self.sc, now=3700, max_booted=3, keep=P.sim_name(str(self.wt[4])), reg_path=self.reg)
        states = [self.sc.devs[u]["state"] for u in us]
        self.assertEqual(states, ["Booted", "Shutdown", "Shutdown", "Booted", "Booted"])
        P.gc(self.sc, now=3700, max_booted=1, keep=P.sim_name(str(self.wt[4])), reg_path=self.reg)
        self.assertEqual(self.sc.devs[us[0]]["state"], "Booted")  # vẫn chưa đủ 30 phút nhàn

    def test_gc_khong_dung_sim_ngoai_so_dang_ky(self):
        self.sc.create("iPhone của tôi", T16, RT)
        self.sc.create("factory-la-ma", T16, RT)  # tên giống nhưng không do pool tạo
        self.ensure(self.wt[0], now=0)
        P.gc(self.sc, now=10 ** 9, idle_hours=1, reg_path=self.reg)
        names = {d["name"] for d in self.sc.devs.values()}
        self.assertEqual(names, {"iPhone của tôi", "factory-la-ma"})

    def test_gc_quen_sim_bi_xoa_tay(self):
        u = self.ensure(self.wt[0])
        self.sc.devs.pop(u)
        acts = P.gc(self.sc, now=1001, reg_path=self.reg)
        self.assertTrue(any(a.startswith("quên") for a in acts))

    def test_dry_run_khong_dung_gi(self):
        u = self.ensure(self.wt[0], now=0)
        P.gc(self.sc, now=10 ** 9, idle_hours=1, dry_run=True, reg_path=self.reg)
        self.assertIn(u, self.sc.devs)

    def test_rm(self):
        u = self.ensure(self.wt[0])
        P.remove(str(self.wt[0]), self.sc, reg_path=self.reg)
        self.assertNotIn(u, self.sc.devs)


class RegistryLocationTests(unittest.TestCase):
    """R7: MỘT sổ toàn máy (trần --max-booted tính toàn máy khi có nhiều app), không phụ thuộc cấu hình app."""

    def import_in(self, cwd, env_extra=None):
        import subprocess
        env = {k: v for k, v in os.environ.items() if k != "FACTORY_SIM_REGISTRY" and not k.startswith("GIT_")}
        env.update(env_extra or {})
        code = f"import sys; sys.path.insert(0, {str(Path(P.__file__).parent)!r}); import sim_pool; print(sim_pool.REGISTRY)"
        return subprocess.run([sys.executable, "-c", code], cwd=cwd, env=env, capture_output=True, text=True)

    def test_so_mac_dinh_co_dinh_toan_may(self):
        with tempfile.TemporaryDirectory() as td:
            r = self.import_in(td)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(),
                         str(Path.home() / "Library" / "Caches" / "ios-app-factory" / "sims.json"))

    def test_import_khong_doc_cau_hinh(self):
        # Thư mục không phải repo git, không có app.config.toml ⇒ import vẫn được (trước đây: traceback ConfigError).
        with tempfile.TemporaryDirectory() as td:
            r = self.import_in(td)
        self.assertNotIn("Traceback", r.stderr)

    def test_bien_moi_truong_ghi_de(self):
        with tempfile.TemporaryDirectory() as td:
            want = str(Path(td) / "x" / "sims.json")
            r = self.import_in(td, {"FACTORY_SIM_REGISTRY": want})
        self.assertEqual(r.stdout.strip(), want, r.stderr)


if __name__ == "__main__":
    unittest.main()
