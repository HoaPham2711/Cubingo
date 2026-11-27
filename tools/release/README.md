# Công cụ phát hành

| File | Việc |
|---|---|
| `verify_release_clean.sh` | Soi `.app`/`.xcarchive` để chứng minh bản Store sạch code debug và đúng định danh. `--expect-debug-symbols <Internal.app>` = đối chứng dương: mọi tên `[binary]` phải CÓ trong binary Internal (tên không thấy = mục vô tác dụng, rc 1) |
| `debug_symbols.txt` (+ `AppHost/Config/debug_symbols.app.txt`) | Tên chỉ được có ở build Internal. File này giữ tên của LÕI (template sở hữu); tên của app ở `AppHost/Config/debug_symbols.app.txt` (app sở hữu, cùng định dạng, vắng = rỗng) — lint và cổng 1 đọc HỢP, tên trùng giữa hai file ⇒ lỗi. Mỗi file hai mục: `[binary]` (tên type — cổng 1 grep binary Release) và `[source-only]` (tên hàm/biến ghim bằng marker — tên hàm bị strip khỏi binary nên chỉ lint gác). Cú pháp ở đầu file |
| `bump_version.sh` | Tăng version, ghi CHANGELOG, commit + tag release |
| `stamp_whats_new.py` | Đóng dấu thẻ What's New (`.unreleased` → `.released("X.Y.Z")`) lúc bump |
| `lint_preview_code.py` | Kiểu seed/store giả của route preview (tên kết thúc `PreviewSeed`/`PreviewStore`) chỉ trong vùng `#if targetEnvironment(simulator)`; rc 1 in `file:dòng: <Tên> …`. Chạy ở `selfcheck.sh` bước 1 và pre-commit |
| `check_storekit.py` | Id trong `AppHost/StoreKitConfig/Products.storekit` khớp `[purchases] product_ids` (rc 1 nêu id thừa/thiếu; paywall tắt ⇒ `SKIP`). Chạy ở `selfcheck.sh` bước 1 và pre-commit khi commit đụng một trong hai file |
| `lint_debug_symbols.py` | `debug_symbols.txt` + `debug_symbols.app.txt` (hợp) khớp nguồn hai chiều: type khai trong `#if INTERNAL` phải có tên ở `[binary]`; hàm/biến có marker ở `[source-only]`; tên trong file phải còn khai, đúng loại với mục (type ở `[binary]`, hàm/biến/typealias ở `[source-only]`) và chỉ trong vùng `#if INTERNAL`; tên trước mọi mục/mục lạ/trùng ⇒ lỗi; comment có chữ `debug-symbol` mà không đúng nguyên văn marker ⇒ lỗi. Quét `SRC_ROOTS` + `CoreOptional/` nếu có. rc 1 in `file:dòng: <Tên> chưa khai`. Chạy ở `selfcheck.sh` bước 1, pre-commit khi commit đụng `.swift`/một trong hai danh sách, và cổng 1b của `verify_release_clean.sh`. Hàm/biến nguy hiểm ghim bằng comment `// debug-symbol: required` ngay dòng trên khai báo (trong `#if INTERNAL`) ⇒ tên đó bắt buộc có ở `[source-only]`; marker ngoài vùng/không kèm khai báo ⇒ rc 1. `INTERNAL && X` tính là vùng INTERNAL; `INTERNAL \|\| X` không. Lỗ hổng đã biết nằm ở docstring của script |

Mọi định danh (bundle id, tên hiển thị, host web, version) đọc từ `app.config.toml` qua
`tools/common/appconfig.py`; các script ở đây không chứa literal định danh.

## Cổng kiểm bản phát hành

Chạy **trước mỗi lần upload**:

```bash
xcodebuild -project AppHost/AppHost.xcodeproj -scheme AppHost-Store -configuration Release \
  -destination generic/platform=iOS archive -archivePath /tmp/store.xcarchive
./tools/release/verify_release_clean.sh /tmp/store.xcarchive
```

rc 0 = sạch, 1 = có lỗi, 2 = sai cách dùng. Các cổng:

| # | Kiểm | So với |
|---|---|---|
| 0 | `appconfig.py check`: cấu hình đọc được và file sinh ra (`Identity.xcconfig`, `Features.generated.yml`, privacy manifest, `Entitlements.generated.yml`, `AppHost.entitlements`) không cũ | `app.config.toml` |
| 1 | Không còn tên debug trong **mọi** Mach-O của `.app` (`nm` + `strings`) | từng tên ở mục `[binary]` của `debug_symbols.txt` và `debug_symbols.app.txt` (cắt khoảng trắng/`\r`); `[source-only]` KHÔNG soi (in số tên mỗi mục); mục `[binary]` rỗng/thiếu file/tên trước mọi mục/mục lạ ⇒ FAIL |
| 1b | `lint_debug_symbols.py` sạch (danh sách khớp nguồn) — bỏ bằng `SKIP_SYMBOL_LINT=1` (chỉ test của script) | nguồn Swift |
| 2 | `CFBundleIdentifier` | `bundle.store` |
| 3 | `CFBundleDisplayName`, `CFBundleShortVersionString`, `CFBundleVersion` bằng đúng | `app.display_name`, `version.marketing`, `version.build` |
| 4 | Không file `*.md` nào trong resource của app (README là tài liệu nguồn; `project.yml` loại `**/*.md` khỏi resource) — bỏ qua `Frameworks/`, `PlugIns/` và mọi thư mục `*.bundle` (resource của bên thứ ba có thể kèm README); `SampleData/` (nếu có) không chứa file nào khác `README.md` | — |
| 5 | Có `GoogleService-Info.plist` với `BUNDLE_ID`; không phải plist fixture (trừ khi `ALLOW_FIXTURE_PLIST=1` — chỉ selfcheck) | `bundle.store` |
| 6 | Không lẫn `GoogleService-Info-Prod.plist`/`-Dev.plist` | — |
| 7 | Có `PrivacyInfo.xcprivacy`, và `NSPrivacyCollectedDataTypes` khớp công tắc trong Info (`FeaturePaywall`/`FeatureWebAPI`/`FeatureAppleAds`, phải là YES/NO): khối bật ⇒ đủ kiểu của khối, khối tắt ⇒ không còn kiểu nào (FAIL nêu từng kiểu). Bảng khối ↔ kiểu: `appconfig.PRIVACY_BLOCKS` (paywall → PurchaseHistory; web_api → CustomerSupport + EmailAddress; apple_ads → AdvertisingData) | Info.plist của `.app` |
| 9 | iPad đủ 4 hướng hoặc có `UIRequiresFullScreen` | — |
| 10 | Chỉ khi `web.host_prod` khác rỗng: khoá Info `WebHost` (= `$(APP_WEB_HOST)`, Release ⇒ host_prod) khớp. Bản ĐÃ KÝ (có `_CodeSignature/CodeResources`): có host mà thiếu khoá associated-domains ⇒ FAIL; khoá mang đúng một mục `applinks:<host_prod>`, không mục nào trỏ `web.host_dev`; `web.host_prod` rỗng ⇒ không được có khoá associated-domains (build không ký: in dòng SKIP, bước 0 giữ file nguồn khớp) | `web.*` |
| 11 | What's New không còn `unreleased` | `stamp_whats_new.py --check` |
| 12 | `lint_localizable.py` + `verify_catalog.py --check` (bỏ bằng `SKIP_CATALOG_CHECK=1`) | — |
| 13 | LUÔN (bật hay tắt paywall): `.app` không chứa file `*.storekit` nào (cấu hình StoreKit local chỉ là resource của test bundle) và Info `FeaturePaywall` khớp cấu hình. Khi `features.paywall` bật thêm: `ProductIDs` khác rỗng, `WebHost` khác rỗng (paywall cần link Điều khoản/Quyền riêng tư). Paywall tắt ⇒ `BỎ QUA` riêng phần `ProductIDs`/`WebHost` | `features.paywall` (phần `ProductIDs`/`WebHost`) |
| 14 | Không còn tính năng mẫu của template: chuỗi `SampleItemStore` không có trong dump `nm` + `strings` của cổng 1 ⇒ nếu có: FAIL `còn tính năng mẫu trong bản Store — chạy tools/template/remove_sample.py`. `ALLOW_SAMPLE_IN_RELEASE=1` ⇒ in `BỎ QUA` — chỉ với `.app` trần, chỉ script tự kiểm của template đặt khi cây còn mẫu; với `.xcarchive` biến bị TỪ CHỐI (FAIL); luồng ra bản không bao giờ đặt | — |
| 15 | Chỉ ở app. Repo mà LỊCH SỬ từng có `core.lock` là app, kể cả khi file đánh dấu của template đang được track. Lịch sử chưa từng có lock ⇒ template nhận diện DƯƠNG: `new_app.py` của template (thư mục tools/template) được track trong HEAD (HEAD chưa có: trong index; gốc không phải repo git ⇒ file đó trên đĩa, có in rõ) — mọi repo khác là app. Ở app: `core.lock` không được TRACK (kể cả đã commit gỡ, hay còn trên đĩa mà `git rm --cached` / chỉ `git add -N`; gốc không phải repo git ⇒ không có trên đĩa) hoặc thiếu `tools/template/manifest.py`/`sync_core.py` ⇒ FAIL kèm cách khôi phục từ lịch sử (không dấu nào ⇒ thông báo nêu cả hai khả năng: app mất lock / template mất file đánh dấu); rồi `tools/template/sync_core.py check` rc 0 — file lớp đồng bộ khớp digest (`M`/`D`), không có file mới track trong thư mục lớp đồng bộ (`A`). Template ⇒ in `BỎ QUA — … đây là template` | `core.lock` |

| 16 | Chỉ khi `web.host_prod` khác rỗng: `web/tools/check_site.py --release` xanh — đủ trang bất biến `/`, `/privacy/`, `/terms/`, `/support/` (app nướng cứng), không còn `TEMPLATE-PLACEHOLDER`, privacy khớp công tắc `[features]`, không dấu khối/biến gieo sót, `web.host_prod`/e-mail hỗ trợ không phải host giữ chỗ (`example.com`, `*.test`…), canonical/`mailto:` khớp cấu hình ; có host mà thiếu `web/site/public/` ⇒ FAIL, trừ khi `[web] external_site = true` (site ngoài repo) ⇒ in `SKIP (web.external_site)`, không đòi công cụ; có host mà thiếu công cụ ⇒ FAIL. `ALLOW_SITE_PLACEHOLDER=1` ⇒ chạy không `--release` (chữ giữ chỗ chỉ cảnh báo, kiểm khác vẫn gác) — chỉ với `.app` trần, chỉ `selfcheck.sh`/`feature_matrix_check.sh` đặt; với `.xcarchive` biến bị TỪ CHỐI (FAIL). Host rỗng ⇒ `BỎ QUA` | `web/site/public/`, `[features]` |

Cổng 15 chỉ có nghĩa ở app (template in `BỎ QUA`). Nó là lưới đỡ khi hook pre-commit không chạy: ai đã sửa lõi bằng
`--no-verify` thì lúc ra bản vẫn bị bắt. Mô hình đe doạ và cách đồng bộ lõi: `docs/ARCHITECTURE.md` §"Ba lớp sở hữu,
`core.lock`, đồng bộ".

Kiểm chứng chính cổng: `tools/template/selfcheck.sh` build `Release` (cổng phải qua) rồi build `Internal`
(cổng phải **từ chối**, nêu cả `bundle id` lẫn `InternalDebugMarkerView`, và `--expect-debug-symbols` phải thấy MỌI
tên `[binary]`). Một cổng chỉ biết nói PASS thì không chứng minh được gì. Đã chứng minh trên archive thật
(`docs/lessons-learned/cong-symbol-debug-chi-thay-symbol-duoc-link.md`).

## Bump version

```bash
./tools/release/bump_version.sh <major|minor|patch> [--force|--dry-run]
```

Chạy trên `main` (hoặc `hotfix/*`) với cây sạch. Ghi `[version]` của `app.config.toml`, sinh lại
`AppHost/Config/Identity.xcconfig`, thêm mục vào `CHANGELOG.md`, đóng dấu What's New (nếu có catalog), rồi
commit + tag `vX.Y.Z`. Lỗi giữa chừng ⇒ tự hoàn tác và kiểm hậu điều kiện (xem đầu file script).
`--dry-run` chỉ in việc sẽ làm.

Test: `python3 -m unittest discover -s tools/release -p 'test_*.py'` (repo git tạm — không bao giờ chạy
`bump_version.sh` thật trong test; ~2,5 phút vì có fuzz hoàn tác). `test_verify_release_clean.py` chạy cổng trên
một `.app` giả tối thiểu (Mach-O biên dịch bằng clang).
