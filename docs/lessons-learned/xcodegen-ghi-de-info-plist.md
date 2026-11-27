# `xcodegen generate` ghi đè `Info.plist`

Nguồn: comment trong `project.yml` của app gốc, viết lại cho template.

## Chuyện đã xảy ra
- Key hướng màn hình iPhone được thêm thẳng vào `Info.plist` — lần `xcodegen generate` kế tiếp xoá sạch.
- Thiếu `CFBundleShortVersionString`/`CFBundleVersion` trong khối `info` ⇒ mỗi lần generate, version reset về
  1.0 (1).
- Thiếu key mô tả quyền (camera, ảnh…) không lỗi build: app crash khi xin quyền, hoặc hệ thống **im lặng** không
  làm gì (không prompt, không lỗi, share sheet ẩn mục lưu ảnh).

## Nguyên nhân
Target có `info.path` thì XcodeGen **sinh lại** file plist đó từ `info.properties` mỗi lần generate. Sửa tay trong
file không sống qua lần generate kế.

## Đã áp ở template
`AppHost/project.yml` khai mọi key trong `targets.AppHost.info.properties`: version qua `$(APP_MARKETING_VERSION)` /
`$(APP_BUILD_NUMBER)` (từ `app.config.toml`, `bump_version.sh` ghi), tên hiển thị, `UILaunchScreen` (thiếu là app
chạy chế độ compatibility-scaled), hướng màn hình iPhone/iPad.

## Bài học
- Key Info.plist mới = sửa `project.yml`, rồi generate, rồi kiểm plist trong `.app` đã build
  (`/usr/libexec/PlistBuddy -c 'Print <key>' <App>.app/Info.plist`).
- App iPad không có `UIRequiresFullScreen` phải khai đủ 4 hướng, không thì App Store Connect từ chối bản upload —
  cổng 9 của `tools/release/verify_release_clean.sh` gác.
- Mỗi key quyền mới: thử luồng xin quyền thật trên device — thiếu key nhiều khi không có triệu chứng nào khác.
