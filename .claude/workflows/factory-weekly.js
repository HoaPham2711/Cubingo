export const meta = {
  name: 'factory-weekly',
  description: 'Nhà máy agent: bản tin tuần đa vai — số liệu sản phẩm, ASO, sức khoẻ bản phát hành, nợ ROADMAP/nhánh — rồi giám đốc gộp thành 1 trang có 3 việc nên làm',
  whenToUse: 'Đầu tuần hoặc khi user hỏi "tuần này thế nào / nên làm gì tiếp". args = { today?: "YYYY-MM-DD", since?: "YYYY-MM-DD" }. Chỉ đọc + báo cáo, không sửa code.',
  phases: [
    { title: 'Thu thập', detail: '4 vai song song, chỉ đọc' },
    { title: 'Gộp', detail: 'bản tin + 3 việc nên làm, critic soát số' },
  ],
}

const TODAY = (args && args.today) || '(chạy `date +%F`)'
const SINCE = (args && args.since) || '(7 ngày trước hôm nay)'
const RO = 'CHỈ ĐỌC và chạy lệnh đọc/kéo số. Không sửa code/docs, không commit, không gửi gì ra ngoài. Mỗi con số kèm nguồn (file/lệnh). Thiếu khoá hoặc cấu hình ⇒ báo đúng một dòng hướng dẫn của lệnh rồi ghi "chưa có dữ liệu" — không bịa số, không đọc/in file khoá, không cài gói.'

// Bậc model/effort cho đường fallback general-purpose (mất frontmatter) — khớp `.claude/agents/` (lint_harness gác).
const ROLE_TIER = {
  'data-analyst': { model: 'sonnet', effort: 'medium' },
  'growth-marketer': { model: 'opus', effort: 'medium' },
  'release-manager': { model: 'sonnet', effort: 'medium' },
  'factory-scribe': { model: 'sonnet', effort: 'low' },
  'factory-critic': { model: 'opus', effort: 'high' },
}

const ROLES = [
  { role: 'data-analyst', prompt: `Bản tin tuần ${SINCE} → ${TODAY}. Theo skill product-analytics: dùng insights.json + report.md mới nhất nếu lần kéo ≤ 1 ngày tuổi; nếu không, chạy lần lượt ga4_pull.py, asc_pull.py, crash_pull.py rồi digest.py (lệnh nào thiếu khoá thì ghi nguồn đó "missing"). Trả ĐÚNG các chỉ số insights.json có: lượt tải đầu (asc.first_downloads), người dùng mới, giữ chân D1/D3/D7 (retention.dN), người dùng hoạt động, số lượt mua trong app (asc.in_app_purchases — digest KHÔNG có doanh thu: đừng tự tính từ TSV thô, ghi "doanh thu: chưa có trong digest"), crash mới và cảnh báo theo dõi crash; so tuần trước nếu có báo cáo cũ; nêu rõ nguồn missing/stale/partial. ${RO}` },
  { role: 'growth-marketer', prompt: `Bản tin tuần ${SINCE} → ${TODAY}: tình trạng ASO. Dùng \`python3 tools/aso/aso.py lint\` (local) và, nếu app.config.toml đã có apple.app_store_id, \`python3 tools/aso/aso.py plan\` (không apply) để biết store/ có lệch App Store Connect không; đọc store/README.md và memory về ASO. Trả: lint/plan nói gì, chữ giữ chỗ còn sót, store/review/notes.txt còn khớp bản đang ra không, 1–2 thử nghiệm ASO nên làm kèm giả thuyết và cách đo (số lấy từ .temp/analytics/ nếu có). ${RO}` },
  { role: 'release-manager', prompt: `Sức khoẻ phát hành tính tới ${TODAY}: bản đang bán (version.marketing trong app.config.toml), \`git log --oneline main..develop\` nhóm theo feat/fix, nhánh feature chưa merge (\`git branch -a --no-merged develop\`), \`python3 tools/factory/roadmap.py debt --kind merge\`, crash đang theo dõi (mục theo dõi crash trong report.md của digest nếu có). Có nên cắt bản mới tuần này không, vì sao. ${RO}` },
  { role: 'factory-scribe', prompt: `Nợ dự án tính tới ${TODAY}: \`python3 tools/factory/roadmap.py debt${(args && args.since) ? ' --since ' + args.since : ''}\`${(args && args.since) ? '' : ' (lệnh không có mặc định thời gian — khi không có --since, TỰ lọc trong kết quả: chỉ giữ các mục ghi trong 30 ngày gần nhất tính từ hôm nay)'} (kiểm chéo 3–5 mục quan trọng với memory/ROADMAP mục sau để loại nợ ảo), mission đang mở (\`python3 tools/factory/mission.py list --all\`). Trả: top nợ device cần user thử (gom theo màn), mục ROADMAP có tiêu đề lỗi thời cần sửa. ${RO}` },
]

const parts = await parallel(ROLES.map(r => () =>
  agent(r.prompt, { label: r.role, phase: 'Thu thập', agentType: r.role })
    .catch(() => agent(`Đọc .claude/agents/${r.role}.md và làm theo vai đó.\n\n${r.prompt}`, { label: r.role, phase: 'Thu thập', ...ROLE_TIER[r.role] }))
    .then(text => ({ role: r.role, text }))))

const draft = await agent(
  `Bạn là giám đốc nhà máy agent của app này. Gộp 4 báo cáo dưới thành BẢN TIN TUẦN tiếng Việt cho user (không chuyên marketing): ` +
  `1) Tóm tắt 5 dòng; 2) Số liệu (bảng, có nguồn; nguồn thiếu ghi rõ "chưa có dữ liệu"); 3) ASO; 4) Phát hành & crash; 5) Nợ cần user (device/quyết định); ` +
  `6) BA việc nên làm tuần này — mỗi việc ghi playbook nhà máy (feature/fix/growth/analytics/…) và câu lệnh "/factory <mục tiêu>" để giao luôn. ` +
  `Không thêm số không có trong báo cáo.\n\n${JSON.stringify(parts.filter(Boolean), null, 1)}`,
  { label: 'gộp', phase: 'Gộp', model: 'opus', effort: 'medium' })

const review = await agent(
  `Soát bản tin sau: mọi con số phải có trong báo cáo nguồn; tìm số lệch, "trả tiền" nhầm "bắt đầu gói", kết luận quá tay, số bịa cho nguồn thiếu. Trả danh sách sửa (hoặc "OK").\n\nBÁO CÁO NGUỒN:\n${JSON.stringify(parts.filter(Boolean))}\n\nBẢN TIN:\n${draft}`,
  { label: 'soát số', phase: 'Gộp', agentType: 'factory-critic' })
  .catch(() => agent(`Đọc .claude/agents/factory-critic.md và làm theo. Soát số bản tin:\n${draft}\nNguồn:\n${JSON.stringify(parts.filter(Boolean))}`, { label: 'soát số', phase: 'Gộp', ...ROLE_TIER['factory-critic'] }))

return { brief: draft, review, sources: parts.filter(Boolean).map(p => p.role) }
