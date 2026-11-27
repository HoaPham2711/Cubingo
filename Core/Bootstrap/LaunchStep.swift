import Foundation

/// Một bước của chuỗi khởi động app (`App.init`). Gom các `if !isUnitTestHost` rải rác của app nguồn thành DỮ LIỆU:
/// `AppBootstrap.run` chạy tuần tự đúng thứ tự khai báo và bỏ bước theo môi trường.
///
/// - `skipInUnitTestHost` (mặc định `true`): app làm host cho unit test không được đọc/xoá dấu sự cố thật, dọn tmp
///   (test đặt file làm việc trong tmp trước khi host mở), ghi datastore TipKit thật… Chỉ đặt `false` cho bước tự nó
///   đã an toàn trong host (VD `TelemetryBootstrap.start` tự là no-op ở đó).
/// - `skipInUIPreview` (mặc định `false`): route `-uiPreview` trên Simulator (chụp ảnh) — bỏ bước làm ảnh phụ thuộc
///   lần dùng sim trước hoặc ghi trạng thái thật (dọn tmp, TipKit).
struct LaunchStep {
    let name: String
    var skipInUnitTestHost = true
    var skipInUIPreview = false
    let run: () -> Void
}
