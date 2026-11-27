# CLAUDE.md

Hướng dẫn cho Claude Code khi làm việc trong repo này: một app iOS (SwiftUI) dựng từ template "xưởng app" —
vỏ app + máy móc build/test/release + harness agent, không chứa nghiệp vụ riêng.

Quy ước bắt buộc ở **hai file**: `.claude/rules/conventions.core.md` (chung, thuộc template — không sửa tại chỗ ở
app sinh ra) và `.claude/rules/conventions.app.md` (riêng app này: khuôn viết một tính năng, invariant nghiệp vụ). Đọc cả
hai trước khi sửa code.

## Lần đầu sau khi clone

```bash
git config core.hooksPath .githooks   # NGƯỜI chạy (bắt buộc ở mỗi clone mới; agent không tự đặt được — nhờ người dùng)
brew install xcodegen                 # nếu máy chưa có
```

## Cấu hình app

Mọi định danh (tên hiển thị Store + Internal, slug, bundle id Store + internal, team, version, cờ tính năng, ngôn
ngữ) nằm **duy nhất** ở `app.config.toml`. Sửa xong:

```bash
python3 tools/common/appconfig.py render   # sinh lại Identity.xcconfig + Features.generated.yml + PrivacyInfo.xcprivacy (từ AppHost/Config/PrivacyInfo.template.xcprivacy) — commit cùng
python3 tools/common/appconfig.py check    # rc 0 = file sinh ra khớp config
```

Pre-commit và `tools/dev/run_tests.py` từ chối xcconfig cũ. Tool đọc định danh qua `tools/common/appconfig.py`
(`get <khoá>`); `python3 tools/common/lint_identity.py` cấm literal định danh ở nơi khác. `render` còn sinh
`Entitlements.generated.yml` + `AppHost.entitlements` (associated-domains theo `[web] host_prod`; `project.yml` phải `include` fragment đó)
và — khi `[web] host_prod` có giá trị — hai `web/api|site/wrangler.jsonc` (Cloudflare; không sửa tay).
Khoá/trạng thái của công cụ nằm NGOÀI repo (`IOS_APP_FACTORY_STATE|CONFIG|BIN`; `appconfig.py state-dir <tool>` / `config-dir`).

## Metadata App Store và số liệu

- `store/metadata/**` là nguồn sự thật listing (khung mới sinh còn chữ `TEMPLATE-PLACEHOLDER` ⇒ `aso.py lint` đỏ cho tới khi viết chữ
  thật). Sửa → `python3 tools/aso/aso.py lint` → `plan` → người xác nhận → `apply` (skill `release-aso`; ra bản: `docs/RELEASE.md`).
  Ghi lên App Store Connect CHỈ qua `aso.py apply` — hook `guard_asc` hỏi Allow/Deny và chặn lối khác; mỗi lệnh `aso.py` chạy từ gốc
  repo, một lệnh đơn lẻ. Cần `apple.app_store_id` (app record tạo tay), `asc` (cài = tải mạng, hỏi người dùng) và khoá của người
  dùng ngoài repo (không đọc/in).
- `tools/analytics` (skill `product-analytics`) kéo số App Store Connect / GA4 / Crashlytics ra thư mục ngoài repo rồi `digest.py`.
- Privacy manifest SINH theo `[features]` từ `AppHost/Config/PrivacyInfo.template.xcprivacy` (sửa mẫu, không sửa file sinh).

## Web (`web/`)

Site tĩnh + API tuỳ chọn trên Cloudflare Workers — chi tiết `web/README.md`. `cd web && npm test && npm run typecheck` (không mạng;
`npm ci` lần đầu cần mạng, Node ≥ 22.12). Sửa trang `web/site/public/**` ⇒ sửa `<lastmod>` trong `sitemap.xml` cùng commit;
`python3 web/tools/check_site.py --release` phải xanh trước bản Store (cổng 16). Đường dẫn `/`, `/privacy/`, `/terms/`, `/support/`
không đổi (app nướng cứng). Deploy (`npm run deploy:dev|prod`, `wrangler login`, migration `--remote`, `secret put`) là cổng user.

## Build

```bash
cd AppHost
xcodegen generate          # sinh .xcodeproj từ project.yml (bắt buộc sau khi thêm/xoá file)
open AppHost.xcodeproj
```

Scheme `AppHost`: Run = `Internal`, Test = `Debug`, Archive = `Release`. Scheme `AppHost-Store` cho bản App
Store; `AppHost-UIShots` chỉ để chụp ảnh UI. Ba config:

- `Internal` — build device hằng ngày, có tool debug (`#if INTERNAL`), bundle id internal, cài song song bản Store.
- `Release` — bản App Store, không chứa code debug, bundle id Store.
- `Debug` — test/compile-check (không tối ưu, đừng đo hiệu năng ở đây).

`Internal`/`Release` lỗi build khi thiếu plist Firebase (cố ý); `Debug` chỉ cảnh báo. Template không chứa plist
thật — build thử: `python3 tools/common/appconfig.py fixture-plist --out <thư mục>` rồi truyền
`FIREBASE_PLIST_DIR=<thư mục>`. Skill `build-and-run`, `compile-check`.

## Thêm file nguồn

Luôn sửa `AppHost/project.yml` (không sửa `.xcodeproj`, nó bị `.gitignore`) rồi `xcodegen generate`. Key
Info.plist và file XcodeGen không tự nhận (`.xcprivacy`) khai trong `project.yml`. Code debug của APP (wrapper +
màn debug) đặt ở `AppHost/AppHost/Internal/AppInternalEntry.swift` — chỗ DUY NHẤT trong app viết `#if INTERNAL`;
không sửa `Core/` cho việc đó (lõi chỉ cấp `dtext`, `internalBadge`, `InternalLongPressSheet`, `InternalLaunch` và
màn debug chung của nó). Chuỗi debug qua `dtext(...)`, tên type debug thêm vào mục `[binary]` của
`AppHost/Config/debug_symbols.app.txt` — danh sách của app; `tools/release/debug_symbols.txt` là của lõi, không sửa (hàm nguy hiểm: marker `// debug-symbol: required` + mục `[source-only]`). Skill
`add-source-file`.

## Lõi `Core/` và công tắc tính năng

`Core/` (8 khối: Bootstrap, Design, Telemetry, Purchases, Engage, Support, Shell, Internal) giống hệt ở mọi app (lớp
đồng bộ — `template.manifest.toml`; ở app khoá bằng `core.lock`, không sửa tại chỗ): không nhắc kiểu của app, không `#if`
theo tính năng, target `CoreOnly` phải build. Phần riêng của app đi vào qua khe: theme ở `AppHost/AppHost/AppTheme.swift`
(`DSTheme`, `.standard.withAccent(hex:)`), ngôn ngữ lấy từ `Bundle.main.localizations` (`docs/ARCHITECTURE.md`
§"Theme và ngôn ngữ của app"). Khối tuỳ chọn ở `CoreOptional/`
(hiện `WebAPI/`) chỉ biên dịch khi `[features]` bật; cờ `FEATURE_*` chỉ dùng trong `AppHost/`. Quy tắc → mục "Sửa
`Core/`" và "Công tắc tính năng" của `.claude/rules/conventions.core.md`; sơ đồ khối, luồng cấu hình, trình tự khởi
động, cách thêm khối tuỳ chọn → `docs/ARCHITECTURE.md`.

**Sửa lõi / lên bản lõi mới**: file lớp đồng bộ KHÔNG sửa ở app — hook pre-commit (khối 0) chặn commit làm lệch `core.lock`
(dòng `M`/`D`/`A`) và cổng 15 của `verify_release_clean.sh` chặn bản ra. Cần đổi lõi: sửa ở repo template, gắn tag, rồi
`python3 tools/template/sync_core.py sync --to <tag>` ở app (skill `sync-core`). Không có lối "chấp nhận lệch". Việc riêng của app
đặt ở `AppHost/…`, `tools/app/…`, `docs/lessons-learned/app/…`, agent/skill mới trong `.claude/`.

## Test

```bash
tools/dev/run_tests.py           # L1 — chỉ test liên quan tới file đổi (so với develop)
tools/dev/run_tests.py --full    # L2 — cả suite, nhiều clone simulator song song
tools/dev/run_tests.py FooTests  # đúng class
tools/dev/run_tests.py --storekit  # LiveStoreClientTests (StoreKit thật) — scheme chính skip
tools/template/selfcheck.sh      # cổng tự kiểm: cấu hình, lint, test, cổng release (--quick bỏ simulator suite; bản đủ cần ≥ 10 GB đĩa)
python3 tools/template/sync_core.py check   # ở app: lõi khớp core.lock (hook + cổng 15 cũng chạy)
python3 tools/template/remove_sample.py --check   # khối `sample:` + tài liệu gieo (selfcheck + pre-commit chạy)
```

Test chỉ chạy ở `Debug` (bundle id internal) — không bao giờ `Release`/`AppHost-Store` (hook chặn). rc 3 +
`[false-green]` không phải xanh. Mỗi worktree có simulator riêng (`tools/dev/sim_pool.py`, dọn tự động). Khi nào
chạy mức nào → "Thang kiểm chứng" trong `.claude/rules/conventions.core.md`. Test tooling Python:
`python3 -m unittest discover -s tools/<thư mục> -p 'test_*.py'`.

## Kiến trúc & trạng thái

- Kiến trúc, bố cục repo, lớp sở hữu, invariant → `docs/ARCHITECTURE.md`.
- Trạng thái & roadmap → `docs/ROADMAP.md` (đọc trước).
- Bài học rút ra → `docs/lessons-learned/` (chung, từ template) và `docs/lessons-learned/app/` (riêng app này).
- Spec/plan của app → `docs/superpowers/`.

## Release

`main` = luôn khớp bản đã/sắp nộp App Store, chỉ tiến qua PR; `develop` = trunk hằng ngày. Quy trình
release/hotfix + version bump → `docs/RELEASE.md`, `tools/release/README.md`, `tools/release/bump_version.sh`.
Trước mỗi upload: `./tools/release/verify_release_clean.sh <archive>`.

## Harness

- **Nhà máy agent**: giao một mục tiêu bằng `/factory <mục tiêu>` — phiên chính làm giám đốc, ledger
  `tools/factory/mission.py` (`.factory/missions/`), 11 vai ở `.claude/agents/` (factory-planner, factory-critic,
  factory-verifier, factory-scribe, ios-engineer, platform-engineer, ui-reviewer, release-manager, researcher, data-analyst,
  growth-marketer), workflow `factory-execute|review|research|eval|weekly` ở `.claude/workflows/`. Bảng tự chủ (việc nào tự làm, việc nào
  là cổng user): `.claude/skills/factory/autonomy.md`.
- Skill ở `.claude/skills/`, hook ở `.claude/hooks/` (khai trong `.claude/settings.json`).
- Sửa `.claude/` ⇒ `python3 tools/factory/lint_harness.py` (pre-commit tự chạy). Thay đổi harness chỉ có hiệu lực
  ở phiên Claude Code MỚI.
- Chưa có trong template: trang admin web, ảnh/video/Custom Product Page, quảng cáo, và việc thử thật với App Store Connect / deploy
  Cloudflare thật.
