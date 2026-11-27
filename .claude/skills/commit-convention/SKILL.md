---
name: commit-convention
description: Ghi commit/PR đúng convention dự án (trailer Co-Authored-By, Claude-Session khi có URL, branch). Dùng khi commit hoặc mở PR. KHÔNG phải công cụ tăng version app — cái đó là tools/release/bump_version.sh.
---

## Convention commit và PR

### Trailer commit message

Điền giá trị **của phiên đang chạy** — không chép literal từ commit cũ hay từ ví dụ:

```
Co-Authored-By: Claude <tên model đang chạy> <noreply@anthropic.com>
Claude-Session: <URL claude.ai/code của phiên này>
```

- Tên model lấy từ system prompt của phiên.
- Dòng `Claude-Session` CHỈ ghi khi phiên có URL thật (phiên chạy trên claude.ai/code hoặc bật remote control).
  Phiên local thuần không có URL → **bỏ hẳn dòng này**, chỉ giữ `Co-Authored-By` (thiếu một dòng còn hơn ghi URL
  sai vào lịch sử git).

### Trước khi commit

- Chỉ `git add` file của việc mình làm (không `git add -A` khi cây có thay đổi của người khác); kiểm nhánh.
- Pre-commit (`.githooks/pre-commit`) phải chạy: người dùng bật một lần ở clone mới bằng `git config core.hooksPath .githooks` (agent không tự đặt — hook chặn; nhờ người dùng).
  Không `--no-verify` để lách cổng — sửa lỗi cổng báo.

### Gom commit trong vòng sửa

Vòng sửa theo feedback (L1 — "Thang kiểm chứng" trong `.claude/rules/conventions.core.md`) không cần commit từng
lượt. Gom lại, commit khi đạt checkpoint L2 (full suite xanh). Commit WIP giữa chừng vẫn được nếu user yêu cầu.

### PR body

Kết thúc bằng `🤖 Generated with [Claude Code](https://claude.com/claude-code)` (+ link session nếu có).

### Branch

- `main` chỉ tiến qua PR (`docs/RELEASE.md`); `develop` là trunk hằng ngày.
- Việc mới trên `main`/`develop` → tạo branch trước khi commit. Worktree luôn ở `.claude/worktrees/<name>`.
