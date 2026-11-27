@testable import AppHost
import Foundation

/// Test double cho `StoreClient`. Mọi ca hiểm (pending, hoàn tiền, chữ ký sai, mất mạng) dựng
/// được bằng cách set thuộc tính, không cần StoreKit.
@MainActor
final class FakeStoreClient: StoreClient {

    var stubProducts: [ProProduct] = []
    var productsError: Error?
    var entitled = false
    /// Loại quyền trả về khi `entitled` (không có quyền ⇒ luôn `nil`, như StoreKit). Mặc định `nil` ("chưa rõ
    /// loại") để các test cũ chỉ đặt `entitled` giữ nguyên nghĩa.
    var entitledKind: ProProduct.Kind?
    var eligibleForIntroOffer = true
    var purchaseResult: Result<PurchaseOutcome, Error> = .success(.success)
    var syncError: Error?
    var environment: String? = "production"

    /// Đếm MỌI lời gọi vào protocol — gác "paywall tắt ⇒ không chạm StoreKit" (một con số, không sót hàm nào).
    private(set) var callCount = 0
    private(set) var productsCallCount = 0
    private(set) var syncCallCount = 0
    private(set) var purchasedIDs: [String] = []

    private var continuation: AsyncStream<Void>.Continuation?

    // MARK: - Gate cho sync() — dựng ca "Restore đang chạy"

    private var shouldGateNextSync = false
    private var syncGateContinuation: CheckedContinuation<Void, Never>?
    private var syncGateReachedContinuation: CheckedContinuation<Void, Never>?

    /// Lần gọi `sync()` TIẾP THEO treo cho tới `releaseGatedSync()` (lỗi `syncError` nếu có vẫn ném SAU khi thả).
    func gateNextSync() {
        shouldGateNextSync = true
    }

    /// Trả về khi `sync()` bị gate đã THỰC SỰ treo — đồng bộ bằng tín hiệu, không đoán bằng `Task.yield()`.
    func waitUntilSyncGated() async {
        guard syncGateContinuation == nil else { return }
        await withCheckedContinuation { syncGateReachedContinuation = $0 }
    }

    func releaseGatedSync() {
        syncGateContinuation?.resume()
        syncGateContinuation = nil
    }

    // MARK: - Gate cho currentEntitlement() — dựng ca `refresh()` chồng lấn

    private var shouldGateNextEntitlementCall = false
    private var gateContinuation: CheckedContinuation<Void, Never>?
    private var gateReachedContinuation: CheckedContinuation<Void, Never>?

    /// Lần gọi `currentEntitlement()` TIẾP THEO sẽ chụp `entitled` NGAY (mô phỏng "đã đọc xong",
    /// giống StoreKit đã lấy được giá trị) rồi treo tại `await` cho tới khi test gọi
    /// `releaseGatedEntitlement()`. Nhờ vậy test dựng được: cuộc gọi A đọc giá trị CŨ nhưng ghi
    /// (kết thúc) SAU cuộc gọi B đọc giá trị MỚI hơn.
    func gateNextEntitlementCall() {
        shouldGateNextEntitlementCall = true
    }

    /// Trả về khi cuộc gọi bị gate ở trên đã THỰC SỰ treo — đồng bộ hoá bằng tín hiệu, không đoán
    /// thời điểm bằng `Task.yield()`.
    func waitUntilEntitlementGated() async {
        guard gateContinuation == nil else { return }
        await withCheckedContinuation { gateReachedContinuation = $0 }
    }

    func releaseGatedEntitlement() {
        gateContinuation?.resume()
        gateContinuation = nil
    }

    // MARK: - Gate cho currentEntitlementKind() — dựng ca "đọc loại đang chờ mạng"

    private var shouldGateNextKindCall = false
    private var kindGateContinuation: CheckedContinuation<Void, Never>?
    private var kindGateReachedContinuation: CheckedContinuation<Void, Never>?

    /// Lần gọi `currentEntitlementKind()` TIẾP THEO chụp kết quả NGAY rồi treo cho tới `releaseGatedKind()` —
    /// mô phỏng `Product.products(for:)` đang chờ mạng.
    func gateNextKindCall() {
        shouldGateNextKindCall = true
    }

    /// Trả về khi lần đọc loại bị gate đã THỰC SỰ treo (tín hiệu, không `Task.yield()`).
    func waitUntilKindGated() async {
        guard kindGateContinuation == nil else { return }
        await withCheckedContinuation { kindGateReachedContinuation = $0 }
    }

    func releaseGatedKind() {
        kindGateContinuation?.resume()
        kindGateContinuation = nil
    }

    /// Giả lập StoreKit đẩy một giao dịch về (gia hạn, mua ở máy khác, hoàn tiền). Chưa ai gọi
    /// `transactionUpdates()` thì tín hiệu rơi mất — đúng như StoreKit khi chưa có listener.
    func emitTransactionUpdate() {
        continuation?.yield(())
    }

    func products() async throws -> [ProProduct] {
        callCount += 1
        productsCallCount += 1
        if let productsError { throw productsError }
        return stubProducts
    }

    func currentEntitlement() async -> Bool {
        callCount += 1
        guard shouldGateNextEntitlementCall else { return entitled }
        shouldGateNextEntitlementCall = false
        let snapshot = entitled
        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            gateContinuation = cont
            gateReachedContinuation?.resume()
            gateReachedContinuation = nil
        }
        return snapshot
    }

    func currentEntitlementKind() async -> ProProduct.Kind? {
        callCount += 1
        let snapshot = entitled ? entitledKind : nil
        guard shouldGateNextKindCall else { return snapshot }
        shouldGateNextKindCall = false
        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            kindGateContinuation = cont
            kindGateReachedContinuation?.resume()
            kindGateReachedContinuation = nil
        }
        return snapshot
    }

    func isEligibleForIntroOffer() async -> Bool {
        callCount += 1
        return eligibleForIntroOffer
    }

    func purchase(_ productID: String) async throws -> PurchaseOutcome {
        callCount += 1
        purchasedIDs.append(productID)
        return try purchaseResult.get()
    }

    func sync() async throws {
        callCount += 1
        syncCallCount += 1
        if shouldGateNextSync {
            shouldGateNextSync = false
            await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
                syncGateContinuation = cont
                syncGateReachedContinuation?.resume()
                syncGateReachedContinuation = nil
            }
        }
        if let syncError { throw syncError }
    }

    func storeEnvironment() async -> String? {
        callCount += 1
        return environment
    }

    func transactionUpdates() -> AsyncStream<Void> {
        callCount += 1
        return AsyncStream { continuation in
            self.continuation = continuation
        }
    }
}

/// Kho đếm trên bộ nhớ cho test logic (Keychain cần app được ký — host test chạy không ký).
final class MemoryCounterStore: SecureCounterStore {
    var value = 0
    var failRead = false
    var failWrite = false
    private(set) var writeCount = 0

    func read() throws -> Int {
        if failRead { throw NSError(domain: "test", code: 1) }
        return value
    }

    func write(_ v: Int) throws {
        if failWrite { throw NSError(domain: "test", code: 2) }
        writeCount += 1
        value = v
    }
}

/// Bộ sản phẩm mẫu cho test — id giả, KHÔNG phụ thuộc cấu hình thật của app (`AppConfig.productIDs`).
enum TestProducts {
    static let monthlyID = "test.pro.monthly"
    static let yearlyID = "test.pro.yearly"
    static let lifetimeID = "test.pro.lifetime"

    static let monthly = ProProduct(id: monthlyID, displayPrice: "$2.99", kind: .month, freeTrialDays: 7)
    static let yearly = ProProduct(id: yearlyID, displayPrice: "$19.99", kind: .year, freeTrialDays: 7)
    static let lifetime = ProProduct(id: lifetimeID, displayPrice: "$49.99", kind: .lifetime)
}
