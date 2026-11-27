# Quy ước riêng của app

Ghi ở đây quy ước chỉ đúng cho app này (invariant nghiệp vụ, điểm một-nguồn của tính năng, ngưỡng đã chốt) — quy ước chung nằm ở `.claude/rules/conventions.core.md`, đừng chép lại.

Các mục dưới đây là khuôn viết một tính năng của app (`<Tên>` = tên tính năng); file này thuộc app (lớp seed) — sửa, thêm mục theo nghiệp vụ thật.

## Đặt code

- Mỗi tính năng một thư mục `AppHost/AppHost/Features/<Tên>/`, test ở `AppHost/AppHostTests/<Tên>/`; mọi kiểu của tính năng mang tiền tố `<Tên>`. Thêm/xoá file ⇒ `cd AppHost && xcodegen generate`.
- Khung dùng chung (`AppHostApp`, `AppShellView`, `AppTab`, `HomeView`, `AppOnboarding`, `AppPaywall`, `AppPreview`, `WhatsNew/`) chỉ nối tính năng vào bằng vài dòng; logic nằm trong thư mục tính năng. `Core/` không biết tính năng nào (target `CoreOnly` gác).
- `#if INTERNAL` của app CHỈ ở `AppHost/AppHost/Internal/AppInternalEntry.swift` (call site dùng wrapper, không tự viết `#if`); `#if FEATURE_*` CHỈ ở `AppHostApp.swift`.
- Không `public`; không `@EnvironmentObject` cho đối tượng nghiệp vụ.
- Theme của app ở `AppHost/AppHost/AppTheme.swift` (`DSTheme`, `.standard.withAccent(hex:)`); không sửa `Core/Design/`.

## Phụ thuộc

- Một struct phụ thuộc tường minh (`<Tên>Dependencies`: store, entitlements, nội dung paywall, `ReviewPrompter`, closure `arm`, bộ đếm hạn mức…), dựng MỘT lần ở `AppHostApp` và truyền qua `init` xuống view. View không tự dựng store/ledger, không singleton ẩn; test dựng struct bằng đối tượng giả/tạm.
- Thao tác file/Keychain đưa vào qua tham số có mặc định (một struct `…FileOps`, closure `write:` của runner) để test ép lỗi xác định mà không sleep.

## Event, màn, thuộc tính người dùng

- Tên event và tên màn của tính năng bắt đầu bằng tiền tố tính năng (`<tên>_item_add`, `.trackScreen("<tên>_items")`). Event là `enum <Tên>EventName: String, EventNameCatalog` + `extension AppEvent` với static factory; thuộc tính người dùng đi qua `UserProperty` mở rộng + `UserPropertySync`.
- Mỗi catalog có (a) một mảng mẫu `AppEvent` đủ mọi tên, (b) hai test: taxonomy của chính catalog (`EventNameCatalog`) và `TelemetryTaxonomy.crossCatalogViolations(catalogs: [lõi, app…], samples: …)` — bắt tên trùng giữa catalog, mẫu mồ côi, khoá param chứa mảnh vị trí (`lat`, `lon`, `coord`, `gps`, `location`, so chuỗi con). Đặt tên khoá tránh các mảnh đó. Số đếm gửi đi là số thô, không chia khoảng.
- Tên event không trùng tên fixture của test (`DemoEventName`, …).

## Khoá Pro và hạn mức dùng thử

- Quyết định khoá là HÀM THUẦN có test (`<Tên>Gate.exportAll(entitlements:)`, `shareItem(isPro:ledger:)` → `.allow`/`.paywall(source:)`). Chỉ quyết định thuần trên state sẵn có (kiểu `exportAll(entitlements:)`) mới được gọi từ `body`; quyết định đọc bộ đếm Keychain (`shareItem(isPro:ledger:)`) phải gọi lúc hành động / làm mới state, view giữ kết quả trong state. Paywall tắt ⇒ `isPro` luôn true ⇒ không cần nhánh riêng.
- `pro_gate_hit` bắn khi user CHẠM control bị khoá (`noteGateHit`), không bắn trong `body`; `paywall_view(source:)` bắn khi paywall hiện; đóng mà không mua ⇒ `reviewPrompter.notePaywallDismissed`.
- Lượt dùng thử chỉ tiêu thụ SAU khi hành động thành công thật (`didShare`: sau khi share sheet báo hoàn tất, không phải lúc mở); Pro không đụng bộ đếm; lỗi Keychain nuốt + `applog`, không chặn oan. View giữ số lượt còn lại trong state, làm mới sau khi tiêu thụ hoặc khi `isPro` đổi — không đọc Keychain trong `body`.
- Sau khi mua ở paywall từ một cổng, hành động đang chờ KHÔNG tự chạy lại (user bấm lại) — giới hạn đã biết của khung.

## Việc chạy lâu

- Việc có thể bị hệ điều hành giết giữa chừng: `ActiveWorkMarkerStore.begin(kind:workID:)` TRƯỚC khi ghi, `clear` ở mọi đường ra (thành công, lỗi); lần mở sau `AppBootstrap.launchIncident` cho tính năng hỏi lại (`<Tên>Incident`, prompt hiện một lần). Gắn `.keepScreenAwake(<kind>, when: runner.isRunning)`; runner có chốt chống gọi chồng (`isRunning`).
- Xong ⇒ `ReviewSignals.noteValueAction()` + `arm(.outputDone)`; lỗi ⇒ `reviewPrompter.noteTaskFailed()`. Mọi tín hiệu qua đường thật của `ReviewScheduler`, không bypass policy.

## Dữ liệu của app

- Không bao giờ ở `tmp/` (`purgeTmp` dọn mỗi lần mở). Dữ liệu bền ở `Application Support/<tính năng>/`; file sinh lại được (xuất…) ở `Caches/<tính năng>-…/` và thư mục đó đưa vào `AppBootstrap.standardSteps(tmpDirs:)`.
- Mọi store file JSON của app: ghi nguyên tử mỗi thay đổi; không có file ⇒ rỗng, không tạo; file 0 byte ⇒ rỗng; giải mã lỗi ⇒ đổi tên `*.corrupt-<n>.json` (không đè bản hỏng cũ) rồi rỗng; ĐỌC lỗi (dữ liệu bảo vệ chưa mở khoá) hoặc cách ly thất bại ⇒ giữ nguyên file và CHẶN ghi (`isPersistenceBlocked`, UI báo); ghi lỗi ⇒ bộ nhớ vẫn đúng, lỗi vào `applog`, lần sau ghi lại. Không bao giờ ghi đè file mình không đọc được.

## Route preview và seed

- Màn mới có trạng thái đáng chụp ⇒ thêm `case` vào `AppPreview` + một dòng ở README của thư mục tính năng (`ui_shots.py all` tự thấy). Seed/store giả đặt tên kết thúc `PreviewSeed`/`PreviewStore` và nằm trong `#if targetEnvironment(simulator)` (`tools/release/lint_preview_code.py` gác); dữ liệu là code Swift, không bao giờ resource; chỉ ghi vào suite/thư mục `uiPreview…`, không đụng `UserDefaults.standard` ngoài cờ khung đã có, không Keychain.
- Màn cuộn dài cần ảnh phần dưới ⇒ khai số lần vuốt ở `UIShotsTests.scrollRoutes`.

## Giao diện

- Cỡ chữ cố định ⇒ `.scaledFont(size:weight:…)` (Core/Design), KHÔNG `.font(.system(size:))` trần; kiểm bằng `ui_shots.py --content-size accessibility-extra-large`. Màn gốc có cột đọc ⇒ `readableColumnNavigationTitle(_:)` + `ReadableColumnTitle` (iPad vẽ tiêu đề trong cột). Chip/tiêu đề dài phải còn đọc được ở cỡ trợ năng; footer không che nội dung cuộn.
- Bố cục theo size class/bề rộng thật, `DSColor` token, xác nhận bằng `.alert`; chụp iPhone dọc VÀ iPad ngang trước khi báo xong (xem conventions.core).
- Chuỗi UI tiếng Anh, qua biến `String` bọc `String(localized:)`; chuỗi INTERNAL/preview dùng `dtext`/`Text(verbatim:)`; không hard-code tên app (`AppConfig.displayName`).
