# Signing đặt ở `project.yml`, không sửa trong Xcode

Nguồn: app gốc của template (comment trong `project.yml` + ghi chép 2026-08/09), viết lại cho template.

## Chuyện đã xảy ra
Đổi team ký trong Xcode (*Signing & Capabilities*) ba lần, lần nào `xcodegen generate` kế tiếp cũng xoá sạch:
thay đổi nằm ở `.xcodeproj` — file sinh ra.

## Ba bẫy đã mất công tìm ra
1. **`CODE_SIGN_STYLE` phải khai TƯỜNG MINH `Automatic`** ở `base`. Checkbox "Automatically manage signing" trong
   Xcode là per-target, không per-config: chỉ một config để `Manual` là cả target mất tick.
2. **Đừng khai `CODE_SIGN_IDENTITY` khi dùng automatic signing.** Ép `Apple Distribution` cho riêng Release bị Xcode
   bác ("automatically signed for development, but a conflicting code signing identity … has been manually
   specified"). Automatic hiện `Apple Development` ở mọi config, kể cả Release — **bình thường**; chứng nhận phân
   phối được chọn ở bước Archive → Distribute.
3. Chuyển sang manual, Xcode tự thêm `DEVELOPMENT_TEAM = ""` — đừng chép dòng rỗng đó vào yml: team rỗng làm
   XcodeGen bỏ luôn team của target.

## Đã áp ở template
`AppHost/project.yml` đặt ở `settings.base`: `DEVELOPMENT_TEAM: $(APP_TEAM_ID)` (giá trị từ `app.config.toml`
`[apple] team_id` qua `AppHost/Config/Identity.xcconfig`) và `CODE_SIGN_STYLE: Automatic`; không khai
`CODE_SIGN_IDENTITY` ở đâu. Team ở `base` nên app và test target chung team — cần để chạy test trên device.

## Bài học
- Đổi team = sửa `app.config.toml` rồi `python3 tools/common/appconfig.py render`; không đụng Xcode.
- Kiểm không cần device:
  `xcodebuild -project AppHost/AppHost.xcodeproj -target AppHost -configuration Release -showBuildSettings | grep -E "DEVELOPMENT_TEAM =|CODE_SIGN"`.
- Nguyên tắc rộng hơn: mọi thứ sửa trong Xcode IDE mà không có trong `project.yml` sẽ mất ở lần generate kế.
