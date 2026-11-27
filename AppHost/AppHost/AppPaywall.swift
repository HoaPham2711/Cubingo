import Foundation

/// Phần paywall do app cấp (bảng Free / Pro, tiêu đề, link điều khoản). Một nhóm, ít hàng: hàng chung + hàng của từng
/// tính năng Pro, số lấy từ chính luật app thi hành (xem `PaywallContent`) — không gõ lại.
enum AppPaywall {
    static func content(config: AppConfig) -> PaywallContent {
        PaywallContent(
            defaultHeadline: String(localized: "Upgrade to Pro"),
            sections: [.init(title: nil, rows: [
                .init(title: String(localized: "Everyday features"), free: .yes, pro: .yes),
                .init(title: String(localized: "Pro features"), free: .no, pro: .yes),
            ])],
            termsURL: config.termsURL,
            privacyURL: config.privacyURL)
    }
}
