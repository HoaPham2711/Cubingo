# Quy trình release

Mục tiêu: đơn giản, đủ dùng cho team nhỏ — không git-flow đầy đủ, không release branch riêng. Công cụ:
`tools/release/README.md`.

## Vai trò branch

- **`main`** — luôn khớp bản đã (hoặc sắp) nộp App Store. Chỉ tiến lên qua PR `develop`→`main` hoặc PR
  `hotfix/*`→`main`. Nếu gói GitHub của repo không cho bật branch protection, đây là **quy ước, không phải cổng kỹ
  thuật** — kỷ luật tự giác, không push thẳng vào `main` (hook `guard_autonomy` hỏi trước mọi push vào
  `main`/`develop`).
- **`develop`** — trunk tích hợp hằng ngày. Feature branch (`claude/*`, cá nhân) rẽ từ `develop`, merge lại qua PR
  hoặc trực tiếp.

`main` chỉ tiến lên qua **release** (merge `develop` → `main`) hoặc **hotfix**. Không sync `main` theo `develop`
ngoài 2 luồng đó.

## Release bình thường

1. `develop` xanh:
   - L2: `python3 tools/dev/run_tests.py --full`; `python3 tools/i18n/lint_localizable.py`.
   - `python3 tools/release/stamp_whats_new.py --check` (exit 1 = catalog What's New
     `AppHost/AppHost/WhatsNew/WhatsNewCatalog.swift` còn chữ `unreleased` ở bất kỳ đâu, kể cả comment — bình thường
     trước bump; `bump_version.sh` chạy `--dry-run` của bước đóng dấu ở preflight; chưa có catalog ⇒ bỏ qua). Chốt
     THẬT chống ship thẻ chưa đóng dấu là trình biên dịch: case `CardVersion.unreleased`
     (`Core/Engage/WhatsNew/WhatsNewCard.swift`) chỉ tồn tại dưới `#if INTERNAL || WHATSNEW_ALLOW_UNRELEASED`.
     `INTERNAL` có ở Debug + Internal (`AppHost/project.yml`), Release không có; `WHATSNEW_ALLOW_UNRELEASED` chỉ do
     `tools/i18n/verify_catalog.py` truyền qua dòng lệnh khi build Release để đọc chuỗi ⇒ archive Store còn sót thẻ
     là lỗi biên dịch (`type 'CardVersion' has no member 'unreleased'`). Hệ quả: archive Release trên `develop` lỗi khi
     còn thẻ chưa đóng dấu — đúng thiết kế; muốn archive thử thì làm sau bump. Cổng có thể mất lặng lẽ (ai đó bỏ
     `#if`, hoặc thêm cờ vào Release) nên `tools/release/test_whats_new_compile_gate.py` gác tĩnh — chạy trong
     `tools/template/selfcheck.sh` (unittest `tools/release`).
   - Archive thử + cổng sạch (cần plist Firebase thật của app; template dùng plist giả như
     `tools/template/selfcheck.sh`):
     ```bash
     xcodebuild -project AppHost/AppHost.xcodeproj -scheme AppHost-Store -configuration Release \
       -destination generic/platform=iOS archive -archivePath .temp/store.xcarchive
     ./tools/release/verify_release_clean.sh .temp/store.xcarchive
     ```
     Luồng ra bản KHÔNG BAO GIỜ đặt `ALLOW_SAMPLE_IN_RELEASE` (cổng 14: binary còn tính năng mẫu của template ⇒ FAIL,
     gỡ bằng `python3 tools/template/remove_sample.py`) — biến đó chỉ dành cho tự kiểm của template, và với `.xcarchive`
     cổng 14 từ chối chính biến đó. Cổng 4 còn cấm mọi file `*.md` trong `.app` (README trong thư mục nguồn không vào bundle).
     Tương tự `ALLOW_SITE_PLACEHOLDER` (cổng 16): app có `web.host_prod` ⇒ `python3 web/tools/check_site.py --release` phải
     xanh — trang `/privacy/`, `/terms/`, `/support/` có nội dung thật, khớp công tắc `[features]`.
   - **Web lên prod TRƯỚC bản app cần nó** (app có `web/`): bản app mới dựa vào route/trang/AASA mới ⇒ deploy web prod
     trước khi nộp (Apple duyệt bằng chính link privacy/terms/support của bản đó). Thứ tự (việc của người — cần tài khoản
     Cloudflare; `web/README.md` §"Deploy"): khi có API (`web_api`), migration D1 mới (nếu có) `--remote` TRƯỚC → `npm run
     deploy:dev` + thử → `npm run deploy:prod` (kiểm cấu hình + sitemap + changelog + `check_site.py --release`, rồi API nếu có, rồi
     site; `web_api` tắt ⇒ chỉ site, không migration). Sau khi bản được
     duyệt: thêm bản vào `web/site/releases.json`, `python3 web/tools/changelog.py`, deploy prod lại.
2. Mở PR `develop` → `main`, merge (không cần review nếu solo — PR là lối đi duy nhất vào `main`).
3. Checkout `main`, chạy:
   ```bash
   ./tools/release/bump_version.sh <major|minor|patch>     # --dry-run để xem trước
   ```
   Script: tăng `[version]` trong `app.config.toml` theo semver, sinh lại `AppHost/Config/Identity.xcconfig`, gom
   commit (không merge) kể từ tag trước thành mục mới trong `CHANGELOG.md`, đóng dấu What's New (nếu có catalog),
   tạo commit `chore(release): bump version to vX.Y.Z (build N)` + tag `vX.Y.Z`. Preflight chặn trước khi ghi
   (nhánh sai, cây bẩn, tag đã có…). Lỗi/Ctrl-C sau lần ghi đầu ⇒ script tự hoàn tác rồi KIỂM hậu điều kiện thật;
   chỉ in `đã hoàn tác` khi đúng hết, sai ⇒ `KHÔNG hoàn tác được: …` kèm thư mục giữ bản gốc — sửa tay theo đó.
4. `git push origin main --tags` (cổng con người).
5. Merge `main` ngược về `develop` để đồng bộ version + changelog:
   ```bash
   git checkout develop && git merge main && git push
   ```
6. Archive, upload, metadata: qua skill `release-aso` (luồng "Ra bản"), mỗi lệnh một bước, ghi lên App Store Connect chỉ bằng
   `apply` có người xác nhận (hook `guard_asc`):
   - `python3 tools/aso/aso.py build --version <v>` — local, không gọi App Store Connect: archive scheme `AppHost-Store` Release +
     export `.ipa` + hai cổng (`verify_release_clean.sh` trên archive, `verify_catalog.py --check` — tự SKIP khi chỉ có `en`); chỉ chạy ở `main` có tag `v<v>`, cây sạch, file sinh khớp
     `app.config.toml`; ghi `build.json` ở thư mục trạng thái (ngoài repo). Cần plist Firebase thật của app.
   - `python3 tools/aso/aso.py release-plan --build-json <build.json>` rồi `python3 tools/aso/aso.py apply --plan <file> --expect <mã>`
     — upload build, tạo version, gắn build (người duyệt bản xác nhận và bấm Allow ở hộp của hook).
   - Làm bước 5 (merge `main` về `develop`) rồi `aso.py pull-version --version <v>`, soạn `whatsNew` trong `store/metadata/version/<v>/`,
     `aso.py lint --version <v>` → `plan --version <v>` → `apply` (như sửa metadata).
   - Notes cho Apple Review (`store/review/notes.txt`) do người dán tay vào App Store Connect mỗi bản; ảnh/video store tải lên tay.
   - Nộp review là việc của người trên App Store Connect — công cụ không bao giờ nộp. Lần đầu của một app: tạo app record trên
     App Store Connect, điền `apple.app_store_id`, cài `asc` (`bash tools/aso/install_asc.sh`, tải mạng) và đặt khoá — `docs/NEW_APP_CHECKLIST.md`.
   Xong quay về `develop` — mọi commit sau đó nằm trên `develop`, không commit thẳng `main`.

**Chọn major/minor/patch:** patch = sửa lỗi/nội dung nhỏ không đổi hành vi; minor = tính năng mới tương thích ngược;
major = đổi lớn (ví dụ đổi mô hình dữ liệu, breaking với bản cũ).

## Hotfix (khi đã lên App Store, phát hiện bug khẩn)

1. `git checkout main && git pull`
2. `git checkout -b hotfix/<mô-tả>`
3. Sửa, test (L2), commit.
4. Merge `hotfix/<mô-tả>` → `main` (qua PR).
5. Trên `main`: `./tools/release/bump_version.sh patch` (script chấp nhận `main` hoặc `hotfix/*`).
6. `git push origin main --tags`.
7. Merge `main` ngược `develop` (bước 5 ở luồng bình thường) — nếu `develop` đã đi xa hơn `main` (thường vậy),
   đây là merge thường, không fast-forward.

## Phát hành một bản của template

Mục này dùng ở **repo template** (app không phát hành template). Version của template là **tag git** `vX.Y.Z` trên `main` —
không có file `VERSION`; app đang đứng ở tag nào thì ghi trong `core.lock`. Từ `v0.4.0` app sinh ra được tạo từ một tag và
kéo lõi về bằng `sync_core.py sync --to <tag>`, nên tag là hợp đồng: file nào template xếp lớp đồng bộ ở tag đó là file app
nhận nguyên văn.

1. `develop` xanh: L2 + `tools/template/selfcheck.sh` đầy đủ (gồm tạo app thật, đồng bộ lên tag thử, tổ hợp tắt hết, gỡ mẫu).
2. Mục `## Chưa phát hành` của `CHANGELOG.md` (của template) đổi thành `## vX.Y.Z — <ngày>`; mỗi mục từ v0.4.0 PHẢI có tiểu mục
   `### Việc phải làm tay khi lên bản này` (viết "Không có." nếu không có): lệnh `sync` in tiểu mục của mọi bản nằm giữa bản
   app đang đứng và bản đích — đó là chỗ báo trước đổi lược đồ manifest, file app phải chuyển ra khỏi thư mục template sở
   hữu, cờ build mới… Pre-commit và `manifest.py check` đỏ khi thiếu.
   Bản đổi LƯỢC ĐỒ `template.manifest.toml` (kể cả thêm khoá) hoặc `core.lock` (`SCHEMA` trong `sync_core.py`): tool CŨ
   của app không đọc được cây mới và từ chối trước khi ghi (lược đồ lock nó biết qua dòng `SCHEMA = <n>` của `sync_core.py`
   mới — giữ dòng đó dạng ấy). Quy tắc tương thích: `manifest.py` + `sync_core.py` mới PHẢI đọc được manifest và `core.lock`
   lược đồ của bản TRƯỚC (app chạy chúng trên cây cũ của mình); "Việc phải làm tay" của bản đó PHẢI bảo app chạy tool của
   bản mới: `python3 <template ở tag>/tools/template/sync_core.py sync --root <app> --to <tag> --source <template>`.
3. PR `develop` → `main`, merge (cổng con người).
4. Trên `main`: gắn tag `vX.Y.Z` và `git push origin main --tags` (cổng con người). Tag cũ hơn `v0.4.0` không có manifest nên
   không tạo được app.
5. Merge `main` ngược `develop`.

Sau khi tag lên, mỗi app tự quyết lúc nào kéo về (`sync-core`); template không đẩy cập nhật vào app.

## CHANGELOG.md

Sinh tự động bởi `bump_version.sh`, không sửa tay ngoài đính chính lỗi chính tả. Mỗi mục là danh sách commit (không
tính merge commit) giữa tag trước và tag mới trên `main`.

## Việc KHÔNG làm (chủ đích, giữ đơn giản)

- Không release branch riêng (`release/x.y`) — `main` sau bump đã đóng vai trò đó.
- Không CI/CD tự động archive/upload — `bump_version.sh` lo version + changelog, phần còn lại chạy theo yêu cầu.
- Không bắt buộc PR vào `develop` — chỉ `main` được bảo vệ.
- Không dọn branch cũ tự động — dọn `claude/*` stale là việc riêng, không thuộc quy trình release.
