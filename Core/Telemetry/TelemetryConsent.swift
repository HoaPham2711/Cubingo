import Foundation

/// Đồng ý chia sẻ dữ liệu sử dụng. Mô hình **opt-out**: mặc định BẬT, user tắt được trong Settings.
///
/// Đọc bằng `object(forKey:)` chứ KHÔNG bằng `bool(forKey:)`: `bool` trả `false` cho key chưa
/// từng ghi, tức mọi user mới sẽ mặc định tắt — sai hẳn mô hình opt-out và không có triệu chứng nào
/// ngoài dashboard trống rỗng.
enum TelemetryConsent {

    /// Cùng key này được `@AppStorage` trong `SettingsView` dùng — đổi tên là mất lựa chọn của user.
    static let defaultsKey = "telemetry.shareUsageData"

    /// Mặc định khi key chưa từng ghi (opt-out ⇒ BẬT). Một nguồn cho cả `isEnabled` lẫn `@AppStorage` của Settings.
    static let defaultValue = true

    static func isEnabled(in defaults: UserDefaults = .standard) -> Bool {
        guard defaults.object(forKey: defaultsKey) != nil else { return defaultValue }
        return defaults.bool(forKey: defaultsKey)
    }

    static func set(_ enabled: Bool, in defaults: UserDefaults = .standard) {
        defaults.set(enabled, forKey: defaultsKey)
    }
}
