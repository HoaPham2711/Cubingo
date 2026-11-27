import Foundation

/// Nội dung alert sau một lần bấm Khôi phục — nguồn DUY NHẤT cho cả paywall lẫn Settings (trước đây mỗi nơi tự ánh
/// xạ `RestoreOutcome` ⇒ hai bản sao có thể trôi lệch nhau).
struct RestoreAlert: Equatable {
    let title: String
    let message: String

    /// `.restored` ⇒ không alert (Settings: hàng trạng thái tự đổi; paywall: tự đóng). Hai nhánh còn lại KHÔNG được
    /// gộp: nói với người ĐÃ trả tiền rằng họ chưa từng mua — chỉ vì mạng lỗi — là sai sự thật và đẻ ra khiếu nại
    /// hoàn tiền.
    static func make(_ outcome: Entitlements.RestoreOutcome) -> RestoreAlert? {
        switch outcome {
        case .restored:
            return nil
        case .noPurchasesFound:
            return RestoreAlert(title: String(localized: "No purchase found"),
                                message: String(localized: "This account has never purchased Pro."))
        case .failed:
            return RestoreAlert(title: String(localized: "Restore failed"),
                                message: String(localized: "Could not reach the App Store. Check your connection and try again."))
        }
    }
}
