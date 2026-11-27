"""Test allowlist lệnh asc (policy.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401 — thư mục trạng thái + cấu hình giả
import policy  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


class CheckAscArgsTests(unittest.TestCase):
    def test_read_command_ok(self):
        policy.check_asc_args(["metadata", "pull", "--app", "1", "--dir", "x"], write=False)

    def test_write_command_rejected_when_read_only(self):
        with self.assertRaises(policy.PolicyError):
            policy.check_asc_args(["metadata", "push", "--app", "1", "--version", "1", "--dir", "x"], write=False)

    def test_write_command_ok_when_write(self):
        policy.check_asc_args(["metadata", "push", "--app", "1", "--version", "1", "--dir", "x"], write=True)

    def test_forbidden_flag_rejected(self):
        with self.assertRaises(policy.PolicyError):
            policy.check_asc_args(["metadata", "push", "--dir", "x", "--allow-deletes"], write=True)

    def test_forbidden_flag_with_equals_rejected(self):
        with self.assertRaises(policy.PolicyError):
            policy.check_asc_args(["metadata", "push", "--force=true"], write=True)

    def test_unlisted_commands_rejected(self):
        with self.assertRaises(policy.PolicyError):
            policy.check_asc_args(["submit", "create"], write=True)
        with self.assertRaises(policy.PolicyError):
            policy.check_asc_args(["asset-library", "images", "delete", "--id", "1"], write=True)

    def test_empty_rejected(self):
        with self.assertRaises(policy.PolicyError):
            policy.check_asc_args([], write=False)


class HookDecisionTests(unittest.TestCase):
    @staticmethod
    def summ(path, expect=None):
        return "version 1.0, 2 thay đổi" if path == "p.json" else None

    def test_apply_asks(self):
        d, why = policy.hook_decision(
            "python3 tools/aso/aso.py apply --plan p.json --expect ab12cd34", self.summ)
        self.assertEqual(d, "ask")
        self.assertIn("ab12cd34", why)
        self.assertIn("2 thay đổi", why)

    def test_apply_unreadable_plan_blocks(self):
        d, _ = policy.hook_decision(
            "python3 tools/aso/aso.py apply --plan nope.json --expect ab12cd34", self.summ)
        self.assertEqual(d, "block")

    def test_apply_missing_expect_blocks(self):
        d, _ = policy.hook_decision("python3 tools/aso/aso.py apply --plan p.json", self.summ)
        self.assertEqual(d, "block")

    def test_blocks_asc_variants(self):
        for c in ["asc metadata push --dir store", "bash -c 'asc submit create'",
                  "echo $(asc apps list)", "echo `asc apps list`", "env FOO=1 asc metadata pull",
                  "/opt/homebrew/bin/asc versions list", "cd x && asc apps list",
                  "ls | xargs asc foo", 'sh -c "asc x"']:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_blocks_api_and_key_and_cpp(self):
        for c in ["curl https://api.appstoreconnect.apple.com/v1/apps",
                  "cat ~/.config/ios-app-factory/thu-app/asc-listing.json", "python3 tools/listing/asc_cpp.py"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_own_tool_not_blocked_by_substring(self):
        c = "python3 tools/aso/aso.py pull --key asc-listing.json"
        self.assertEqual(policy.hook_decision(c, self.summ)[0], "allow")

    def test_own_tool_chained_with_api_blocks(self):
        c = "python3 tools/aso/aso.py plan; curl https://api.appstoreconnect.apple.com/v1/apps"
        self.assertEqual(policy.hook_decision(c, self.summ)[0], "block")

    def test_apply_noncanonical_forms_block(self):
        a = "apply --plan p.json --expect ab"
        for c in [f"python3 -u tools/aso/aso.py {a}", f"cd tools/aso && python3 aso.py {a}",
                  f"tools/aso/aso.py {a}", f"./tools/aso/aso.py {a}",
                  f"uv run tools/aso/aso.py {a}", f"python3 tools/aso/aso.py --verbose {a}",
                  f"env X=1 python3 tools/aso/aso.py {a}", f"bash -c 'python3 tools/aso/aso.py {a}'"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_apply_canonical_forms_ask(self):
        a = "apply --plan p.json --expect ab"
        for c in [f"python3 tools/aso/aso.py {a}", f"python3 ./tools/aso/aso.py {a}",
                  f"python3 tools/aso/aso.py apply --plan=p.json --expect=ab"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "ask", c)

    def test_apply_option_tricks_block(self):
        base = "python3 tools/aso/aso.py apply"
        for c in [f"{base} --plan p.json --expect ab --plan other.json",
                  f"{base} --plan p.json --expect ab --plan=other.json",
                  f"{base} --plan p.json --expect ab --pla other.json",
                  f"{base} --plan p.json --expect ab --exp zz",
                  f"{base} --plan p.json --expect ab --expect cd"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_apply_must_run_alone(self):
        base = "python3 tools/aso/aso.py apply --plan p.json --expect ab"
        for c in [f"{base}; rm -rf x", f"{base} && echo hi", f"{base} | tee x", f"{base} > out",
                  f"{base} 2>&1", f"{base} $(echo)", f"echo hi; {base}", f"{base} <in"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_blocks_asc_through_wrappers(self):
        for c in ["timeout 5 asc metadata push", "caffeinate asc x", "eval asc x", "{ asc x; }",
                  "if true; then asc x; fi", "! asc x", "xargs -I {} asc", "find . -exec asc {} \\;",
                  "bash -s <<<'asc x'"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_backstop_wrapped_apply_blocks(self):
        a = "python3 tools/aso/aso.py apply --plan p.json --expect ab"
        for c in [f'eval "{a}"', f'timeout 60 bash -c "{a}"', f'caffeinate -i sh -c "{a}"',
                  f'echo "{a}" | sh', "cd tools/aso && python3 -m aso apply --plan p.json --expect ab",
                  "python3 -c \"import runpy; runpy.run_path('tools/aso/aso.py'); apply\"",
                  f"{a} &", "python3 tools/aso/aso.py plan --version 1.12.0 && echo applied apply"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_backstop_wrapped_asc_blocks(self):
        for c in ['eval "asc metadata push"', 'timeout 5 bash -c "asc metadata push"',
                  "printf 'asc metadata push' | bash"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_backstop_allows(self):
        for c in ["python3 tools/aso/aso.py plan --version 1.12.0", 'git commit -m "asc metadata push"',
                  "python3 tools/analytics/asc_pull.py --days 7", "asc version", "ls -la"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "allow", c)
        self.assertEqual(policy.hook_decision(
            "  python3 tools/aso/aso.py apply --plan p.json --expect ab  ", self.summ)[0], "ask")

    def test_allowlist_layer_blocks(self):
        for c in ["python3 tools/aso/aso.p? apply --plan p.json --expect ab",
                  "cd tools/aso && python3 a?o.py apply --plan p.json --expect ab",
                  "cd tools/aso && python3 [a]so.py apply --plan p.json --expect ab",
                  "cd tools && python3 as?.py apply --plan p.json --expect ab",
                  'eval "python3 tools/aso/as""o.py apply --plan p.json --expect ab"',
                  'eval "python3 tools/aso/aso.py ap""ply --plan p.json --expect ab"',
                  'cd tools/aso && python3 -c "import aso; aso.main([\'apply\'])"',
                  'PYTHONPATH=tools/aso python3 -c "import aso; aso.main()" apply',
                  'python3 -c "import asc_cli; asc_cli.run([\'metadata\',\'push\'])"',
                  "python3 -c \"import subprocess; subprocess.run(['as'+'c','x'])\"",
                  'git -c alias.x="!asc metadata push" x']:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_allowlist_layer_allows(self):
        for c in ["cat tools/aso/policy.py", "grep -n apply tools/aso/policy.py",
                  "grep -n apply tools/aso/aso.py", "ls tools/aso", "git add tools/aso/policy.py",
                  "python3 -m unittest discover -s tools/aso -p 'test_*.py'",
                  "python3 -m unittest tools/aso/test_policy.py -v",
                  "python3 -m unittest -v tools.aso.test_policy.HookDecisionTests",
                  "bash -n tools/aso/install_asc.sh",
                  "python3 -m py_compile tools/aso/policy.py tools/aso/aso.py",
                  "python3 tools/aso/aso.py pull --app 1", "python3 tools/aso/aso.py plan --version 1.12.0"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "allow", c)

    def test_dotted_module_path_blocks(self):
        # Dạng chấm là cách gọi tự nhiên (không phải lách) — phải chặn như dạng đường dẫn.
        for c in ["python3 -m tools.aso.aso apply --plan p.json --expect ab",
                  "python3 -c \"from tools.aso.aso import main; main(['apply','--plan','p','--expect','x'])\"",
                  "python3 -c \"import tools.aso.aso as m; m.main(['apply'])\"",
                  "python3 -c \"from tools.aso.asc_cli import run; run(['metadata','push'])\"",
                  "python3 -m tools.aso.asc_cli metadata push",
                  "python3 -c \"from tools . aso import aso\"",
                  "python3 -c \"import tools .aso .asc_cli as m; m.run([])\"",
                  "python3 -m tools\\aso\\aso apply --plan p.json --expect ab"]:
            self.assertEqual(policy.hook_decision(c, self.summ, cwd=str(ROOT))[0], "block", c)
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_cwd_inside_tools_blocks_code(self):
        a = "apply --plan p.json --expect ab"
        cmds = [f"python3 a?o.py {a}", f"python3 [a]so.py {a}", f"python3 *.py {a}",
                f"python3 aso.py {a}", 'python3 -c "import aso; aso.main()"', f"./aso.py {a}",
                "python3 -m unittest discover", f"python3 tools/aso/aso.py {a}"]
        for where in (ROOT / "tools" / "aso", ROOT / "tools", ROOT / "tools" / "aso" / "x"):
            for c in cmds:
                d, why = policy.hook_decision(c, self.summ, cwd=str(where))
                self.assertEqual(d, "block", (c, where))
                self.assertIn("gốc repo", why)
        # Lệnh không chạy code trong tools/aso vẫn được.
        for c in ["cat aso.py", "ls", "grep -n apply aso.py", f"cd {ROOT}"]:
            self.assertEqual(policy.hook_decision(c, self.summ, cwd=str(ROOT / "tools" / "aso"))[0],
                             "allow", c)

    def test_glob_in_exec_command_blocks(self):
        # Không có cwd (hoặc cwd khác tools) nhưng glob chưa nháy trong lệnh chạy code ⇒ chặn.
        a = "apply --plan p.json --expect ab"
        for c in [f"python3 a?o.py {a}", f"python3 [a]so.py {a}", f"python3 *.py {a}",
                  f"tools/as?/aso.p? {a}", f"python3 tools/as?/a?o.py {a}"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)
            self.assertEqual(policy.hook_decision(c, self.summ, cwd=str(ROOT))[0], "block", c)

    def test_read_only_first_word_does_not_exempt_later_segments(self):
        for c in ["cat x; python3 -c 'import aso; aso.main()' apply --plan p --expect x",
                  'grep x y; python3 -c "import asc_cli; asc_cli.run([\'metadata\',\'push\'])"',
                  'ls && python3 -c "import applier"', 'git status || python3 -c "from remote import x"',
                  'cat x | python3 -c "import aso"', 'cat x & python3 -c "import aso"',
                  'cat x\npython3 -c "import aso"', 'cat $(python3 -c "import aso")',
                  'grep python3 -c "import aso"']:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_assets_apply_import_blocks(self):
        # Lối ghi asset/CPP chỉ qua `aso.py apply` — import thẳng assets_apply (kể cả sau lệnh chỉ-đọc) ⇒ chặn.
        for c in ['python3 -c "import assets_apply; assets_apply.apply_assets(p)"',
                  'ls && python3 -c "from assets_apply import apply_assets"',
                  'cat x; python3 -c "import assets_apply"']:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_python_c_extra_danger_blocks(self):
        for c in ["python3 -c \"import os; os.popen('x')\"", "python3 -c \"import os; os.spawnlp(0,'x')\"",
                  "python3 -c \"import os; os.spawnv(0,'x',[])\"", "python2 -c \"import commands; commands.getoutput('x')\""]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_round4_allows_and_asks_kept(self):
        for cwd in (None, str(ROOT)):
            for c in ["python3 tools/aso/aso.py plan --version 1.12.0", 'git commit -m "asc metadata push"',
                      "python3 tools/analytics/asc_pull.py --days 7", "asc version", "ls -la",
                      "cat tools/aso/policy.py", "grep -n apply tools/aso/aso.py",
                      "git add tools/aso/policy.py",
                      "python3 -m unittest discover -s tools/aso -p 'test_*.py'",
                      "python3 -m unittest tools/aso/test_policy.py -v",
                      "python3 -m unittest tools.aso.test_policy", "bash -n tools/aso/install_asc.sh",
                      "python3 -c 'print([1, 2])'", "python3 x.py; echo $?", "[ -f x ] && ls",
                      "ls *.swift"]:
                self.assertEqual(policy.hook_decision(c, self.summ, cwd=cwd)[0], "allow", (c, cwd))
            self.assertEqual(policy.hook_decision(
                "python3 tools/aso/aso.py apply --plan p.json --expect ab", self.summ, cwd=cwd)[0], "ask")

    def test_round5_glob_feeders_block(self):
        a = "apply --plan p.json --expect ab"
        for c in [f"ls tools/*/a?o.py | xargs -I{{}} python3 {{}} {a}",
                  f"ls 'tools/*/a?o.py' | xargs -I{{}} python3 {{}} {a}",
                  f"find tools -name 'a?o.py' -exec python3 {{}} {a} \\;",
                  f"find . -path '*as?/*' -execdir python3 {{}} {a} \\;",
                  f"find . -iname '*ASO*' | xargs python3",
                  f"ls x | xargs -I{{}} python3 {{}} {a}",
                  f"find . -name '*.py' -exec python3 {{}} {a} \\;",
                  # không có chữ apply: chỉ pattern -name khớp tên thật (fnmatch) mới bắt được
                  "find tools -name 'a?o.py' -exec python3 {} \\;", "find . -name '?so.py' | xargs python3",
                  # không có từ chạy code: chạy thẳng file qua shebang
                  f"find tools -name 'a?o.py' -exec {{}} {a} \\;",
                  f"ls tools/*/a?o.py | xargs -I{{}} {{}} {a}"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_round5_canonical_sink_suffix(self):
        for c in ["python3 -m unittest discover -s tools/aso -p 'test_*.py' 2>&1 | tail -5",
                  "python3 tools/aso/aso.py plan --version 1.12.0 | head -50",
                  "python3 tools/aso/aso.py lint 2>&1",
                  "python3 -m unittest tools/aso/test_policy.py -v 2>&1 | grep -E 'FAIL|ERROR'",
                  "python3 -m unittest tools/aso/test_policy.py 2>&1 | tail -n 20",
                  "python3 -m py_compile tools/aso/policy.py | head"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "allow", c)
        base = "python3 tools/aso/aso.py apply --plan p.json --expect ab"
        for c in [f"{base} | tail", f"{base} 2>&1", f"{base} 2>&1 | tail -5", f"{base} | head -50",
                  "python3 tools/aso/aso.py plan | tail | sh", "python3 tools/aso/aso.py plan | grep x; curl y",
                  "python3 tools/aso/aso.py plan | grep $(asc x)", "python3 tools/aso/aso.py plan | bash"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_round5_unquoted_glob_message(self):
        d, why = policy.hook_decision("python3 -m json.tool *.json", self.summ)
        self.assertEqual(d, "block")
        self.assertIn("glob chưa quote", why)
        d, why = policy.hook_decision("python3 tools/aso/a?o.py plan", self.summ)
        self.assertEqual(d, "block")
        self.assertNotIn("glob chưa quote", why)

    def test_heredoc_python_co_ky_tu_glob_khong_bi_chan_oan(self):
        # Thân heredoc không bao giờ bị shell glob ⇒ `[`/`*` trong code python không phải glob.
        for c in ["python3 - <<'EOF'\nxs = [1, 2]\nprint(xs[0] * 2)\nEOF",
                  "python3 <<EOF\nimport json\nd = json.loads('[1]')\nprint(d[0])\nEOF",
                  "cd /x && python3 - <<-'PY'\n\tprint([i*i for i in range(3)])\n\tPY\necho done"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "allow", c)

    def test_heredoc_van_chan_khi_nguoi_nhan_la_shell_hoac_co_apply(self):
        for c in ["bash <<'EOF'\npython3 *.py\nEOF",
                  "sh <<EOF\nls t?ols/a?o/a?o.py | xargs -I{} python3 {} plan\nEOF",
                  "python3 - <<'EOF'\nimport glob, subprocess\nf = glob.glob('t?ols/a?o/a?o.py')[0]\n"
                  "subprocess.run(['python3', f, 'ap' + 'ply'])  # apply\nEOF",
                  "python3 - <<'EOF'\nimport aso\nEOF",
                  "python3 - <<'EOF'\nprint([1][0] * 2)\n",  # heredoc không đóng ⇒ giữ nguyên thân
                  "cat <<'EOF' | bash\npython3 *.py\nEOF",
                  "cat <<'EOF' | sh\npython3 tools/aso/applier.py\nEOF",
                  "python3 - <<'EOF'\nopen('tools/aso/asc-listing.json')\nEOF"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_heredoc_message_git_nhac_python_va_vung_aso_khong_bi_chan(self):
        c = ("git add tools/aso/policy.py && git commit -q -F - <<'EOF'\nfix: guard\n\n"
             "- thân heredoc gửi vào python không bị coi là glob [x] *\nEOF")
        self.assertEqual(policy.hook_decision(c, self.summ)[0], "allow")

    def test_round6_parked_feeder_bypasses_block(self):
        # Ruling 10: feeder ⇒ glob xét mọi đoạn; chữ apply xét sau khi bỏ nháy/backslash; `\Z` không phải `$`.
        b = 'ap""ply --plan p.json --expect ab'
        for c in [f"ls t?ols/a?o/a?o.py | xargs -I{{}} python3 {{}} {b}",
                  f"echo t*/a*/a?o.py | xargs -I% python3 % {b}",
                  f"find . -name a\\?o.py -exec python3 {{}} {b} \\;",
                  "find . -name a\\?o.py -exec python3 {} ap\\ply --plan p.json --expect ab \\;",
                  "find . -name a\\?o.py -exec python3 {} 'ap'ply --plan p.json --expect ab \\;",
                  "python3 tools/aso/aso.py plan --version 1.12.0\n | tail",
                  "ls t?ols/a?o/a?o.py | xargs -I{} python3 {} plan"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_round6_quoted_state_dir_paths(self):
        snap = "'/Users/x/Library/Application Support/ios-app-factory/thu-app/aso/snapshots/20261029T000000Z'"
        self.assertEqual(policy.hook_decision(
            f"python3 tools/aso/aso.py restore --snapshot {snap}", self.summ)[0], "allow")
        for c in [f"python3 tools/aso/aso.py restore --snapshot {snap}; ls",
                  "python3 tools/aso/aso.py restore --snapshot '$(x)'",
                  "python3 tools/aso/aso.py restore --snapshot 'a'b'"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "block", c)

    def test_apply_summary_gets_expect(self):
        seen = []

        def summ(path, expect):
            seen.append((path, expect))
            return "ok"
        d, _ = policy.hook_decision("python3 tools/aso/aso.py apply --plan p.json --expect ab12cd34", summ)
        self.assertEqual(d, "ask")
        self.assertIn(("p.json", "ab12cd34"), seen)

    def test_case_insensitive_host(self):
        self.assertEqual(policy.hook_decision("curl https://API.AppStoreConnect.Apple.com/x",
                                              self.summ)[0], "block")

    def test_allows_unrelated(self):
        for c in ["git status", "python3 tools/analytics/asc_pull.py --days 7", "asc version",
                  "python3 tools/aso/aso.py plan", "git commit -m 'fix asc metadata push'",
                  'git commit -m "x; asc y"', "ls asc_cli", "echo asc"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "allow", c)

    def test_unbalanced_quote_with_bare_asc_blocks(self):
        self.assertEqual(policy.hook_decision("echo 'oops && asc foo", self.summ)[0], "block")


class ReleaseCommandsTests(unittest.TestCase):
    """Lệnh của luồng ra bản: upload/attach-build ghi; release/delete/update/expire cấm hẳn."""

    @staticmethod
    def summ(path, expect=None):
        return None

    def test_upload_write_only(self):
        a = ["builds", "upload", "--app", "1", "--ipa", "/x/a.ipa"]
        policy.check_asc_args(a, write=True)
        with self.assertRaises(policy.PolicyError):
            policy.check_asc_args(a, write=False)

    def test_versions_create_and_attach_build(self):
        policy.check_asc_args(["versions", "create", "--app", "1", "--version", "1.12.0", "--platform", "IOS",
                               "--release-type", "MANUAL"], write=True)
        policy.check_asc_args(["versions", "attach-build", "--app", "1", "--version", "1.12.0",
                               "--build-number", "24"], write=True)

    def test_forbidden_commands_even_when_write(self):
        for a in (["versions", "release", "--version-id", "x"], ["versions", "delete", "--version-id", "x"],
                  ["versions", "update", "--version-id", "x"], ["builds", "expire", "--build-number", "1"]):
            for w in (True, False):
                with self.assertRaises(policy.PolicyError, msg=(a, w)):
                    policy.check_asc_args(a, write=w)

    def test_write_commands_exact_flag_sets(self):
        ok = {
            "upload": ["builds", "upload", "--app", "1", "--ipa", "/x/a.ipa"],
            "create": ["versions", "create", "--app", "1", "--version", "1.12.0", "--platform", "IOS",
                       "--release-type", "MANUAL"],
            "attach": ["versions", "attach-build", "--app", "1", "--version", "1.12.0", "--build-number", "24"],
            "push": ["metadata", "push", "--app", "1", "--version", "1.12.0", "--dir", "/x"],
        }
        for a in ok.values():
            policy.check_asc_args(a, write=True)
        policy.check_asc_args(["versions", "create", "--app=1", "--version=1.12.0", "--platform=IOS",
                               "--release-type=MANUAL"], write=True)
        extras = ["--if-exists", "--copy-metadata-from", "--test-notes", "--wait", "--confirm",
                  "--allow-deletes", "--output"]
        bad = []
        for name, a in ok.items():
            for flag in extras:
                bad += [a + [flag, "x"], a + [flag], a + [f"{flag}=x"]]
            bad.append(a[:-2])                                  # thiếu một cờ bắt buộc
            bad.append(a + [a[2], a[3]])                        # cờ lặp
            bad.append(a + ["positional"])                      # đối số lạ
            bad.append(a[:2] + [a[2]] + a[4:])                  # cờ không có giá trị
        bad += [ok["create"][:-1] + ["AFTER_APPROVAL"], ok["create"][:-1] + ["SCHEDULED"],
                ok["create"][:-1] + ["manual"], ok["create"][:-2] + ["--release-type=AFTER_APPROVAL"]]
        for a in bad:
            with self.subTest(a):
                with self.assertRaises(policy.PolicyError):
                    policy.check_asc_args(a, write=True)

    def test_confirm_flag_still_forbidden(self):
        with self.assertRaises(policy.PolicyError):
            policy.check_asc_args(["builds", "upload", "--app", "1", "--confirm"], write=True)

    def test_read_commands(self):
        policy.check_asc_args(["builds", "wait", "--app", "1", "--build-number", "24", "--version", "1.12.0",
                               "--platform", "IOS", "--timeout", "45m"], write=False)
        policy.check_asc_args(["builds", "list", "--app", "1"], write=False)
        policy.check_asc_args(["builds", "info", "--app", "1"], write=False)
        policy.check_asc_args(["versions", "list", "--app", "1"], write=False)

    def test_hook_allows_new_subcommands(self):
        for c in ["python3 tools/aso/aso.py build --version 1.12.0",
                  "python3 tools/aso/aso.py release-plan --build-json '/a b/build.json'",
                  "python3 tools/aso/aso.py pull-version --version 1.12.0"]:
            self.assertEqual(policy.hook_decision(c, self.summ)[0], "allow", c)

    def test_hook_blocks_chained_new_subcommand(self):
        self.assertEqual(policy.hook_decision(
            "python3 tools/aso/aso.py build --version 1.12.0; rm -rf x", self.summ)[0], "block")


class AssetCppCommandsTests(unittest.TestCase):
    """Asset library, placements, custom product page (allowlist giữ sẵn, template chưa có lệnh dùng)."""
    L = "localizations"
    C = ["product-pages", "custom-pages"]
    OK = {
        "img-up": ["asset-library", "images", "upload", "--library-id", "1", "--file", "/a.png",
                   "--category", "x", "--reference-name", "n"],
        "vid-up": ["asset-library", "videos", "upload", "--library-id", "1", "--file", "/a.mp4",
                   "--category", "x", "--reference-name", "n"],
        "poster": ["asset-library", "videos", "set-poster-frame", "--id", "1", "--time-code", "00:00:01"],
        "pl-create-img": ["localizations", "placements", "create", "--localization-id", "1", "--image-id", "2",
                          "--placement-type", "t", "--placement-group", "g"],
        "pl-create-vid": ["localizations", "placements", "create", "--localization-id", "1", "--video-id", "2",
                          "--placement-type", "t", "--placement-group", "g"],
        "cpp-pl-create": ["product-pages", "custom-pages", "localizations", "placements", "create",
                          "--localization-id", "1", "--image-id", "2", "--placement-type", "t",
                          "--placement-group", "g"],
        "pl-delete": ["localizations", "placements", "delete", "--placement-ids", "1,2", "--confirm"],
        "cpp-pl-delete": ["product-pages", "custom-pages", "localizations", "placements", "delete",
                          "--placement-ids", "1,2", "--confirm"],
        "cpp-loc-create": ["product-pages", "custom-pages", "localizations", "create",
                           "--custom-page-version-id", "1", "--locale", "en-US", "--promotional-text", "x"],
        "cpp-loc-update": ["product-pages", "custom-pages", "localizations", "update",
                           "--localization-id", "1", "--promotional-text", "x"],
        "kw-add": ["product-pages", "custom-pages", "localizations", "search-keywords", "add",
                   "--localization-id", "1", "--keywords", "a,b"],
        "kw-del": ["product-pages", "custom-pages", "localizations", "search-keywords", "delete",
                   "--localization-id", "1", "--keywords", "a,b", "--confirm"],
    }

    def test_valid_writes_ok_and_not_readable(self):
        for name, a in self.OK.items():
            with self.subTest(name):
                policy.check_asc_args(a, write=True)
                with self.assertRaises(policy.PolicyError):
                    policy.check_asc_args(a, write=False)

    def test_equals_form_ok(self):
        policy.check_asc_args(["product-pages", "custom-pages", "localizations", "update", "--localization-id=1",
                               "--promotional-text=x"], write=True)

    def test_missing_extra_repeated_flags_rejected(self):
        for name, a in self.OK.items():
            flags = [t for t in a if t.startswith("--")]
            bare = "--confirm" in a
            bad = [a + ["--bogus", "x"], a + ["positional"], a + ["--output", "json"]]
            for f in flags:
                k = a.index(f)
                n = 1 if f == "--confirm" else 2
                bad.append(a[:k] + a[k + n:])               # thiếu cờ
                bad.append(a + a[k:k + n])                  # cờ lặp
            for b in bad:
                with self.subTest(name=name, args=b):
                    with self.assertRaises(policy.PolicyError):
                        policy.check_asc_args(b, write=True)
            self.assertTrue(bare or "--confirm" not in a)

    def test_placement_create_exactly_one_of_image_video(self):
        for pre in (["localizations", "placements", "create"], self.C + ["localizations", "placements", "create"]):
            base = ["--localization-id", "1", "--placement-type", "t", "--placement-group", "g"]
            policy.check_asc_args(pre + base + ["--image-id", "2"], write=True)
            for extra in ([], ["--image-id", "2", "--video-id", "3"], ["--image-id", "2", "--image-id", "3"]):
                with self.assertRaises(policy.PolicyError, msg=extra):
                    policy.check_asc_args(pre + base + extra, write=True)

    def test_confirm_only_where_listed(self):
        for name in ("img-up", "pl-create-img", "cpp-pl-create", "cpp-loc-create", "kw-add", "cpp-loc-update"):
            with self.assertRaises(policy.PolicyError, msg=name):
                policy.check_asc_args(self.OK[name] + ["--confirm"], write=True)
        with self.assertRaises(policy.PolicyError):
            policy.check_asc_args(self.OK["pl-delete"] + ["--confirm=true"], write=True)
        with self.assertRaises(policy.PolicyError):
            policy.check_asc_args(["builds", "upload", "--app", "1", "--ipa", "/a", "--confirm"], write=True)

    def test_forbidden_commands(self):
        cmds = [["asset-library", k, v, "--id", "x", "--confirm"] for k in ("images", "videos")
                for v in ("delete", "archive", "unarchive", "rename")]
        cmds += [["localizations", "placements", "swap", "--placement-ids", "1,2"],
                 self.C + ["localizations", "placements", "swap", "--placement-ids", "1,2"],
                 self.C + ["delete", "--id", "x", "--confirm"], self.C + ["update", "--id", "x"],
                 self.C + ["localizations", "delete", "--id", "x", "--confirm"],
                 ["review", "submissions-submit", "--id", "x"], ["review", "submissions-create"],
                 ["product-pages", "experiments", "create"], ["product-pages", "experiments", "list"],
                 # M-c: không op nào tạo CPP / version CPP — tạo tay trên ASC (least privilege)
                 self.C + ["create", "--app", "1", "--name", "n"],
                 self.C + ["versions", "create", "--custom-page-id", "1"]]
        for a in cmds:
            for w in (True, False):
                with self.subTest(a=a, w=w):
                    with self.assertRaises(policy.PolicyError):
                        policy.check_asc_args(a, write=w)

    def test_reorder_bi_cam_han(self):
        # Tool không sắp thứ tự placement (API không cho đọc thứ tự hiển thị) ⇒ cả hai lệnh reorder bị cấm hẳn
        for pre in (["localizations", "placements", "reorder"],
                    self.C + ["localizations", "placements", "reorder"]):
            a = pre + ["--localization-id", "1", "--placement-group", "g", "--placement-ids", "1,2"]
            for w in (True, False):
                with self.subTest(a=a, w=w):
                    with self.assertRaisesRegex(policy.PolicyError, "bị cấm hoàn toàn"):
                        policy.check_asc_args(a, write=w)
            self.assertIn(tuple(pre), policy.FORBIDDEN_COMMANDS)
            self.assertNotIn(tuple(pre), policy.WRITE_COMMANDS)
            self.assertNotIn(tuple(pre), policy.WRITE_FLAGS)

    def test_cpp_create_va_version_create_bi_cam_han(self):
        for a in (self.C + ["create", "--app", "1", "--name", "n"], self.C + ["versions", "create", "--custom-page-id", "1"]):
            with self.assertRaisesRegex(policy.PolicyError, "bị cấm hoàn toàn"):
                policy.check_asc_args(a, write=True)
        self.assertNotIn(("product-pages", "custom-pages", "create"), policy.WRITE_COMMANDS)
        self.assertNotIn(("product-pages", "custom-pages", "versions", "create"), policy.WRITE_COMMANDS)

    def test_read_commands(self):
        for a in (["asset-library", "view", "--app", "1"], ["asset-library", "images", "list", "--library-id", "1"],
                  ["asset-library", "images", "view", "--id", "1"], ["asset-library", "videos", "list"],
                  ["asset-library", "videos", "view", "--id", "1"], ["localizations", "placements", "list"],
                  self.C + ["list", "--app", "1"], self.C + ["view", "--id", "1"],
                  self.C + ["versions", "list"], self.C + ["localizations", "list"],
                  self.C + ["localizations", "placements", "list"],
                  self.C + ["localizations", "search-keywords", "list"]):
            with self.subTest(a):
                policy.check_asc_args(a, write=False)
                with self.assertRaises(policy.PolicyError):
                    policy.check_asc_args(a, write=True)

    def test_lenh_con_khong_co_trong_aso_bi_chan(self):
        # Allowlist chỉ gồm lệnh con aso.py thật sự có (SUBCOMMANDS): lệnh con của app nguồn mà template không mang
        # (ảnh/CPP, web) không còn là dạng chuẩn.
        def summ(p, e=None):
            return None
        for sub in ("assets-pull", "assets-plan", "web-release", "frobnicate"):
            self.assertEqual(policy.hook_decision(
                f"python3 tools/aso/aso.py {sub} --version 1.12.0", summ)[0], "block", sub)

    def test_git_config_dat_lenh_roi_chay_bi_chan(self):
        # Ghi cấu hình git chứa lệnh (alias `!`, core.fsmonitor, core.hooksPath, textconv, sshCommand) rồi chạy một
        # lệnh git bình thường ⇒ asc ghi thẳng mà không xác nhận. Mọi dạng phải bị chặn, với mọi toán tử nối.
        summ = HookDecisionTests.summ
        dat = ["git config alias.x '!asc metadata push --dir d'",
               "git config --global alias.x '!asc metadata push --dir d'",
               "git config --file f alias.x '!asc metadata push --dir d'",
               "git -C /tmp/e config core.fsmonitor '!asc metadata push --dir d'",
               "git config core.sshCommand 'asc metadata push --dir d'",
               "git config diff.x.textconv 'python3 tools/aso/applier.py'",
               "git config core.hooksPath tools/aso"]
        chay = ["git x", "git -C /tmp/e status", "git fetch", "git commit -m y", "git diff"]
        for a in dat:
            for b in chay:
                for op in (" && ", "; ", " || ", "\n"):
                    c = a + op + b
                    self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)
        for c in ["git -c core.fsmonitor='!asc metadata push' status",
                  "git -c core.hooksPath=tools/aso commit -m x",
                  "git --git-dir=/tmp/e/.git -c alias.y='!asc versions list' y",
                  "env git config alias.x '!asc metadata push'"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)

    def test_dong_bat_dau_bang_git_khong_mien_ca_dong(self):
        # Backstop 2 chỉ miễn khi MỌI đoạn là git "chữ": một dòng mở đầu bằng git không được che đoạn sau đưa `asc`
        # qua biến vào shell.
        summ = HookDecisionTests.summ
        for c in ["git status; X='asc metadata push' bash -c \"$X\"",
                  "git log -1 && Y='asc versions list' sh -c \"$Y\""]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)
        self.assertEqual(policy.hook_decision('git commit -m "asc metadata push"; git status', summ)[0], "allow")

    def test_git_config_doc_hoac_ghi_vo_hai_cho_qua(self):
        # Luật (Ruling 6): `git config` là "safe" — đọc/xoá mọi khoá và ĐẶT khoá vô hại thì qua; ĐẶT khoá chạy được
        # lệnh thì chặn, bất kể giá trị (kể cả `core.hooksPath .githooks` — làm tay).
        summ = HookDecisionTests.summ
        for c in ["git config user.name X", "git config --get remote.origin.url", "git config --list",
                  "git config --get core.hooksPath", "git config --unset alias.x", "git config alias.st status",
                  "git config core.hooksPath", "git -C '/a b' status", "git fetch origin",
                  "git -c color.ui=never log --oneline"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "allow", c)
        self.assertEqual(policy.hook_decision("git config core.hooksPath .githooks", summ)[0], "block")
        self.assertEqual(policy._git_kind("git config --get remote.origin.url"), "safe")
        self.assertEqual(policy._git_kind("git --git-dir=/x/.git status"), "text")
        self.assertEqual(policy._git_kind("git -C /x status"), "text")
        self.assertEqual(policy._git_kind("git --no-optional-locks status"), "text")
        self.assertEqual(policy._git_kind("git xaso"), "exec")

    def test_asc_go_nhay_va_hoa_thuong_bi_chan(self):
        # Shell gỡ nháy trước khi chạy: `'a''sc'` = asc; chữ hoa cũng là lệnh asc trên ổ không phân biệt hoa thường.
        summ = HookDecisionTests.summ
        for c in ["git config --global alias.x '!a''sc metadata push --dir d' && git x",
                  "git config alias.x '!ASC metadata push --dir d'",
                  "git -c core.pager='a''sc metadata push' log",
                  "GIT_PAGER='a''sc metadata push' git log",
                  "X='a''sc metadata push' bash -c \"$X\"",
                  "ASC metadata push --dir d",
                  "A\"S\"C metadata push --dir d",
                  "bash -c 'a\"\"sc metadata push'",
                  "timeout 5 Asc versions list",
                  "git xaso '!a''sc'"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)

    def test_dat_khoa_git_chay_lenh_bi_chan_bat_ke_gia_tri(self):
        summ = HookDecisionTests.summ
        for key in ["core.fsmonitor", "core.hooksPath", "core.pager", "core.sshCommand", "core.editor",
                    "diff.x.textconv", "diff.external", "gpg.program", "gpg.ssh.program", "include.path",
                    "includeIf.gitdir:/x/.path", "filter.lfs.clean", "sequence.editor", "pager.log",
                    "credential.helper", "merge.x.driver"]:
            for c in [f"git config {key} /bin/true", f"git config --global {key} vô-hại",
                      f"git config --file f {key} x", f"git config set {key} x",
                      f"git -c {key}=x status", f"git -C /tmp/e -c {key}=x log",
                      f"git --config-env={key}=SOME_VAR status", f"git --config-env {key}=SOME_VAR log"]:
                self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)
        for c in ["git config alias.x '!sh x.sh'", "git --config-env=alias.x=V x"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)
        for env in ["GIT_CONFIG_COUNT=1", "GIT_CONFIG_KEY_0=core.pager", "GIT_CONFIG_VALUE_0=x",
                    "GIT_CONFIG_PARAMETERS=x", "GIT_PAGER=less", "GIT_EXTERNAL_DIFF=x", "GIT_SSH_COMMAND=ssh",
                    "GIT_EDITOR=vi", "GIT_SEQUENCE_EDITOR=vi"]:
            for c in [f"{env} git log", f"export {env}", f"env {env} git status"]:
                self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)

    def test_ruling8_lo_hong_round3_bi_chan(self):
        summ = HookDecisionTests.summ
        for c in [
            # (a) alias không `!` mà thân chứa lệnh asc; grep -O; push --receive-pack.
            "git config alias.x \"fetch --upload-pack='asc metadata push --dir d' .\" && git x",
            "git config alias.y \"grep -O'asc metadata push' -e foo\" && git y",
            "git config alias.z \"push --receive-pack='asc metadata push' .\"",
            "git -c alias.x=\"fetch --upload-pack='asc metadata push' .\" x",
            # (b) tuỳ chọn viết tắt / dính.
            "git fetch --upl='sh -c \"asc metadata push\" x' .",
            "git grep '-Osh -c \"asc metadata push\" x' -e foo",
            "git push --rec='a''sc metadata push' .",
            # (c) ext transport.
            "git -c protocol.allow=always fetch 'ext::asc metadata push --dir d'",
            "git -c protocol.allow=always fetch origin",
            "GIT_ALLOW_PROTOCOL=ext git fetch x",
            # (d) EDITOR/VISUAL.
            "git status && EDITOR='sh -c \"asc metadata push\" x' git commit --allow-empty",
            "VISUAL='sh x.sh' git commit --allow-empty",
            "git checkout asc-branch-not-a-word && git checkout ASC",
            # (e) chuẩn hoá đường dẫn thư mục cài.
            "~/.local/share/ios-app-factory/./asc/5.17.1/as? version",
            "ls ~/.local/share/ios-app-factory//asc", "ls ~/.local/share/ios-app-factory/x/../asc",
            # chỉ luật thư mục cài (đã chuẩn hoá) bắt được: basename không phải asc, không glob.
            "cp x ~/.local/share/ios-app-factory/./asc/", "ls \"$HOME/.local/share/ios-app-factory/x/../asc/5.17.1\"",
            "chmod +x ~/.local/share/ios-app-factory//asc/5.17.1",
            "ls ~/.local/share/ios-app-factory/a?c/", "ls '/u/.local/share/ios-app-factory/'[a]sc"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)

    def test_ruling8_gia_tri_tro_va_message_cho_qua(self):
        summ = HookDecisionTests.summ
        for c in ["GIT_EDITOR=true git rebase --continue", "git -c core.editor=true rebase --continue",
                  "GIT_PAGER=cat git log", "git -c core.pager=cat log", "git -c core.pager= log",
                  "EDITOR=: git commit --allow-empty", "git config core.pager cat", "git config alias.nop '!true'",
                  "git config alias.st status", "git log --grep asc", "git log --grep=ASC",
                  "git commit -m \"feat: asc metadata push qua aso.py\"", "git commit -m'asc'",
                  "git log -S asc --oneline", "git commit -S -m 'asc ready'", "echo asc", "printf 'asc\\n'",
                  "git checkout asc-branch", "ls ~/.local/share/ios-app-factory/"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "allow", c)

    def test_hookspath_bao_viec_cua_nguoi_dung(self):
        d, why = policy.hook_decision("git config core.hooksPath .githooks", HookDecisionTests.summ)
        self.assertEqual(d, "block")
        self.assertTrue(why.startswith(policy.HUMAN_ONLY), why)
        self.assertFalse(policy.needs_canon_hint(why))
        self.assertNotIn("tools/aso", why)

    def test_thu_muc_cai_asc_bi_chan(self):
        summ = HookDecisionTests.summ
        for c in ["ls ~/.local/share/ios-app-factory/asc/", "~/.local/share/ios-app-factory/asc/5.17.1/x version",
                  "cp /tmp/y \"$HOME/.local/share/ios-app-factory/as\"c/1/asc",
                  "find ~/.local/share/ios-app-factory/ASC -type f"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)
        self.assertEqual(policy.hook_decision("ls ~/.local/share/ios-app-factory/", summ)[0], "allow")

    def test_git_thuong_ngay_khong_bi_chan_nham(self):
        # Ruling 6: -C/--git-dir/--work-tree không đổi loại; nhóm "safe" không bị xét vùng/cwd/import trên
        # đường dẫn/message; message không bao giờ bị quét import; `--grep asc` là chữ.
        summ = HookDecisionTests.summ
        tools = str(ROOT / "tools")
        cmds = ["git -C /abs/path diff -- tools/aso/policy.py", "git -C '/a b' log -- tools/aso/aso.py",
                "git --git-dir=/r/.git --work-tree=/r show HEAD:tools/aso/policy.py",
                "git checkout develop -- tools/aso/policy.py", "git restore tools/aso/x.py",
                "git stash push -- tools/aso", "git grep foo -- tools/aso", "git stash push -m \"from lint fix\"",
                "git -C r log --grep asc", "git log --grep=ASC --oneline", "git commit -m 'import aso; from lint x'",
                "git branch -m feature/aso-fix", "git switch -c fix/tools-aso", "git reset HEAD tools/aso/x.py",
                "git fetch origin && git merge --ff-only origin/develop", "git tag -a v1 -m 'asc ready'",
                "git worktree list", "git remote -v", "git clean -n -- tools/aso",
                "git cherry-pick abc123", "git pull --ff-only"]
        for c in cmds:
            self.assertEqual(policy.hook_decision(c, summ)[0], "allow", c)
        for c in ["git status", "git checkout develop -- aso.py", "git stash list", "git diff"]:
            self.assertEqual(policy.hook_decision(c, summ, cwd=tools)[0], "allow", (c, "cwd tools"))
        # Phía chặn vẫn giữ: lệnh con safe có tuỳ chọn chạy chương trình ⇒ exec.
        for c in ["git fetch --upload-pack='python3 tools/aso/applier.py' /r",
                  "git grep -O 'python3 tools/aso/applier.py' foo",
                  "git push --receive-pack='a''sc metadata push' /r"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)

    def test_round4_message_chi_bo_o_lenh_con_message(self):
        # R1: `-F`/`-m` chỉ là message ở commit/tag/merge/stash/notes/revert/cherry-pick; `grep -F` (chuỗi cố định),
        # `fetch -m` (--multiple) không có giá trị ⇒ token kế tiếp vẫn bị dò. Không bao giờ bỏ token bắt đầu bằng `-`.
        summ = HookDecisionTests.summ
        for c in ["git grep -F -O'sh -c \"asc metadata push --dir d\" x' -e foo",
                  "git fetch -m --upload-pack='sh -c \"asc metadata push\" x' .",
                  "git fetch -m 'ext::sh -c \"a\"\"sc metadata push --dir d\" x' origin",
                  "git push -F 'ext::sh -c \"asc metadata push\" x' main",
                  "git commit -m -O'asc metadata push' --allow-empty",
                  "git grep -Oasc -e foo", "git grep -O'a''sc' -e foo", "git grep -Oa?c -e foo",
                  "git log --grep -O'asc metadata push'"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)

    def test_round4_go_nhay_long_nhau_de_quy(self):
        # R2: shell gỡ nháy nhiều lớp (git split_cmdline cho thân alias, sh -c cho chuỗi lệnh) ⇒ dò trên mọi lớp.
        summ = HookDecisionTests.summ
        for c in ["git fetch --upload-pack='sh -c \"a\"\"sc metadata push\" x' .",
                  "git config alias.x \"fetch --upload-pack='a''sc metadata push --dir d' .\"",
                  "git config alias.x \"fetch --upload-pack='sh -c \\\"a\\\"\\\"sc metadata push\\\" x' .\"",
                  "timeout 5 sh -c 'a\"\"sc metadata push --dir d'",
                  "timeout 5 bash -c \"sh -c 'a\\\"\\\"sc metadata push'\"",
                  "env -S 'a\"\"sc metadata push' x"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)

    def test_round4_glob_nham_asc_bi_chan(self):
        # R3: basename glob khớp asc (không chung chung) = chữ asc; đường dẫn có chuỗi thư mục cài dạng glob ⇒ chạm.
        summ = HookDecisionTests.summ
        for c in ["timeout 5 ~/.local/share/*/asc/*/a?c metadata push --dir d",
                  "nice -n 5 a?c metadata push --dir d",
                  "nohup ~/.local/share/*/asc/*/asc metadata push --dir d",
                  "git fetch --upload-pack='/opt/x/a?c metadata push' .",
                  "git fetch --upload-pack='/opt/x/[a]sc' .",
                  "sh -c '/opt/x/*/* metadata push --dir d'",
                  "ls ~/.local/share/i*/a*/", "ls '/u/x/'*/asc/5.17.1/"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)
        self.assertTrue(policy._asc_token("/opt/x/a?c"))
        self.assertTrue(policy._asc_token("--upload-pack=/p/[A]SC"))
        for t in ["*", "build/*", "*.py", "[a-z]*", "src/**/*.swift", "?"]:
            self.assertFalse(policy._asc_token(t), t)
        self.assertTrue(policy._touches_install_dir("~/.local/share/*/asc/*/a?c"))
        self.assertFalse(policy._touches_install_dir("ls build/*/* src/*/x.py"))

    def test_round4_wrapper_trong_suot(self):
        # Mọi tiền tố chạy lệnh khác (timeout, nice, caffeinate, sudo, xcrun…) trong suốt với MỌI luật, kể cả luật khoá
        # cấu hình git và luật glob ở vị trí lệnh.
        summ = HookDecisionTests.summ
        for c in ["timeout 5 git -c core.fsmonitor='sh x.sh' status",
                  "nice -n 10 git -c core.pager=less log", "caffeinate -i git config core.hooksPath x",
                  "stdbuf -oL git -c alias.x='!sh x.sh' x", "sudo -u me git config core.sshCommand ssh",
                  "timeout -s KILL 5 nohup env GIT_PAGER=less git log", "command git -c diff.external=x diff",
                  "time -p ionice -c 3 git config --global core.editor vi", "doas -u me git -c gpg.program=x log",
                  "arch -arm64 git -c core.pager=less log", "builtin exec git -c core.pager=less log",
                  "timeout 5 ./x/*.sh", "xcrun --sdk iphoneos git -c core.pager=less log"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)
        self.assertEqual(policy._peel(["timeout", "-k", "3", "5", "nice", "-n", "5", "X=1", "git", "log"])[0], 8)
        self.assertEqual(policy._git_kind("timeout 5 git commit -m 'python3 tools/aso/aso.py'"), "text")

    def test_round4_lop_viet_chu_cua_shell_bi_go(self):
        # Các lớp viết chữ shell gỡ trước khi chạy (không phải tên ghép lúc chạy): ANSI-C, nối dòng, ngoặc nhọn, giá trị
        # mặc định của biến; tiền tố lạ trước git/shell; env -S; IOS_APP_FACTORY_BIN.
        summ = HookDecisionTests.summ
        for c in ["$'\\141sc' metadata push --dir d", "timeout 5 $'\\x61sc' versions list",
                  "sh -c \"$'\\\\141sc' metadata push --dir d\"",
                  "git config alias.x \"!sh -c \\\"\\$'\\\\\\\\141sc' metadata push\\\"\"",
                  "a\\\nsc metadata push --dir d", "timeout 5 {a,}sc metadata push", "nice ${X:-asc} metadata push",
                  "env -S'a\"\"sc metadata push' x", "strace git -c core.pager='sh x.sh' log",
                  "strace sh -c 'git -c core.fsmonitor=x status'", "strace -f sh -c './x/*.sh'",
                  "ls ~/.local/share/ios-app-factory/{asc,x}/"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)
        from unittest import mock
        with mock.patch.dict("os.environ", {"IOS_APP_FACTORY_BIN": "/opt/rieng/bin"}):
            self.assertEqual(policy.hook_decision("/opt/rieng/bin/a?c/1/x metadata push", summ)[0], "block")
            self.assertEqual(policy.hook_decision("ls /opt/rieng/bin/", summ)[0], "allow")

    def test_round4_lenh_thuong_ngay_van_qua(self):
        summ = HookDecisionTests.summ
        for c in ["git log -- docs/javascript.md", "git checkout feature/cascade", "git grep basic",
                  "GIT_EDITOR=true git rebase --continue", "git commit -m \"fix: asc metadata push qua aso.py\"",
                  "git log --grep asc", "echo asc", "git grep -F foo -- src", "git fetch -m origin upstream",
                  "git stash push -m 'asc wip'", "git tag -a v1 -F notes.txt", "git merge -m 'asc' feature/x",
                  "git revert -m 1 HEAD", "git cherry-pick -m 1 abc123", "git notes add -m 'asc'",
                  "git log -S asc -G asc --author asc --oneline", "git show --grep=asc HEAD",
                  "timeout 60 git status", "nice -n 5 git log --oneline", "time git commit -m 'asc'",
                  "ls build/*", "rm -rf build/*", "git add 'src/*.swift'", "ls ~/.local/share/ios-app-factory/",
                  "timeout 120 python3 -m pytest -q", "caffeinate -i make build",
                  "xcrun simctl list devices", "sudo -n true", "env -i PATH=/usr/bin ls",
                  "cp a.txt a.txt{,.bak}", "echo ${HOME:-/tmp}", "git log --format='%h %s' -n 5",
                  "git commit -F msg.txt", "git -c core.quotepath=off status", "printf '%s\\n' $'a\\tb'",
                  "bash -c 'ls -la && git status'", "git diff HEAD~1 -- 'tools/*'"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "allow", c)

    def test_offline_fixture_dang_bang(self):
        # Chỉ dạng `--offline-fixture DIR` (cách) là chuẩn; `--offline-fixture=DIR` bị chặn — cả với lệnh chỉ-đọc.
        summ = HookDecisionTests.summ
        for c in ["python3 tools/aso/aso.py --offline-fixture=fx lint",
                  "python3 tools/aso/aso.py --offline-fixture=fx apply --plan p.json --expect ab12cd34"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)

    def test_offline_fixture_truoc_lenh_con_chi_doc(self):
        summ = HookDecisionTests.summ
        for c in ["python3 tools/aso/aso.py --offline-fixture tools/aso/fixtures/app-moi lint",
                  "python3 tools/aso/aso.py --offline-fixture '/tmp/a b/fx' plan --version 1.2.3",
                  "python3 tools/aso/aso.py --offline-fixture fx release-plan --build-json '/a b/build.json'"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "allow", c)
        for c in ["python3 tools/aso/aso.py --offline-fixture fx apply --plan p.json --expect ab12cd34",
                  "python3 tools/aso/aso.py --offline-fixture fx --offline-fixture fy lint",
                  "python3 tools/aso/aso.py --offline-fixture fx assets-plan",
                  "python3 tools/aso/aso.py --offline-fixture fx lint; rm -rf x"]:
            self.assertEqual(policy.hook_decision(c, summ)[0], "block", c)
        self.assertNotIn("assets-", policy.CANON_MSG)
        self.assertNotIn("web-release", policy.CANON_MSG)

    def test_subcommands_khop_parser_aso(self):
        import aso
        parser, dispatch = aso.build_parser()
        self.assertEqual(set(policy.SUBCOMMANDS) | {"apply"}, set(dispatch))
        for sub in policy.SUBCOMMANDS:
            self.assertIn(sub, policy.CANON_MSG)

    def test_git_chi_truyen_chu_khong_phai_chay_code(self):
        for c in ['git commit -m "feat: python3 tools/aso/aso.py plan"',
                  'git commit -m "env cho tools/aso; source tools/aso/x"',
                  "git --no-optional-locks commit -q -m 'import aso từ python3 tools/aso'",
                  "git log --grep 'python3 tools/aso'", "git show HEAD:tools/aso/policy.py",
                  "git diff -- tools/aso/policy.py", "git status --short tools/aso",
                  "git add tools/aso/policy.py tools/aso/test_policy.py",
                  "git -C '/a b' commit -F msg.txt"]:
            self.assertEqual(policy.hook_decision(c, HookDecisionTests.summ)[0], "allow", c)

    def test_git_chay_duoc_code_van_bi_chan(self):
        for c in ['git -c core.hooksPath=/tmp/h commit -m "sửa tools/aso"',
                  "git -c alias.x=log x tools/aso/aso.py",
                  "git xaso tools/aso/aso.py plan",
                  "git --exec-path=tools/aso status",
                  "GIT_EXTERNAL_DIFF=tools/aso/x.py git diff",
                  "git diff --ext-diff tools/aso/policy.py",
                  "git bisect run tools/aso/aso.py lint",
                  'git commit -m "$(python3 tools/aso/aso.py lint)"',
                  "git diff <(python3 tools/aso/aso.py lint) x"]:
            self.assertEqual(policy.hook_decision(c, HookDecisionTests.summ)[0], "block", c)


if __name__ == "__main__":
    unittest.main()
