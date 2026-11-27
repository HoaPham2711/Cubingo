# Kiến trúc

Doc này mô tả cái **đang có**: lõi `Core/` + khối tuỳ chọn, vỏ app `AppHost/`, máy móc build/test/release và các cổng
gác. Nó thuộc lớp đồng bộ (giống hệt ở template và mọi app sinh ra) nên chỉ tả điều đúng ở mọi app; phần riêng của app
nằm ở `CLAUDE.md`, `.claude/rules/conventions.app.md` và `docs/superpowers/` (spec/plan của app). Lịch sử thiết kế của
template (spec, plan, quyết định) nằm ở repo template. Phần chưa có ghi rõ ở cuối.

## Bố cục repo

```
app.config.toml          nguồn DUY NHẤT của định danh app (tên, bundle id, team, version, cờ, sản phẩm, ngôn ngữ)
Core/                    lõi dùng chung — 8 khối, biên dịch thẳng vào target AppHost (một module, không framework/package)
CoreTests/<Khối>/        test của Core/ (+ Fake*), chạy trong AppHostTests
CoreOptional/WebAPI/     khối TUỲ CHỌN — chỉ biên dịch khi `[features] web_api = true`; CoreOptionalTests/WebAPI/ đi kèm
AppHost/
  project.yml            spec XcodeGen — sinh AppHost.xcodeproj (không commit .xcodeproj); target phụ CoreOnly
  Config/Identity.xcconfig        SINH từ app.config.toml (appconfig.py render) — không sửa tay
  Config/Features.generated.yml   SINH cùng lúc; project.yml `include` — chỗ nối khối tuỳ chọn theo công tắc
  Config/Entitlements.generated.yml  SINH; project.yml `include` — entitlement associated-domains (`applinks:$(APP_WEB_HOST)`)
                         chỉ khi `[web] host_prod` khác rỗng; `render` ghi luôn AppHost/AppHost.entitlements đúng byte XcodeGen ghi
  Config/PrivacyInfo.template.xcprivacy  mẫu privacy manifest (app sửa ở đây); `render` cắt khối `feature:<công tắc>` ⇒ AppHost/PrivacyInfo.xcprivacy (SINH)
  AppHost/               vỏ app: AppHostApp, AppTheme, AppShellView, AppTab, HomeView, AppOnboarding, AppPaywall, AppPreview,
                         WhatsNew/WhatsNewCatalog.swift, Internal/AppInternalEntry.swift, Info.plist (sinh lại bởi
                         xcodegen), PrivacyInfo.xcprivacy (SINH), AppHost.entitlements (SINH), Localizable.xcstrings
  AppHost/AppHost/Features/<Tên>/   mỗi tính năng của app một thư mục; app còn tính năng mẫu của template thì có
                         `Sample/` (mục "Tính năng mẫu và khối đánh dấu")
  AppHostTests/          SmokeTests + test của vỏ app; AppHostTests/<Tên>/ = test của tính năng (host = app, config Debug)
  AppHostUITests/        XCUITest chụp ảnh (UIShotsTests) — không thuộc L1/L2
  StoreKitConfig/Products.storekit  cấu hình StoreKit local CỦA APP (resource của AppHostTests + Run của scheme AppHost,
                         KHÔNG vào .app); test lõi `LiveStoreClientTests` dùng fixture riêng
                         `CoreTests/Purchases/CoreProducts.storekit` (id `test.pro.*`, ngoài check_storekit.py)
store/                   nguồn sự thật metadata App Store (lớp gieo): `metadata/app-info/<locale>.json`,
                         `metadata/version/<v>/<locale>.json`, `lint.toml` (chữ cấm của app), `review/notes.txt` (notes cho
                         Apple Review — người dán tay); mục "Cửa hàng, ASO và số liệu"
tools/
  common/                appconfig.py (get/render/check/state-dir/config-dir/fixture-plist), lint_identity.py, lint_feature_flag.py
  aso/                   aso.py (pull/import/lint/plan/pull-version/snapshot/build/apply/restore/release-plan: lint → plan → xác nhận →
                         apply), policy.py (luật của hook guard_asc), install_asc.sh (cài `asc` ghim phiên bản, ngoài PATH)
  analytics/             asc_pull.py, ga4_pull.py, crash_pull.py, crash_watch.py, retention.py, digest.py (kéo số → insights.json +
                         report.md; gói Python tuỳ chọn ở requirements.txt)
  dev/                   run_tests.py (L1/L2, --storekit), sim_pool.py, sync_develop.py, ui_shots.py (chụp ảnh theo route)
  i18n/                  lint_localizable.py, verify_catalog.py (ngủ khi chỉ có en)
  telemetry/             lint_firebase_imports.py
  release/               verify_release_clean.sh, debug_symbols.txt, lint_debug_symbols.py, lint_preview_code.py,
                         check_storekit.py, bump_version.sh, stamp_whats_new.py
  factory/               mission.py (ledger), mutate.py, roadmap.py, hooks_logic.py, lint_harness.py, evals/
  template/              selfcheck.sh (cổng tự kiểm), manifest.py (lớp sở hữu), blocks.py (khối đánh dấu),
                         sync_core.py (core.lock: check/status/sync), remove_sample.py (gỡ tính năng mẫu + kiểm biên);
                         repo template còn script chỉ-template (tạo app, kiểm app sinh ra, tổ hợp tắt hết, gỡ mẫu
                         trên bản chép) không chép sang app
web/                     site tĩnh + API tuỳ chọn trên Cloudflare Workers (npm workspaces; mục "Web" — `web/README.md`):
  api/                   Hono + D1 (feedback, App Store Server Notifications V2, admin, số web), migrations/ — đồng bộ
  site/                  src/worker.ts (AASA, noindex dev, chuyển /api/*) — đồng bộ; public/** + releases.json — gieo (app sở hữu)
  api|site/wrangler.jsonc  SINH từ app.config.toml (appconfig.py render) — không sửa tay
  tools/                 check_sitemap.py, check_site.py, changelog.py (+ test predeploy) — đồng bộ
  scripts/predeploy.mjs  `npm run deploy:*`: kiểm cấu hình rồi deploy — API chỉ khi `web_api` (D1/App Check/ASSN chỉ kiểm lúc đó) — đồng bộ
.claude/                 agents, skills, workflows, hooks (guard_asc, guard_autonomy, guard_test_config…), rules (quy ước), settings.json
.githooks/pre-commit     lint tĩnh trước commit (người dùng bật một lần ở mỗi clone: `git config core.hooksPath .githooks`;
                         agent không tự đặt được — hook `guard_asc` chặn lệnh đó, nhờ user)
docs/                    ARCHITECTURE, RELEASE, lessons-learned (chung; lessons-learned/app/ = riêng app), ROADMAP,
                         superpowers (spec/plan của app)
template.manifest.toml   ba lớp sở hữu của mọi file (mục "Ba lớp sở hữu, `core.lock`, đồng bộ")
core.lock                CHỈ ở app, được track: bản template đang đứng + checksum từng file lớp đồng bộ (cùng mục)
```

## Tám khối của `Core/` và khối tuỳ chọn

Không khối nào biết kiểu của app: phần riêng của app đi vào qua `init`, protocol, generic và closure. Không `public`,
không `@EnvironmentObject` cho đối tượng nghiệp vụ (truyền tường minh — `fullScreenCover` không kế thừa environment).

| Khối | Lối vào chính (app gọi) | Ghi chú |
|---|---|---|
| `Bootstrap/` | `AppConfig.current` (đọc Info.plist), `AppEnvironment` (`isUnitTestHost`, `uiPreviewRoute`), `applog(_:)`/`AppLog`, `AppBootstrap.run(standardSteps(...))`, `AppBootstrap.skipsStoreKit/skipsNetwork`, `AppRootGate(onboarding:main:willFinishOnboarding:)`, `AppLifecycle.handle(_:onActive:)` | Trình tự khởi động — mục riêng bên dưới |
| `Design/` | `DSTheme` (+ `.standard`, `.withAccent(hex:)`, `DSTheme.install`), `DSColor`, `DSLayout`, `DSRadius`, `.readableContentWidth()`, `.scaledFont(size:weight:design:monospacedDigit:relativeTo:)` (thay `.font(.system(size:))` trần — co giãn theo Dynamic Type), `ReadableColumnTitle` + `ReadableColumnTitlePlacement` + `.readableColumnNavigationTitle(_:)` (iPad: tiêu đề lớn tự vẽ TRONG cột đọc, thanh điều hướng inline; iPhone: tiêu đề lớn hệ thống), `PrimaryCapsuleButton`, `EmptyStateView`, `FilterChip`, `GlassIconButton`, `InsetGroupedList`, `StatPill`, `BottomSheetChrome`, `ProgressRing` | Giao diện tối + bảng màu chuẩn `DSTheme.standard`; app chọn theme ở `AppHost/AppHost/AppTheme.swift` (mục "Theme và ngôn ngữ của app") — không sửa `Core/`. `InsetGroupedList`/`BottomSheetChrome` còn cỡ chữ cố định (nợ) |
| `Telemetry/` | `Track.log(.<event>(...))`, `AppEvent` (struct + static factory, app thêm event của nó), `.trackScreen(...)`, `TelemetryConsent`, `TelemetryBootstrap.start/consentDidChange`, `TelemetryConfig`, `UserPropertySync`, `AppleAdsAttribution` | `import Firebase*` CHỈ ở `FirebaseSink.swift`; taxonomy gác bằng `EventNameCatalog` + `TelemetryTaxonomy` — gồm `crossCatalogViolations(catalogs:samples:)` (trùng tên giữa các catalog, mẫu mồ côi, khoá param chứa mảnh vị trí `locationKeyFragments`: `lat`, `lon`, `coord`, `gps`, `location`; so chuỗi con không phân biệt hoa/thường nên `allocation`/`latest` cũng bị bắt — đặt tên khoá tránh các mảnh đó) |
| `Purchases/` | `Entitlements.live(config:)` (`start`, `refresh`, `subscribe`, `restore`, `isPro`, `isRestoring`, `entitlementKind`, `canManageSubscription`, `paywallEnabled`), `ProFeature`, `FreeUseLedger`, `PaywallView`, `PaywallContent`, `PaywallLayout`, `RestoreAlert`, `StoreClient`/`LiveStoreClient` | Paywall tắt ⇒ coi như Pro, không lời gọi StoreKit nào; mua trọn đời (`ProProduct.Kind.lifetime`). `StoreClient.currentEntitlementKind()` → `Entitlements.entitlementKind` (đọc trong `refresh()` khi đang có quyền); `canManageSubscription` = Pro và không phải trọn đời (loại chưa rõ ⇒ vẫn `true`, thà thừa hàng "Manage subscription" còn hơn giấu lối huỷ). `RestoreAlert.make(_:)` là ánh xạ `RestoreOutcome` → alert DUY NHẤT (paywall + Settings); `PaywallLayout.pinsFooter(isAccessibilitySize:)` quyết footer ghim hay cuộn |
| `Engage/` | `UpdateChecker.makeDefault(appID:)` + `UpdateBanner`; `ReviewPrompter` + `ReviewScheduler` + `.reviewPromptHost(...)`; `WhatsNewHost.make(cards:...)` → `WhatsNewPresenter` + `FeatureUsageLedger`, `.whatsNewSheet(...)`, `WhatsNewListView` | Thẻ What's New `.unreleased` chỉ tồn tại dưới `#if INTERNAL \|\| WHATSNEW_ALLOW_UNRELEASED` ⇒ archive Store còn sót là lỗi biên dịch |
| `Support/` | `FeedbackView` + `FeedbackTransport` (app cấp), `FeedbackDraft`, `DiagnosticsSnapshot`, `SupportMail`/`SupportMailOpener` (mailto), `ActiveWorkMarkerStore`, `ModalPresentationProbe`, `ShareSheet` | Form phản hồi CHỈ khi có web API (mailto không xác nhận được đã gửi) |
| `Shell/` | `RootShellView` (tab bar compact / sidebar regular, lặp một `ShellTab`), `ShellNavigationModel`, `SidebarItem` (+ `erased(_:)` ép `AnyHashable` của `selectSidebarItem` về đúng kiểu, khác kiểu ⇒ `nil`), `OnboardingView`/`OnboardingFlow`, `AppTips`, `IdleTimerCoordinator`, `SettingsView(SettingsDependencies…)`, `StorageBarChart` + `StorageBarMath` (phần tính thuần: bề rộng lát, nhãn %, nhãn dung lượng), `StorageOtherData.runAtLaunch`, `AppLinks`, `AppLanguage` (danh sách từ `Bundle.main.localizations`) | Settings tự có `NavigationStack` — không bọc thêm |
| `Internal/` | `dtext(_:)`, `InternalBuild.isEnabled`, `.internalBadge()`, `InternalLaunch`, `UIPreviewLaunch`/`UIPreviewRoute`; chỉ INTERNAL: `InternalLongPressSheet`, `LogFileView`, `FirstLaunchSimulation`, `ReviewPromptDebugSection` | Wrapper biên dịch ở mọi config, nội dung debug chỉ ở INTERNAL |

**Khối tuỳ chọn `CoreOptional/WebAPI/`**: `WebAPIFeedbackTransport(baseURL:appVersion:)` (gửi phản hồi tới API của app,
kèm token App Check), `FeedbackRequestEncoder`, `AppCheckTokenSource` (`installProvider()` gọi trong
`TelemetryConfig.preConfigure`, ngay trước `FirebaseApp.configure()`; `currentToken()` trả `nil` khi Firebase chưa cấu
hình). `import FirebaseAppCheck` chỉ ở `AppCheckTokenSource.swift` (allow-list theo file trong
`lint_firebase_imports.py`). App chọn transport ở `AppHostApp.makeFeedbackTransport` (`#if FEATURE_WEB_API`).

## Luồng cấu hình

```
app.config.toml ──appconfig.py render──► AppHost/Config/Identity.xcconfig     (biến APP_*)
      │                              ├─► AppHost/Config/Features.generated.yml (khối tuỳ chọn đang bật, hoặc `{}`)
      │                              ├─► AppHost/Config/Entitlements.generated.yml (associated-domains khi có host, hoặc `{}`)
      │                              │     + AppHost/AppHost/AppHost.entitlements (đúng byte XcodeGen ghi)
      │                              └─► AppHost/AppHost/PrivacyInfo.xcprivacy (cắt từ Config/PrivacyInfo.template.xcprivacy theo [features])
      │                                        │ project.yml `include`
      ▼                                        ▼
tools (appconfig.get) ── project.yml gán build setting + khoá Info.plist ──► Info.plist ──► AppConfig (lúc chạy)
```

- xcconfig: `APP_BUNDLE_ID_STORE|INTERNAL`, `APP_DISPLAY_NAME_STORE|INTERNAL`, `APP_TEAM_ID`, `APP_MARKETING_VERSION`,
  `APP_BUILD_NUMBER`, `APP_WEB_HOST_PROD|DEV`, `APP_STORE_ID`, `APP_SUPPORT_EMAIL`, `APP_FEATURE_PAYWALL|APPLE_ADS|WEB_API`
  (`YES`/`NO`), `APP_PRODUCT_IDS` (cách nhau bằng dấu cách).
- Khoá cấu hình chỉ công cụ đọc (không vào xcconfig): `[store] locales` (locale của listing; phần tử đầu = locale chính; mặc
  định `["en-US"]`; `appconfig.py get store.locales` in cách nhau bằng dấu phẩy), `[analytics] ga4_property` (chữ số hoặc rỗng) và
  `bq_project` (id project GCP hoặc rỗng), `[apple] app_store_id` (rỗng tới khi người tạo app record trên App Store Connect — rỗng
  ⇒ mọi lệnh `aso.py` cần App Store Connect từ chối bằng một dòng hướng dẫn). `[web] host_prod` có ⇒ `host_dev` bắt buộc.
- Thư mục NGOÀI repo (tool tính qua `appconfig.state_dir(cfg, tool)`, `config_dir(cfg)`, `shared_bin_dir()`; CLI
  `appconfig.py state-dir <tool>` / `config-dir`): trạng thái `$IOS_APP_FACTORY_STATE/<slug>/<tool>` (mặc định
  `~/Library/Application Support/ios-app-factory/<slug>/<tool>`; slug nằm trong đường dẫn để nhiều app trên một máy không đè
  nhau), cấu hình và khoá `$IOS_APP_FACTORY_CONFIG/<slug>` (mặc định `~/.config/ios-app-factory/<slug>`), binary dùng chung cả
  máy `$IOS_APP_FACTORY_BIN` (mặc định `~/.local/share/ios-app-factory`, chỗ cài `asc`). Test và tự kiểm trỏ cả ba vào thư mục tạm.
- Info.plist (khoá do `project.yml` khai): `WebHost` (Release ⇒ host_prod, Debug/Internal ⇒ host_dev), `AppStoreID`,
  `SupportEmail`, `FeaturePaywall`/`FeatureAppleAds`/`FeatureWebAPI`, `ProductIDs`.
- `Core/Bootstrap/AppConfig.swift` đọc lúc chạy (`AppConfig(info:)` không crash khi thiếu khoá; test dựng fixture
  riêng, không phụ thuộc cấu hình thật). Công tắc tính năng đọc qua `AppConfig.current.features`.
- `appconfig.py load` có lược đồ CHẶT (khoá lạ bị từ chối) và từ chối cấu hình mâu thuẫn (paywall bật mà không có
  `product_ids`, web API hoặc paywall bật mà thiếu `web.host_prod`/`web.host_dev` — paywall cần link Điều khoản/Quyền
  riêng tư —, email sai dạng); lỗi nêu tên khoá. `check` rc 1 khi một file sinh ra cũ
  (pre-commit, `run_tests.py`, `verify_release_clean.sh` gọi).

## Quy tắc biên

1. `Core/` **không** tham chiếu kiểu của `AppHost/` hay `CoreOptional/` — target `CoreOnly` (static library chỉ chứa
   `Core/`, scheme `CoreOnly`, không ship) phải build được (`selfcheck.sh` bước 4b, cả `--quick`).
2. `Core/` giống hệt ở mọi app (lớp đồng bộ; phần riêng của app — theme, nội dung, cấu hình — đi vào qua khe ở
   `AppHost/`): không `#if` theo tính năng. Chỉ được `#if INTERNAL`, `#if DEBUG`,
   `#if targetEnvironment(simulator)`, `WHATSNEW_ALLOW_UNRELEASED`.
3. Cờ `FEATURE_*` chỉ trong `AppHost/AppHost/AppHostApp.swift`; `Core/` + `CoreTests/` không nhắc khối tuỳ chọn; `AppHost/` chỉ nhắc kiểu của khối trong `#if <cờ của khối>` (không tính nhánh `#else`/`!cờ`) — `tools/common/lint_feature_flag.py`
   (selfcheck bước 1, pre-commit khi commit đụng `.swift`). Hiện chỉ `AppHostApp.swift` nhắc `FEATURE_WEB_API`.
4. `import Firebase*` chỉ ở `Core/Telemetry/FirebaseSink.swift` và `CoreOptional/WebAPI/AppCheckTokenSource.swift` —
   `tools/telemetry/lint_firebase_imports.py`. `import StoreKit` chỉ ở ĐÚNG ba file: `Core/Purchases/LiveStoreClient.swift` (chỗ duy nhất đọc/ghi
   trạng thái quyền và mua — mọi nơi khác đi qua `StoreClient`), `Core/Engage/Review/ReviewPromptHost.swift`
   (`requestReview` của SwiftUI) và `Core/Shell/SettingsAccountSection.swift` (`manageSubscriptionsSheet`); hai file
   sau chỉ dùng API UI hệ thống, không chạm trạng thái quyền.
5. Code debug chỉ dưới `#if INTERNAL`, khai trong `AppHost/Config/debug_symbols.app.txt` (app) hoặc `tools/release/debug_symbols.txt` (lõi) — mục riêng bên dưới.

## Khối tuỳ chọn — cách nối và cách thêm khối mới

`[features] web_api = true` ⇒ `render` ghi vào `Features.generated.yml`: nguồn `CoreOptional/WebAPI` vào target
`AppHost`, `CoreOptionalTests/WebAPI` vào `AppHostTests`, product `FirebaseAppCheck` của package `Firebase` đã ghim
(`exactVersion`, không thêm package thứ hai), cờ `FEATURE_WEB_API` vào `SWIFT_ACTIVE_COMPILATION_CONDITIONS` của cả hai
target (`$(inherited) …`, giữ DEBUG/INTERNAL). `false` ⇒ file là `{}` và không file nào của khối được biên dịch.
Đường dẫn trong file sinh ra tính từ `AppHost/Config/` (`../../CoreOptional/...`) — XcodeGen tính theo file `include`.

Thêm một khối tuỳ chọn mới:
1. Đặt nguồn ở `CoreOptional/<Khối>/`, test ở `CoreOptionalTests/<Khối>/`. Khối được dùng kiểu của `Core/`, không
   ngược lại; không type debug nào chưa khai.
2. Thêm khoá cờ vào `appconfig.SCHEMA["features"]` + `_FEATURE_KEYS`, và vào `[features]` của `app.config.toml`
   (luật mâu thuẫn mới, nếu có, vào `_check_features`); thêm biến `APP_FEATURE_<X>` ở `render_xcconfig` và khoá
   `Feature<X>` vào Info.plist (`project.yml`) + `AppConfig.Features` nếu app cần đọc lúc chạy.
3. Thêm một phần tử vào `appconfig.OPTIONAL_BLOCKS` (`feature`, `flag` = `FEATURE_<X>`, `src`, `tests`, `products` của
   package Firebase nếu cần). `render_features_yml`, `disabled_block_roots` (run_tests bỏ test của khối tắt) và
   lint biên tự đi theo.
4. Nếu khối import Firebase: thêm file vào allow-list của `tools/telemetry/lint_firebase_imports.py`.
5. Chỗ chọn cài đặt cụ thể (dưới `#if FEATURE_<X>`) đặt trong `AppHost/` (như `AppHostApp.makeFeedbackTransport`).
6. Cập nhật script tổ hợp tắt hết (`feature_matrix_check.sh` của template — khối tuỳ chọn là lớp đồng bộ nên việc này
   làm ở repo template): thêm cờ vào bước lật cờ và chuỗi mốc của khối vào `NEEDLES`
   (mốc phải có trong binary bật và KHÔNG có trong binary tắt — FirebaseCore luôn mang `FIRAppCheckComponent`, nên
   không dùng tên trần như `AppCheck`).
7. Privacy manifest SINH theo công tắc, không phải file tĩnh: khai dữ liệu khối thu trong mẫu
   `AppHost/Config/PrivacyInfo.template.xcprivacy`, bọc đúng các mục của khối giữa hai dòng
   `<!-- feature:<x>:begin -->` … `<!-- feature:<x>:end -->` (`<x>` = tên công tắc); thêm một hàng vào `appconfig.PRIVACY_BLOCKS`
   (`switch`, `info_key` = `Feature<X>`, `types` = các `NSPrivacyCollectedDataType…` chỉ khối đó khai). `render` cắt khối của công
   tắc tắt (`AppHost/AppHost/PrivacyInfo.xcprivacy` là file sinh, commit cùng), và cổng 7 của `verify_release_clean.sh` đối chiếu
   `.app` với bảng đó. Khoá `Feature<X>` phải có ở Info.plist (bước 2): thiếu ⇒ cổng 7 FAIL. Test gác bảng khớp mẫu:
   `test_bang_privacy_blocks_khop_khoi_trong_mau`. Cổng 7 chưa có lối thoát: nó đối chiếu THEO KIỂU dữ liệu, không theo vị trí trong
   file — app tắt công tắc mà vẫn cần khai kiểu của khối đó (vd `EmailAddress` cho tính năng riêng của app khi `web_api` tắt) thì
   FAIL dù khai ở mục nằm ngoài khối (nợ của template; app gặp ca này thì ghi vào `docs/ROADMAP.md` của app và báo template).
8. Chạy `appconfig.py render`, `xcodegen generate`, rồi `tools/template/selfcheck.sh` đầy đủ (tổ hợp bật + tắt hết).

## Trình tự khởi động

`AppHostApp.init()`: (1) Simulator + route `-uiPreview`: `AppPreviewSeed.prepare()` ép trạng thái tất định (cờ
onboarding, suite What's New) — TRƯỚC `WhatsNewHost.make` vì nó đọc cờ onboarding đúng một lần; (2)
`WhatsNewHost.make` — presenter + ledger dùng chung danh sách thẻ; (3) `AppBootstrap.run(standardSteps(...))`:

| # | Bước | Vì sao ở vị trí này | Host unit test | `-uiPreview` |
|---|---|---|---|---|
| 1 | `takeIncident` | đọc + xoá dấu "đang làm việc" của lần chạy trước TRƯỚC khi có gì `begin` dấu mới (kết quả: `AppBootstrap.launchIncident`) | bỏ | chạy |
| 2 | `purgeTmp` (`StorageOtherData.runAtLaunch`) | lấy mốc cắt lúc gọi, xoá mục `tmp/` tạo trước mốc ⇒ phải trước mọi bước có thể ghi tmp (Firebase configure) | bỏ | bỏ (seed preview chạy trước `run` mà không bị dọn) |
| 3 | `usageObserver` (khi app có What's New) | gắn ledger TRƯỚC sink để không lỡ event "đã dùng" | bỏ | chạy |
| 4 | `telemetry` (`TelemetryBootstrap.start`) | sớm nhất sau 3 bước trên: `first_open`/`session_start` bắn lúc configure; tự khởi động attribution Apple Ads | chạy (tự no-op ở host test / Simulator / thiếu plist) | chạy (tự no-op) |
| 5 | `firstLaunchSim` (`InternalLaunch.beforeTipsConfigure`) | giả lập lần đầu (INTERNAL) xin TipKit xoá datastore — chỉ hợp lệ TRƯỚC configure | bỏ | bỏ |
| 6 | `tips` (`AppTips.configure`) | sau cùng | bỏ | bỏ |

Ngoài `init`: `entitlements.start()` ở `.task` (bỏ khi `AppBootstrap.skipsStoreKit` — host test, hoặc route không nằm
trong `AppPreview.routesNeedingStore`), kiểm tra cập nhật ở `.task` (bỏ khi `skipsNetwork`), `scenePhase == .active`
⇒ `AppLifecycle.handle` → `reviewPrompter.noteAppBecameActive()`, `entitlements.refresh()`, kiểm tra cập nhật.
`Entitlements`/`UpdateChecker`/`ReviewPrompter`/presenter sở hữu ở cấp App (`Transaction.updates` nghe từ giây đầu).

## Route preview, seed và chụp ảnh (chỉ Simulator)

`-uiPreview <route>` (`AppPreview`) mở thẳng một màn với trạng thái tất định cho `tools/dev/ui_shots.py`. Route của
**khung**: `home`, `onboarding`, `settings`, `paywall`, `whatsNew`, `feedback`. Tính năng của app thêm route của nó (nằm
trong khối `// sample:` nếu là của tính năng mẫu — mất cùng mẫu; danh sách và ý nghĩa ở README của thư mục tính năng).
Còn tính năng mẫu thì `home` là Home đã seed nội dung của mẫu; gỡ mẫu xong Home là màn giữ chỗ (`EmptyStateView`).
Thêm route = thêm `case` (+ dựng màn ở `AppShellView`/seed) + một dòng ở README của tính năng; `ui_shots.py all` tự thấy.

- Code seed/store giả chỉ biên dịch cho Simulator (`#if targetEnvironment(simulator)`) và có tên kết thúc bằng
  `PreviewSeed`/`PreviewStore`; `tools/release/lint_preview_code.py` (selfcheck bước 1, cổng pre-commit) từ chối kiểu mang
  hậu tố đó mà nằm ngoài vùng chỉ-Simulator (không ngoại lệ cho `#Preview`). Dữ liệu mẫu là code Swift, KHÔNG bao giờ
  là resource (một `.json` dưới `AppHost/AppHost/` sẽ vào `.app` ở mọi config).
- Route không đụng dữ liệu thật của simulator đó: mọi seed ghi vào suite `uiPreview…` hoặc thư mục `uiPreview-…`
  (vd `Application Support/uiPreview-<tính năng>/`, viết lại mỗi lần mở ⇒ ảnh lặp lại được); bộ đếm ở bộ nhớ
  (không Keychain). Route `paywall` vẽ bằng `AppPreviewStore` — store giả (file `.storekit` của scheme không áp cho app do
  XCUITest khởi chạy); `routesNeedingStore` rỗng nên không route nào chạm StoreKit thật. `PaywallPreviewStore` của
  lõi chỉ mở khi `DEBUG && simulator`.
- `SmokeTests.testStoreGiaCuaPreviewKhopFileStorekit` giữ giá/kỳ dùng thử của store giả khớp `Products.storekit` — nó
  nhận gói theo HẬU TỐ id (`monthly`/`yearly`/`lifetime`), nên app đổi id sản phẩm phải giữ hậu tố đó hoặc sửa
  `AppPreviewStore.products`. Huy hiệu INTERNAL ẩn khi có route preview.
- **`tools/dev/ui_shots.py`** (XCUITest, scheme `AppHost-UIShots`, DerivedData `.temp/DerivedData/uishots`):
  `ui_shots.py all --label <tên>` chụp MỌI `case` của `AppPreview` (đọc thẳng file Swift, kể cả khối sample) ra
  `.temp/ui-shots/<tên>/<route>-port.png|-land.png`. Tuỳ chọn: `--udid` (mặc định sim riêng của worktree); `--orient auto|landscape|portrait`
  (auto: sim iPad ⇒ ngang, còn lại dọc; iPhone chỉ hỗ trợ dọc nên ngang trên iPhone FAIL thay vì ghi ảnh nghiêng);
  `--out DIR` hoặc `--label` (loại trừ nhau); `--content-size <cỡ>` (Dynamic Type của sim, luôn trả về `large` kể cả khi lỗi
  hay SIGTERM); `--print-cmd`. Ảnh ngang đã xoay đứng lại. Route có thêm ảnh sau khi cuộn
  (`<route>-scrolled-*.png`) khai ở `UIShotsTests.scrollRoutes` = map route → SỐ LẦN vuốt (`settings` 1, `paywall` 3,
  `onboarding` 1; tính năng thêm route của nó — route của tính năng mẫu nằm trong khối `// sample:` ở chính file đó). Thiếu ảnh ⇒ rc 1.
  Không có chế độ hai máy một lượt: chạy hai lượt cùng `--label`, lượt iPad cần sim iPad tạm (tạo rồi xoá bằng
  `simctl`, không mượn sim đang boot của phiên khác).
- Ở repo template, `MATRIX_SHOTS_DIR=<dir>` của script tổ hợp tắt hết (`feature_matrix_check.sh` của template) chụp thêm
  `settings feedback home` (+ route của tính năng mẫu khi còn) ở tổ hợp tắt hết — ảnh "tắt hết" không cần chụp tay.

## Tính năng mẫu và khối đánh dấu

App sinh từ template mặc định còn **tính năng mẫu** của template (thư mục `Features/Sample/` của target app, test ở
thư mục `Sample/` tương ứng của target test): giàn giáo cho thấy mỗi khối lõi được nối vào app thật ra sao. Nếu thư mục đó còn, README
của nó tả tính năng, dữ liệu, route và bảng "khối lõi nào được gọi ở đâu" — README mất cùng thư mục khi gỡ. App thật gỡ
mẫu trước khi ra bản Store (cổng 14). Phần dưới đúng cả trước lẫn sau khi gỡ.

### Quy ước khối đánh dấu

Ngoài hai thư mục mẫu, dòng Swift nào nhắc một symbol của mẫu phải nằm giữa `// sample:begin` và `// sample:end` (mỗi dấu
chiếm trọn một dòng, không lồng nhau). Chỗ cần một dòng thay thế sau khi gỡ thì viết dòng đó ở dạng comment giữa
`// sample:else-begin` … `// sample:else-end` (lệnh gỡ bỏ đúng một `// ` mỗi dòng). Sau khi cắt, file phải còn là Swift hợp
lệ và app phải có nghĩa (Home hiện `EmptyStateView` giữ chỗ). `Core/`/`CoreOptional/` không được nhắc mẫu.

Tài liệu lớp seed tả mẫu (`CLAUDE.md`, `README.md`, `.claude/rules/conventions.app.md`, `AppHost/project.yml`, `docs/NEW_APP_CHECKLIST.md` — danh
sách `SEED_DOCS` của `remove_sample.py`) đặt phần đó giữa hai dòng `<!-- sample:begin -->` … `<!-- sample:end -->` (Markdown,
không nhánh else) hoặc `# sample:begin` … `# sample:end` (YAML). Tài liệu lớp đồng bộ (doc này, agent, skill) không có
khối: không tool nào sửa file đồng bộ tại chỗ, nên chúng viết có điều kiện ("nếu app còn tính năng mẫu…"). Cùng bộ cắt
(`tools/template/blocks.py`) xử lý họ `template:` — phần của file seed chỉ đúng ở template, bị cắt khi tạo app.

### `tools/template/remove_sample.py`

- `--check` (selfcheck bước 1, pre-commit khi commit đụng `.swift`): rc 1 + `file:dòng` khi dấu sai cú pháp (không cặp,
  lồng nhau, dính code, nằm trong chuỗi nhiều dòng/khối `/* */`), khi dòng NGOÀI khối mang dấu vết của mẫu (phân biệt hoa
  thường, comment cũng tính: `Sample[A-Z]…`, `sample_…`, `sample[A-Z]…`, `Features/Sample`, `tính năng mẫu`, tên TRỌN của
  route mẫu — đọc từ khối trong `AppPreview.swift` — chỉ ở vị trí route: `AppPreview.x`, `"x"`, `` `x` ``, `.x` ngầm không
  đứng sau định danh/`)`/`]`/`?`/`!`/`\`; `let items`/`store.items`/key path `\.items` không tính; `case` route có raw value
  ⇒ rc 2), khi `Core/`/`CoreOptional/` mang dấu vết, hoặc khi tài liệu gieo sai khối / tả mẫu ngoài khối. Hai thư mục mẫu
  đã vắng ⇒ Swift không soi nữa (luật `sampleX` chữ thường bắt cả `sampleRate` — chỉ áp khi còn mẫu), chỉ còn kiểm tài
  liệu gieo không sót dấu `sample:` hay câu tả mẫu.
- Gỡ: validate hết rồi mới ghi; từ chối (không ghi gì) khi gốc sai (không có `app.config.toml` + `AppHost/project.yml`,
  rc 2), khi `--check` đỏ, khi bất kỳ đường dẫn sẽ ghi/xoá có thành phần symlink hoặc resolve ra ngoài gốc, khi một file
  sẽ ghi thuộc lớp đồng bộ (`template.manifest.toml`), khi cây git còn thay đổi chưa commit ở đường dẫn sẽ đụng (trừ
  `--force`). Ghi từng file nguyên tử, xoá hai thư mục mẫu SAU CÙNG, không in traceback; chạy lại trên cây đã gỡ không đổi
  gì. Cắt khối trong Swift và tài liệu gieo, rồi in việc tay còn lại (`FOLLOW_UPS`: tour onboarding, bảng so sánh
  paywall, thẻ What's New của app).
- Repo template còn chứng minh trên một bản chép rằng gỡ mẫu để lại app vẫn `selfcheck.sh --quick` + `run_tests.py
  --full`, không còn symbol mẫu, file lớp đồng bộ không đổi một byte, tài liệu gieo sạch, binary Release không còn mốc của
  mẫu và cổng 14 qua THẬT (`sample_removal_check.sh` của template, trong selfcheck đầy đủ).

### Cổng 14 và `ALLOW_SAMPLE_IN_RELEASE`

`verify_release_clean.sh` cổng 14: bản Store còn mốc của mẫu ⇒ FAIL "còn tính năng mẫu — chạy remove_sample.py".
`ALLOW_SAMPLE_IN_RELEASE=1` chỉ để TỰ KIỂM (`selfcheck.sh` đặt riêng cho từng lệnh verify, không export, và chỉ khi
`Features/Sample` còn) — luồng ra bản không bao giờ đặt; với đầu vào `.xcarchive` biến bị TỪ CHỐI. `selfcheck.sh` còn có đối chứng
dương: thiếu biến thì chính `.app` Release còn mẫu PHẢI bị cổng 14 từ chối (đúng một dòng FAIL). Cổng 4 mở rộng: không file
`*.md` nào trong resource của `.app` (`project.yml` loại `**/*.md` khỏi resource nguồn app nên README trong thư mục nguồn không
lọt vào bundle); bỏ qua `Frameworks/`, `PlugIns/`, mọi `*.bundle` (resource bên thứ ba có thể kèm README).

## Ba lớp sở hữu, `core.lock`, đồng bộ

### Ba lớp

`template.manifest.toml` xếp MỌI file đang track vào đúng một lớp:

| Lớp | Ai sở hữu | Ví dụ | Đổi thế nào |
|---|---|---|---|
| **đồng bộ** (`sync`) | template; giống hệt từng byte ở mọi app | `Core/`, `CoreOptional/`, phần lớn `tools/`, `.githooks/`, agent/hook/workflow/skill của `.claude/`, `conventions.core.md`, doc này, `docs/RELEASE.md`, `docs/lessons-learned/` | chỉ ở template, rồi `sync_core.py sync` thay NGUYÊN file ở app |
| **gieo một lần** (`seed`) | app, sau khi tạo | `app.config.toml`, `AppHost/`, `CLAUDE.md`, `conventions.app.md`, `docs/lessons-learned/app/`, và README / CHANGELOG / ROADMAP / checklist của app | app sửa thoải mái; template đổi bản gốc thì lệnh đồng bộ chép bản mới ra để so tay, không đụng file của app |
| **chỉ-template** (`template_only`) | template; không bao giờ tới app | spec/plan/quyết định của template, README/CHANGELOG/ROADMAP của chính template, các script tạo app và kiểm app sinh ra | — |

Luật của manifest (`tools/template/manifest.py`): mục kết thúc bằng `/` là cả thư mục, không thì đúng một file; **mục khai
dài nhất khớp thắng** (nên một thư mục con khai ở lớp khác thắng thư mục cha — `docs/lessons-learned/app/` là lớp gieo
nằm trong `docs/lessons-learned/` lớp đồng bộ); một mục không được khai ở hai lớp. Chỗ Claude Code cố định, app lại cần
thêm đồ của riêng mình (agent, hook, workflow, skill): manifest khai **từng file** của `.claude/agents|hooks|workflows/` và
**từng thư mục** của `.claude/skills/` — agent/skill mới của app vì thế không thuộc lớp đồng bộ, không bị cổng báo. Đồ của
app ở các chỗ của app: `AppHost/…`, `tools/app/…`, `docs/lessons-learned/app/…`; một file MỚI nằm trong thư mục do template
sở hữu (vd một file Swift mới dưới `Core/`) bị cổng chặn — chuyển ra chỗ của app hoặc đưa nó vào template.

Ở template, `manifest.py check` (pre-commit khối 1d + selfcheck bước 1) đỏ khi: một file track chưa có lớp; một mục khai
không khớp file nào; một file thư mục gieo che lên file track không phải chỉ-template; file đồng bộ/gieo nhắc (trong
backtick hay link Markdown) một file chỉ-template — tài liệu đồng bộ nhắc script chỉ-template bằng tên trần kèm "của
template", phần chỉ đúng ở template của file lớp gieo nằm giữa `<!-- template:begin -->` … `<!-- template:end -->`; khối
đánh dấu sai; `CHANGELOG.md` của template thiếu tiểu mục `### Việc phải làm tay khi lên bản này` (bản ≥ v0.4.0).

**Template hay app** do HEAD quyết định: repo là template khi `new_app.py` của template (thư mục `tools/template`) được
track trong HEAD (HEAD chưa có commit: trong index); mọi repo khác là app, và app phải track `core.lock`.

### `core.lock`

JSON ở gốc app (khoá sắp xếp, thụt 2, có xuống dòng cuối), được track; do lệnh tạo app ghi, lệnh đồng bộ cập nhật:

```json
{ "schema": 1,
  "template": { "source": "<đường dẫn hoặc URL repo template>", "tag": "v0.4.0", "commit": "<sha đầy đủ>" },
  "synced": { "<đường dẫn>": "<sha256>[+x]" },
  "seeded": { "<đường dẫn>": "<sha256>[+x]" } }
```

`synced` ghim digest mọi file lớp đồng bộ (`+x` = có bit thực thi của chủ); `seeded` ghim digest NGUYÊN BẢN của file gieo ở
template lúc gieo (để lần đồng bộ sau biết file gieo nào template đã đổi). `tag` là `null` khi app tạo từ một commit không có
tag. Chỉ file lớp đồng bộ bị gác; file gieo thuộc app. `python3 tools/template/sync_core.py status` in tag, commit, nguồn.

### Vòng đời một bản lõi

1. Sửa lõi **ở template** (không có lối "chấp nhận lệch" ở app) — lỗi lõi gấp cũng vậy: sửa ở template, gắn tag bản vá.
2. Template gắn tag `vX.Y.Z` trên `main` (`docs/RELEASE.md` §"Phát hành một bản của template"); mục CHANGELOG của bản đó
   có `### Việc phải làm tay khi lên bản này`.
3. Ở app: `python3 tools/template/sync_core.py sync --to vX.Y.Z` (cây git sạch; `--dry-run` xem kế hoạch). Lệnh lấy cây
   NGUYÊN BẢN ở tag, thêm/sửa/xoá file lớp đồng bộ, file template chuyển sang lớp gieo thì app giữ file, file gieo mới đổi thì
   bản mới nằm ở `.temp/core-sync/<tag>/` để so tay, ghi `core.lock` sau cùng, in các tiểu mục "việc phải làm tay" của các
   bản đi qua. Không tự commit.
4. App render lại cấu hình, `xcodegen generate`, chạy test, rồi commit (lệnh in sẵn bốn bước).

### Chặn ở đâu

| Cổng | Chặn gì |
|---|---|
| pre-commit khối 0 (app) | file lớp đồng bộ trong commit lệch digest (`M` sửa, `D` mất), file MỚI trong thư mục lớp đồng bộ (`A`), `core.lock` bị gỡ khỏi commit, thiếu `manifest.py`/`sync_core.py`, app track file đánh dấu của template. Đọc đúng index đang commit nên `git commit -a` cũng bị bắt; commit do lệnh đồng bộ tạo (file + lock cùng stage) qua |
| pre-commit khối 1d (template) | `manifest.py check --staged`; template không được track `core.lock` |
| `verify_release_clean.sh` cổng 15 (app) | cùng kiểm trên working tree + `core.lock` phải được track, lịch sử từng có lock thì là app — lưới đỡ khi hook bị tắt |
| `selfcheck.sh` bước 1 | template: `manifest.py check`; app: `sync_core.py check` |

**Mô hình đe doạ — nói thẳng.** Các cổng này chặn trôi lõi do vô ý hoặc do agent: sửa tay một file lõi, thêm file vào thư mục
của template, xoá `core.lock` hay một tool của cổng (kể cả qua `commit -a`). Chúng KHÔNG chặn người cố ý: ai dùng
`--no-verify` rồi viết lại lịch sử, hay dựng giả file đánh dấu của template, thì qua được — đó là ngoài phạm vi. Cổng 15 lúc
ra bản là lưới đỡ cho trường hợp hook chưa bật (`git config core.hooksPath .githooks` ở MỖI clone; phiên Claude Code cảnh báo
khi quên). Merge, cherry-pick, rebase không chạy pre-commit — chỉ cổng 15 và `sync_core.py check` bắt được lệch từ đó.

### Giới hạn đã biết

- Không có lối tắt sửa lõi tại app (quyết định có chủ ý): lỗi lõi ⇒ sửa ở template → tag → `sync`.
- `sync` chạy bằng `manifest.py`/`sync_core.py` CŨ của app để đọc cây MỚI. Bản template đổi lược đồ manifest (hay thêm khoá)
  hoặc lược đồ `core.lock` mà tool cũ không hiểu ⇒ tool cũ từ chối TRƯỚC khi ghi (rc 1) và in lệnh đường ra: chạy
  `sync_core.py` CỦA BẢN MỚI trên app — `python3 <checkout template ở tag đích>/tools/template/sync_core.py sync --root <app>
  --to <tag> --source <template>` (tool đó nhập `manifest.py` của chính nó). Đừng chép tay file mới vào app: cây bẩn ⇒ `sync`
  từ chối, khối 0 chặn commit. Lược đồ lock của bản mới được biết bằng dòng `SCHEMA = <n>` trong `sync_core.py` của cây mới
  (không chạy file đó); không thấy dòng ⇒ không biết, chỉ manifest được kiểm. Bản mới phải đọc được lock/manifest bản trước —
  quy tắc ở `docs/RELEASE.md` §"Phát hành một bản của template".
- `withAccent` chỉ đổi `accent`/`accentDark`/`onAccent`; ba màu biểu đồ giữ màu chuẩn trừ khi app tự đặt.
- Lệnh tạo app dựng khung `store/` nhưng chưa dựng trang pháp lý, AppIcon (template chưa có asset catalog), app record trên App
  Store Connect, Associated Domains ở App ID: đó là mục tay trong checklist việc của app.
- File gieo MỚI của một bản template (`store/…`, mẫu privacy manifest…) mặc định chỉ tới app cũ dưới dạng bản chép thô ở
  `.temp/core-sync/<tag>/`. `sync --to <tag> --adopt-new-seed` tạo chúng ngay ở app (thay biến bằng cấu hình CỦA APP, cắt khối
  `template:`, nhân bản metadata theo `[store] locales`). KHÔNG nhận: file Swift (thường kéo theo sửa file gieo đã có mà `sync` không
  sửa), hai thư mục mẫu `Sample/`, file do `render` sinh ra, metadata mẫu của template khi khung đã có; đích đã track của app
  không bị đụng (chỉ có bản chép thô). Tool CŨ của app không có cờ này — chạy `sync_core.py` của bản đích với `--root <app>`
  (mục này ở CHANGELOG của template, "Việc phải làm tay").

## Hai danh sách tên debug (`tools/release/debug_symbols.txt` + `AppHost/Config/debug_symbols.app.txt`)

Có HAI file cùng định dạng, đọc HỢP: `tools/release/debug_symbols.txt` giữ tên của lõi (template sở hữu, app không sửa),
`AppHost/Config/debug_symbols.app.txt` giữ tên của app (app sở hữu; vắng file = rỗng). Một tên có ở cả hai ⇒ lỗi. Mỗi file
có hai mục:

- `[binary]` — tên TYPE khai trong `#if INTERNAL`. Metadata reflection giữ tên type trong binary ⇒
  `verify_release_clean.sh` cổng 1 grep mọi Mach-O của `.app` Release (thấy ⇒ FAIL), và selfcheck bước 8b chạy
  `verify_release_clean.sh --expect-debug-symbols` trên `.app` Internal: MỌI tên `[binary]` phải có mặt — tên không
  thấy (optimizer bỏ, gõ sai) là "mục vô tác dụng".
- `[source-only]` — tên HÀM/BIẾN nguy hiểm (lối bật Pro, đặt tay hạn mức), ghim bằng marker `// debug-symbol: required`
  NGAY dòng trên khai báo trong `#if INTERNAL`. Tên hàm bị strip khỏi binary (đo được: không có cả ở Internal) nên
  không soi binary; chỗ dựa là `#if INTERNAL` + lint.
- Một type `[binary]` chỉ được code debug KHÁC gọi (vd `InternalLogText`) có thể bị dead-strip khỏi một bản Release
  làm rò nó, nên grep binary không thấy — với những tên đó chỗ gác thật là lint nguồn (cổng 1b).
- `tools/release/lint_debug_symbols.py` (selfcheck bước 1, pre-commit, cổng 1b): type INTERNAL-only phải ở `[binary]`,
  hàm/biến có marker ở `[source-only]`, tên sai mục/mồ côi/khai ngoài vùng INTERNAL là lỗi, comment có chữ
  `debug-symbol` mà không đúng nguyên văn marker là lỗi. Luật chặt: type lồng trong type INTERNAL cũng phải khai.

## Giới hạn và chốt chặn đáng biết

- **Chẩn đoán của form phản hồi** (`DiagnosticsSnapshot`): extra do app thêm có nhãn ≤ 64 byte UTF-8 (dài hơn ⇒ bị
  loại), giá trị cắt còn ≤ 500 byte, phần đầu (dòng lõi + extra) ≤ 3000 byte — extra không còn chỗ bị loại; đuôi log
  ≤ 11 000 byte; toàn bộ ≤ `FeedbackDraft.maxDiagnosticsLength` = 12 000 byte. Dòng lõi: app version, build, device
  model, iOS version, locale, free storage (câu quyền riêng tư của form sinh từ chúng — `7D9E.1` của privacy manifest
  đòi dung lượng hiện rõ trong báo lỗi).
- **`StorageOtherData.purge`** từ chối thư mục BẰNG hoặc là TỔ TIÊN của một gốc bảo vệ (`defaultProtectedRoots`: home,
  Documents, Library, Application Support, Caches, Library/Preferences) — truyền nhầm một trong số đó là mỗi lần mở
  app xoá sạch dữ liệu. Thư mục con của chúng vẫn được phép (`tmp/` là con của home). `protectedRoots` của nơi gọi chỉ
  THÊM gốc (luôn hợp với danh sách mặc định — `[]` không tắt được chốt chặn); so đường dẫn sau khi chuẩn hoá (giải
  `..`/symlink) và bỏ `/private` ở đầu (gốc chưa tồn tại trên đĩa vẫn khớp); kiểm và liệt kê cùng một URL đã chuẩn hoá.

## Ba config build

| Config | Cờ Swift | Bundle id | Tối ưu | Dùng cho |
|---|---|---|---|---|
| `Debug` | `DEBUG INTERNAL` (+ `FEATURE_*` đang bật) | internal | không | test, compile-check, chụp ảnh |
| `Internal` | `INTERNAL` (+ `FEATURE_*`) | internal | như Release | build device hằng ngày |
| `Release` | (`FEATURE_*` đang bật) | Store | có | archive App Store |

Plist Firebase chọn theo config ở **build** (post-build script trong `project.yml`): Release nhận bản Prod, còn lại
bản Dev; thiếu file ⇒ Debug cảnh báo, Internal/Release lỗi.

## Invariant (cổng nào gác)

1. Không literal định danh ngoài `app.config.toml`/xcconfig/`docs/` — `tools/common/lint_identity.py`.
2. File sinh ra (xcconfig, Features.generated.yml, Entitlements.generated.yml + AppHost.entitlements, privacy manifest) khớp config — `appconfig.py check` (pre-commit, `run_tests.py`,
   `verify_release_clean.sh`).
3. Bản Release sạch — `tools/release/verify_release_clean.sh` (bảng cổng ở `tools/release/README.md`): không tên
   `[binary]` nào, bundle id + tên + version đúng cấu hình, Firebase prod, privacy manifest, iPad, What's New đóng dấu,
   String Catalog, không `*.storekit` trong `.app` (luôn kiểm) và paywall bật ⇒ có `ProductIDs` + `WebHost` (cổng 13). Cổng phải
   TỪ CHỐI bản Internal và bản Internal phải chứa mọi tên `[binary]` — `tools/template/selfcheck.sh`. Đã chứng minh
   trên archive thật (`docs/lessons-learned/cong-symbol-debug-chi-thay-symbol-duoc-link.md`).
4. Test chỉ ở Debug, không bao giờ Release/`AppHost-Store` — scheme `AppHost-Store` không có action test + hook `guard_test_config`.
5. Chuỗi UI localize được, chuỗi debug không localize — `tools/i18n/lint_localizable.py`.
6. Firebase không import lẻ ngoài facade — `tools/telemetry/lint_firebase_imports.py`.
7. Harness hợp lệ — `tools/factory/lint_harness.py`.
8. Biên lõi — target `CoreOnly`, `lint_feature_flag.py` (mục "Quy tắc biên").
9. Id sản phẩm của `Products.storekit` (file của APP) khớp `[purchases] product_ids` — `tools/release/check_storekit.py`.
10. Template đạt ở tổ hợp bật hết (mặc định) VÀ tắt hết, và dưới định danh khác — các script chỉ-template trong
    selfcheck đầy đủ của repo template (`feature_matrix_check.sh` và `new_app_check.sh` của template — chạy trên app
    sinh ra bằng lệnh tạo app).
11. Biên của tính năng mẫu (khi còn) — dấu `sample:` hợp lệ, không dấu vết mẫu ngoài khối/trong `Core/`, tài liệu gieo
    sạch: `remove_sample.py --check`; gỡ mẫu để lại app build + test + cổng ra bản qua: `sample_removal_check.sh` của
    template; bản Store không còn mẫu: cổng 14 (mục "Tính năng mẫu và khối đánh dấu").
12. Kiểu seed/store giả chỉ biên dịch cho Simulator — `tools/release/lint_preview_code.py`.
13. Mọi file có đúng một lớp sở hữu, file đồng bộ/gieo không trỏ tới file chỉ-template — `tools/template/manifest.py check`
    (ở template).
14. Ở app, file lớp đồng bộ khớp `core.lock` từng byte, không có file mới trong thư mục do template sở hữu —
    `tools/template/sync_core.py check` (pre-commit khối 0, cổng 15, selfcheck bước 1). Template chứng minh cả vòng đời này
    trên một app thật (tạo, đồng bộ lên tag thử, sửa tay bị chặn) bằng `new_app_check.sh` của template.
15. Ghi lên App Store Connect chỉ qua `aso.py apply` có mã plan đã duyệt + hộp Allow/Deny — hook `guard_asc` (dây bẫy, không phải
    sandbox: mục "Cửa hàng, ASO và số liệu"). `store/` còn chữ giữ chỗ (cả `store/review/notes.txt`) hay URL trỏ host giữ chỗ/dành
    riêng không lint qua được — `aso.py lint`. `new_app_check.sh` của template chứng minh trên app sinh ra: lint đỏ ở khung → điền chữ thử ⇒ xanh → plan ngoại tuyến ra plan; test `tools/analytics` xanh.
16. Privacy manifest khớp công tắc (khối bật có đủ kiểu, khối tắt không còn kiểu nào) và entitlement associated-domains khớp
    `web.host_prod` — cổng 7 và cổng 10 của `verify_release_clean.sh` trên `.app` thật.
17. Site của app (khi có `web.host_prod`): đủ trang bất biến `/`, `/privacy/`, `/terms/`, `/support/`, không chữ giữ chỗ, privacy khớp
    công tắc — `web/tools/check_site.py` (pre-commit; `--release` ở cổng 16 của `verify_release_clean.sh` và `npm run deploy:prod`);
    sitemap đủ + `lastmod` kịp — `web/tools/check_sitemap.py` (pre-commit `--staged`, deploy prod); deploy không đi với biến chỉ-test,
    và (khi có API — `web_api`) không đi với D1 id/App Check/`ASSN_ENVIRONMENTS` còn thiếu — `web/scripts/predeploy.mjs`; app có
    `web.host_prod` mà không có `web/site/public/` thì cổng 16 FAIL, trừ khi khai `[web] external_site = true` (SKIP thấy rõ). `new_app_check.sh` của template chạy hai công cụ site +
    `appconfig.py check` trên app bật hết và app tắt hết.

## Theme và ngôn ngữ của app

`Core/` không còn file nào phải sửa theo app:

- **Theme**: app khai theme ở `AppHost/AppHost/AppTheme.swift` (lớp gieo) — `static let theme: DSTheme = .standard` hoặc
  `.standard.withAccent(hex: 0xRRGGBB)`; `AppHostApp.init` gọi `DSTheme.install` đúng một lần, `DSColor` đọc qua khe đó.
  `withAccent` chỉ đổi `accent`/`accentDark`/`onAccent` (chữ trên nền nhấn tự chọn sáng/tối theo độ tương phản); ba màu
  biểu đồ `chartSeries1…3` và các màu còn lại giữ như `.standard` trừ khi app tự đặt (`var t = DSTheme.standard;
  t.palette.chartSeries1 = …`).
- **Ngôn ngữ**: `AppLanguage.available()` lấy từ `Bundle.main.localizations` (các `.lproj` thật có trong app) — thêm bản
  dịch là ngôn ngữ tự hiện trong Settings. `[i18n] languages` của `app.config.toml` chỉ phục vụ `verify_catalog.py`.

## Cửa hàng, ASO và số liệu

**`store/` — nguồn sự thật metadata App Store (lớp gieo, của app).** `store/metadata/` đúng bố cục `asc metadata pull`:
`app-info/<locale>.json` (`name`, `subtitle`, `privacyPolicyUrl`) và `version/<version>/<locale>.json` (`description`, `keywords`,
`promotionalText`, `whatsNew`, `supportUrl`, `marketingUrl`); mỗi locale của `[store] locales` một file. `new_app` sinh KHUNG: `name`
= tên hiển thị, `subtitle` rỗng, URL theo `web.host_prod`, mọi ô chữ phải tự viết chứa `TEMPLATE-PLACEHOLDER` — `aso.py lint` cố ý đỏ
cho tới khi thay hết (cổng chặn đẩy khung rỗng lên App Store Connect). `store/lint.toml` (chữ cấm của app), `store/review/notes.txt`
(notes cho Apple Review, ≤ 384 ký tự; công cụ không đọc/ghi, người dán tay). Chi tiết giới hạn và quy trình: `store/README.md`. Ảnh, video,
Custom Product Page, quảng cáo chưa thuộc template.

**`tools/aso/aso.py` — mọi thao tác với App Store Connect.** `lint` (giới hạn ký tự/byte, chữ giữ chỗ, chữ cấm, URL theo host — host
giữ chỗ/dành riêng và `privacyPolicyUrl`/`supportUrl` lệch `host_prod` là lỗi —, notes Apple Review, thiếu thư mục version đang soi, audit
từ khoá; chạy được không cần app record) · `plan` (so `store/` với App Store Connect, in bản xác nhận + mã plan 8 hex — gồm App Store id
của app —, lưu `<state>/aso/plans/<mã>.json`) · `apply --plan <file> --expect <mã>` (LỐI GHI DUY NHẤT: kiểm lại mã từ nội dung file,
từ chối plan của app khác, kiểm App Store Connect chưa đổi từ lúc plan, chụp snapshot trước, kiểm lại sau) · `restore --snapshot <thư mục>` (chỉ TẠO plan đưa về snapshot) ·
`snapshot`, `pull`, `import [--force-over-skeleton]`, `pull-version` · `build` (archive + export `.ipa` + cổng, ghi `build.json`, không gọi App
Store Connect; chỉ chạy ở nhánh `main` có tag `v<marketing>`, cây sạch) · `release-plan --build-json <file>` (plan upload build + tạo
version + gắn build, đi cùng cổng duyệt như plan metadata). `--version` mặc định `[version] marketing`. `asc` là binary ngoài PATH:
`bash tools/aso/install_asc.sh` tải bản ghim (`ASC_VERSION` + `ASC_SHA256`) vào `$IOS_APP_FACTORY_BIN/asc/<phiên bản>/asc` — tải mạng,
hỏi user trước. Mọi lời gọi `asc` trừ `apply` chạy với `ASC_READ_ONLY=1` và qua allowlist (`policy.py`). Khoá App Store Connect nằm ngoài
repo: `asc-listing.json` (`key_id`, `issuer_id`) ở thư mục cấu hình theo slug (`$ASO_CONFIG` ghi đè) + file `.p8` (`$ASC_KEY_FILE` hoặc
`~/.appstoreconnect/private_keys/AuthKey_<key_id>.p8`); không đọc/in chúng. Kiểm không cần App Store Connect: `aso.py` nhận cờ ẩn
`--offline-fixture <thư mục>` TRƯỚC lệnh con chỉ-đọc (`asc` không chạy, phản hồi đọc từ `<thư mục>/<khoá>.json`;
`tools/aso/fixtures/app-moi/` là App Store Connect của một app chưa có metadata) — không dùng được với `apply`. Quy trình cho agent:
skill `release-aso`; ra bản: `docs/RELEASE.md`.

**Hook `guard_asc` (`.claude/hooks/guard_asc.py`, đăng ký ở `.claude/settings.json` giữa `guard_test_config` và `guard_autonomy`).**
`apply` đúng dạng chuẩn ⇒ hộp Allow/Deny với mã plan TÍNH LẠI từ file (lệch `--expect` ⇒ chặn); `asc` gọi trực tiếp, API App Store
Connect, file khoá, thư mục cài `asc`, lệnh chạy code đụng `tools/aso` không đúng dạng chuẩn ⇒ chặn kèm lệnh chuẩn thay thế; lỗi nội bộ
mà lệnh có dấu hiệu App Store Connect ⇒ chặn (fail-closed). Cũng chặn cả việc ĐẶT khoá git chạy được lệnh, trong đó
`git config core.hooksPath …` — đó là việc của người dùng. **Mô hình đe doạ — nói thẳng:** hook là DÂY BẪY chống ghi nhầm hoặc do
agent tự làm, KHÔNG phải sandbox shell. Hàng rào cấu trúc là (a) `asc` ngoài PATH, (b) `ASC_READ_ONLY=1` ở mọi lời gọi không phải `apply`,
(c) vai trò của khoá App Store Connect; hook chỉ thấy văn bản MỘT lệnh Bash nên không thấy tên ghép lúc chạy, code đã nằm sẵn trong file,
cấu hình đã nằm sẵn trong `.git/config`… (danh sách đủ: docstring của `tools/aso/policy.py`). Chặn nhầm đã biết: thân heredoc của
`git commit -F -`, `grep … asc`, `ORDER BY x ASC`… có chữ `asc` — ghi message ra file rồi `git commit -F <file>`, tìm bằng công cụ Grep.
Cổng con người (kind `asc`): `.claude/skills/factory/autonomy.md`.

**`tools/analytics` — kéo số, ghi ra thư mục ngoài repo.** `asc_pull.py` (báo cáo bán hàng App Store Connect), `ga4_pull.py` (GA4 Data API),
`crash_pull.py` (Crashlytics qua BigQuery), `retention.py`, `crash_watch.py` (danh sách issue theo dõi), `digest.py` (`insights.json` +
`report.md`). Đầu ra ở `$ANALYTICS_OUT` (mặc định `<repo>/.temp/analytics`; mỗi lệnh kéo nhận thêm `--out`). Cấu hình: `asc.json`
(`key_id`, `issuer_id`, `vendor_number`) ở `$ASC_CONFIG` hoặc thư mục cấu hình theo slug; service account `$GA4_KEY_FILE` hoặc
`analytics-reader.json` ở thư mục cấu hình; property `$GA4_PROPERTY_ID` > `[analytics] ga4_property`; project/dataset BigQuery
`$GA4_BQ_PROJECT` > `[analytics] bq_project`, `$GA4_BQ_DATASET` (mặc định `analytics_<property>`), `$GA4_BQ_LOCATION`; danh sách issue
theo dõi `$CRASH_WATCH_FILE`, không đặt thì `<gốc app>/tools/app/crash_watch.json` nếu có (file của app, ngoài lớp đồng bộ), không thì
`tools/analytics/crash_watch.json` (lõi, rỗng). Gói Python (`requirements.txt`: PyJWT, cryptography,
requests, google-auth) chỉ nhập TRONG hàm — thiếu gói ⇒ một dòng `FAIL: cần cài: …` rc 2 và test vẫn xanh; cài gói là việc user đồng ý.
Mọi từ chối là một dòng `FAIL:` rc 2. `subs_pull.py` (sự kiện đăng ký từ App Store Server Notifications) và `web_pull.py` (số web +
feedback đang mở) đọc qua API admin của `web/` (`https://<host_prod>/api/v1/admin/…`, token ở `$WEB_ADMIN_TOKEN_FILE` hoặc
`web-admin-token` trong thư mục cấu hình; thiếu ⇒ `missing` trong digest, không lỗi). Chưa có ở template: kéo số quảng cáo, người
dùng dùng thử.

**Universal Link.** Khi `[web] host_prod` có giá trị: `appconfig.py render` sinh `Config/Entitlements.generated.yml` (project.yml
`include`) mang `com.apple.developer.associated-domains = applinks:$(APP_WEB_HOST)` — Debug/Internal theo `host_dev`, Release theo
`host_prod` — và ghi `AppHost.entitlements` đúng byte XcodeGen ghi (host rỗng ⇒ không có khoá). `AppLinkRouter` (`Core/Shell`) tách URL
`https://<host>/…` thành `AppLink` (path + query; host khác `AppConfig.webHost` ⇒ bỏ) rồi giao qua `WhatsNewPresenter.routeIncomingLink`
(đang mở What's New thì chờ đóng; link mới nhất thắng); `AppHostApp` nhận bằng `.onOpenURL` + `.onContinueUserActivity` và
`AppShellView` đưa tới `AppLinkActions.perform`, nơi app thêm đích (mẫu: `/items`). Cổng 10 của `verify_release_clean.sh` đọc entitlement của
`.app` đã ký: có host ⇒ đúng một mục `applinks:<host_prod>`, không mục nào mang host dev; không host ⇒ không được có khoá. Tệp
`apple-app-site-association` do Worker của `web/site` phục vụ (mục "Web"): link chỉ mở app sau khi site đã deploy, và App ID phải bật
Associated Domains (checklist việc tay của app).

## Web (`web/`)

Chi tiết lệnh, route, deploy: `web/README.md`. Monorepo npm (`api/` + `site/`) trên Cloudflare Workers; test chạy cục bộ (vitest +
Miniflare, D1 cục bộ, không mạng, không tài khoản).

- **Cấu hình một nguồn.** `appconfig.py render` sinh `web/api/wrangler.jsonc` + `web/site/wrangler.jsonc` (chỉ khi `web.host_prod` có
  giá trị) từ `app.config.toml`: tên Worker `<slug>-api|site` (+ `-dev`), D1 `<slug>`/`<slug>-dev` (`[cloudflare] d1_*`, rỗng ⇒
  `TODO-d1-id`), vars API (`ASSN_BUNDLE_ID` = bundle Store ở CẢ HAI môi trường — Apple gửi thông báo, kể cả Sandbox về dev, theo
  bản ghi App Store Connect của bản Store; `ASSN_ENVIRONMENTS` Production/Sandbox; App Check `[firebase]
  app_check_*`; `APP_CHECK_REQUIRED` 1/0), AASA (`APP_IDS` = `<team>.<bundle>`, bundle Store ở prod, Internal ở dev, `APP_PATHS` từ `[web] app_paths`), route dev, service
  binding `API` của site CHỈ khi `features.web_api`. `appconfig.py check` báo file lệch (FAIL) và việc tay còn thiếu (WARN, rc 0).
- **Site luôn có, API tuỳ chọn.** Site = trang tĩnh `public/` + Worker nhỏ (AASA theo môi trường, `X-Robots-Tag: noindex` ở dev,
  `/api/*` → API khi có binding, không thì 404 `no_api`). Không `web_api` ⇒ site vẫn deploy một mình.
- **Lớp sở hữu.** Mã (`api/**`, `site/src|test`, `tools/`, `scripts/`, package/lock/tsconfig, `site/public/m.js`) là đồng bộ; trang
  `site/public/**` + `site/releases.json` là gieo — `new_app` dựng từ thư mục gieo của template (thay `$display_name`, `$host_prod`,
  `$support_email`…, escape HTML; cắt khối `<!-- feature:<x>:begin|end -->` theo `[features]` + `app_store`) — rồi thuộc app; hai
  `wrangler.jsonc` là file sinh. App cũ nhận `web/` bằng `sync_core.py sync --to <tag> --adopt-new-seed` — **chạy `sync_core.py` CỦA
  TAG ĐÍCH (`--root <app>`), không phải bản chép cũ trong app** (tool `v0.5.0` không cắt khối, chép `wrangler.jsonc` của template): trang được tạo như new_app
  (biến + cắt khối theo cấu hình CỦA APP), hai `wrangler.jsonc` được dựng bằng `appconfig.generated_files` của cây mới trên cấu hình
  của app (không lấy bản sinh của template).
- **Cổng.** `check_site.py` (trang bất biến, chữ giữ chỗ, privacy ⇔ công tắc, `m.js` ⇔ `web_api`) và `check_sitemap.py` ở pre-commit;
  `check_site.py --release` ở cổng 16 của `verify_release_clean.sh` (bản Store) và `npm run deploy:prod`; `predeploy.mjs` trước mọi
  deploy; selfcheck: unit test `web/tools` mọi lúc, `npm ci && npm test && npm run typecheck` ở bản đầy đủ (Node ≥ 22.12).
- **`web_api` tắt ⇒ không có API** (Ruling 11): site không có binding, `npm run deploy:*` chỉ deploy site, không cần D1/App Check,
  `appconfig.py check` không cảnh báo D1, `subs_pull`/`web_pull` ghi `missing` (không gọi mạng). File `web/api/wrangler.jsonc` vẫn sinh
  (mã api là lớp đồng bộ) nhưng không dùng. App bật paywall muốn nhận App Store Server Notifications thì bật `web_api`.
- **Site ngoài repo**: `[web] external_site = true` ⇒ cổng 16 in `SKIP (web.external_site)`; mặc định false ⇒ có host mà thiếu
  `web/site/public/` là FAIL (không bao giờ im lặng thành OK).
- **Deploy là cổng user** (tài khoản Cloudflare): migration trước API, API (nếu có) trước site, dev trước prod, web prod trước bản app cần nó
  (`docs/RELEASE.md`).

## Chưa có

Trang admin web, ảnh/video/Custom Product Page, quảng cáo và việc thử thật với App Store Connect (chưa từng chạy `asc` thật, chưa có
app record) chưa có trong template; `web/` chưa từng deploy thật (Universal Link trên thiết bị, App Store Server Notification thật chưa
thử) — khi về, mục tương ứng được thêm vào doc này.
