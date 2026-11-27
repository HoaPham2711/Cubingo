# Sửa harness `.claude/` không có hiệu lực ở phiên đang chạy

Nguồn: `docs/lessons-learned/` của app gốc (2026-11), viết lại cho template.

## Triệu chứng
- Thêm hook vào `.claude/settings.json` rồi chạy lệnh mà hook phải hỏi ⇒ không có hộp hỏi: hook chưa chạy.
- Thêm agent ⇒ gọi agent type đó báo lỗi; thêm skill ⇒ "Unknown skill"; thêm workflow ⇒ "not found". Kể cả sau khi
  app khởi động lại và phiên được *resume*.

## Nguyên nhân
Claude Code chụp hook, agent type, skill, workflow đã đăng ký **lúc phiên bắt đầu**; phiên resume giữ bản chụp cũ.

## Cách làm đúng
1. Kiểm hook bằng cách chạy **đúng file hook** với JSON giả qua subprocess (`tools/factory/test_hooks.py`) — không
   dựa vào phiên đang sửa.
2. Workflow mới chạy được ngay bằng `Workflow({scriptPath: ".claude/workflows/<tên>.js"})`.
3. Agent type mới: workflow nhà máy có đường lùi `general-purpose` + "đọc `.claude/agents/<vai>.md`"
   (`roleAgent()` trong `.claude/workflows/factory-execute.js`); eval hành vi vai sau khi sửa prompt dùng
   `factory-eval` với `args.fromFile = true`.
4. Kiểm tĩnh trước commit: `python3 tools/factory/lint_harness.py` (frontmatter sai tên khoá bị Claude Code lờ đi
   im lặng — lint bắt).
5. Nghiệm thu cuối của thay đổi harness = mở **phiên mới** rồi thử (ví dụ `/factory status`).
