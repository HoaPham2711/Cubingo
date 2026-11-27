import SwiftUI
import TipKit

/// Trạng thái dùng chung cho rule của tip. Lõi chỉ giữ cờ mọi app cần; cờ riêng của app (VD "danh sách rỗng") khai
/// trong một `enum` của app — `@Parameter static` là stored property nên KHÔNG thêm được bằng `extension`.
enum AppTipState {
    /// Không tip nào hiện khi user còn ở tour onboarding. App đặt theo cờ `WhatsNewHost.hasSeenOnboardingKey`
    /// (lúc mở app và khi onboarding xong). Mọi tip của app nên có `#Rule(AppTipState.$onboardingFinished) { $0 }`.
    @Parameter static var onboardingFinished: Bool = false
}

/// Điểm cấu hình TipKit — app gọi MỘT lần lúc khởi động, NGOÀI host unit test (host test không được ghi datastore
/// TipKit). Tip cụ thể là của app; copy tip để ở hằng `static let titleText = String(localized: …)` cho test đọc được.
enum AppTips {
    static let resetPendingKey = "tips.resetPending"

    /// `Tips.resetDatastore()` CHỈ hợp lệ trước `configure` ⇒ "Show tips again" (`requestReset`) chỉ đặt cờ; xoá thật
    /// ở lần mở app kế tiếp, ngay đây.
    static func configure(defaults: UserDefaults = .standard) {
        if defaults.bool(forKey: resetPendingKey) {
            try? Tips.resetDatastore()
            defaults.removeObject(forKey: resetPendingKey)
        }
        try? Tips.configure([.displayFrequency(.immediate)])
    }

    /// Có hiệu lực từ lần mở app sau — UI gọi nơi này phải nói rõ điều đó với user.
    static func requestReset(defaults: UserDefaults = .standard) {
        defaults.set(true, forKey: resetPendingKey)
    }
}
