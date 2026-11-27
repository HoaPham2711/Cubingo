export const meta = {
  name: 'factory-research',
  description: 'Nhà máy agent: research nhiều góc song song (nguồn gốc, thực hành, học thuật, thị trường) → kiểm chéo khẳng định then chốt → tổng hợp có nguồn',
  whenToUse: 'Playbook research. args = { question: "…", angles?: ["…"], context?: "…" }',
  phases: [
    { title: 'Tìm', detail: 'mỗi góc một researcher' },
    { title: 'Kiểm chéo', detail: 'khẳng định một-nguồn được kiểm bằng nguồn thứ hai' },
    { title: 'Tổng hợp' },
  ],
}

const Q = args && args.question
if (!Q) throw new Error('factory-research cần args.question')
const CTX = (args && args.context) ? `\nBối cảnh: ${args.context}` : ''
const ANGLES = (args && args.angles) || [
  'Nguồn GỐC: tài liệu chính thức, docs của nhà cung cấp, changelog, bài kỹ thuật của chính tác giả',
  'THỰC HÀNH: kỹ sư/cộng đồng đang làm gì thật (GitHub, blog kỹ thuật, diễn đàn) — tách số đo với quảng cáo',
  'HỌC THUẬT/SỐ ĐO: paper, benchmark, nghiên cứu có số — ghi rõ điều kiện đo',
  'THỊ TRƯỜNG/ĐỐI THỦ + liên hệ app: app/dịch vụ cạnh tranh, App Store, hệ quả cho app (grep docs/research/ nếu có, docs/superpowers/ và memory trước)',
]

const CLAIMS = {
  type: 'object',
  properties: { claims: { type: 'array', items: { type: 'object', properties: {
    claim: { type: 'string' }, url: { type: 'string' }, primary: { type: 'boolean' },
    importance: { type: 'string', enum: ['then-chot', 'phu'] } },
    required: ['claim', 'url', 'primary', 'importance'] } },
    notes: { type: 'string' } },
  required: ['claims'],
}
const CHECK = {
  type: 'object',
  properties: { status: { type: 'string', enum: ['xac-nhan', 'mau-thuan', 'khong-tim-thay'] }, url: { type: 'string' }, note: { type: 'string' } },
  required: ['status', 'note'],
}

const found = await pipeline(
  ANGLES,
  (angle, _a, i) => agent(`Câu hỏi: ${Q}${CTX}\nGóc tìm của bạn: ${angle}.\nDùng WebSearch/WebFetch. Liệt kê 4–10 khẳng định, mỗi cái một URL; primary=true nếu là nguồn gốc. Hôm nay: chạy \`date\`.`,
    { label: `tìm#${i + 1}`, phase: 'Tìm', schema: CLAIMS, agentType: 'researcher' }).catch(() =>
    agent(`Đọc .claude/agents/researcher.md và làm theo. Câu hỏi: ${Q}${CTX}\nGóc: ${angle}.`, { label: `tìm#${i + 1}`, phase: 'Tìm', schema: CLAIMS, model: 'sonnet', effort: 'medium' })),
  (res, _a, i) => parallel(((res && res.claims) || [])
    .filter(c => c.importance === 'then-chot' && !c.primary)
    .map((c, k) => () => agent(`Kiểm chéo khẳng định bằng một nguồn ĐỘC LẬP khác (không phải ${c.url}): "${c.claim}". Không tìm được ⇒ khong-tim-thay.`,
      { label: `kiểm#${i + 1}.${k + 1}`, phase: 'Kiểm chéo', schema: CHECK, model: 'sonnet', effort: 'low' }).then(v => ({ ...c, check: v }))))
    .then(checked => ({ claims: (res && res.claims) || [], checked: checked.filter(Boolean), notes: res && res.notes })),
)

const report = await agent(
  `Tổng hợp research (tiếng Việt) cho câu hỏi: ${Q}${CTX}\n\nDữ liệu các góc (khẳng định + kiểm chéo):\n${JSON.stringify(found.filter(Boolean), null, 1)}\n\n` +
  'Viết đúng các mục: Trả lời ngắn; Phát hiện (mỗi gạch có URL, đánh dấu [gốc]/[2nd], [đã kiểm chéo]/[một nguồn]/[mâu thuẫn]); Mâu thuẫn/chưa chắc; Hệ quả cho app (đề xuất, không quyết); Nguồn. Không thêm khẳng định không có trong dữ liệu.',
  { label: 'tổng hợp', phase: 'Tổng hợp', model: 'opus', effort: 'medium' })
return { question: Q, report, raw: found }
