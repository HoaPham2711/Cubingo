"""Test logic 3 hook nhà máy + chạy thật vỏ hook qua subprocess (stdin JSON → stdout/exit)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import hooks_logic as H  # noqa: E402
import mission as M  # noqa: E402


def br(name):
    return lambda cwd: name


class AutonomyTests(unittest.TestCase):
    def ask(self, cmd, branch="claude/x"):
        r = H.autonomy_decision(cmd, None, branch_of=br(branch))
        return r is not None and r[0] == "ask"

    def test_push_nhanh_feature_cho_qua(self):
        self.assertFalse(self.ask("git push -u origin claude/harness-2"))
        self.assertFalse(self.ask("git push", branch="claude/x"))

    def test_push_nhanh_bao_ve_phai_hoi(self):
        for c in ("git push origin develop", "git push origin main --tags", "git push origin HEAD:main",
                  "git push origin claude/x:develop", "git -C /tmp/r push origin develop",
                  "git push origin refs/heads/main"):
            self.assertTrue(self.ask(c), c)
        self.assertTrue(self.ask("git push", branch="develop"))
        self.assertTrue(self.ask("git push origin HEAD", branch="main"))

    def test_force_va_tag(self):
        self.assertTrue(self.ask("git push --force origin claude/x"))
        self.assertTrue(self.ask("git push --force-with-lease"))
        self.assertTrue(self.ask("git push origin +claude/x"))
        self.assertTrue(self.ask("git push origin v1.14.0"))
        self.assertTrue(self.ask("git push --all origin"))

    def test_lenh_ghep_bat_duoc_doan_nguy_hiem(self):
        self.assertTrue(self.ask("git add -A && git commit -m x && git push origin develop"))
        self.assertFalse(self.ask("git status; git log --oneline | head"))

    def test_deploy_web(self):
        self.assertTrue(self.ask("cd web && npm run deploy:prod"))
        self.assertFalse(self.ask("cd web && npm run deploy:dev"))
        self.assertTrue(self.ask("cd web/api && npx wrangler deploy"))
        self.assertFalse(self.ask("cd web/api && npx wrangler deploy --env dev"))
        self.assertFalse(self.ask("CLOUDFLARE_ENV=dev npx wrangler deploy"))
        self.assertTrue(self.ask("npx wrangler d1 migrations apply appdb --remote"))
        self.assertFalse(self.ask("npx wrangler d1 migrations apply appdb --remote --env dev"))
        self.assertFalse(self.ask("npx wrangler d1 migrations apply appdb --local"))
        self.assertTrue(self.ask("wrangler secret put ADMIN_TOKEN"))

    def test_github_va_apple(self):
        self.assertTrue(self.ask("gh pr merge 99 --squash"))
        self.assertFalse(self.ask("gh pr create --base develop --title x --body y"))
        self.assertFalse(self.ask("gh pr view 98"))
        self.assertTrue(self.ask("gh release create v1.15.0"))
        self.assertTrue(self.ask("xcrun altool --upload-app -f a.ipa"))
        self.assertTrue(self.ask("firebase deploy --only firestore:rules"))
        self.assertTrue(self.ask("./tools/release/bump_version.sh minor"))
        self.assertTrue(self.ask("bash tools/release/bump_version.sh patch"))

    def test_dang_lenh_boc_ngoai_van_bi_bat(self):
        # factory-review 2026-11-06: các dạng này từng lọt cổng
        for c in ("(git push origin develop)", "bash -c 'git push origin main'", "sh -c \"npm run deploy:prod\"",
                  "env GIT_TRACE=1 git push origin develop", "command git push origin main",
                  "time git push origin develop", "git --no-pager push origin develop",
                  "nohup npx wrangler deploy &", "echo $(git push origin main)", "eval 'git push origin develop'",
                  "git push origin :claude/old-branch", "{ git push origin develop; }"):
            self.assertTrue(self.ask(c), c)

    def test_lenh_ghep_trong_chuoi_nhay(self):
        # review vòng 2: tách theo && TRƯỚC khi hiểu dấu nháy làm bash -c "…&&…" lọt
        for c in ('bash -c "cd /x && git push origin main"', "bash -c 'cd web && npm run deploy:prod'",
                  'bash -c "git push origin main 2>&1"', "zsh -lc 'git push origin develop'",
                  "bash -ec 'git push origin main'", "timeout -s KILL 60 git push origin main",
                  "timeout -k 5 60 git push origin develop", "eval \"cd /x; git push origin main\"",
                  "echo `git push origin main`"):
            self.assertTrue(self.ask(c), c)
        # review vòng 3: '#' giữa từ không phải chú thích; $(…)/backtick trong nháy kép vẫn chạy; nháy không đóng
        for c in ("git log --grep=#97 -1; git push origin main", "echo issue#97 && git push origin develop",
                  "[ $# -eq 0 ] && git push origin main", "curl -s https://x.com/#/a && cd web && npm run deploy:prod",
                  'out="$(git push origin develop 2>&1)"; echo $out', 'echo "$(git push origin main)"',
                  'echo "`git push origin main`"', 'R="$(cd web && npm run deploy:prod)"',
                  "diff <(git push origin main) x", 'git push origin main "chưa đóng nháy'):
            self.assertTrue(self.ask(c), c)
        for c in ("if true; then git push origin main; fi", "for b in main; do git push origin $b; done",
                  "while false; do :; done; ! git push origin develop", "git push origin ${BR}"):
            self.assertTrue(self.ask(c), c)
        self.assertTrue(self.ask("git status\ngit push origin main"))  # xuống dòng ngoài nháy = biên lệnh
        self.assertTrue(self.ask("bash -c 'git status\ngit push origin develop'"))
        self.assertFalse(self.ask('git commit -m "dòng 1\ngit push origin main"'))  # trong nháy: chỉ là chữ
        for c in ('git commit -m "fix (a && b); push later"', "echo 'git push origin main'",
                  "git log --format='%h (%s)' | head", "python3 x.py 2>&1 | tail"):
            self.assertFalse(self.ask(c), c)

    def test_cd_va_git_C_sang_checkout_khac(self):
        seen = []

        def br_of(cwd):
            seen.append(cwd)
            return "develop" if cwd and cwd.endswith("/main-checkout") else "claude/x"

        r = H.autonomy_decision("cd /repo/main-checkout && git push", "/repo/wt", branch_of=br_of)
        self.assertIsNotNone(r)
        r = H.autonomy_decision("git -C /repo/main-checkout push", "/repo/wt", branch_of=br_of)
        self.assertIsNotNone(r)
        self.assertIsNone(H.autonomy_decision("git push", "/repo/wt", branch_of=br_of))
        self.assertIn("/repo/main-checkout", seen)

    def test_gh_api_ghi(self):
        for c in ("gh api repos/o/r/merges -f base=main -f head=develop", "gh api -X POST repos/o/r/issues",
                  "gh api --method=DELETE repos/o/r/git/refs/heads/x", "gh api -XPATCH repos/o/r",
                  "gh api repos/o/r/pulls/1/merge --input body.json", "gh release upload v1 a.zip",
                  "gh release delete v1"):
            self.assertTrue(self.ask(c), c)
        for c in ("gh api repos/o/r/pulls", "gh api -X GET repos/o/r", "gh release view v1", "gh release list"):
            self.assertFalse(self.ask(c), c)

    def test_cac_nhanh_con_lai(self):
        for c in ("firebase deploy", "wrangler secret delete X", "npx wrangler r2 object delete b/k",
                  "xcrun notarytool submit a.zip", "xcodebuild -exportArchive -archivePath a -exportOptionsPlist upload.plist",
                  "npx wrangler d1 execute appdb --remote --command 'DELETE FROM x'"):
            self.assertTrue(self.ask(c), c)
        for c in ("firebase emulators:start", "xcodebuild -exportArchive -archivePath a -exportOptionsPlist dev.plist",
                  "npx wrangler d1 execute appdb --local --command 'SELECT 1'", "npx wrangler dev"):
            self.assertFalse(self.ask(c), c)

    def test_khong_nham_lenh_doc(self):
        for c in ("grep -rn 'git push origin main' docs", "cat docs/RELEASE.md",
                  "python3 tools/dev/run_tests.py --full", "echo deploy"):
            self.assertFalse(self.ask(c), c)


class LedgerEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("FACTORY_ROOT")
        os.environ["FACTORY_ROOT"] = self.tmp.name
        self.transcript = Path(self.tmp.name) / "t.jsonl"

    def tearDown(self):
        if self._old is None:
            os.environ.pop("FACTORY_ROOT", None)
        else:
            os.environ["FACTORY_ROOT"] = self._old
        self.tmp.cleanup()

    def mission(self, autopilot=True, mention=True):
        m = M.new_mission("Mục tiêu thử", "ops", autopilot=autopilot, today="2026-11-05")
        M.add_task(m, "làm a", "platform-engineer", accept=["a chạy"])
        M.save(m)
        self.transcript.write_text(
            ('{"x":"' + M.director_mark(m["id"]) + '"}\n') if mention else '{"x":"khác"}\n',
            encoding="utf-8")
        return m

    def payload(self, sid="s", path=None):
        return {"session_id": sid, "transcript_path": str(path or self.transcript), "stop_hook_active": False,
                "hook_event_name": "Stop"}


class StopGateTests(LedgerEnv):
    def test_chan_khi_chua_xong(self):
        m = self.mission()
        r = H.stop_decision(self.payload())
        self.assertEqual(r["decision"], "block")
        self.assertIn(m["id"], r["reason"])
        self.assertIn("T1", r["reason"])
        self.assertEqual(M.load(m["id"])["stop_blocks"], {"s": 1})

    def test_toi_da_3_lan_roi_cho_dung(self):
        self.mission()
        for _ in range(H.MAX_STOP_BLOCKS):
            self.assertIsNotNone(H.stop_decision(self.payload()))
        self.assertIsNone(H.stop_decision(self.payload()))

    def test_ledger_doi_thi_reset_dem(self):
        m = self.mission()
        for _ in range(H.MAX_STOP_BLOCKS):
            H.stop_decision(self.payload())
        m = M.load(m["id"])
        M.set_status(m, "T1", "doing")
        M.save(m)
        self.assertIsNotNone(H.stop_decision(self.payload()))

    def test_phien_khac_khong_bi_chan(self):
        self.mission(mention=False)
        self.assertIsNone(H.stop_decision(self.payload()))

    def test_khong_autopilot_khong_chan(self):
        self.mission(autopilot=False)
        self.assertIsNone(H.stop_decision(self.payload()))

    def test_cong_mo_cho_dung(self):
        m = self.mission()
        M.open_gate(m, "device", "Thử trên máy thật?")
        M.save(m)
        self.assertIsNone(H.stop_decision(self.payload()))

    def test_dat_dod_nhac_close(self):
        m = self.mission()
        M.set_status(m, "T1", "verified", evidence=["ok"], by="factory-verifier")
        M.save(m)
        r = H.stop_decision(self.payload())
        self.assertIn("close", r["reason"])

    def test_transcript_thieu_file_khong_loi(self):
        self.mission()
        p = self.payload()
        p["transcript_path"] = "/khong/ton/tai.jsonl"
        self.assertIsNone(H.stop_decision(p))

    def test_ma_nam_vat_qua_ranh_gioi_chunk(self):
        m = self.mission(mention=False)
        pad = "x" * ((1 << 20) - 5)
        self.transcript.write_text(pad + M.director_mark(m["id"]) + "\n", encoding="utf-8")
        self.assertIsNotNone(H.stop_decision(self.payload()))

    def test_phien_chi_nhan_context_sessionstart_khong_bi_chan(self):
        # factory-review 2026-11-06 (blocker): SessionStart in mã mission vào transcript MỌI phiên
        self.mission(mention=False)
        other = Path(self.tmp.name) / "other.jsonl"
        ctx = H.session_context({"source": "startup"})
        other.write_text('{"attachment":{"type":"hook_success","hookEvent":"SessionStart","stdout":'
                         + json.dumps(ctx) + '}}\n{"x":"Mission ' + M.all_missions()[0]["id"] + '"}\n',
                         encoding="utf-8")
        self.assertNotIn("FACTORY-DIRECTOR", ctx)
        self.assertIsNone(H.stop_decision(self.payload(sid="other", path=other)))

    def test_bo_dem_chan_theo_tung_phien(self):
        m = self.mission()
        for _ in range(H.MAX_STOP_BLOCKS):
            self.assertIsNotNone(H.stop_decision(self.payload(sid="A")))
        self.assertIsNone(H.stop_decision(self.payload(sid="A")))
        # phiên giám đốc khác (claim sau resume) vẫn còn đủ lượt của mình
        self.assertIsNotNone(H.stop_decision(self.payload(sid="B")))
        self.assertEqual(M.load(m["id"])["stop_blocks"], {"A": 3, "B": 1})

    def test_mission_blocked_cho_dung(self):
        m = self.mission()
        for _ in range(M.MAX_ATTEMPTS):
            M.set_status(m, "T1", "failed")
        M.save(m)
        self.assertEqual(M.load(m["id"])["status"], "blocked")
        self.assertIsNone(H.stop_decision(self.payload()))

    def test_ledger_cu_stop_blocks_so_nguyen(self):
        m = self.mission()
        m["stop_blocks"] = 2  # schema cũ
        M.save(m)
        self.assertIsNotNone(H.stop_decision(self.payload()))


class SessionContextTests(LedgerEnv):
    def test_khong_mission_im_lang(self):
        self.assertIsNone(H.session_context({"source": "startup"}))

    def test_co_mission_in_tom_tat(self):
        m = self.mission()
        s = H.session_context({"source": "compact"})
        self.assertIn(m["id"], s)
        self.assertLessEqual(len(s), 1500)


class HookShellTests(LedgerEnv):
    """Chạy đúng file hook như Claude Code gọi (stdin JSON), với ledger trỏ vào thư mục tạm."""

    def run_hook(self, name, payload):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(REPO), FACTORY_ROOT=self.tmp.name)
        r = subprocess.run([sys.executable, str(REPO / ".claude" / "hooks" / name)],
                           input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=20)
        return r.returncode, r.stdout, r.stderr

    def test_guard_autonomy_ask(self):
        rc, out, _ = self.run_hook("guard_autonomy.py",
                                   {"tool_input": {"command": "git push origin develop"}, "cwd": str(REPO)})
        self.assertEqual(rc, 0)
        d = json.loads(out)
        self.assertEqual(d["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_guard_autonomy_im_lang_va_stdin_hong(self):
        rc, out, _ = self.run_hook("guard_autonomy.py", {"tool_input": {"command": "ls"}})
        self.assertEqual((rc, out), (0, ""))
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(REPO))
        r = subprocess.run([sys.executable, str(REPO / ".claude" / "hooks" / "guard_autonomy.py")],
                           input="không phải json", capture_output=True, text=True, env=env, timeout=20)
        self.assertEqual(r.returncode, 0)

    def test_guard_autonomy_loi_noi_bo_van_hoi(self):
        broken = Path(self.tmp.name) / "broken"
        (broken / "tools" / "factory").mkdir(parents=True)
        (broken / "tools" / "factory" / "hooks_logic.py").write_text("def x(:\n", encoding="utf-8")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(broken))
        hook = str(REPO / ".claude" / "hooks" / "guard_autonomy.py")
        r = subprocess.run([sys.executable, hook], input=json.dumps({"tool_input": {"command": "git push origin main"}}),
                           capture_output=True, text=True, env=env, timeout=20)
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertIn("lỗi nội bộ", r.stdout)
        r = subprocess.run([sys.executable, hook], input=json.dumps({"tool_input": {"command": "ls -la"}}),
                           capture_output=True, text=True, env=env, timeout=20)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_stop_gate_vo(self):
        self.mission()
        rc, out, _ = self.run_hook("factory_stop_gate.py", self.payload())
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["decision"], "block")

    def test_context_vo(self):
        m = self.mission()
        rc, out, _ = self.run_hook("factory_context.py", {"source": "startup"})
        self.assertEqual(rc, 0)
        self.assertIn(m["id"], out)

    def test_canh_bao_khi_chua_dat_hooks_path(self):
        # Repo tạm (có dấu cách) có .githooks/pre-commit: chưa đặt core.hooksPath ⇒ một dòng cảnh báo kèm lệnh đặt;
        # đặt rồi ⇒ im lặng; không phải repo git ⇒ im lặng. Luôn rc 0.
        repo = Path(self.tmp.name) / "repo có dấu cách"
        (repo / ".githooks").mkdir(parents=True)
        (repo / ".githooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(CLAUDE_PROJECT_DIR=str(repo), FACTORY_ROOT=self.tmp.name)
        hook = str(REPO / ".claude" / "hooks" / "factory_context.py")

        def run():
            r = subprocess.run([sys.executable, hook], input=json.dumps({"source": "startup"}), capture_output=True,
                               text=True, env=env, timeout=20)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout

        self.assertNotIn("[hooks]", run(), "chưa là repo git ⇒ không cảnh báo")
        subprocess.run(["git", "init", "-q", str(repo)], env=env, check=True)
        out = run()
        lines = [ln for ln in out.splitlines() if ln.startswith("[hooks]")]
        self.assertEqual(len(lines), 1, out)
        self.assertIn("git config core.hooksPath .githooks", lines[0])
        subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", "hooks-khac"], env=env, check=True)
        self.assertIn("'hooks-khac'", run())
        subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", ".githooks"], env=env, check=True)
        self.assertNotIn("[hooks]", run())


if __name__ == "__main__":
    unittest.main()
