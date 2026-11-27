---
name: ui-preview-sim
description: Build Debug + chạy app trên iOS Simulator để screenshot/kiểm tra UI (iPhone dọc, iPad ngang). Dùng khi cần review UI mà không có device.
---

## UI preview trên iOS Simulator

Khác `compile-check` (chỉ compile/test): skill này **chạy** app + screenshot. Cổng L2 cho thay đổi UI là ảnh
iPhone dọc VÀ iPad ngang đã được mở ra xem (`.claude/rules/conventions.core.md`).

**Route `-uiPreview <màn>`** (`AppHost/AppHost/AppPreview.swift`, chỉ Simulator). Khung: `home` (app còn tính năng mẫu:
Home đã seed nội dung của mẫu; gỡ mẫu xong: màn giữ chỗ `EmptyStateView`), `onboarding`, `settings` (+ ảnh cuộn
`settings-scrolled-*`), `paywall` (store giả
`AppPreviewStore` khớp `Products.storekit` — file `.storekit` của scheme không được áp cho app do XCUITest mở),
`whatsNew` (suite riêng `uiPreview.whatsNew`), `feedback` (form phản hồi, cần khối Web API bật).

**Route của tính năng**: mỗi tính năng khai route của nó trong `AppPreview` và liệt kê ý nghĩa từng route ở README của
thư mục tính năng (`AppHost/AppHost/Features/<Tên>/README.md`). App còn tính năng mẫu của template thì route của mẫu nằm
trong khối `// sample:` (mất cùng mẫu) và danh sách ở README của thư mục mẫu. Seed ghi vào suite/thư mục `uiPreview…`
(viết lại mỗi lần mở — ảnh lặp lại được; không bao giờ file thật, không Keychain).
Thêm route: thêm `case` + dựng màn (`AppShellView` / seed của tính năng) + một dòng ở README của tính năng;
`ui_shots.py all` tự thấy route mới. Kiểu seed/store giả đặt tên `*PreviewSeed`/
`*PreviewStore` và nằm trong `#if targetEnvironment(simulator)` (`tools/release/lint_preview_code.py`).
Route preview KHÔNG vẽ dấu INTERNAL (ảnh review/store phải sạch); muốn nhìn dấu đó thì mở app thường bằng Cách B.
Route preview ghi cờ `hasSeenOnboarding` (và khoá seed khác) vào UserDefaults CHUẨN của app trên simulator đó ⇒ lần
chạy thường sau thừa hưởng; muốn thử "lần đầu mở app" thì gỡ app (`xcrun simctl uninstall`) hoặc dùng sim khác.

### Cách A — `tools/dev/ui_shots.py` (chụp theo hướng, đường chính)

Máy dev không có Simulator.app để xoay, `simctl` không có lệnh xoay, và app hỗ trợ multitasking thì iPad bỏ qua
`requestGeometryUpdate`. Đường duy nhất: XCUITest (`XCUIDevice.orientation`) — target `AppHostUITests`
(`AppHost/AppHostUITests/UIShotsTests.swift`), scheme riêng `AppHost-UIShots` (Debug, không vào L1/L2):

```bash
tools/dev/ui_shots.py home settings                       # sim riêng của worktree (iPhone), dọc, .temp/ui-shots/default/
tools/dev/ui_shots.py all --label p3                      # MỌI route của AppPreview ⇒ .temp/ui-shots/p3/
tools/dev/ui_shots.py --udid <iPad UDID> all --label p3   # iPad ⇒ tự chọn ngang (--orient auto)
tools/dev/ui_shots.py --content-size accessibility-extra-large --label ax settings paywall
tools/dev/ui_shots.py --udid "$UDID" --orient portrait --out .temp/shots home   # đường cũ vẫn chạy
tools/dev/ui_shots.py --print-cmd home                    # in lệnh xcodebuild rồi thoát
```

- `all` = danh sách `case` của `enum AppPreview` đọc từ file Swift (kể cả trong khối `// sample:` nếu còn) — một nguồn.
- Ảnh ra `<out>/<target>-land.png` / `-port.png`; ảnh ngang (cả `-scrolled-`) đã xoay đứng lại để đọc. Thiếu ảnh
  hoặc không xoay được ⇒ script trả rc 1, không coi là xanh. DerivedData riêng ở `.temp/DerivedData/uishots`.
- `--content-size <cỡ>` (tên của `xcrun simctl ui <udid> content_size`): đặt Dynamic Type trước khi chụp, LUÔN trả
  về `large` sau đó (cả khi lỗi/Ctrl-C/SIGTERM). Kiểm: `xcrun simctl ui <udid> content_size` in `large`.
- `--orient auto` (mặc định): tên sim có "iPad" ⇒ landscape, còn lại ⇒ portrait. iPhone chỉ hỗ trợ dọc (project.yml)
  ⇒ `--orient landscape` trên sim iPhone làm `testChupMan` FAIL ("App không xoay ngang") thay vì ghi ảnh nằm nghiêng.
- `UIShotsTests.testChupMan` mở app một lần cho mỗi route (`-uiPreview <route>`), ghi `<route>-*.png`. Route cần ảnh
  phần dưới có thêm `<route>-scrolled-*.png`: map route → SỐ LẦN vuốt lên ở `UIShotsTests.scrollRoutes` (`settings` 1,
  `paywall` 3, `onboarding` 1, + route của tính năng — xem chính file đó); route chậm khai ở `slowRoutes`. Thêm màn dài ⇒ thêm vào map.
- iPad: tạo sim tạm (`xcrun simctl create "<tên>" <device type> <runtime>`, chọn từ `xcrun simctl list`), chụp,
  rồi `xcrun simctl delete <UDID>` — đừng mượn sim đang boot của phiên khác.
- Chạy bằng Bash foreground (`timeout: 600000`), không chạy nền rồi poll.
- Ảnh ở tổ hợp tắt hết khối tuỳ chọn (chỉ ở repo template): `MATRIX_SHOTS_DIR=<dir>` của `feature_matrix_check.sh` của
  template (chụp `settings feedback home`, + route của tính năng mẫu khi còn). Cỡ chữ lớn cho cả bộ: chạy
  `all --content-size accessibility-extra-large --label <tên>-ax` (cần xem ảnh cuộn của `paywall` và màn chi tiết dài: ở cỡ
  trợ năng phần dưới nằm ngoài màn đầu).

Xem ảnh bằng Read tool trên file PNG.

### Cách B — `xcrun simctl` thô (khi chỉ cần một ảnh dọc nhanh)

```bash
UDID=$(python3 tools/dev/sim_pool.py ensure)
cd AppHost && xcodegen generate && cd ..
xcodebuild -project AppHost/AppHost.xcodeproj -scheme AppHost -configuration Debug \
  -destination "id=$UDID" -derivedDataPath .temp/DerivedData/ui CODE_SIGNING_ALLOWED=NO build
APP=$(find .temp/DerivedData/ui/Build/Products/Debug-iphonesimulator -maxdepth 1 -name '*.app' | head -1)
BUNDLE=$(/usr/libexec/PlistBuddy -c 'Print CFBundleIdentifier' "$APP/Info.plist")
xcrun simctl install "$UDID" "$APP"
xcrun simctl launch "$UDID" "$BUNDLE"
xcrun simctl io "$UDID" screenshot .temp/ui.png
```

Bundle id lấy từ chính `.app` (đừng gõ literal — định danh chỉ nằm ở `app.config.toml`).

### Bẫy & lưu ý

- Build `Debug` (bundle id internal) — không chụp bằng Release/`AppHost-Store`: app host mang id Store chạm
  StoreKit sandbox thật, hộp thoại hệ thống "Sign in to Apple Account" có thể che màn và sống qua các lần
  relaunch (đã lỡ hiện thì `xcrun simctl erase <UDID>`).
- Build Debug thiếu plist Firebase chỉ cảnh báo — bình thường khi chụp ảnh.
- Không đo hiệu năng trên sim — chỉ review UI; hiệu năng thật đo bằng `Internal`/`Release` trên device
  (skill `build-and-run`).
- Dấu `INTERNAL` (`internalBadge()`) hiện ở ảnh Debug — đúng thiết kế, không phải lỗi bố cục.
