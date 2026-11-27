import Foundation

/// Copy phụ thuộc gói và điều kiện dùng thử — hàm THUẦN để test được mà không dựng View. Mọi quyết định
/// về câu chữ của nút mua, dòng điều khoản và hàng gói nằm ở đây, không nằm trong body của `PaywallView`.
///
/// `String(localized:)` bắt buộc ở đây: chuỗi đi qua giá trị trả về kiểu `String` trước khi tới
/// `Text(...)`, nếu không bọc thì Xcode không extract được vào String Catalog.
///
/// Luật Guideline 3.1.2 (mỗi luật có test ở `PaywallCopyTests`):
/// - Chào dùng thử khi và chỉ khi user còn đủ điều kiện (thuộc tính của subscription group) VÀ gói đang chọn
///   thật sự có offer miễn phí (`ProProduct.freeTrialDays`) — số ngày lấy từ StoreKit, không viết cứng.
/// - Subscription có dùng thử ⇒ nêu độ dài dùng thử VÀ giá sau đó theo đúng chu kỳ của gói.
/// - Gói trọn đời (mua đứt): không bao giờ nói tới dùng thử, "free", gia hạn hay huỷ; nêu giá là mua một lần.
/// - CTA và điều khoản luôn mô tả GÓI ĐANG CHỌN (call site truyền đúng gói đó).
enum PaywallCopy {

    /// Số ngày dùng thử được CHÀO trên gói này (`nil` = không chào). Gói trọn đời LUÔN `nil`, kể cả khi dữ liệu lỗi gắn
    /// `freeTrialDays` cho nó: cờ đủ-điều-kiện là của subscription group, không áp cho mua đứt.
    static func offeredTrialDays(_ product: ProProduct, eligibleForTrial: Bool) -> Int? {
        guard product.kind != .lifetime, eligibleForTrial, let days = product.freeTrialDays else { return nil }
        return days
    }

    static func cta(for product: ProProduct, eligibleForTrial: Bool) -> String {
        switch product.kind {
        case .lifetime:
            return String(localized: "Buy once for \(product.displayPrice)")
        case .month, .year:
            guard let days = offeredTrialDays(product, eligibleForTrial: eligibleForTrial) else {
                return String(localized: "Subscribe")
            }
            return String(localized: "Start \(days)-day free trial")
        }
    }

    /// Nút mua khi CHƯA có gói nào để mô tả (đang tải / tải lỗi). Bấm vẫn có tác dụng (tải lại) — xem
    /// `PaywallView.footer`. Trung tính: không biết app bán subscription hay mua đứt.
    static var ctaWithoutProduct: String { String(localized: "Continue") }

    /// `price` là giá của GÓI ĐANG CHỌN (không phải luôn giá năm) — chu kỳ hiển thị theo `kind` của chính gói đó.
    static func terms(for product: ProProduct, eligibleForTrial: Bool) -> String {
        let price = product.displayPrice
        if let days = offeredTrialDays(product, eligibleForTrial: eligibleForTrial) {
            switch product.kind {
            case .year:
                return String(localized: "Free for \(days) days, then \(price)/year. Cancel anytime.")
            case .month:
                return String(localized: "Free for \(days) days, then \(price)/month. Cancel anytime.")
            case .lifetime:
                break   // không tới được: `offeredTrialDays` trả nil cho gói trọn đời
            }
        }
        switch product.kind {
        case .year:
            return String(localized: "\(price)/year, auto-renews. Cancel anytime.")
        case .month:
            return String(localized: "\(price)/month, auto-renews. Cancel anytime.")
        case .lifetime:
            return String(localized: "\(price), one-time purchase. No subscription.")
        }
    }

    static func planTitle(_ kind: ProProduct.Kind) -> String {
        switch kind {
        case .month: return String(localized: "Monthly")
        case .year: return String(localized: "Yearly")
        case .lifetime: return String(localized: "Lifetime")
        }
    }

    /// Dòng giá dưới tên gói trong hàng chọn gói.
    static func planPrice(_ product: ProProduct) -> String {
        switch product.kind {
        case .month: return String(localized: "\(product.displayPrice) / month")
        case .year: return String(localized: "\(product.displayPrice) / year")
        case .lifetime: return String(localized: "\(product.displayPrice) one-time")
        }
    }
}
