---
name: sync-core
description: Đồng bộ lõi do template sở hữu về app (core.lock, tools/template/sync_core.py status/check/sync). Dùng ở repo APP khi hook báo file lõi lệch core.lock, khi muốn lên bản lõi mới của template, hoặc khi cần sửa một file lớp đồng bộ.
---

## Đồng bộ lõi template ở app

Việc này làm ở **repo app** (có `core.lock` ở gốc, được track). Ở repo template, lệnh `sync` bị từ chối.

### `core.lock` là gì và vì sao không sửa tay lõi

`core.lock` ghim tag + commit của template mà app đang đứng và sha256 từng file **lớp đồng bộ** (`Core/`, `CoreOptional/`,
phần lớn `tools/`, `.githooks/`, agent/hook/workflow/skill của template, `conventions.core.md`, `docs/ARCHITECTURE.md`,
`docs/RELEASE.md`, `docs/lessons-learned/`…). Template sở hữu các file đó; ở mọi app chúng phải giống hệt từng byte. Danh sách
lớp: `template.manifest.toml` (`python3 tools/template/manifest.py classify <đường dẫn>` in lớp của một file).

Hệ quả: **không có lối sửa file lớp đồng bộ tại app, cũng không có cơ chế "chấp nhận lệch"**. Cần đổi lõi (kể cả lỗi gấp)
⇒ sửa ở repo template → template gắn tag bản vá → `sync_core.py sync --to <tag>` ở app. Việc riêng của app đặt ở chỗ của app:
`AppHost/…`, `tools/app/…`, `docs/lessons-learned/app/…`; agent/skill riêng của app là thư mục/file MỚI trong `.claude/` (không
trùng tên file/thư mục skill của template). Một file mới nằm trong thư mục do template sở hữu (vd một file Swift mới dưới `Core/`) cũng bị chặn.

### Ba lệnh

```bash
python3 tools/template/sync_core.py status                 # in tag, commit, nguồn, số file của core.lock
python3 tools/template/sync_core.py check                  # rc 0 khớp · 1 lệch · 2 không có/hỏng core.lock
python3 tools/template/sync_core.py sync --to vX.Y.Z [--dry-run] [--adopt-new-seed] [--source <repo cục bộ hoặc URL>]
```

`check` in mỗi file lệch một dòng: `M <file>` (nội dung/bit thực thi khác), `D <file>` (mất), `A <file>` (file mới trong thư mục do
template sở hữu). Muốn bỏ thay đổi tay: `git restore <file>` (M/D), chuyển file ra chỗ của app (A).

### `sync --to <tag>`

Điều kiện: cây git SẠCH (commit/dọn trước), `check` sạch, `.temp/` bị git ignore; tag phải là tag thật của template. Nguồn mặc
định là `template.source` trong `core.lock`; `--source` chỉ thay cho lần chạy này. Luôn thử `--dry-run` trước. Cách đọc output:

| Dòng | Nghĩa |
|---|---|
| `+ file` / `~ file` / `- file` | thêm / sửa / xoá file lớp đồng bộ |
| `> file` | file nay do app sở hữu (template chuyển nó sang lớp gieo): app giữ file, bỏ khỏi lock |
| `! file …` + rc 1 | XUNG ĐỘT: app đã có thứ ở chỗ template nay sở hữu — không ghi gì; làm theo lời báo (chuyển file của app đi, hoặc `git rm` bản cũ lớp gieo), commit, chạy lại |
| `File gieo đổi … ở .temp/core-sync/<tag>/` | template đổi file lớp gieo (vd `CLAUDE.md`, README…): file của app KHÔNG bị đụng; bản mới (file NGUYÊN BẢN của template — chưa cắt khối, chưa thay `$biến`) nằm ở đó để so tay và gộp phần nên lấy. Nhãn `(đổi)` / `(mới ở template)` / `(app không còn file này)`; dòng `git -C … diff <cũ>..<mới> -- …` cho xem đúng thay đổi |
| `Gợi ý: N file gieo mới … --adopt-new-seed` | tag đích có file lớp gieo MỚI mà app chưa có (vd khung `store/`) — xem mục "Nhận file gieo mới" dưới đây |
| `* file  (đã tạo ở app)` / `(sẽ tạo ở app)` | chỉ với `--adopt-new-seed`: file gieo mới đã/sẽ được tạo ở app |
| `Việc phải làm tay (CHANGELOG của template …)` | tiểu mục "Việc phải làm tay khi lên bản này" của mọi bản đi qua — làm hết |
| `CẢNH BÁO … cũ hơn …` | đang hạ lõi về tag cũ hơn; lệnh vẫn làm |
| `không có gì đổi` | app đã ở tag đó, rc 0, không ghi gì |

Sync KHÔNG tự commit. Sau khi xong, theo đúng thứ tự:

```bash
python3 tools/common/appconfig.py render
(cd AppHost && xcodegen generate)
python3 tools/dev/run_tests.py --full
git add -A && git commit -m "chore(core): đồng bộ lõi <cũ> → <mới>"
```

(`git add -A` an toàn vì `.temp/` bị ignore.) Commit này qua hook vì file lõi và `core.lock` mới cùng nằm trong index.

**Lỗi giữa chừng** (rc 1 kèm "lệnh khôi phục"): lock chưa đổi; chạy đúng dòng lệnh được in — dạng
`cd <gốc app> && git clean -fd -- <các file mới> && git restore --staged --worktree -- .` — rồi chạy lại.

### Nhận file gieo mới: `sync --to <tag> --adopt-new-seed`

File lớp gieo chỉ được chép MỘT lần lúc tạo app; bản sau của template thêm file gieo mới (vd `store/` — metadata App Store,
`store/lint.toml`, notes Apple Review; mẫu privacy manifest) thì app cũ không tự có. Dùng cờ khi muốn nhận chúng — thường là
lần đầu lên bản có thêm thư mục gieo mới (CHANGELOG của template nói rõ). Cờ chỉ tạo file **app chưa có**:

- Ứng viên = file gieo của tag đích chưa từng có trong `core.lock` cũ (`seeded`/`synced`). File app đã được gieo từ trước
  (kể cả khi app đã xoá nó) không bao giờ được tạo lại.
- Không nhận: file do `appconfig.py render` sinh (xcconfig, `Features.generated.yml`, privacy manifest, entitlements — app tự
  render; chúng cũng không còn hiện ở "file gieo đổi"), mã Swift (thường cần sửa ở file gieo đã có — đồng bộ không sửa file
  của app), tính năng mẫu, và metadata MẪU của template dưới `store/metadata/` (thay bằng khung). Swift và mẫu vẫn chép bản
  nguyên ra `.temp/core-sync/<tag>/` như cũ để so tay; metadata mẫu thì không (trùng đường dẫn với khung vừa tạo).
- Nội dung dựng như lúc tạo app: biến (`$display_name`, `$slug`, `$bundle_id`, `$host_prod`, `$marketing_version`,
  `$primary_locale`, `$template_tag`, `$date`) lấy từ `app.config.toml` **của app**; metadata nhân cho mọi locale ở
  `[store] locales`; khối `template:` bị cắt. `core.lock` ghi digest bản NGUYÊN của template (để lần sau so được).
- Đích đã track ⇒ không đụng. Đích chưa track mà có thứ trên đĩa (file bị ignore…) ⇒ rc 1, không ghi gì: xoá/chuyển nó,
  hoặc `git add` + commit nếu là file của app, rồi chạy lại.
- Lỗi giữa chừng ⇒ lệnh khôi phục in ra gồm cả file vừa tạo (`git clean -fd -- …`).

Không cờ ⇒ như trước (bản nguyên ra `.temp/`, app không đụng) và in MỘT dòng gợi ý. Lệnh không cờ đã áp thì `core.lock` đã
ghi các file đó vào `seeded` — muốn nhận thì TRƯỚC khi commit chạy lệnh khôi phục mà dòng gợi ý in sẵn, rồi chạy lại với
cờ. Luôn `--dry-run --adopt-new-seed` trước để xem danh sách. Xong thì đọc lại từng file "(đã tạo ở app)" (khung
`store/` có chữ giữ chỗ mà `aso.py lint` cố ý từ chối tới khi viết thật), rồi các bước tiếp theo như thường.

App đang đứng ở bản mà `sync_core.py` chưa có cờ này (`unrecognized arguments: --adopt-new-seed`): chạy tool CỦA BẢN ĐÍCH
trên app — `python3 <template ở tag đích>/tools/template/sync_core.py sync --root <gốc app> --to <tag> --source <template>
--adopt-new-seed` (cùng dạng lệnh ở "Giới hạn cần nhớ").

### Hook báo gì

Pre-commit khối 0 chạy ở mọi commit của app:

- Dòng `M`/`D`/`A <file>` + câu "File này do template sở hữu — sửa ở template rồi chạy … sync --to <tag>": bạn đã đổi/xoá/thêm
  file lõi. Hoàn lại (`git restore --staged --worktree <file>`) hoặc chuyển ra chỗ của app. Đừng tìm cách lách (`--no-verify`
  không cứu được: cổng 15 của `verify_release_clean.sh` bắt lại lúc ra bản).
- "HEAD có core.lock nhưng commit này không có" / "không có core.lock": lock bị gỡ — `git restore --staged --worktree core.lock`.
- "thiếu tools/template/manifest.py|sync_core.py": công cụ của cổng bị xoá — khôi phục từ lịch sử hoặc đồng bộ lại.
- "core.lock hỏng": file sai lược đồ/không đọc được; khôi phục từ lịch sử (`git log --diff-filter=D -- core.lock`, hoặc
  `git checkout <commit> -- core.lock`), rồi `check`.

### Giới hạn cần nhớ

- Bản lõi lên được cần tag của template ≥ tag app đang đứng; tag đích do template công bố (CHANGELOG của template ghi
  việc tay).
- `sync` đọc cây MỚI bằng `manifest.py`/`sync_core.py` CŨ của app. Bản mới đổi lược đồ manifest / `core.lock` ⇒ `sync` từ
  chối trước khi ghi ("cây template mới không dùng được" / "lược đồ …") và in sẵn lệnh chạy tool CỦA BẢN MỚI trên app:
  `python3 <template ở tag đích>/tools/template/sync_core.py sync --root <gốc app> --to <tag> --source <template>`. Chạy đúng
  lệnh đó. KHÔNG chép tay file mới vào app (cây bẩn ⇒ `sync` từ chối; khối 0 chặn commit).
- Hook phải bật ở mỗi clone: người dùng chạy `git config core.hooksPath .githooks` (agent không tự đặt được — nhờ người dùng).
