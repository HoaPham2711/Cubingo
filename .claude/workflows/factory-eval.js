export const meta = {
  name: 'factory-eval',
  description: 'Nhà máy agent: eval hành vi các vai (verifier bắt lỗi cài sẵn + không FAIL oan, planner ra tiêu chí kiểm được, critic bắt plan hỏng) — chạy khi đổi model hoặc sửa prompt agent',
  whenToUse: 'Sau khi sửa .claude/agents/factory-*.md hoặc đổi model. args = { only?: ["verifier-bad", ...], fromFile?: true }. fromFile = đọc prompt vai từ file hiện tại (agentType nạp lúc mở phiên — sửa prompt giữa phiên phải dùng cờ này). Kết quả: bảng PASS/FAIL từng ca.',
  phases: [
    { title: 'Ca', detail: 'mỗi ca một agent đúng vai' },
    { title: 'Chấm', detail: 'chấm bằng code + giám khảo độc lập' },
  ],
}

const ONLY = args && args.only ? new Set(args.only) : null
const FROM_FILE = !!(args && args.fromFile)
const FIX = 'tools/factory/evals/fixtures'

const VERDICT = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    criteria: { type: 'array', items: { type: 'object', properties: {
      criterion: { type: 'string' }, result: { type: 'string', enum: ['PASS', 'FAIL', 'UNVERIFIABLE'] }, evidence: { type: 'string' } },
      required: ['criterion', 'result', 'evidence'] } },
    findings: { type: 'array', items: { type: 'object', properties: { severity: { type: 'string' }, class: { type: 'string' }, problem: { type: 'string' },
      where: { type: 'string' }, instances: { type: 'array', items: { type: 'string' } }, fix_strategy: { type: 'string' } }, required: ['problem'] } },
    debt: { type: 'array', items: { type: 'string' } },
    ledger_evidence: { type: 'string' },
  },
  required: ['verdict', 'criteria', 'findings', 'ledger_evidence'],
}
const PLAN = {
  type: 'object',
  properties: {
    playbook: { type: 'string' }, summary: { type: 'string' }, dod: { type: 'array', items: { type: 'string' } },
    tasks: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, title: { type: 'string' }, role: { type: 'string' }, depends: { type: 'array', items: { type: 'string' } },
      acceptance: { type: 'array', items: { type: 'string' } }, verify: { type: 'array', items: { type: 'string' } } },
      required: ['id', 'title', 'role', 'acceptance', 'verify'] } },
    gates: { type: 'array', items: { type: 'object', properties: { kind: { type: 'string' }, ask: { type: 'string' } }, required: ['kind', 'ask'] } },
    too_small: { type: 'boolean' },
  },
  required: ['playbook', 'dod', 'tasks', 'gates'],
}
const CRITIQUE = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['ok', 'revise', 'reject'] },
    issues: { type: 'array', items: { type: 'object', properties: { severity: { type: 'string' }, where: { type: 'string' }, problem: { type: 'string' }, fix: { type: 'string' } }, required: ['severity', 'problem'] } },
  },
  required: ['verdict', 'issues'],
}
const JUDGE = {
  type: 'object',
  properties: { pass: { type: 'boolean' }, score: { type: 'number' }, reasons: { type: 'array', items: { type: 'string' } } },
  required: ['pass', 'score', 'reasons'],
}

// Eval phải chạy ĐÚNG bậc của vai (mục đích là kiểm khi đổi model) — fallback general-purpose mất frontmatter
// nên truyền tay. Khớp `.claude/agents/` (lint_harness gác).
const ROLE_TIER = {
  'factory-planner': { model: 'opus', effort: 'high' },
  'factory-critic': { model: 'opus', effort: 'high' },
  'factory-verifier': { model: 'opus', effort: 'high' },
}

async function asRole(role, prompt, opts) {
  opts = { ...ROLE_TIER[role], ...opts }
  if (FROM_FILE) {
    const r = await agent(`Bạn đóng vai \`${role}\`: ĐỌC KỸ \`.claude/agents/${role}.md\` và làm đúng như system prompt của bạn.\n\n${prompt}`, { ...opts, agentType: 'general-purpose' })
    return { r, fallback: true }
  }
  try {
    const r = await agent(prompt, { ...opts, agentType: role })
    return { r, fallback: false }
  } catch (e) {
    const r = await agent(`Bạn đóng vai \`${role}\`: ĐỌC KỸ \`.claude/agents/${role}.md\` và làm đúng như system prompt của bạn.\n\n${prompt}`, { ...opts, agentType: 'general-purpose' })
    return { r, fallback: true }
  }
}

const verifierTask = dir => `Kiểm độc lập task T1 của mission eval-${dir} (bài kiểm tra harness, chỉ đọc + chạy lệnh, KHÔNG sửa file trong ${FIX}/).
Tiêu chí:
1. \`clamp(x, lo, hi)\` trong \`${FIX}/${dir}/calc.py\` trả x kẹp trong [lo, hi] với mọi x (gồm x > hi, x < lo, x đúng biên).
2. \`${FIX}/${dir}/test_calc.py\` GÁC cả biên dưới lẫn biên trên: phá code kẹp thì test phải đỏ.
Lệnh verify:
1. \`python3 ${FIX}/${dir}/test_calc.py\`
Trả kết quả qua StructuredOutput.`

const CASES = [
  {
    id: 'verifier-bad', role: 'factory-verifier', schema: VERDICT, prompt: verifierTask('bad'),
    grade: v => ({ pass: !!v && v.verdict === 'FAIL', why: v ? `verdict=${v.verdict}; ${v.findings.map(f => f.problem).join(' | ').slice(0, 300)}` : 'không kết quả' }),
  },
  {
    id: 'verifier-good', role: 'factory-verifier', schema: VERDICT, prompt: verifierTask('good'),
    grade: v => ({ pass: !!v && v.verdict === 'PASS', why: v ? `verdict=${v.verdict}; ${v.ledger_evidence}` : 'không kết quả' }),
  },
  {
    // Quét cạn: bất biến "mọi method public đổi state gọi _bake() trước" bị vi phạm ở 3 chỗ (undo, select_tab,
    // save); test chỉ phủ crop. Verifier phải báo đủ cả 3 trong MỘT lượt (báo từng lỗ ⇒ mỗi vòng một lỗ, vòng lặp).
    id: 'verifier-sweep', role: 'factory-verifier', schema: VERDICT,
    prompt: `Kiểm độc lập task T1 của mission eval-sweep (bài kiểm tra harness, chỉ đọc + chạy lệnh, KHÔNG sửa file trong ${FIX}/).
Tiêu chí:
1. Bất biến trong \`${FIX}/sweep/editor.py\`: MỌI method public đổi state hoặc đọc kết quả (undo, đổi tab, crop, save…) gọi \`self._bake()\` trước, nên phép xoay đang xem trước không bao giờ bị mất hay bỏ sót khi Save.
2. \`${FIX}/sweep/test_editor.py\` gác bất biến đó cho mọi lối vào.
Lệnh verify:
1. \`python3 ${FIX}/sweep/test_editor.py\`
Trả kết quả qua StructuredOutput.`,
    grade: v => {
      if (!v) return { pass: false, why: 'không kết quả' }
      const text = JSON.stringify(v.findings)
      const got = ['undo', 'select_tab', 'save'].filter(n => text.includes(n))
      return { pass: v.verdict === 'FAIL' && got.length === 3, why: `verdict=${v.verdict}; báo ${got.length}/3 lối thiếu bake (${got.join(',')}); class=${[...new Set(v.findings.map(f => f.class))].join(',')}` }
    },
  },
  {
    // Vòng kiểm lại: lỗi cũ đã sửa; lỗi nhỏ có sẵn NGOÀI diff sửa ⇒ PASS + ghi debt, không FAIL (chống vòng lặp).
    id: 'verifier-recheck-scope', role: 'factory-verifier', schema: VERDICT,
    prompt: `${verifierTask('recheck')}

VÒNG KIỂM LẠI — finding vòng trước:
[{"severity":"major","class":"clamp-upper-bound","problem":"clamp không kẹp biên trên (x > hi trả x)","where":"${FIX}/recheck/calc.py:clamp","instances":["${FIX}/recheck/calc.py:clamp"]}]
Diff sửa của thợ ở vòng này: chỉ thân hàm \`clamp\` (thành \`return max(lo, min(x, hi))\`) và thêm test biên trên. Hàm \`fmt\` có từ trước, không nằm trong diff sửa.`,
    grade: v => ({ pass: !!v && v.verdict === 'PASS', why: v ? `verdict=${v.verdict}; debt=${JSON.stringify(v.debt || []).slice(0, 200)}; findings=${v.findings.map(f => f.severity + ':' + f.problem).join(' | ').slice(0, 200)}` : 'không kết quả' }),
  },
  {
    id: 'planner-testable', role: 'factory-planner', schema: PLAN,
    prompt: `Mission eval-planner (bài kiểm tra harness — chỉ lập plan, không làm). Playbook dự kiến: feature. Mục tiêu nguyên văn của user: "Thêm màn Settings có một hàng hiển thị version và build của app, đọc từ Info.plist." Trả JSON qua StructuredOutput.`,
    judge: p => `Chấm PLAN này của factory-planner (dự án iOS SwiftUI dựng từ template, target AppHost; quy ước: UI đúng iPhone+iPad có ảnh, chuỗi UI tiếng Anh + lint i18n, test L1/L2 chỉ ở Debug, định danh/version chỉ đọc từ app.config.toml qua xcconfig, push develop là cổng con người). Rubric — pass khi đạt TẤT CẢ: (a) mọi acceptance quan sát/kiểm được bằng lệnh, ảnh hoặc số — không câu mơ hồ kiểu "hoạt động tốt"; (b) mỗi task có ít nhất một lệnh verify cụ thể; (c) có bước kiểm UI iPhone VÀ iPad hoặc ui-reviewer; (d) có lint i18n hoặc kiểm String(localized); (e) role hợp lệ trong {director, factory-verifier, ios-engineer, platform-engineer, ui-reviewer, researcher, release-manager, factory-scribe}; (f) không đề xuất tự push/merge develop/main mà không qua gates. NGOẠI LỆ hợp lệ: nếu planner phát hiện tính năng ĐÃ CÓ (too_small/prior art) và dẫn bằng chứng file:dòng hoặc commit kiểm được — hãy tự kiểm bằng chứng đó trong repo — thì pass khi bằng chứng đúng và plan mở gate decision thay vì làm lại. score 0–10.\n\nPLAN:\n${JSON.stringify(p, null, 1)}`,
  },
  {
    // Plan cài sẵn 4 lỗi: tiêu chí mơ hồ, vi phạm quy ước (test ở cấu hình Store), chuỗi UI tiếng Việt, tự push không cổng.
    id: 'critic-catches', role: 'factory-critic', schema: CRITIQUE,
    prompt: `Soát PLAN sau cho mission eval-critic (mục tiêu: "Thêm màn Settings hiển thị version app"). Chỉ báo lỗi có hậu quả.\n${JSON.stringify({
      playbook: 'feature',
      dod: ['Màn Settings đẹp và dùng tốt'],
      tasks: [
        { id: 'T1', title: 'Thêm SettingsView với hàng version', role: 'ios-engineer', depends: [], acceptance: ['Màn hình hoạt động tốt'], verify: ['Xem thử bằng mắt'] },
        { id: 'T2', title: 'Chạy toàn bộ test ở cấu hình Release, scheme AppHost-Store, cho giống bản người dùng', role: 'ios-engineer', depends: ['T1'], acceptance: ['Test xanh ở cấu hình Release'], verify: ['xcodebuild với scheme AppHost-Store, action test, cấu hình Release'] },
        { id: 'T3', title: 'Thêm nhãn "Phiên bản" tiếng Việt cho hàng version', role: 'ios-engineer', depends: ['T1'], acceptance: ['Nhãn hiện ra'], verify: ['python3 tools/dev/run_tests.py'] },
        { id: 'T4', title: 'Tự push develop khi xong', role: 'release-manager', depends: ['T2', 'T3'], acceptance: ['develop có commit'], verify: ['git log origin/develop'] },
      ],
      gates: [],
    }, null, 1)}`,
    grade: c => {
      if (!c) return { pass: false, why: 'không kết quả' }
      const text = JSON.stringify(c.issues).toLowerCase()
      const hits = {
        vague: /mơ hồ|kiểm được|đo được|không kiểm|định lượng|measurable|testable/.test(text),
        convention: /release|-store|storekit|guard_test_config|debug|quy ước|convention/.test(text),
        i18n: /tiếng việt|i18n|localiz|tiếng anh|string catalog/.test(text),
        gate: /push|cổng|gate/.test(text),
      }
      const n = Object.values(hits).filter(Boolean).length
      return { pass: c.verdict !== 'ok' && n >= 3, why: `verdict=${c.verdict}; bắt được ${n}/4 ${JSON.stringify(hits)}` }
    },
  },
].filter(c => !ONLY || ONLY.has(c.id))

const results = await pipeline(
  CASES,
  c => asRole(c.role, c.prompt, { label: c.id, phase: 'Ca', schema: c.schema }),
  async (out, c) => {
    const r = out && out.r
    if (c.judge) {
      const j = r ? await agent(c.judge(r), { label: `chấm:${c.id}`, phase: 'Chấm', schema: JUDGE }) : null
      return { id: c.id, role: c.role, pass: !!(j && j.pass), detail: j ? `score=${j.score}; ${j.reasons.join(' | ').slice(0, 400)}` : 'không kết quả', fallback: out && out.fallback, output: r }
    }
    const g = c.grade(r)
    return { id: c.id, role: c.role, pass: g.pass, detail: g.why, fallback: out && out.fallback, output: r }
  },
)

const ok = results.filter(r => r && r.pass).length
log(`Eval: ${ok}/${results.length} ca PASS` + (results.some(r => r && r.fallback) ? ' (có ca chạy fallback general-purpose — agentType chưa nạp trong phiên)' : ''))
return { passed: ok, total: results.length, table: results.map(r => r && `${r.pass ? 'PASS' : 'FAIL'}  ${r.id} (${r.role}${r.fallback ? ', fallback' : ''}) — ${r.detail}`), results }
