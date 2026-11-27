# Test gọi `git` chạy trong hook git ghi nhầm vào repo thật

Nguồn: `docs/lessons-learned/` của app gốc (2026-11), viết lại cho template.

## Chuyện đã xảy ra
Một test dựng repo tạm (`git -C <tmp> init`, `git -C <tmp> config user.*`). Chạy tay thì xanh. Khi commit,
`.githooks/pre-commit` chạy lại test `tools/factory` — và trong hook, git đặt sẵn `GIT_DIR`/`GIT_INDEX_FILE` của
repo đang commit. `GIT_DIR` thắng `-C`, nên:

- `git init` "khởi tạo lại" chính repo thật, không có work tree ⇒ ghi `core.bare = true` vào `.git/config` chung ⇒
  checkout chính và **mọi worktree** báo "this operation must be run in a work tree";
- `git config user.email …` ghi vào config repo thật.

Không mất code/commit, nhưng git của mọi phiên đang chạy hỏng tới khi sửa tay (`core.bare false`, xoá mục `[user]`).

## Bài học
- Code/test nào gọi `git` trên một thư mục **khác** repo hiện tại phải gỡ mọi biến `GIT_*` khỏi env của subprocess
  (và khỏi `os.environ` nếu gọi qua hàm thật). `-C` không đủ.
- Test dựng repo tạm nên kiểm `git rev-parse --show-toplevel` = thư mục tạm **trước** lệnh ghi nào.
- "Xanh khi chạy tay" chưa phải bằng chứng cho test chạm git: chạy lại với `GIT_DIR` trỏ một **repo mồi** rồi so
  config mồi trước/sau; phá đoạn gỡ env ⇒ mồi phải bị ghi.

Đã áp ở template: `tools/factory/mission.py` (đếm file hồ sơ chưa commit), `tools/factory/test_mission.py`,
`tools/factory/test_hooks.py`. Test mới dựng repo tạm ở thư mục khác (`tools/release`, `tools/dev`…) phải theo cùng
luật — các test hiện có ở đó chưa gỡ `GIT_*` vì pre-commit chỉ chạy test `tools/factory`.
