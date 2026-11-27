export const meta = {
  name: 'factory-execute',
  description: 'Nhà máy agent: chạy task graph của một mission — thợ theo vai → verifier độc lập → sửa theo phát hiện (≤1 vòng — trần 2 FAIL); task iOS tuần tự',
  whenToUse: 'Giám đốc (skill factory) đã có ledger nhiều task; truyền args.mission = JSON của `mission.py show --json`',
  phases: [
    { title: 'Thi công', detail: 'thợ theo vai làm từng task theo thứ tự phụ thuộc' },
    { title: 'Kiểm chứng', detail: 'factory-verifier kiểm độc lập, FAIL thì thợ sửa lại' },
  ],
}

// args = { mission: <mission.json>, maxFixRounds?: number, only?: ["T1", ...] }
const M = args && args.mission
if (!M || !Array.isArray(M.tasks)) throw new Error('factory-execute cần args.mission = JSON của `python3 tools/factory/mission.py show --json`')
// Trần 2 lần FAIL mỗi task (lần đầu + 1 vòng sửa) — khớp MAX_ATTEMPTS trong tools/factory/mission.py.
const MAX_FIX = (args.maxFixRounds ?? 1)
const DONE = new Set(['verified', 'skipped'])
// Vai tự kiểm (đầu ra của chúng đã là phán quyết có bằng chứng) — không cần verifier chồng lên.
const SELF_VERIFYING = new Set(['ui-reviewer', 'factory-critic', 'factory-verifier'])
// Vai/tiêu chí dùng simulator/Xcode ⇒ chạy tuần tự (phiên/agent song song dùng chung simulator của worktree).
const SIM_ROLES = new Set(['ios-engineer', 'ui-reviewer'])
const usesSim = t => SIM_ROLES.has(t.role) || (t.verify || []).some(v => /run_tests\.py|xcodebuild|ui_shots|simctl|selfcheck\.sh/.test(v))

const VERDICT = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    criteria: { type: 'array', items: { type: 'object', properties: {
      criterion: { type: 'string' }, result: { type: 'string', enum: ['PASS', 'FAIL', 'UNVERIFIABLE'] }, evidence: { type: 'string' } },
      required: ['criterion', 'result', 'evidence'] } },
    findings: { type: 'array', items: { type: 'object', properties: {
      severity: { type: 'string' }, class: { type: 'string' }, problem: { type: 'string' }, where: { type: 'string' },
      instances: { type: 'array', items: { type: 'string' } }, repro: { type: 'string' }, fix_strategy: { type: 'string' } },
      required: ['severity', 'class', 'problem'] } },
    debt: { type: 'array', items: { type: 'string' } },
    ledger_evidence: { type: 'string' },
  },
  required: ['verdict', 'criteria', 'findings', 'ledger_evidence'],
}

// Bậc model/effort từng vai — PHẢI khớp frontmatter `.claude/agents/<vai>.md` (test_lint_harness gác).
// Dùng khi agentType không nạp được (fallback general-purpose sẽ mất frontmatter).
const ROLE_TIER = {
  'factory-planner': { model: 'opus', effort: 'high' },
  'factory-critic': { model: 'opus', effort: 'high' },
  'factory-verifier': { model: 'opus', effort: 'high' },
  'ios-engineer': { model: 'opus', effort: 'high' },
  'platform-engineer': { model: 'sonnet', effort: 'medium' },
  'researcher': { model: 'sonnet', effort: 'medium' },
  'release-manager': { model: 'sonnet', effort: 'medium' },
  'ui-reviewer': { model: 'sonnet', effort: 'medium' },
  'factory-scribe': { model: 'sonnet', effort: 'low' },
}
const tierFor = role => ROLE_TIER[role] || {}

// Đếm MỌI lượt agent (kể cả lượt fallback) để giám đốc `tick` đúng số — agent trong workflow không được cộng vào
// ngân sách thì cảnh báo vòng lặp mất tác dụng đúng ở task lớn.
let AGENT_RUNS = 0
const RUNS_BY_TASK = {}
async function roleAgent(role, prompt, opts, t) {
  const tier = tierFor(role)
  AGENT_RUNS++
  if (t) RUNS_BY_TASK[t.id] = (RUNS_BY_TASK[t.id] || 0) + 1
  try {
    return await agent(prompt, { ...tier, ...opts, agentType: role })
  } catch (e) {
    AGENT_RUNS++
    if (t) RUNS_BY_TASK[t.id] = (RUNS_BY_TASK[t.id] || 0) + 1
    log(`agentType ${role} không dùng được (${(e && e.message) || e}) — chạy general-purpose đọc .claude/agents/${role}.md, giữ bậc ${tier.model || 'phiên'}/${tier.effort || 'phiên'}`)
    return agent(`Bạn đóng vai \`${role}\` của nhà máy agent: ĐỌC KỸ \`.claude/agents/${role}.md\` và làm đúng như đó là system prompt của bạn (vai, luật, định dạng Ra).\n\n${prompt}`,
      { ...tier, ...opts, agentType: 'general-purpose' })
  }
}

const list = xs => (xs || []).map((x, i) => `${i + 1}. ${x}`).join('\n') || '(không có)'

// Báo cáo của thợ theo task id — chuyển cho task phụ thuộc (bàn giao qua file + brief, không qua trí nhớ).
const REPORTS = {}
const ART = `.factory/missions/${M.id}/artifacts`
const clip = (s, n) => (typeof s === 'string' ? s : JSON.stringify(s)).slice(0, n)

function depsSection(t) {
  const deps = (t.depends || []).filter(d => REPORTS[d])
  if (!deps.length) return ''
  return 'Kết quả các task phụ thuộc (đã được verifier duyệt; bản đầy đủ có thể ở `' + ART + '/<id>.md`):\n' +
    deps.map(d => `--- ${d} ---\n${clip(REPORTS[d], 12000)}`).join('\n')
}

// Kiểm chứng gọn: L2 chạy lặp ở nhiều vai và agent ngồi poll `while sleep` là hai nguồn đốt lượt lớn nhất.
const LEAN_RULES = [
  'Kiểm chứng gọn: L1 theo đúng class (`python3 tools/dev/run_tests.py FooTests`), KHÔNG chạy `--full` (L2 chỉ chạy một lần ở task "Tích hợp L2"), KHÔNG chạy `tools/i18n/verify_catalog.py`, KHÔNG tự chạy `mutate.py` (verifier làm).',
  'Lệnh dài (build/test/ui_shots): chạy Bash foreground với `timeout: 600000`. CẤM `&`/`nohup` rồi vòng `sleep`/`until`/`while kill -0` — mỗi vòng chờ là một lượt model đọc lại cả context.',
].join('\n')

function workerBrief(t, findings) {
  return [
    `Mission ${M.id} (mục tiêu: "${M.goal}"), task ${t.id}: ${t.title}.`,
    `Nhánh: ${M.branch || '(nhánh hiện tại)'}. Làm trong thư mục làm việc hiện tại.`,
    `Đầu ra dài (bảng, dữ liệu): ghi ra \`${ART}/${t.id}.md\` (gitignored) và nêu đường dẫn trong báo cáo.`,
    depsSection(t),
    `Tiêu chí (phải đạt hết):\n${list(t.acceptance)}`,
    `Lệnh verifier sẽ chạy:\n${list(t.verify)}`,
    t.notes ? `Ghi chú/ràng buộc: ${t.notes}` : '',
    findings ? `VÒNG SỬA — verifier độc lập báo FAIL:\n${JSON.stringify(findings, null, 1)}\n\nSửa CẢ LỚP: mọi \`instances\`, rồi tự grep thêm chỗ cùng \`class\` có thể bị sót. \`fix_strategy\` là bất biến/test thuộc tính ⇒ viết test đó trước, đừng vá từng ca. Báo cáo liệt kê mọi chỗ đã rà.` : '',
    LEAN_RULES,
    'Chỉ làm task này. Không commit, không push. Trả báo cáo đúng mẫu "Ra" của vai bạn, có dòng bằng chứng cho mỗi lệnh đã chạy.',
  ].filter(Boolean).join('\n\n')
}

function verifierBrief(t, prior) {
  return [
    `Kiểm độc lập task ${t.id} của mission ${M.id}: ${t.title}. Bạn KHÔNG có báo cáo của thợ — tự kiểm trên mã nguồn hiện tại (\`git status\`, \`git diff\`).`,
    `Tiêu chí:\n${list(t.acceptance)}`,
    `Lệnh verify:\n${list(t.verify)}`,
    'Có test mới bảo vệ bất biến ⇒ `python3 tools/factory/mutate.py` chứng minh test đỏ khi phá code — TỐI ĐA 3 mutant mỗi task, chọn bất biến quan trọng nhất. Mặc định FAIL nếu thiếu bằng chứng.',
    'KHÔNG chạy `run_tests.py --full` (trừ khi đây là task "Tích hợp L2"), KHÔNG chạy `verify_catalog.py`. Lệnh dài: Bash foreground `timeout: 600000`, không chạy nền rồi poll.',
    'Quét cạn (luật trong .claude/agents/factory-verifier.md): không dừng ở lỗi đầu; mỗi finding có `class` (slug cơ chế, ổn định giữa các vòng) + mọi `instances`; lớp mở ⇒ `fix_strategy` = bất biến + test thuộc tính.',
    prior ? `VÒNG KIỂM LẠI — finding vòng trước:\n${JSON.stringify(prior, null, 1)}\nKiểm từng finding (cả instances) đã hết, hồi quy trong diff sửa, chạy lại mọi lệnh verify. Lỗi MỚI ngoài diff sửa và ngoài các lớp trên chỉ FAIL nếu blocker/major có repro; còn lại ghi vào \`debt\`.` : '',
    'Trả kết quả qua StructuredOutput đúng schema.',
  ].filter(Boolean).join('\n\n')
}

async function runTask(t) {
  const label = `${t.id}·${t.role}`
  let findings = null
  let lastWorker = null
  const seen = {}  // class ⇒ số vòng FAIL; lặp lại ⇒ escalate, không vá tiếp
  const debt = []
  for (let round = 0; round <= MAX_FIX; round++) {
    const tag = round ? ` (sửa ${round})` : ''
    if (SELF_VERIFYING.has(t.role)) {
      const v = await roleAgent(t.role, workerBrief(t, findings) + '\n\nTrả phán quyết qua StructuredOutput: verdict PASS/FAIL, criteria có evidence, findings.',
        { label: label + tag, phase: 'Kiểm chứng', schema: VERDICT }, t)
      if (!v) return { id: t.id, status: 'failed', note: 'agent không trả kết quả' }
      if (v.verdict === 'PASS') REPORTS[t.id] = v
      return { id: t.id, status: v.verdict === 'PASS' ? 'verified' : 'failed', by: 'director', reviewer: t.role,
        evidence: v.ledger_evidence, criteria: v.criteria, findings: v.findings, rounds: round }
    }
    lastWorker = await roleAgent(t.role, workerBrief(t, findings), { label: label + tag, phase: 'Thi công' }, t)
    if (lastWorker === null) return { id: t.id, status: 'failed', note: 'thợ không trả kết quả (bị bỏ qua hoặc lỗi API)' }
    const v = await roleAgent('factory-verifier', verifierBrief(t, findings), { label: `${t.id}·verify${tag}`, phase: 'Kiểm chứng', schema: VERDICT }, t)
    if (!v) return { id: t.id, status: 'failed', note: 'verifier không trả kết quả', worker: lastWorker }
    debt.push(...(v.debt || []))
    if (v.verdict === 'PASS') {
      REPORTS[t.id] = lastWorker
      return { id: t.id, status: 'verified', by: 'factory-verifier', evidence: v.ledger_evidence, criteria: v.criteria,
        findings: v.findings, debt, rounds: round, worker: lastWorker }
    }
    findings = v.findings.length ? v.findings : v.criteria.filter(c => c.result !== 'PASS').map(c => ({ severity: 'major', class: 'criterion-fail', problem: c.criterion, repro: c.evidence }))
    const classes = [...new Set(findings.map(f => f.class).filter(Boolean))]
    const hot = classes.filter(c => seen[c])
    classes.forEach(c => { seen[c] = (seen[c] || 0) + 1 })
    log(`${t.id} FAIL vòng ${round} [${classes.join(', ') || '?'}]: ${(findings[0] && findings[0].problem) || 'xem criteria'}`)
    if (hot.length) {
      return { id: t.id, status: 'failed', escalate: hot, fail_classes: classes, findings, debt, worker: lastWorker, rounds: round,
        note: `ESCALATE: lớp ${hot.join(', ')} FAIL lần 2 — đổi cách (bất biến + test thuộc tính / thu hẹp / hỏi user), đừng vá tiếp` }
    }
  }
  return { id: t.id, status: 'failed', exhausted: true, fail_classes: Object.keys(seen), findings, debt, worker: lastWorker,
    note: `FAIL sau ${MAX_FIX} vòng sửa — giám đốc quyết (blocked/đổi plan)` }
}

// ---- lập lịch theo phụ thuộc: mỗi đợt = task sẵn sàng; task dùng simulator chạy nối tiếp, phần còn lại song song
const only = args.only ? new Set(args.only) : null
const pending = M.tasks.filter(t => !DONE.has(t.status) && t.status !== 'blocked' && (!only || only.has(t.id)))
const done = new Set(M.tasks.filter(t => DONE.has(t.status)).map(t => t.id))
const results = []
const failed = new Set()
let wave = 0
while (pending.length) {
  const ready = pending.filter(t => (t.depends || []).every(d => done.has(d)))
  const dead = pending.filter(t => (t.depends || []).some(d => failed.has(d) || (!done.has(d) && !pending.find(p => p.id === d))))
  for (const t of dead) {
    results.push({ id: t.id, status: 'skipped_by_dependency', note: `phụ thuộc chưa xong: ${(t.depends || []).filter(d => !done.has(d)).join(', ')}` })
    pending.splice(pending.indexOf(t), 1)
    failed.add(t.id)
  }
  if (!ready.length) {
    if (dead.length) continue
    log('Không task nào sẵn sàng (vòng phụ thuộc?) — dừng: ' + pending.map(t => t.id).join(', '))
    for (const t of pending) results.push({ id: t.id, status: 'skipped_by_dependency', note: 'không giải được phụ thuộc' })
    break
  }
  wave++
  const sim = ready.filter(usesSim)
  const free = ready.filter(t => !usesSim(t))
  log(`Đợt ${wave}: ${sim.map(t => t.id).join(',') || '-'} (tuần tự, simulator) | ${free.map(t => t.id).join(',') || '-'} (song song)`)
  const serialChain = async () => { const out = []; for (const t of sim) out.push(await runTask(t)); return out }
  const outs = await parallel([serialChain, ...free.map(t => () => runTask(t))])
  const flat = outs.filter(Boolean).flat()
  for (const r of flat) {
    results.push(r)
    if (r.status === 'verified') done.add(r.id); else failed.add(r.id)
  }
  for (const t of ready) pending.splice(pending.indexOf(t), 1)
}

// Quote đơn kiểu POSIX: backtick/$ trong evidence không bị bash thực thi.
const shq = s => "'" + String(s).replace(/'/g, "'\\''") + "'"
const summary = results.map(r => `${r.id}: ${r.status}${r.escalate ? ` ESCALATE[${r.escalate.join(',')}]` : ''}${r.rounds ? ` (${r.rounds} vòng sửa)` : ''}`).join('; ')
log('Kết quả: ' + summary + ` — ${AGENT_RUNS} lượt agent`)
const tickWhat = 'factory-execute: ' + Object.entries(RUNS_BY_TASK).map(([k, n]) => `${k}×${n}`).join(' ')
return { mission: M.id, results, summary, agent_runs: AGENT_RUNS, runs_by_task: RUNS_BY_TASK,
  ledger_commands: [
    ...(AGENT_RUNS ? [`python3 tools/factory/mission.py tick ${AGENT_RUNS} --mission ${M.id} --what ${shq(tickWhat)}`] : []),
    ...results.flatMap(r => r.status === 'verified'
    ? [`python3 tools/factory/mission.py set ${r.id} --mission ${M.id} --status verified --by ${r.by} --evidence ${shq(r.evidence || '')}`]
    : r.status === 'failed'
      ? [`python3 tools/factory/mission.py set ${r.id} --mission ${M.id} --status failed ${(r.fail_classes && r.fail_classes.length ? r.fail_classes : ['unclassified']).map(c => '--fail-class ' + shq(c)).join(' ')} --note ${shq(r.note || '')}`]
      : []) ] }
