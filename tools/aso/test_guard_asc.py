"""Test hook .claude/hooks/guard_asc.py chạy như subprocess (JSON trên stdin), đúng như Claude Code gọi nó."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401 — thư mục trạng thái + cấu hình giả

import planner  # noqa: E402
import policy  # noqa: E402
import release  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".claude" / "hooks" / "guard_asc.py"


def run_hook(command, cwd=None, hook_cwd=None, project_dir=None):
    """`hook_cwd` = trường `cwd` trong JSON stdin (thư mục của lệnh Bash); None ⇒ không gửi."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir or ROOT))
    payload = {"tool_input": {"command": command}}
    if hook_cwd is not None:
        payload["cwd"] = str(hook_cwd)
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, cwd=cwd)


def write_plan(path, n_ops=3, version="1.12.0"):
    """Plan thật (planner.save) với n_ops op; trả plan_id."""
    ops = [planner.Op("update", "version", "en-US", f"f{i}", "a", "b") for i in range(n_ops)]
    plan = planner.Plan(version, "0" * 64, ops, "2026-10-29T00:00:00+00:00")
    planner.save(plan, Path(path))
    return plan.plan_id


def tmpdir(tc):
    """Thư mục tạm (đường dẫn có dấu cách), tự dọn."""
    d = Path(tempfile.mkdtemp(prefix="guard asc ")).resolve()
    tc.addCleanup(shutil.rmtree, d, True)
    return d


def ask_of(r):
    return json.loads(r.stdout)["hookSpecificOutput"]


class GuardAscTests(unittest.TestCase):
    def test_hook_asks_for_apply(self):
        plan = tmpdir(self) / "p.json"
        pid = write_plan(plan)
        r = run_hook(f"python3 tools/aso/aso.py apply --plan '{plan}' --expect {pid}")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = ask_of(r)
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "ask")
        reason = out["permissionDecisionReason"]
        self.assertIn(f"mã tính lại {pid}", reason)
        self.assertIn("1.12.0", reason)
        self.assertIn("3 thay đổi", reason)

    def test_hook_summary_for_release_plan(self):
        rp = release.ReleasePlan("1.12.0", "42", "abc", "/x.ipa", "a" * 64, {"verify_release_clean": "ok"},
                                 "0" * 64, [release.Step("upload_build"), release.Step("create_version"),
                                            release.Step("attach_build")], "t")
        plan = tmpdir(self) / "r.json"
        release.save(rp, plan)
        r = run_hook(f"python3 tools/aso/aso.py apply --plan '{plan}' --expect {rp.plan_id}")
        self.assertEqual(r.returncode, 0, r.stderr)
        reason = ask_of(r)["permissionDecisionReason"]
        self.assertIn(f"mã tính lại {rp.plan_id}", reason)
        self.assertIn("release 1.12.0 build 42: upload_build → create_version → attach_build", reason)
        self.assertNotIn("thay đổi", reason)

    def test_hook_asks_for_apply_with_cwd_root(self):
        plan = tmpdir(self) / "p.json"
        pid = write_plan(plan, 1)
        r = run_hook(f"python3 tools/aso/aso.py apply --plan '{plan}' --expect {pid}", hook_cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(ask_of(r)["permissionDecision"], "ask")

    def test_hook_blocks_wrong_expect(self):
        plan = tmpdir(self) / "p.json"
        pid = write_plan(plan)
        wrong = "deadbeef" if pid != "deadbeef" else "cafebabe"
        r = run_hook(f"python3 tools/aso/aso.py apply --plan '{plan}' --expect {wrong}")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("BLOCKED", r.stderr)

    def test_hook_blocks_tampered_plan_file(self):
        plan = tmpdir(self) / "p.json"
        pid = write_plan(plan)
        data = json.loads(plan.read_text())
        data["ops"][0]["new"] = "khác thứ đã duyệt"      # plan_id trong file giữ nguyên
        plan.write_text(json.dumps(data))
        r = run_hook(f"python3 tools/aso/aso.py apply --plan '{plan}' --expect {pid}")
        self.assertEqual(r.returncode, 2)

    def test_plan_sua_sau_khi_tinh_ma_bi_chan(self):
        # Plan được duyệt với mã X; sau đó file bị sửa (thêm op / đổi .ipa) và ghi lại đúng "plan_id": X
        # ⇒ hook tính lại mã từ nội dung, khác X ⇒ chặn (không bao giờ tin plan_id trên đĩa).
        d = tmpdir(self)
        meta = d / "p.json"
        pid = write_plan(meta)
        data = json.loads(meta.read_text())
        data["ops"].append({"kind": "update", "scope": "version", "locale": "en-US", "field": "keywords",
                            "old": "a", "new": "b"})
        data["plan_id"] = pid
        meta.write_text(json.dumps(data))
        r = run_hook(f"python3 tools/aso/aso.py apply --plan '{meta}' --expect {pid}")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("BLOCKED", r.stderr)

        rp = release.ReleasePlan("1.12.0", "42", "abc", "/x.ipa", "a" * 64, {}, "0" * 64,
                                 [release.Step("upload_build")], "t")
        rel = d / "r.json"
        release.save(rp, rel)
        data = json.loads(rel.read_text())
        data["ipa"] = "/khac.ipa"
        data["plan_id"] = rp.plan_id
        rel.write_text(json.dumps(data))
        r = run_hook(f"python3 tools/aso/aso.py apply --plan '{rel}' --expect {rp.plan_id}")
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_hook_resolves_relative_plan_against_payload_cwd(self):
        d = tmpdir(self)
        work = d / "work"
        work.mkdir()
        other = d / "khac"
        other.mkdir()
        pid = write_plan(work / "p.json")
        cmd = f"python3 tools/aso/aso.py apply --plan p.json --expect {pid}"
        r = run_hook(cmd, hook_cwd=work)                      # p.json nằm đúng trong cwd ⇒ ask
        self.assertEqual(ask_of(r)["permissionDecision"], "ask", r.stderr)
        self.assertEqual(run_hook(cmd, hook_cwd=other).returncode, 2)   # cwd khác ⇒ không có file ⇒ chặn
        self.assertEqual(run_hook(cmd).returncode, 2)         # không có cwd ⇒ gốc repo ⇒ không có ⇒ chặn

    def test_hook_blocks_when_cwd_inside_tools_aso(self):
        a = "apply --plan p.json --expect ab"
        for c in [f"python3 aso.py {a}", f"python3 a?o.py {a}", f"python3 *.py {a}",
                  'python3 -c "import aso; aso.main()"']:
            for where in (ROOT / "tools" / "aso", ROOT / "tools"):
                r = run_hook(c, hook_cwd=where)
                self.assertEqual(r.returncode, 2, (c, where))
                self.assertIn("gốc repo", r.stderr)

    def test_tu_thu_muc_con_van_chan(self):
        # Đứng ở thư mục con KHÁC tools/ (vd store/, AppHost/): đường dẫn tương đối tới công cụ không phải dạng
        # chuẩn (dạng chuẩn tính theo gốc repo) ⇒ chặn; asc trực tiếp ⇒ chặn; thông báo nói lệnh chuẩn.
        sub = tmpdir(self) / "store"
        sub.mkdir()
        for where in (sub, ROOT / "AppHost"):
            for c in ["python3 ../tools/aso/aso.py apply --plan p.json --expect ab12cd34",
                      "python3 ../tools/aso/aso.py plan",
                      "cd .. && python3 tools/aso/aso.py plan; python3 tools/aso/applier.py",
                      "asc metadata push --dir metadata",
                      "../../bin/asc versions list"]:
                r = run_hook(c, hook_cwd=where)
                self.assertEqual(r.returncode, 2, (c, where))
                self.assertIn("python3 tools/aso/aso.py", r.stderr, c)

    def test_hook_blocks_dotted_module(self):
        for c in ["python3 -m tools.aso.aso apply --plan p.json --expect ab",
                  "python3 -m tools.aso.asc_cli metadata push"]:
            self.assertEqual(run_hook(c, hook_cwd=ROOT).returncode, 2, c)

    def test_hook_blocks_apply_with_missing_plan(self):
        r = run_hook("python3 tools/aso/aso.py apply --plan /nonexistent.json --expect ab12cd34")
        self.assertEqual(r.returncode, 2)

    def test_hook_blocks_direct_asc(self):
        r = run_hook("asc metadata push --dir store")
        self.assertEqual(r.returncode, 2)
        self.assertIn("BLOCKED", r.stderr)

    def test_thong_bao_chan_noi_lenh_chuan_thay_the(self):
        for c in ["asc metadata push --dir store", "python3 tools/aso/applier.py",
                  "curl https://api.appstoreconnect.apple.com/v1/apps"]:
            r = run_hook(c)
            self.assertEqual(r.returncode, 2, c)
            self.assertIn(policy.CANON_FORMS, r.stderr, c)

    def test_hook_blocks_nested_asc(self):
        for c in ["bash -c 'asc submit create'", "echo $(asc apps list)",
                  "env FOO=1 asc metadata pull", "/opt/homebrew/bin/asc versions list"]:
            r = run_hook(c)
            self.assertEqual(r.returncode, 2, c)
            self.assertTrue(r.stderr.strip())

    def test_hook_blocks_api_host(self):
        self.assertEqual(run_hook("curl https://api.appstoreconnect.apple.com/v1/apps").returncode, 2)

    def test_hook_allows_unrelated(self):
        for c in ["git status", "python3 tools/analytics/asc_pull.py --days 7", "asc version", "ls -la"]:
            r = run_hook(c)
            self.assertEqual(r.returncode, 0, c)
            self.assertEqual(r.stdout, "", c)

    def test_commit_message_nhac_tools_aso_khong_bi_chan(self):
        # git chỉ truyền chữ: message nhắc công cụ (kể cả "python3", "apply", tên module) không chạy code nào.
        for c in ['git commit -m "feat(aso): python3 tools/aso/aso.py plan rồi apply"',
                  "git commit -q -m 'import aso; sửa tools/aso/policy.py'",
                  "git --no-optional-locks log --grep 'tools/aso' --oneline",
                  "git add tools/aso/policy.py tools/aso/test_guard_asc.py"]:
            r = run_hook(c, hook_cwd=ROOT)
            self.assertEqual((r.returncode, r.stdout), (0, ""), (c, r.stderr))
        # Còn git chạy được code thì vẫn chặn.
        for c in ['git -c core.hooksPath=/tmp/h commit -m "tools/aso"', "git xaso tools/aso/aso.py plan"]:
            self.assertEqual(run_hook(c, hook_cwd=ROOT).returncode, 2, c)

    def test_hook_release_subcommands(self):
        for sub in ("build --version 1.12.0", "pull-version --version 1.12.0",
                    "release-plan --build-json '/a b/build.json'", "lint", "plan"):
            self.assertEqual(run_hook(f"python3 tools/aso/aso.py {sub}", hook_cwd=ROOT).returncode, 0, sub)
        r = run_hook("python3 tools/aso/aso.py build --version 1.12.0; rm -rf x", hook_cwd=ROOT)
        self.assertEqual(r.returncode, 2)

    def test_offline_fixture_chi_cho_lenh_chi_doc(self):
        fx = "'/tmp/fx dir'"
        for sub in ("lint", "plan", "snapshot"):
            r = run_hook(f"python3 tools/aso/aso.py --offline-fixture {fx} {sub}", hook_cwd=ROOT)
            self.assertEqual((r.returncode, r.stdout), (0, ""), (sub, r.stderr))
        # apply với fixture: không hỏi, chặn thẳng — kể cả khi plan hợp lệ.
        plan = tmpdir(self) / "p.json"
        pid = write_plan(plan)
        r = run_hook(f"python3 tools/aso/aso.py --offline-fixture {fx} apply --plan '{plan}' --expect {pid}",
                     hook_cwd=ROOT)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertEqual(r.stdout, "")

    def test_hook_bad_json_exit_0(self):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(ROOT))
        r = subprocess.run([sys.executable, str(HOOK)], input="not json",
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0)

    def test_hook_fails_closed_on_broken_policy(self):
        # Hai kiểu hỏng: lỗi lúc import, và import được nhưng hook_decision ném lỗi.
        hong = {"import": "raise RuntimeError('hỏng')\n",
                "goi": "CANON_FORMS = 'x'\ndef hook_decision(*a, **k):\n    raise RuntimeError('hỏng')\n"}
        for kieu, src in hong.items():
            d = tmpdir(self)
            (d / "tools" / "aso").mkdir(parents=True)
            (d / "tools" / "aso" / "policy.py").write_text(src)
            for c in ("asc metadata push", "python3 tools/aso/aso.py apply --plan p --expect ab",
                      "curl https://api.appstoreconnect.apple.com/v1/apps",
                      "python3 tools/aso/applier.py", "python3 -m tools.aso.applier", "python3 -m aso apply",
                      "cd tools && python3 x.py", "PYTHONPATH=x python3 -c 'import applier'"):
                r = run_hook(c, project_dir=d)
                self.assertEqual(r.returncode, 2, (kieu, c))
                self.assertIn("BLOCKED", r.stderr, (kieu, c))
            self.assertEqual(run_hook("git status", project_dir=d).returncode, 0, kieu)
            self.assertEqual(run_hook("ls -la", project_dir=d).returncode, 0, kieu)

    def test_khoa_an_toan_khi_loi_cung_nguon_ref_area(self):
        # Bản sao trong hook phải trùng NGUYÊN VĂN policy.REF_AREA (một nguồn, policy hỏng thì không import được).
        self.assertIn(f'REF_AREA_SRC = r"{policy.REF_AREA.pattern}"', HOOK.read_text(encoding="utf-8"))

    def test_khoa_chay_lenh_la_viec_nguoi_dung_khong_goi_y_lenh_aso(self):
        r = run_hook("git config core.hooksPath .githooks", hook_cwd=ROOT)
        self.assertEqual(r.returncode, 2)
        self.assertIn("người dùng", r.stderr)
        self.assertNotIn(policy.CANON_FORMS, r.stderr)
        for c in ["GIT_EDITOR=true git rebase --continue", "GIT_PAGER=cat git log", "git -c core.pager=cat log"]:
            r = run_hook(c, hook_cwd=ROOT)
            self.assertEqual((r.returncode, r.stdout), (0, ""), (c, r.stderr))
        r = run_hook("git status && EDITOR='sh -c \"asc metadata push\" x' git commit --allow-empty", hook_cwd=ROOT)
        self.assertEqual(r.returncode, 2)

    def test_git_thuong_ngay_qua_hook(self):
        for c in ["git checkout develop -- tools/aso/policy.py", "git stash push -m \"from lint fix\"",
                  "git -C /abs/path diff -- tools/aso/policy.py", "git log --grep asc"]:
            r = run_hook(c, hook_cwd=ROOT / "tools")
            self.assertEqual((r.returncode, r.stdout), (0, ""), (c, r.stderr))

    def test_git_alias_noi_chuoi_bi_chan_o_hook(self):
        for c in ["git config --global alias.x '!a''sc metadata push --dir d' && git x",
                  "git -c core.pager='a''sc metadata push' log", "ASC metadata push --dir d",
                  "git config alias.x '!asc metadata push --dir d' && git x",
                  "git -C /tmp/e config core.fsmonitor '!asc metadata push' && git -C /tmp/e status"]:
            r = run_hook(c, hook_cwd=ROOT)
            self.assertEqual(r.returncode, 2, c)
            self.assertIn("BLOCKED", r.stderr, c)

    def test_round4_lo_hong_bi_chan_o_hook_lenh_thuong_qua(self):
        # R1 (message chỉ bỏ ở lệnh con message), R2 (nháy lồng), R3 (glob nhắm asc + wrapper trong suốt).
        for c in ["git grep -F -O'sh -c \"asc metadata push --dir d\" x' -e foo",
                  "git fetch -m --upload-pack='sh -c \"asc metadata push\" x' .",
                  "git fetch --upload-pack='sh -c \"a\"\"sc metadata push\" x' .",
                  "git config alias.x \"fetch --upload-pack='a''sc metadata push' .\"",
                  "timeout 5 sh -c 'a\"\"sc metadata push'",
                  "timeout 5 ~/.local/share/*/asc/*/a?c metadata push --dir d",
                  "nice -n 5 a?c metadata push", "nohup ~/.local/share/*/asc/*/asc metadata push"]:
            r = run_hook(c, hook_cwd=ROOT)
            self.assertEqual(r.returncode, 2, c)
            self.assertIn("BLOCKED", r.stderr, c)
        for c in ["git log -- docs/javascript.md", "git checkout feature/cascade", "git grep basic",
                  "GIT_EDITOR=true git rebase --continue", "git commit -m \"sửa asc metadata\"",
                  "git log --grep asc", "echo asc", "timeout 60 git status"]:
            r = run_hook(c, hook_cwd=ROOT)
            self.assertEqual((r.returncode, r.stdout), (0, ""), (c, r.stderr))


if __name__ == "__main__":
    unittest.main()
