# Test chạy ở bundle id Store làm treo suite vì StoreKit sandbox thật

Nguồn: app gốc của template (2026-09), viết lại cho template.

## Chuyện đã xảy ra
Full suite treo ~17 phút ở một test mua hàng, trong khi chạy lẻ class thì xanh. Simulator bật hộp thoại hệ thống
"Sign in to Apple Account" giữa suite; lời gọi mua chờ vô hạn.

## Nguyên nhân
Cả Debug (unit test) lẫn Release (lúc đó dùng cho đo đạc) cài app host với **bundle id Store** ⇒ app host trỏ vào
app record THẬT trên App Store Connect, khởi động StoreKit và gọi sandbox thật. Hộp thoại đăng nhập là alert hệ
thống, sống qua các lần relaunch app.

## Đã áp ở template
- Debug và Internal mang bundle id internal (`[bundle] internal` trong `app.config.toml`); chỉ Release mang id
  Store (`AppHost/project.yml`).
- Scheme `AppHost-Store` không có action test; scheme `AppHost` test ở Debug.
- Hook `.claude/hooks/guard_test_config.py` chặn `xcodebuild test|build-for-testing|test-without-building` ở
  Release hoặc scheme `-Store`.
- `tools/dev/run_tests.py` cố định config Debug.
- `AppHost/AppHostTests/SmokeTests.swift` kiểm bundle id của app host = bundle id internal.

## Bài học
- Test CHỈ chạy ở `Debug`, không bao giờ `Release`/`AppHost-Store` — kể cả "chỉ một lần cho giống bản người dùng".
  `Internal` (cũng mang bundle id internal) là config chạy app trên device hằng ngày; template không có đường test
  ở đó.
- Full suite chậm bất thường ⇒ nghi hộp thoại hệ thống trước, chụp sim (`xcrun simctl io <UDID> screenshot`);
  đã lỡ hiện thì `xcrun simctl erase <UDID>`.
- Khi lõi mua hàng về (bản lõi mua hàng của template): app host của unit test phải bỏ qua khởi động StoreKit; test StoreKit thật chạy
  riêng, có trần thời gian.
