# Quy ước chung (template)

File này thuộc lớp đồng bộ của template — giống hệt ở mọi app, app không sửa tại chỗ (bản mới về bằng lệnh đồng bộ lõi;
quy ước chung cần đổi thì đổi ở repo template). Quy ước riêng của một app viết ở `.claude/rules/conventions.app.md`.

- **Định danh app chỉ ở `app.config.toml`** — tên hiển thị (Store + Internal), slug, bundle id (Store +
  internal), team, version, cờ tính năng, ngôn ngữ. Sửa xong chạy `python3 tools/common/appconfig.py render` để
  sinh lại `AppHost/Config/Identity.xcconfig` (file sinh ra, commit cùng). Pre-commit và `tools/dev/run_tests.py`
  từ chối xcconfig cũ. Không viết literal định danh ở Swift/plist/script: tool đọc qua `tools/common/appconfig.py`
  (`get <khoá>`, hằng bố cục `PROJ_DIR`, `SCHEME`…). `python3 tools/common/lint_identity.py` gác (pre-commit chạy).
- **Sửa `AppHost/project.yml`, KHÔNG sửa `.xcodeproj`** — chạy `xcodegen generate` trong `AppHost/` sau khi
  thêm/xoá file (skill `add-source-file`). `.xcodeproj` bị `.gitignore`. Key Info.plist, signing, file
  XcodeGen không tự nhận (`.xcprivacy`) đều khai trong `project.yml` (`docs/lessons-learned/`). File `.cpp`
  perf-critical: source entry riêng với `compilerFlags: "-O2"`, đồng thời loại file đó khỏi glob `- path: AppHost`
  bằng `excludes:` (không thì file bị liệt kê hai lần — skill `add-source-file`).
- **Tên cố định, trung tính cho mọi app**: thư mục `AppHost/`, target `AppHost`/`AppHostTests`/`AppHostUITests`,
  scheme `AppHost` (Run = Internal, Test = Debug, Archive = Release), `AppHost-UIShots`, `AppHost-Store`. Ba config:
  `Debug` (test/compile-check, cờ `DEBUG INTERNAL`, bundle id internal), `Internal` (build device hằng ngày, tối ưu
  như Release, cờ `INTERNAL`, bundle id internal), `Release` (bản App Store, không cờ, bundle id Store).
- **Code debug MỚI phải nằm trong `#if INTERNAL`** — bản App Store (config `Release`) không có cờ này. Call site
  không tự viết `#if`: wrapper và màn debug của APP nằm ở `AppHost/AppHost/Internal/AppInternalEntry.swift` — chỗ DUY
  NHẤT trong app viết `#if INTERNAL` (thêm wrapper mới ở đó, không sửa `Core/`). Lõi chỉ cấp `dtext`, `internalBadge()`,
  `InternalBuild.isEnabled`, `InternalLongPressSheet`, `InternalLaunch` và màn debug chung của chính nó. Type debug mới ⇒ thêm tên vào mục `[binary]` của
  `AppHost/Config/debug_symbols.app.txt` (danh sách của APP; tên của lõi ở `tools/release/debug_symbols.txt`, template sở
  hữu — app không sửa; cổng đọc hợp hai file, tên trùng giữa hai file là lỗi); hàm/biến nguy hiểm (lối bật Pro, đặt tay hạn mức) ⇒ marker
  `// debug-symbol: required` NGAY dòng trên khai báo + tên vào mục `[source-only]` (tên hàm bị strip khỏi binary,
  chỉ ghim được ở nguồn). `python3 tools/release/lint_debug_symbols.py` kiểm (pre-commit, selfcheck); kiểm binary
  bằng `./tools/release/verify_release_clean.sh <app|archive>`. Cổng chỉ thấy symbol THẬT được link: type không ai
  dùng bị dead-strip khỏi Release nên cổng không thấy — muốn chứng minh cổng gác một type thì phép phá phải bỏ
  `#if INTERNAL` ở CẢ type lẫn một chỗ dùng nó; mọi tên `[binary]` phải có trong `.app` Internal (selfcheck đối
  chứng dương) (`docs/lessons-learned/cong-symbol-debug-chi-thay-symbol-duoc-link.md`).
  **Chuỗi debug KHÔNG được localize** — mọi text chỉ hiện ở build INTERNAL đi qua `dtext("...")`
  (= `Text(verbatim:)`), chuỗi thô nếu là `String`. Lý do: Xcode chỉ extract cái nó COMPILE được, nên chuỗi debug
  là `LocalizedStringKey` làm `Localizable.xcstrings` phồng/teo theo config build cuối và có ngày lỡ ship chuỗi
  debug lên App Store. Áp dụng y hệt cho `#Preview`: dùng `Text(verbatim:)`.
- **Test CHỈ chạy ở `Debug`, KHÔNG BAO GIỜ ở `Release`/scheme `AppHost-Store`** (template không có đường test ở
  `Internal` — `Internal` là config chạy app trên device hằng ngày, không phải để test) — Release mang bundle id
  Store → app host đụng StoreKit sandbox thật → hộp thoại "Sign in to Apple Account" treo test. Scheme
  `AppHost-Store` không có action test; hook `.claude/hooks/guard_test_config.py` chặn lệnh `xcodebuild
  test|build-for-testing|test-without-building` ở Release/`-Store`
  (`docs/lessons-learned/test-o-release-treo-vi-storekit.md`).
- **Sửa `Core/`** (lõi giống hệt ở mọi app — lớp đồng bộ, sửa ở repo template rồi đồng bộ về; phần riêng của app đi vào
  qua khe ở `AppHost/`: theme ở `AppHost/AppHost/AppTheme.swift`, ngôn ngữ từ `Bundle.main.localizations` —
  `docs/ARCHITECTURE.md` §"Quy tắc biên", §"Theme và ngôn ngữ của app"):
  - KHÔNG nhắc kiểu, chuỗi hay khái niệm của một app cụ thể; phần riêng của app đi vào qua `init`/protocol/generic/
    closure. `Core/` không tham chiếu `AppHost/` hay `CoreOptional/` — target `CoreOnly` phải build (selfcheck 4b).
  - KHÔNG `#if` theo tính năng trong `Core/`/`CoreTests/`: chỉ `#if INTERNAL`, `#if DEBUG`,
    `#if targetEnvironment(simulator)`, `WHATSNEW_ALLOW_UNRELEASED`. Công tắc đọc lúc chạy qua
    `AppConfig.current.features` — `tools/common/lint_feature_flag.py` gác.
  - Type debug phải khai (`debug_symbols.txt` của lõi / `debug_symbols.app.txt` của app, mục trên); không `public`; không `@EnvironmentObject` cho đối tượng
    nghiệp vụ; `import Firebase*` chỉ ở `Core/Telemetry/FirebaseSink.swift`.
  - Test đi cùng: mỗi file logic có test ở `CoreTests/<Khối>/`, không phụ thuộc giá trị cấu hình thật của template
    (dựng `AppConfig(info:)`/fixture riêng) — ở repo template, selfcheck đầy đủ chạy lại `run_tests.py --full` ở tổ hợp
    tắt hết và dưới định danh khác. Test mới bảo vệ bất biến phải qua "phá code → đỏ" (`tools/factory/mutate.py`).
  - **Pre-commit khối 1c**: commit đụng `.swift`/`debug_symbols.txt`/`debug_symbols.app.txt` bị TỪ CHỐI khi còn file `.swift` (dưới `Core`,
    `CoreOptional`, `AppHost/AppHost`) hoặc một trong hai danh sách thay đổi CHƯA stage/chưa add — lint đọc working tree
    nên phải `git add` đủ file Swift của việc mình trước khi commit (đừng `--no-verify`).
- **Công tắc tính năng (`[features]` của `app.config.toml`: `paywall`, `apple_ads`, `web_api`)**: sửa cờ ⇒
  `appconfig.py render` (sinh lại `Identity.xcconfig` + `Features.generated.yml` + `PrivacyInfo.xcprivacy` — sửa khai báo ở mẫu `AppHost/Config/PrivacyInfo.template.xcprivacy`, commit cùng) ⇒ `xcodegen generate`.
  Cờ `FEATURE_*` (khối tuỳ chọn biên dịch có điều kiện) CHỈ dùng trong `AppHost/`; `Core/` đọc cờ lúc chạy. Paywall tắt
  = app miễn phí hoàn toàn (không chạm StoreKit, mọi `ProFeature` mở). Khối tuỳ chọn mới: các bước ở
  `docs/ARCHITECTURE.md` §"Khối tuỳ chọn". Template mặc định BẬT HẾT; ở repo template, `feature_matrix_check.sh` của
  template (selfcheck đầy đủ) chứng minh tổ hợp TẮT HẾT vẫn build, test, qua cổng ra bản.
- **File lớp đồng bộ KHÔNG sửa ở app.** Mỗi file track thuộc một trong ba lớp ở `template.manifest.toml` (đồng bộ / gieo một
  lần / chỉ-template — `docs/ARCHITECTURE.md` §"Ba lớp sở hữu, `core.lock`, đồng bộ"). Ở app, file lớp đồng bộ được ghim
  bằng `core.lock`; sửa/xoá/thêm vào thư mục do template sở hữu thì pre-commit (khối 0) và cổng 15 của
  `verify_release_clean.sh` đỏ — không `--no-verify` để lách, không có lối "chấp nhận lệch". Cần đổi lõi ⇒ sửa ở repo template,
  gắn tag, rồi `python3 tools/template/sync_core.py sync --to <tag>` ở app (skill `sync-core`). Việc riêng của app đặt ở chỗ
  của app: `AppHost/…`, `tools/app/…`, `docs/lessons-learned/app/…`; agent/hook/workflow/skill riêng của app là file/thư mục
  MỚI trong `.claude/` (không trùng tên của template).
  Ở repo template: file mới PHẢI khai lớp trong `template.manifest.toml` (mục kết thúc `/` = cả thư mục, mục dài nhất thắng;
  harness khai từng file, skill khai từng thư mục) — `python3 tools/template/manifest.py check` đỏ khi thiếu (pre-commit, selfcheck).
  File lớp đồng bộ/gieo không nhắc đường dẫn của file chỉ-template (nói "`<tên>` của template"); phần chỉ đúng ở template của
  file lớp gieo đặt giữa `<!-- template:begin -->` … `<!-- template:end -->`.
- **Metadata App Store, ASO và số liệu** (`docs/ARCHITECTURE.md` §"Cửa hàng, ASO và số liệu"):
  - Nguồn sự thật metadata là `store/metadata/**` (+ `store/lint.toml`, `store/review/notes.txt`); sửa ở đó, commit git, rồi
    `python3 tools/aso/aso.py lint` → `plan` → người xác nhận → `apply` (skill `release-aso`). Mọi lệnh `aso.py` chạy từ gốc repo, MỘT
    lệnh đơn lẻ đúng dạng chuẩn. Ghi lên App Store Connect CHỈ qua `aso.py apply --plan <file> --expect <mã>` sau khi người
    duyệt bản xác nhận; hook `guard_asc` hỏi Allow/Deny ở mỗi `apply` và chặn mọi lối khác (gọi `asc` trực tiếp, API, file khoá, chạy
    module trong `tools/aso`, đặt khoá git chạy được lệnh). Hook là dây bẫy, không phải sandbox — không tìm cách lách.
  - Khung `store/` mới sinh còn chữ `TEMPLATE-PLACEHOLDER` ⇒ `aso.py lint` đỏ (cố ý). `apple.app_store_id` rỗng ⇒ lệnh cần App
    Store Connect từ chối; `lint` vẫn chạy.
  - Khoá và trạng thái nằm NGOÀI repo (`appconfig.state_dir`/`config_dir`, biến `IOS_APP_FACTORY_STATE|CONFIG|BIN`): không `cat`,
    không in, không commit `asc-listing.json`, `*.p8`, service account. Cài `asc` và gói Python của `tools/analytics` là tải từ mạng —
    hỏi người dùng trước.
  - Commit có message nhắc tới công cụ này mà bị hook chặn (heredoc, chữ `asc`): ghi message ra file rồi `git commit -F <file>`.
  - Số liệu: `tools/analytics` (skill `product-analytics`) kéo ra thư mục ngoài repo (`ANALYTICS_OUT`) rồi `digest.py`.
- **Compile-check nhanh không cần device**: build cho iOS Simulator (skill `compile-check`).
- **Plist Firebase**: `Internal`/`Release` lỗi build khi thiếu plist (cố ý), `Debug` chỉ cảnh báo. Template không
  chứa plist thật; build thử dùng plist giả `python3 tools/common/appconfig.py fixture-plist --out <thư mục>` +
  `FIREBASE_PLIST_DIR=<thư mục>` (như `tools/template/selfcheck.sh`).
- **Thang kiểm chứng — chạy ĐÚNG mức, không mặc định full suite mỗi lượt sửa.** Chất lượng vẫn đặt lên đầu:
  mức thấp dùng cho vòng lặp, mức cao là cổng BẮT BUỘC trước khi báo xong/merge.
  | Mức | Khi nào | Chạy gì |
  |---|---|---|
  | **L1 · vòng sửa** | mỗi lượt sửa code (theo feedback user, fix lỗi test, chỉnh UI) | `tools/dev/run_tests.py` (test liên quan tới file đổi + test mới; chạy lại cùng binary: `--no-build`). Đổi UI → thêm ảnh sim (skill `ui-preview-sim`) nếu cần nhìn. Đổi tooling Python → `python3 -m unittest discover -s tools/<thư mục> -p 'test_*.py'` |
  | **L2 · checkpoint** | xong một task/phase, TRƯỚC khi báo user "xong"/nhờ user test device, trước commit feature. Trong `/factory`: đúng MỘT lần, do verifier ở task "Tích hợp L2" — thợ/giám đốc không chạy lại | `tools/dev/run_tests.py --full` (song song nhiều clone sim, tự chạy lại nối tiếp test đỏ) + `python3 tools/i18n/lint_localizable.py` nếu đụng UI |
  | **L3 · merge** | trước merge vào `develop` / trước release | L2 + workflow `factory-review` + `verify_release_clean.sh` trước archive. Repo template: thêm `tools/template/selfcheck.sh` (bản đủ) |
  - L1 tự leo thang lên full khi đụng `project.yml`/`.xcstrings`/plist/`.metal`/`.cpp` (không map được test).
  - File nguồn mà script báo "không test nào nhắc tới" chỉ được compile-check ở L1 — nếu nó chứa logic (không
    phải View thuần) thì viết test hoặc chạy L2.
  - Nguyên tắc **"phá code → test PHẢI đỏ"** áp cho test MỚI bảo vệ bất biến — chứng minh bằng
    `tools/factory/mutate.py` (không `git stash`/`checkout`), chạy L1 (`-only-testing` đúng class), không cần full.
    Test xanh chưa chứng minh test có gác.
  - `run_tests.py` trả **rc=3 + `[false-green]`** khi xcodebuild báo thành công nhưng kết quả không đáng tin (0
    test, test chỉ định không chạy, tên test lệch nguồn, file test đã sửa mà chưa được biên dịch). rc=3 KHÔNG phải
    xanh. Cổng này không bắt được binary cũ khi tên test khớp, nên test mới vẫn phải qua "phá code → đỏ". Script
    gỡ app internal khỏi sim trước mỗi lần chạy (dữ liệu app trên sim đó mất)
    (`docs/lessons-learned/test-chay-binary-cu-va-rc3.md`).
  - Test mới KHÔNG được chậm: suite chạy ở Debug `-O0`, fixture phải nhỏ. Test > 2 s cần lý do.
  - Kỷ luật "có bằng chứng trước khi tuyên bố": trong vòng sửa và trong từng task của mission → L1; câu "đã
    xong/đã pass" gửi USER (cuối task/phase/feature) → L2. Quy ước này quy định MỨC, skill/verifier quy định KỶ LUẬT.
- **Nhà máy agent (`/factory`)** — mục tiêu nhiều bước: ledger `tools/factory/mission.py` (`.factory/missions/`),
  chỉ `factory-verifier` (hoặc giám đốc cho task không code) được đánh `verified`, kèm bằng chứng; hook Stop
  (`.claude/hooks/factory_stop_gate.py`) không cho phiên giám đốc dừng khi mission autopilot chưa đạt DoD (trừ khi
  có cổng mở/task blocked). Cổng con người (push develop/main, deploy prod, upload/App Store Connect, tiêu tiền,
  gửi tin, device) theo `.claude/skills/factory/autonomy.md`; hook `guard_autonomy` hỏi Allow/Deny ở mức lệnh
  shell. Agent nhà máy KHÔNG dùng `isolation: worktree` (rẽ từ nhánh mặc định, không phải HEAD;
  `tools/factory/lint_harness.py` cấm).
- **Workflow theo cỡ việc — không áp quy trình feature lên vòng sửa.**
  - *Feature/phase mới* (màn mới, khối lõi mới, thay đổi kiến trúc): chạy qua nhà máy (`/factory`, playbook
    `feature`): planner → critic → spec + plan (commit riêng) → thợ theo vai, `factory-verifier` kiểm từng task → L2
    → báo user.
  - *Vòng sửa* (user báo "mục 2 chưa khớp", chỉnh layout, đổi ngưỡng, bug nhỏ trong feature đang làm): sửa trực
    tiếp, L1 mỗi lượt, **không mở mission, không viết plan mới, không dispatch reviewer**; gom nhiều lượt rồi chạy
    L2 + commit một lần khi user xác nhận ổn (hoặc khi user bảo commit).
  - Thay đổi phạm vi giữa chừng lớn tới mức thành feature mới → quay lại nhánh "feature mới", hỏi user có cần plan
    không.
- **Mọi thay đổi UI phải đúng cho CẢ iPhone lẫn iPad.** Bố cục theo size class / bề rộng thật
  (`horizontalSizeClass`, `GeometryReader`), KHÔNG theo `userInterfaceIdiom`. Điều hướng cấp cao một nguồn: tab bar
  (compact) và sidebar (regular) cùng lặp một danh sách mục, nội dung bên trong dùng chung — không dựng song song.
  - Hộp xác nhận (xoá, huỷ, reset…) dùng `.alert`, KHÔNG dùng `.confirmationDialog`: từ iOS 26 nó hiện dạng
    popover neo vào view gắn modifier (thường là view gốc của màn) ⇒ trôi lung tung, mà đa số chỗ kích hoạt là
    swipe/context menu/toolbar nên không có nút nào để neo cho đúng.
  - **Cổng L2 cho thay đổi UI**: chụp màn đổi trên iPhone dọc VÀ iPad ngang bằng `tools/dev/ui_shots.py` (skill
    `ui-preview-sim`) rồi xem ảnh, trước khi báo xong/commit.
- **Commit trailer** — mọi commit kết thúc bằng `Co-Authored-By: Claude <model đang chạy> <noreply@anthropic.com>`,
  thêm `Claude-Session: <URL phiên>` CHỈ khi phiên có URL claude.ai/code thật (phiên local thuần → bỏ dòng này).
  Điền giá trị **của phiên đang chạy**, KHÔNG chép literal từ commit/ví dụ cũ. Chi tiết: skill `commit-convention`.
  Chỉ `git add` file của việc mình; kiểm nhánh trước commit.
- **Git hook phải bật**: người dùng chạy một lần `git config core.hooksPath .githooks` ở clone mới (lệnh tạo app đã đặt cho repo
  vừa tạo), nếu không `.githooks/pre-commit` không chạy. Agent KHÔNG tự đặt (hook `guard_asc` chặn lệnh đó) — nhờ người dùng. Hook gồm: (0) chỉ ở app — lõi không lệch `core.lock` (`sync_core.py check --staged`: dòng `M`/`D`/`A`, lock
  bị gỡ, thiếu tool của cổng); (1) luôn — `app.config.toml`, mẫu privacy và năm file sinh ra (xcconfig, `Features.generated.yml`,
  `Entitlements.generated.yml`, `AppHost.entitlements`, privacy manifest) phải đã stage, `appconfig.py check`, `lint_identity.py`;
  (1b) commit đụng `app.config.toml`/`Products.storekit` — `check_storekit.py`; (1c) commit đụng `.swift`/
  `debug_symbols.txt`/`debug_symbols.app.txt` — từ chối khi còn Swift/danh sách chưa stage, rồi `lint_debug_symbols.py`; (1d) chỉ ở template — `manifest.py check --staged` (mọi file có lớp); (2) commit
  đụng `.swift` — `lint_localizable.py`, `lint_firebase_imports.py`, `lint_feature_flag.py`; (3) commit đụng `.claude/`
  hoặc `tools/factory/` — `lint_harness.py` + unit test `tools/factory`. Không `--no-verify` để lách.
- **Docs & comment viết bằng tiếng Việt** — NHƯNG **chuỗi hiển thị cho user (UI) phải tiếng Anh** (String
  Catalog `AppHost/AppHost/Localizable.xcstrings`, source language `en`). Literal trực tiếp trong
  `Text("...")`/`Button("...")`/`.navigationTitle(...)`/... không cần bọc gì. Chuỗi đi qua biến/property/tham số
  kiểu `String` trước khi tới nơi hiển thị (computed property, enum `label`, helper `func row(_ text: String)`, ...)
  **BẮT BUỘC** bọc `String(localized: "...")` tại điểm viết literal, nếu không Xcode không extract được. Trước khi
  coi một màn UI xong: `python3 tools/i18n/lint_localizable.py` phải sạch (pre-commit chạy khi commit đụng
  `.swift`); lint bắt cả literal TRÔNG như localize mà không được extract (`Text("Details".uppercased())`,
  `Text("a " + "b")`).
- **`tools/i18n/verify_catalog.py` đang NGỦ** khi `app.config.toml` `[i18n] languages` chỉ có `en`: thiếu/thừa key
  trong catalog không đổi gì user thấy (fallback là chính literal tiếng Anh). KHÔNG chạy nó (`--check` lẫn
  `--write`) khi thêm/sửa chuỗi UI hay trong L1/L2/mission; `--check` tự in `SKIP` (cả trong
  `verify_release_clean.sh`). **Khi bắt đầu thêm ngôn ngữ**: `verify_catalog.py --write` một lần để đồng bộ catalog,
  rồi thêm ngôn ngữ vào `[i18n] languages` ⇒ cổng tự bật và chặn ship bản dịch nửa vời.
- **`web/` (site tĩnh + API tuỳ chọn, Cloudflare Workers — `web/README.md`)**:
  - Mọi định danh của web đọc từ `app.config.toml`; hai `web/*/wrangler.jsonc` là FILE SINH (`appconfig.py render`) — không
    sửa tay. Mã API, Worker site, `web/tools/`, `web/scripts/` là lớp đồng bộ; trang `web/site/public/**` và
    `web/site/releases.json` thuộc app.
  - **Sitemap viết tay — sửa trang là sửa `<lastmod>` cùng commit.** Đụng `web/site/public/**/index.html` ⇒ `<lastmod>` của
    trang đó trong `web/site/public/sitemap.xml` = hôm nay; thêm/xoá trang ⇒ thêm/xoá `<url>`. Cổng
    `web/tools/check_sitemap.py` chạy ở pre-commit (`--staged`) và trước `npm run deploy:prod` — không `--no-verify` để lách.
  - **Đường dẫn bất biến `/`, `/privacy/`, `/terms/`, `/support/` KHÔNG đổi** — app nướng cứng chúng
    (`Core/Bootstrap/AppConfig.swift`); `web/tools/check_site.py` (pre-commit, cổng 16 của `verify_release_clean.sh` với
    `--release`) bắt trang thiếu, chữ `TEMPLATE-PLACEHOLDER` còn sót, privacy lệch công tắc `[features]`.
  - **Deploy (dev lẫn prod), `wrangler login`, `d1 create`, `migrations apply --remote`, `secret put` là CỔNG USER** — agent
    không chạy. `npm run deploy:*` = `web/scripts/predeploy.mjs <env> --deploy`: deploy API CHỈ khi `features.web_api` (site có
    binding `API`; khi đó từ chối nếu D1 id / App Check / `ASSN_ENVIRONMENTS` còn thiếu), rồi site. `web_api` tắt ⇒ không có API.
  - Site ở ngoài repo ⇒ `[web] external_site = true` (cổng 16 in SKIP); mặc định có host mà thiếu `web/site/public/` ⇒ cổng 16 FAIL.
- **Firebase chỉ ở một chỗ**: không `import Firebase…` lẻ trong View/feature — `tools/telemetry/lint_firebase_imports.py`
  gác (pre-commit, selfcheck bước 1; bắt cả `@_exported`/`@testable import`, `import struct Firebase….X`, comment đuôi dòng). Facade telemetry: `Track.log(.<event>(...))` (`Core/Telemetry/`); ngoại lệ duy nhất là
  `CoreOptional/WebAPI/AppCheckTokenSource.swift` (`FirebaseAppCheck`).
- **Sau merge PR ⇒ `develop` local phải khớp `origin/develop`.** Hook PostToolUse
  `.claude/hooks/post_merge_sync_develop.py` tự chạy `tools/dev/sync_develop.py` sau mọi `gh pr merge` (chỉ
  fast-forward). Lệch nhánh/thay đổi chưa commit đụng file ⇒ `SYNC-DEVELOP FAIL`, báo user — không stash/reset.
  Merge bằng đường khác (nút app, web) ⇒ chạy tay script đó.
- **Git worktree location: LUÔN `.claude/worktrees/<name>`** — kể cả khi fallback tạo bằng `git worktree add`
  thuần. KHÔNG dùng `.worktrees/` ở gốc repo hay trong `AppHost/` — tạo "phantom state" mà harness không thấy/dọn
  được. Mỗi worktree có simulator riêng (`tools/dev/sim_pool.py`, hook `.claude/hooks/sim_gc.py` dọn).
- **Sửa `.claude/` ⇒ `python3 tools/factory/lint_harness.py`** (pre-commit tự chạy kèm unit test `tools/factory`).
  Agent/skill/hook/workflow mới chỉ có hiệu lực ở phiên MỚI (`docs/lessons-learned/sua-harness-can-phien-moi.md`).
