import Foundation

/// Một tính năng có thể bị khoá sau Pro. App khai enum của nó (Core chỉ cấp khuôn):
///
///     enum AppFeature: ProFeature { case premiumAction … }
///
/// `analyticsName` là nhãn snake_case cho `pro_gate_hit.feature` — tách khỏi `rawValue` (dùng để LƯU TRỮ,
/// không được đổi để chiều analytics).
protocol ProFeature: Hashable {
    var isProOnly: Bool { get }
    var analyticsName: String { get }
}

extension Entitlements {
    /// Hàm THUẦN: không bắn event, không đổi trạng thái. Nó chạy trong vòng lặp dựng view và chạy lại mỗi lần
    /// SwiftUI render — bắn `pro_gate_hit` ở đây là hàng nghìn event rác mỗi phiên. Event đó do UI bắn khi user
    /// CHẠM control khoá. Paywall tắt ⇒ `isPro` luôn true ⇒ không gì bị khoá.
    func isLocked<F: ProFeature>(_ feature: F) -> Bool {
        feature.isProOnly && !isPro
    }
}
