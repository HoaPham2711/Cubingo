// Công cụ nội bộ — bản App Store (config Release) không compile file này.
#if INTERNAL
import Foundation

/// Toggle debug "Giả lập lần đầu mở app": BẬT ⇒ mỗi lần mở app quên các trạng thái "lần đầu" để thử lại những thứ
/// chỉ chạy một lần — tour onboarding, tip TipKit và mọi khoá "chỉ lần đầu" app đăng ký ở `extraKeys`. CHỈ xoá đúng
/// các khoá đã đăng ký (`firstRunKeys`), KHÔNG xoá cả domain UserDefaults — bản gốc cũng làm vậy: dữ liệu người dùng,
/// quyền Pro giả lập, hạn mức free, tuỳ chọn hiển thị đều không bị đụng.
///
/// Thêm tính năng "chỉ lần đầu" mới ⇒ app thêm khoá của nó vào `extraKeys` (một lần, lúc khởi động, TRƯỚC
/// `InternalLaunch.beforeTipsConfigure()`).
///
/// Thứ tự: `applyAtLaunch` phải chạy TRƯỚC `AppTips.configure()` — xoá datastore TipKit chỉ hợp lệ trước configure
/// (đi qua `InternalLaunch.beforeTipsConfigure()`).
enum FirstLaunchSimulation {
    static let enabledKey = "debug.simulateFirstLaunch"

    /// `extraKeys`, `onReset` (và `InternalLaunch.afterLaunchHook`): đặt MỘT lần lúc mở app, trên main thread, TRƯỚC
    /// `InternalLaunch.beforeTipsConfigure()` — không có khoá, không an toàn khi đặt từ nhiều thread.
    ///
    /// Khoá "chỉ lần đầu" riêng của app (VD "đã xem video hướng dẫn", "đã chọn chế độ ưa thích").
    static var extraKeys: [String] = []

    /// Cách yêu cầu xoá TipKit. Mặc định `AppTips.requestReset` (đặt cờ chờ, xoá thật ở lần mở sau, trước configure).
    static var onReset: (UserDefaults) -> Void = { AppTips.requestReset(defaults: $0) }

    /// Mọi khoá bị quên khi mô phỏng: cờ onboarding của lõi + `extraKeys`. Không có chuỗi literal thứ hai.
    static var firstRunKeys: [String] { [WhatsNewHost.hasSeenOnboardingKey] + extraKeys }

    static func enabled(in defaults: UserDefaults) -> Bool { defaults.bool(forKey: enabledKey) }

    /// Công tắc trên `UserDefaults.standard`. Bật ⇒ áp dụng ngay phần làm được lúc app đang chạy (cờ onboarding là
    /// `@AppStorage` ở root nên app chuyển sang tour luôn); TipKit chỉ xoá được trước configure ⇒ lần mở sau.
    static var isEnabled: Bool {
        get { enabled(in: .standard) }
        set { setEnabled(newValue, defaults: .standard) }
    }

    static func setEnabled(_ on: Bool, defaults: UserDefaults = .standard) {
        defaults.set(on, forKey: enabledKey)
        if on { resetFirstRunState(defaults) }
    }

    /// Gọi lúc khởi động, TRƯỚC `AppTips.configure()` (qua `InternalLaunch`). No-op nếu toggle không được bật tường minh.
    static func applyAtLaunch(defaults: UserDefaults = .standard) {
        guard enabled(in: defaults) else { return }
        resetFirstRunState(defaults)
    }

    static func resetFirstRunState(_ defaults: UserDefaults = .standard) {
        for k in firstRunKeys { defaults.removeObject(forKey: k) }
        onReset(defaults)
    }
}
#endif
