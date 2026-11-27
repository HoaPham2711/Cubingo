import Foundation
import StoreKit

/// Chỗ DUY NHẤT nói chuyện với StoreKit về TRẠNG THÁI QUYỀN. Mọi thứ khác nói chuyện qua
/// `StoreClient` bằng value type của mình — nhờ vậy logic quyền test được bằng fake.
/// `import StoreKit` chỉ ở ĐÚNG ba file: file này (quyền + mua), `Core/Engage/Review/ReviewPromptHost.swift`
/// (`requestReview` của SwiftUI) và `Core/Shell/SettingsAccountSection.swift` (`manageSubscriptionsSheet`) — hai file
/// sau chỉ dùng API UI hệ thống, không đọc/ghi quyền (`docs/ARCHITECTURE.md` §"Quy tắc biên").
///
/// `productIDs` (từ `AppConfig.productIDs`) phải khớp TUYỆT ĐỐI ba nơi: cấu hình app, file `.storekit` và
/// App Store Connect. Lệch một ký tự ⇒ `products()` rỗng — triệu chứng giống hệt lỗi code.
/// Mọi id trong danh sách đều cấp Pro: subscription tháng/năm và gói trọn đời (non-consumable).
@MainActor
final class LiveStoreClient: StoreClient {

    private let productIDs: [String]

    init(productIDs: [String]) {
        self.productIDs = productIDs
    }

    func products() async throws -> [ProProduct] {
        let raw = try await Product.products(for: productIDs)
        return try Self.requireNonEmpty(raw.compactMap(Self.map))
    }

    /// Guard trên danh sách ĐÃ MAP, không phải danh sách thô: nếu `map` loại hết (vd. StoreKit
    /// trả về sản phẩm loại/chu kỳ không hỗ trợ) thì `raw` không rỗng nhưng `mapped` rỗng —
    /// guard trên `raw` để lọt `[]` xuống UI, paywall hiện `.ready` với 0 gói mà CTA vẫn bật.
    static func requireNonEmpty(_ mapped: [ProProduct]) throws -> [ProProduct] {
        guard !mapped.isEmpty else { throw StoreError.productsUnavailable }
        return mapped
    }

    func currentEntitlement() async -> Bool {
        // Giao dịch non-consumable (trọn đời) cũng nằm trong `currentEntitlements`, cùng đường với subscription
        // còn hạn; subscription hết hạn thì StoreKit tự bỏ khỏi danh sách.
        for await result in Transaction.currentEntitlements {
            guard case .verified(let t) = result else { continue }
            if Self.grantsPro(productID: t.productID, revoked: t.revocationDate != nil, productIDs: productIDs) {
                return true
            }
        }
        return false
    }

    /// Loại quyền từ CÙNG danh sách giao dịch hiệu lực như `currentEntitlement()` (đã xác minh, id trong cấu hình,
    /// chưa thu hồi). Mua trọn đời THẮNG subscription (người có cả hai không cần quản lý/huỷ gói để giữ Pro) — và
    /// trọn đời suy được ngay từ loại giao dịch, không cần mạng. Subscription: chu kỳ không nằm trên `Transaction`
    /// nên phải đọc `Product` của id đó; đọc không được (offline, chưa có cache) ⇒ `nil` (= "không phải trọn đời").
    func currentEntitlementKind() async -> ProProduct.Kind? {
        var kinds: [ProProduct.Kind] = []
        var subscriptionIDs: [String] = []
        for await result in Transaction.currentEntitlements {
            guard case .verified(let t) = result,
                  Self.grantsPro(productID: t.productID, revoked: t.revocationDate != nil, productIDs: productIDs)
            else { continue }
            if t.productType == .autoRenewable {
                subscriptionIDs.append(t.productID)
            } else if let k = Self.kind(productType: t.productType, subscriptionUnit: nil, subscriptionValue: nil) {
                kinds.append(k)
            }
        }
        // Đã có trọn đời thì khỏi hỏi chu kỳ subscription (đỡ một lượt gọi mạng).
        if !kinds.contains(.lifetime), !subscriptionIDs.isEmpty,
           let products = try? await Product.products(for: subscriptionIDs) {
            kinds += products.compactMap {
                Self.kind(productType: $0.type,
                          subscriptionUnit: $0.subscription?.subscriptionPeriod.unit,
                          subscriptionValue: $0.subscription?.subscriptionPeriod.value)
            }
        }
        return Self.strongestKind(kinds)
    }

    /// Nhiều quyền cùng lúc ⇒ chọn một: trọn đời > năm > tháng. Hàm THUẦN (test không cần `SKTestSession`).
    static func strongestKind(_ kinds: [ProProduct.Kind]) -> ProProduct.Kind? {
        if kinds.contains(.lifetime) { return .lifetime }
        if kinds.contains(.year) { return .year }
        return kinds.contains(.month) ? .month : nil
    }

    /// Một giao dịch đã xác minh có cấp Pro không: id nằm trong cấu hình và chưa bị thu hồi (hoàn tiền).
    static func grantsPro(productID: String, revoked: Bool, productIDs: [String]) -> Bool {
        !revoked && productIDs.contains(productID)
    }

    /// Đủ điều kiện dùng thử là thuộc tính của SUBSCRIPTION GROUP — hỏi qua subscription bất kỳ trong cấu hình
    /// (template giả định mọi subscription chung một group). Không có subscription nào (chỉ bán trọn đời) ⇒
    /// `false`: gói mua đứt không có introductory offer.
    func isEligibleForIntroOffer() async -> Bool {
        guard let all = try? await Product.products(for: productIDs),
              let subscription = all.first(where: { $0.subscription != nil })?.subscription else { return false }
        return await subscription.isEligibleForIntroOffer
    }

    func purchase(_ productID: String) async throws -> PurchaseOutcome {
        guard let product = try await Product.products(for: [productID]).first else {
            throw StoreError.productsUnavailable
        }
        switch try await product.purchase() {
        case .success(let verification):
            switch verification {
            case .verified(let transaction):
                // Quên finish() thì StoreKit đẩy lại giao dịch này vĩnh viễn ở mỗi lần mở app.
                await transaction.finish()
                return .success
            case .unverified:
                throw StoreError.unverified
            }
        case .pending:
            return .pending
        case .userCancelled:
            return .cancelled
        @unknown default:
            return .cancelled
        }
    }

    func sync() async throws {
        try await AppStore.sync()
    }

    func transactionUpdates() -> AsyncStream<Void> {
        AsyncStream { continuation in
            let task = Task.detached {
                for await update in Transaction.updates {
                    // `.unverified` CHỦ Ý không `finish()`: một chữ ký JWS hỏng có thể là bằng
                    // chứng máy bị can thiệp, nên giữ nguyên giao dịch để StoreKit đẩy lại (và cho
                    // Apple/App Review còn thấy dấu vết) thay vì âm thầm nuốt nó. Đánh đổi đã biết
                    // và chấp nhận: mỗi lần mở app payload này còn tồn thì bị đẩy lại lần nữa, kéo
                    // theo một `refresh()` — không cấp quyền (đúng), chỉ tốn một lượt đọc quyền.
                    if case .verified(let transaction) = update {
                        await transaction.finish()
                    }
                    continuation.yield(())
                }
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    func storeEnvironment() async -> String? {
        // `AppTransaction` do Apple ký cho chính bản cài này nên phân biệt được TestFlight với
        // App Store dù cùng một binary `Release`. Chỉ đọc `.shared`, KHÔNG gọi `refresh()` — cái
        // đó bật hộp thoại đăng nhập Apple ID, không đáng cho một nhãn analytics.
        guard let result = try? await AppTransaction.shared,
              case .verified(let app) = result else { return nil }
        switch app.environment {
        case .production: return "production"
        case .sandbox:    return "sandbox"
        case .xcode:      return "xcode"
        default:          return nil
        }
    }

    private static func map(_ product: Product) -> ProProduct? {
        guard let kind = kind(productType: product.type,
                              subscriptionUnit: product.subscription?.subscriptionPeriod.unit,
                              subscriptionValue: product.subscription?.subscriptionPeriod.value) else { return nil }
        var freePeriod: (unit: Product.SubscriptionPeriod.Unit, value: Int)?
        if let offer = product.subscription?.introductoryOffer, offer.paymentMode == .freeTrial {
            freePeriod = (unit: offer.period.unit, value: offer.period.value)
        }
        return ProProduct(id: product.id,
                          displayPrice: product.displayPrice,
                          kind: kind,
                          freeTrialDays: freeTrialDays(kind: kind, freeTrialPeriod: freePeriod))
    }

    /// Loại gói từ loại sản phẩm StoreKit. Hàm THUẦN (tách khỏi `map`) để test không cần `SKTestSession`.
    /// Non-consumable ⇒ trọn đời (bỏ qua tham số chu kỳ); subscription tự gia hạn ⇒ CHỈ chu kỳ đúng 1 tháng hoặc
    /// đúng 1 năm; mọi thứ khác (consumable, non-renewing, chu kỳ tuần/ngày, 3/6 tháng, 2 năm…) ⇒ `nil`, bị loại
    /// khỏi paywall thay vì đoán. Map theo ĐƠN VỊ mà bỏ qua GIÁ TRỊ thì gói 3 tháng hiện "/ month" và nhãn
    /// "monthly" — nói sai kỳ thanh toán ngay lúc mua (Guideline 3.1.2), và sai cả `purchase_*.product`.
    static func kind(productType: Product.ProductType,
                     subscriptionUnit: Product.SubscriptionPeriod.Unit?,
                     subscriptionValue: Int?) -> ProProduct.Kind? {
        if productType == .nonConsumable { return .lifetime }
        guard productType == .autoRenewable, subscriptionValue == 1 else { return nil }
        switch subscriptionUnit {
        case .month?: return .month
        case .year?: return .year
        default: return nil
        }
    }

    /// Chỉ offer MIỄN PHÍ mới là "free trial" (`freeTrialPeriod` chỉ có khi offer là `.freeTrial`);
    /// pay-as-you-go/pay-up-front là giảm giá, chào "free" cho chúng là sai giá. Kỳ tháng/năm không quy đổi
    /// ra ngày (độ dài lịch thay đổi) ⇒ `nil`, paywall rơi về copy không trial — an toàn hơn hứa sai số ngày.
    /// Gói trọn đời LUÔN `nil`, bất kể đầu vào: mua đứt không có dùng thử, chào "free trial" trên nó là hứa sai.
    static func freeTrialDays(kind: ProProduct.Kind,
                              freeTrialPeriod: (unit: Product.SubscriptionPeriod.Unit, value: Int)?) -> Int? {
        guard kind != .lifetime, let period = freeTrialPeriod else { return nil }
        switch period.unit {
        case .day:  return period.value
        case .week: return period.value * 7
        default:    return nil
        }
    }
}
