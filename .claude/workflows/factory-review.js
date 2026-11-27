export const meta = {
  name: 'factory-review',
  description: 'Nhà máy agent: review nhánh theo 4 lăng kính (đúng/invariant, test có gác, UI+i18n, bảo mật/privacy/tự chủ) rồi 2 phản biện độc lập mỗi phát hiện',
  whenToUse: 'Cổng L3 trước merge vào develop, hoặc khi cần review độc lập một nhánh. args = { base?: "develop", focus?: "…" }',
  phases: [
    { title: 'Tìm', detail: '4 lăng kính song song trên diff base...HEAD' },
    { title: 'Phản biện', detail: '2 agent cố bác bỏ mỗi phát hiện' },
  ],
}

const BASE = (args && args.base) || 'develop'
const FOCUS = (args && args.focus) ? `\nTrọng tâm user/giám đốc nêu: ${args.focus}` : ''
const SCOPE = `Phạm vi: \`git diff ${BASE}...HEAD\` (và \`git diff\` nếu còn thay đổi chưa commit) trong thư mục làm việc hiện tại.${FOCUS}
Chỉ báo lỗi THẬT có hậu quả (sai hành vi, hỏng build/test, phá invariant, lộ dữ liệu, vi phạm quy ước dự án có hậu quả). BỎ QUA style, đặt tên, sở thích. Không có lỗi thật ⇒ trả findings rỗng.`

const LENSES = [
  { key: 'dung', tier: { model: 'opus', effort: 'high' }, prompt: `Lăng kính ĐÚNG ĐẮN + INVARIANT. Đọc diff, lần theo call site. Kiểm logic, ca biên, xử lý lỗi, invariant trong docs/ARCHITECTURE.md và quy ước .claude/rules/conventions.core.md + conventions.app.md (định danh chỉ ở app.config.toml, sửa project.yml không sửa .xcodeproj), tất định (duyệt Dictionary), luồng async/actor.` },
  { key: 'test', tier: { model: 'opus', effort: 'high' }, prompt: `Lăng kính TEST CÓ GÁC. Test mới/đổi có thật sự đỏ khi code sai không? Chọn tối đa 3 bất biến quan trọng nhất của diff, chứng minh bằng \`python3 tools/factory/mutate.py --file … --find … --replace … -- <lệnh test hẹp>\` (Swift: \`python3 tools/dev/run_tests.py <Class>\`; Python: \`python3 -m unittest …\`). MUTATION SURVIVED = phát hiện. Code logic mới mà không có test = phát hiện.` },
  { key: 'ui', tier: { model: 'sonnet', effort: 'medium' }, prompt: `Lăng kính UI + i18n + iPhone/iPad. Chuỗi UI qua biến String thiếu String(localized:); chuỗi debug ngoài dtext/#if INTERNAL; bố cục theo userInterfaceIdiom thay vì size class; .confirmationDialog thay vì .alert; điều hướng dựng song song cho tab bar và sidebar thay vì một nguồn. Chạy \`python3 tools/i18n/lint_localizable.py\`. Diff không đụng UI ⇒ findings rỗng.` },
  { key: 'an-toan', tier: { model: 'opus', effort: 'medium' }, prompt: `Lăng kính BẢO MẬT + PRIVACY + TỰ CHỦ. Bí mật/key trong code hoặc log; literal định danh ngoài app.config.toml (\`python3 tools/common/lint_identity.py\`); dữ liệu người dùng gửi ra ngoài ngoài khai báo App Privacy/PrivacyInfo.xcprivacy; code debug lọt bản Release (thiếu \`#if INTERNAL\`, type debug mới chưa có trong AppHost/Config/debug_symbols.app.txt hoặc tools/release/debug_symbols.txt); script/hook có thể đẩy/deploy/upload mà không qua cổng (guard_autonomy); hook không fail-safe.` },
]

// Phát hiện của lăng kính đúng đắn ⇒ phản biện opus/high; lăng kính khác ⇒ cùng model, effort medium.
const refuteTier = l => l.key === 'dung' ? { model: 'opus', effort: 'high' } : { model: l.tier.model, effort: 'medium' }

const FINDINGS = {
  type: 'object',
  properties: { findings: { type: 'array', items: { type: 'object', properties: {
    title: { type: 'string' }, file: { type: 'string' }, line: { type: 'number' },
    severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
    scenario: { type: 'string', description: 'đầu vào/trạng thái cụ thể → sai thế nào' },
    evidence: { type: 'string', description: 'lệnh đã chạy / dòng code' } },
    required: ['title', 'file', 'severity', 'scenario', 'evidence'] } } },
  required: ['findings'],
}
const VERDICT = {
  type: 'object',
  properties: { real: { type: 'boolean' }, reason: { type: 'string' } },
  required: ['real', 'reason'],
}

const perLens = await pipeline(
  LENSES,
  l => agent(`${l.prompt}\n\n${SCOPE}`, { label: `tìm:${l.key}`, phase: 'Tìm', schema: FINDINGS, ...l.tier }),
  (res, l) => parallel(((res && res.findings) || []).map((f, i) => () =>
    parallel([0, 1].map(k => () => agent(
      `Cố BÁC BỎ phát hiện review sau (lăng kính ${l.key}). Đọc code thật, chạy lệnh nếu cần. Phát hiện chỉ "real" khi kịch bản lỗi thật xảy ra được và có hậu quả; nghi ngờ ⇒ real=false.\n` +
      `Phạm vi: git diff ${BASE}...HEAD.\nPhát hiện: ${JSON.stringify(f)}\n` +
      (k ? 'Góc nhìn: thử TÁI HIỆN (chạy/viết phép thử nhỏ trong .temp/factory/).' : 'Góc nhìn: đọc kỹ ngữ cảnh code xung quanh và call site.'),
      { label: `bác:${l.key}#${i + 1}.${k + 1}`, phase: 'Phản biện', schema: VERDICT, ...refuteTier(l) })))
      .then(vs => {
        const ok = vs.filter(Boolean).filter(v => v.real).length
        return ok ? { ...f, lens: l.key, verdict: ok === 2 ? 'CONFIRMED' : 'PLAUSIBLE', reasons: vs.filter(Boolean).map(v => v.reason) } : null
      }))),
)

const rank = { blocker: 0, major: 1, minor: 2 }
const sorted = perLens.flat().filter(Boolean)
  .sort((a, b) => (rank[a.severity] - rank[b.severity]) || (a.verdict === 'CONFIRMED' ? -1 : 1))
// Gộp trùng giữa các lăng kính (cùng một lỗi hay bị nhiều lăng kính báo). Chỉ gộp khi
// KHÁC lăng kính, cùng file, CẢ HAI có số dòng và cách ≤ 8 dòng; bản bị gộp giữ nguyên đủ trường trong `also` để
// giám đốc vẫn đọc được — gộp theo cửa sổ rộng/thiếu dòng từng nuốt lỗi khác nhau.
const kept = []
for (const f of sorted) {
  const dup = f.line > 0 && kept.find(k => k.file === f.file && k.lens !== f.lens && k.line > 0 &&
    Math.abs(k.line - f.line) <= 8 && !(k.also || []).some(a => a.lens === f.lens))
  if (dup) { dup.also = [...(dup.also || []), f]; continue }
  kept.push({ ...f })
}
const raw = perLens.flat().length
log(`Giữ ${kept.length} phát hiện sau phản biện + gộp trùng (CONFIRMED ${kept.filter(k => k.verdict === 'CONFIRMED').length}).`)
return { base: BASE, kept, dropped_note: `đã loại các phát hiện bị cả 2 phản biện bác và gộp trùng (tổng đầu vào ${raw}, sau phản biện ${sorted.length})` }
