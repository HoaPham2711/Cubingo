import Foundation

/// Đồng bộ thuộc tính người dùng. Gọi lúc khởi động (SAU khi dữ liệu app đã nạp, để giá trị là thật) và sau
/// mỗi mốc làm chúng đổi.
///
/// Vì sao gom một chỗ: thuộc tính người dùng là trạng thái ĐANG LÀ, khác event là chuyện ĐÃ XẢY
/// RA. Rải lệnh gán khắp app thì không ai trả lời được "giá trị này lúc nào được cập nhật".
///
/// Không gán thì mọi báo cáo mất khả năng cắt lát — biết "30% bỏ dở ở bước X" mà không biết đó là
/// người dùng lần đầu hay người đã dùng 20 lần thì con số không quyết định được gì.
///
/// Lõi chỉ có cơ chế; danh sách thuộc tính là của app (`appProperties`).
enum UserPropertySync {

    /// App đăng ký lúc khởi động: đọc trạng thái hiện tại từ `defaults` được truyền vào (không đọc
    /// `.standard` bên trong — test truyền suite riêng). Mặc định không có thuộc tính nào.
    /// Cờ một chiều của `markFlag` cũng phải có mặt ở đây (đọc `defaults.bool(forKey:)`) để lượt khởi động sau
    /// gửi lại giá trị.
    nonisolated(unsafe) static var appProperties: (UserDefaults) -> [UserProperty] = { _ in [] }

    /// `isPro` KHÔNG được gán ở đây: entitlements là nguồn sự thật duy nhất của quyền và nó tự gán mỗi lần
    /// đổi. Gán lại từ đây là mở đường cho hai nơi nói hai chuyện khác nhau — nên kể cả khi app lỡ đăng ký
    /// `is_pro` trong `appProperties`, nó cũng bị bỏ.
    static func refresh(defaults: UserDefaults = .standard) {
        let isProName = UserProperty.isPro(false).name
        for p in appProperties(defaults) where p.name != isProName {
            Track.set(p)
        }
    }

    /// Cờ một chiều "đã từng làm X ít nhất một lần": cờ `key` trên máy chỉ ghi `true` MỘT lần (không bao giờ về
    /// false), còn `property` được GỬI ở MỌI lần gọi — lượt gửi trước có thể đã rơi (sink chưa gắn, consent tắt
    /// lúc đó), gửi lại cùng giá trị là vô hại và tự bù.
    static func markFlag(_ key: String, _ property: @autoclosure () -> UserProperty,
                         defaults: UserDefaults = .standard) {
        if !defaults.bool(forKey: key) { defaults.set(true, forKey: key) }
        Track.set(property())
    }
}
