# Cổng symbol debug chỉ thấy symbol được link vào binary — và chỉ thấy TÊN TYPE

Nguồn: dựng cổng release của template (bản đầu, 2026-11-21); đo lại ở lượt chuyển lõi (2026-11-22).

## Chuyện đã xảy ra
1. (lượt dựng cổng) Thử chứng minh cổng 1 của `tools/release/verify_release_clean.sh` (không symbol debug trong bản Release) bằng
   cách bỏ `#if INTERNAL` quanh một type debug rồi build Release. Cổng vẫn PASS — trông như cổng không gác.
2. (lượt chuyển lõi) `debug_symbols.txt` có cả tên HÀM (`setInternalProOverride`, `setProForInternalTesting`, `debugSetUsed` — lối
   bật Pro không trả tiền). Đo binary: hai trong ba tên không có cả trong binary **Internal** (tên hàm bị strip/inline;
   tên còn lại chỉ xuất hiện qua symbol closure của build không archive). Cổng grep chúng ở bản Release luôn "sạch" —
   an tâm giả cho đúng thứ nguy hiểm nhất.

## Nguyên nhân
- Type không ai dùng bị linker **dead-strip** khỏi binary Release (tối ưu + strip). Cổng soi Mach-O của `.app`, nên
  chỉ thấy symbol thật sự được link.
- Tên **type** Swift sống sót trong binary nhờ metadata reflection (nominal type descriptor) kể cả khi symbol bị
  strip; tên **hàm/biến** thì không có chỗ nào bắt buộc giữ lại.

## Bài học
- `debug_symbols.txt` có HAI mục: `[binary]` (tên type — cổng 1 grep binary Release) và `[source-only]` (tên hàm/biến
  ghim bằng marker `// debug-symbol: required` — chỉ `#if INTERNAL` + `tools/release/lint_debug_symbols.py` gác; lint
  cấm type ở `[source-only]` và hàm ở `[binary]`).
- **Mỗi tên `[binary]` phải có đối chứng dương**: `verify_release_clean.sh --expect-debug-symbols <Internal.app>`
  (selfcheck bước 8b) đòi MỌI tên `[binary]` có mặt trong binary Internal. Tên không thấy ở đó (optimizer bỏ, gõ sai,
  đổi tên) là "mục vô tác dụng" — cổng gác một chuỗi không bao giờ xuất hiện.
- Muốn chứng minh cổng gác một type: phép phá phải bỏ `#if INTERNAL` ở **cả** type **lẫn** một chỗ dùng nó, rồi
  build/archive Release ⇒ cổng phải FAIL.
- `tools/template/selfcheck.sh` chứng minh chiều ngược lại mỗi lần chạy: bản Internal PHẢI bị từ chối, đúng lý do
  (`bundle id`, `InternalDebugMarkerView`), và chứa đủ mọi tên `[binary]`.

## Bằng chứng trên archive thật (lượt chuyển lõi, 2026-11-22)
- `xcodebuild archive -scheme AppHost-Store -configuration Release -destination generic/platform=iOS
  CODE_SIGNING_ALLOWED=NO FIREBASE_PLIST_DIR=<plist fixture>` ⇒ `ARCHIVE SUCCEEDED`; `ALLOW_FIXTURE_PLIST=1
  verify_release_clean.sh <xcarchive>` rc 0 (`cổng 1: soi 9 tên [binary] trong 3 Mach-O; 3 tên [source-only] không soi
  binary`).
- Phá bằng `tools/factory/mutate.py` (lồng hai lần, tự khôi phục, sha256 khớp): `Core/Internal/LogFileView.swift`
  `#if INTERNAL` → `#if true` (cả file: `InternalLogText` + `LogFileView`) **và** `AppHost/AppHost/Internal/
  AppInternalEntry.swift` nhánh `#else` của `AppInternalSettingsSection` `EmptyView()` →
  `LogFileView(url: URL(fileURLWithPath: "/dev/null"))`. Archive lại ⇒ `ARCHIVE SUCCEEDED`; cổng rc 1 với
  `FAIL: còn symbol debug 'LogFileView' trong binary`, kèm cổng 1b (lint) báo `LogFileView`/`InternalLogText` khai
  ngoài vùng `#if INTERNAL`.
- Quan sát: `InternalLogText` (enum chỉ có hàm static, chỉ được `LogFileView` gọi) KHÔNG xuất hiện trong binary của
  archive mutant dù được biên dịch vào — enum không case nào bị dùng làm giá trị thì metadata có thể bị bỏ. Nó vẫn
  qua đối chứng dương ở build Internal hiện tại, nên chưa phải "mục vô tác dụng"; nếu một ngày đối chứng báo nó, chuyển
  sang `[source-only]` hay đổi thành type được dùng — đừng tắt đối chứng.
