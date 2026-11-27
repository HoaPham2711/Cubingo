import Foundation

/// Một gói bán trên paywall. Value type CỦA MÌNH, không phải `StoreKit.Product` — vì `Product`
/// là struct của Apple, **không khởi tạo được trong unit test**. Nối thẳng StoreKit vào
/// `Entitlements` sẽ biến toàn bộ logic quyền thành vùng không test được.
struct ProProduct: Equatable, Identifiable {
    /// Gói tháng / năm (subscription tự gia hạn) hoặc mua đứt trọn đời (non-consumable).
    ///
    /// Giới hạn có chủ đích: template hỗ trợ ĐÚNG ba loại — subscription 1 tháng, subscription 1 năm, trọn đời.
    /// `Kind` là thông tin chu kỳ DUY NHẤT `ProProduct` mang theo (paywall dựng "/ month", điều khoản, nhãn
    /// analytics từ nó), nên loại khác (tuần, ngày, 3/6 tháng, 2 năm, consumable, non-renewing) bị loại khỏi danh
    /// sách sản phẩm thay vì hiển thị sai kỳ thanh toán (`LiveStoreClient.kind`). Hệ quả cần biết: cấu hình chỉ
    /// có loại không hỗ trợ ⇒ `products()` ném `productsUnavailable`; nhưng nếu user ĐÃ có giao dịch của id đó
    /// (id vẫn nằm trong `productIDs`) thì quyền vẫn cấp Pro — lọc quyền theo id cấu hình (`grantsPro`), không
    /// theo loại gói, để người đã trả tiền không bao giờ mất quyền chỉ vì paywall không hiển thị được gói của họ.
    enum Kind: String {
        case month, year, lifetime

        /// Nhãn ngắn cho analytics (`purchase_*.product`). Suy từ loại gói, KHÔNG từ product id: gửi nguyên id
        /// thì báo cáo đọc không nổi, và id còn đổi khi thêm/đổi gói.
        var analyticsName: String {
            switch self {
            case .month: return "monthly"
            case .year: return "yearly"
            case .lifetime: return "lifetime"
            }
        }
    }

    let id: String
    /// Giá ĐÃ bản địa hoá do StoreKit cấp ("123.000 ₫", "$19.99"). Không bao giờ tự dựng chuỗi này.
    let displayPrice: String
    let kind: Kind
    /// Số ngày dùng thử miễn phí của introductory offer TRÊN CHÍNH GÓI NÀY (`nil` = gói không có
    /// trial). Đọc từ StoreKit, không suy theo chu kỳ: offer bật/tắt ở App Store Connect, nên chỉ
    /// sản phẩm thật mới biết gói nào đang có trial. Đủ điều kiện hay không là chuyện của group
    /// (`isEligibleForIntroOffer`), hai thứ phải cùng đúng mới được chào dùng thử.
    /// Gói `.lifetime` LUÔN `nil`: mua đứt không có introductory offer (xem `LiveStoreClient.freeTrialDays`).
    var freeTrialDays: Int? = nil
}

/// Kết quả một lần bấm mua. Cả ba nhánh đều bình thường — `pending` và `cancelled` KHÔNG phải lỗi.
enum PurchaseOutcome: Equatable {
    case success
    /// Ask to Buy (máy trẻ em) hoặc ngân hàng đang xác thực: có thể duyệt sau nhiều giờ và sẽ
    /// về qua `transactionUpdates()`.
    case pending
    case cancelled
}

enum StoreError: Error, Equatable {
    case productsUnavailable
    case purchaseFailed(String)
    /// Chữ ký JWS không hợp lệ — máy bị can thiệp. Không cấp quyền, không tố cáo user.
    case unverified
}

/// Cửa duy nhất ra StoreKit. `@MainActor` để `Entitlements` (cũng `@MainActor`) gọi thẳng mà
/// không phải rải `Sendable`.
@MainActor
protocol StoreClient {
    func products() async throws -> [ProProduct]

    /// Quyền hiện có (subscription còn hạn HOẶC gói trọn đời chưa bị hoàn tiền). Rỗng/`false` là câu trả lời
    /// CÓ THẨM QUYỀN, kể cả offline — StoreKit 2 giữ bản sao giao dịch có chữ ký ngay trên máy.
    func currentEntitlement() async -> Bool

    /// LOẠI quyền đang hiệu lực (`nil` = không có quyền). Cùng nguồn với `currentEntitlement()`; có cả mua trọn đời
    /// lẫn subscription còn hạn ⇒ `.lifetime` (người đã mua đứt không cần "Manage subscription" — xem
    /// `Entitlements.canManageSubscription`). Có quyền mà không suy được loại (vd. không đọc được chu kỳ gói lúc
    /// offline) ⇒ `nil` — bên nhận hiểu là "không phải trọn đời".
    func currentEntitlementKind() async -> ProProduct.Kind?

    /// Đủ điều kiện dùng thử hay chưa. Thuộc tính của SUBSCRIPTION GROUP, không phải của từng gói.
    func isEligibleForIntroOffer() async -> Bool

    func purchase(_ productID: String) async throws -> PurchaseOutcome

    /// `AppStore.sync()` — CHỈ gọi khi user tự bấm Restore (nó bật hộp thoại nhập mật khẩu).
    func sync() async throws

    /// Phát một tín hiệu mỗi khi StoreKit báo giao dịch đổi (mua ở máy khác, gia hạn, hoàn tiền).
    /// Bên nhận chỉ cần gọi `refresh()`; việc `finish()` giao dịch do implementation lo.
    func transactionUpdates() -> AsyncStream<Void>

    /// Bản app đang chạy được Apple cấp ở môi trường nào: `"production"` (App Store),
    /// `"sandbox"` (TestFlight / chạy từ Xcode mua sandbox), `"xcode"` (file `.storekit`).
    /// `nil` khi không đọc được. CHỈ dùng cho analytics (`store_env`) — tách doanh thu test khỏi
    /// doanh thu thật, vì TestFlight và App Store cùng config `Release`, cùng Firebase Prod.
    func storeEnvironment() async -> String?
}

/// Client không bán được gì — chỗ giữ chỗ cho app chưa nối `LiveStoreClient` (preview, khung chưa có sản phẩm).
/// Trả về đúng sự thật: không sản phẩm, không quyền.
@MainActor
struct UnavailableStoreClient: StoreClient {
    func products() async throws -> [ProProduct] { throw StoreError.productsUnavailable }
    func currentEntitlement() async -> Bool { false }
    func currentEntitlementKind() async -> ProProduct.Kind? { nil }
    func isEligibleForIntroOffer() async -> Bool { false }
    func purchase(_ productID: String) async throws -> PurchaseOutcome {
        throw StoreError.productsUnavailable
    }
    func sync() async throws {}
    func transactionUpdates() -> AsyncStream<Void> { AsyncStream { _ in } }
    func storeEnvironment() async -> String? { nil }
}
