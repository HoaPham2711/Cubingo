"""Test lint_harness: harness thật phải sạch, và từng loại lỗi cài sẵn phải bị bắt."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lint_harness as L  # noqa: E402

GOOD_AGENT = """---
name: good-agent
description: Agent mẫu hợp lệ dùng trong test lint harness, đủ dài để qua ngưỡng mô tả.
tools: Read, Grep, Bash
model: sonnet
effort: high
memory: project
skills:
  - demo
---
Đọc `tools/factory/mission.py`.
"""
GOOD_SKILL = """---
name: demo
description: Skill mẫu.
---
Xem [phụ](extra.md).
"""
GOOD_WF = """export const meta = {
  name: 'demo-wf',
  description: 'Workflow mẫu (có ngoặc trong chuỗi)',
  phases: [{ title: 'Một' }],
}
phase('Một')
const r = await agent('x', { phase: 'Một' })
return r
"""


class LintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "tools" / "factory").mkdir(parents=True)
        (self.root / "tools" / "factory" / "mission.py").write_text("#", encoding="utf-8")
        self.w("agents/good-agent.md", GOOD_AGENT)
        self.w("skills/demo/SKILL.md", GOOD_SKILL)
        self.w("skills/demo/extra.md", "phụ")
        self.w("workflows/demo-wf.js", GOOD_WF)
        self.w("hooks/h.py", "")
        self.w("settings.json", json.dumps({"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/h.py"'}]}]}}))
        self.w("agent-memory/good-agent/MEMORY.md", "- x")

    def tearDown(self):
        self.tmp.cleanup()

    def w(self, rel, text):
        p = self.root / ".claude" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def errors(self):
        return L.run(self.root).errors

    def test_mau_hop_le_sach(self):
        self.assertEqual(self.errors(), [])

    def test_harness_that_cua_repo_sach(self):
        self.assertEqual(L.run(L.ROOT).errors, [])

    def test_khoa_agent_la(self):
        self.w("agents/good-agent.md", GOOD_AGENT.replace("effort: high", "effort: high\nallowed-tools: Read"))
        self.assertTrue(any("khoá frontmatter lạ `allowed-tools`" in e for e in self.errors()))

    def test_ten_agent_lech_file(self):
        self.w("agents/good-agent.md", GOOD_AGENT.replace("name: good-agent", "name: other"))
        self.assertTrue(any("≠ tên file" in e for e in self.errors()))

    def test_model_tool_skill_sai(self):
        self.w("agents/good-agent.md", GOOD_AGENT.replace("model: sonnet", "model: gpt-5")
               .replace("tools: Read, Grep, Bash", "tools: Read, Grap").replace("  - demo", "  - khong-co"))
        errs = " ".join(self.errors())
        self.assertIn("model `gpt-5`", errs)
        self.assertIn("tool lạ `Grap`", errs)
        self.assertIn("skill `khong-co`", errs)

    def test_role_tier_lech_frontmatter(self):
        self.w("workflows/tier.js", GOOD_WF.replace("'demo-wf'", "'tier'") +
               "const ROLE_TIER = {\n  'good-agent': { model: 'opus', effort: 'high' },\n  'ma': { model: 'opus', effort: 'low' },\n}\n")
        errs = " ".join(self.errors())
        self.assertIn("ROLE_TIER `good-agent` = opus/high ≠ frontmatter sonnet/high", errs)
        self.assertIn("vai `ma` không tồn tại", errs)

    def test_role_tier_khop_thi_sach(self):
        self.w("workflows/tier.js", GOOD_WF.replace("'demo-wf'", "'tier'") +
               "const ROLE_TIER = {\n  'good-agent': { model: 'sonnet', effort: 'high' },\n}\n")
        self.assertEqual(self.errors(), [])

    def test_thieu_thu_muc_con_van_sach(self):
        """.claude/ chỉ có hooks + settings.json (chưa có agents/skills/workflows) vẫn rc 0."""
        self.addCleanup(setattr, L, "ROOT", L.ROOT)  # main() đặt lại ROOT toàn cục
        shutil.rmtree(self.root / ".claude" / "agents")
        shutil.rmtree(self.root / ".claude" / "skills")
        shutil.rmtree(self.root / ".claude" / "workflows")
        shutil.rmtree(self.root / ".claude" / "agent-memory")
        self.assertEqual(self.errors(), [])
        self.assertEqual(L.main(["--quiet", "--root", str(self.root)]), 0)

    def test_khong_co_claude_van_sach(self):
        self.addCleanup(setattr, L, "ROOT", L.ROOT)
        shutil.rmtree(self.root / ".claude")
        self.assertEqual(self.errors(), [])
        self.assertEqual(L.main(["--quiet", "--root", str(self.root)]), 0)

    def test_cam_isolation_worktree(self):
        self.w("agents/good-agent.md", GOOD_AGENT.replace("memory: project", "memory: project\nisolation: worktree"))
        self.assertTrue(any("isolation: worktree" in e for e in self.errors()))

    def test_duong_dan_khong_ton_tai(self):
        self.w("agents/good-agent.md", GOOD_AGENT.replace("tools/factory/mission.py", "tools/factory/khong.py"))
        self.assertTrue(any("khong.py" in e for e in self.errors()))

    def test_link_skill_hong(self):
        (self.root / ".claude" / "skills" / "demo" / "extra.md").unlink()
        self.assertTrue(any("extra.md" in e for e in self.errors()))

    def test_workflow_meta_khong_literal(self):
        self.w("workflows/demo-wf.js", GOOD_WF.replace("'Workflow mẫu (có ngoặc trong chuỗi)'", "String(1)"))
        self.assertTrue(any("literal" in e for e in self.errors()))

    def test_workflow_ten_lech_va_date_now(self):
        self.w("workflows/demo-wf.js", GOOD_WF.replace("'demo-wf'", "'khac'").replace("return r", "return Date.now()"))
        errs = " ".join(self.errors())
        self.assertIn("meta.name", errs)
        self.assertIn("Date.now()", errs)

    @unittest.skipUnless(shutil.which("node"), "cần node")
    def test_workflow_cu_phap_loi(self):
        self.w("workflows/demo-wf.js", GOOD_WF.replace("return r", "return r +"))
        self.assertTrue(any("cú pháp" in e for e in self.errors()))

    def test_meta_khong_dung_dau(self):
        self.w("workflows/demo-wf.js", "const x = 1\n" + GOOD_WF)
        self.assertTrue(any("câu lệnh đầu tiên" in e for e in self.errors()))

    def test_hook_tro_file_mat(self):
        (self.root / ".claude" / "hooks" / "h.py").unlink()
        self.assertTrue(any("hook Stop" in e for e in self.errors()))

    def test_agent_memory_mo_coi(self):
        self.w("agent-memory/ma/MEMORY.md", "- x")
        self.assertTrue(any("agent-memory/ma" in e for e in self.errors()))


if __name__ == "__main__":
    unittest.main()
