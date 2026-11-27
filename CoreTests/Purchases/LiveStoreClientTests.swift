@testable import AppHost
import StoreKitTest
import XCTest

/// Test phần NỐI StoreKit (không phải logic quyền — cái đó ở `EntitlementsTests` với fake).
/// `SKTestSession` dựng một App Store giả lập trong tiến trình test từ `CoreProducts.storekit` — fixture RIÊNG của
/// lõi (`CoreTests/Purchases/CoreProducts.storekit`, resource của TEST bundle), không phải file `.storekit` của app:
/// app đổi sản phẩm/giá/dùng thử thì test lõi không phải sửa.
///
/// Scheme chính `AppHost` SKIP class này (StoreKit có thể bật hộp thoại "Sign in to Apple Account" và treo cả
/// suite); chạy riêng: `tools/dev/run_tests.py --storekit` (scheme `AppHost-StoreKitTests`, host ký ad-hoc kèm
/// `get-task-allow` — thiếu nó storekitd không nạp cấu hình `SKTestSession` và `Product.products` trả rỗng).
@MainActor
final class LiveStoreClientTests: XCTestCase {

    // MARK: - Id sản phẩm
    // Id của fixture `CoreProducts.storekit` (không liên quan `[purchases] product_ids` của app — check_storekit.py
    // chỉ lint file `.storekit` của APP). Đổi fixture ⇒ sửa ở đây.
    private static let fixture = "CoreProducts"
    private enum ID {
        static let monthly = "test.pro.monthly"
        static let yearly = "test.pro.yearly"
        static let lifetime = "test.pro.lifetime"
        static let all = [monthly, yearly, lifetime]
    }

    private var session: SKTestSession!

    override func setUp() async throws {
        try await super.setUp()
        session = try SKTestSession(configurationFileNamed: Self.fixture)
        session.resetToDefaultState()
        session.clearTransactions()
        session.disableDialogs = true
    }

    override func tearDown() async throws {
        session = nil
        try await super.tearDown()
    }

    /// Ba sản phẩm của file `.storekit` map đúng ba loại gói — không thừa, không thiếu, không đoán.
    func testTaiDuBaGoiVaMapDungLoai() async throws {
        let products = try await LiveStoreClient(productIDs: ID.all).products()

        XCTAssertEqual(products.count, 3)
        XCTAssertEqual(products.first { $0.id == ID.monthly }?.kind, .month)
        XCTAssertEqual(products.first { $0.id == ID.yearly }?.kind, .year)
        XCTAssertEqual(products.first { $0.id == ID.lifetime }?.kind, .lifetime)
        XCTAssertTrue(products.allSatisfy { !$0.displayPrice.isEmpty }, "giá phải do StoreKit cấp, không tự dựng chuỗi")
    }

    /// Cả hai subscription có trial miễn phí 1 tuần (`CoreProducts.storekit`) — số ngày đọc từ introductory offer,
    /// paywall dùng đúng số này trên nút mua.
    func testDocSoNgayTrialTuIntroOffer() async throws {
        let products = try await LiveStoreClient(productIDs: ID.all).products()
        XCTAssertEqual(products.first { $0.id == ID.yearly }?.freeTrialDays, 7)
        XCTAssertEqual(products.first { $0.id == ID.monthly }?.freeTrialDays, 7)
    }

    func testChuaMuaThiKhongCoQuyen() async throws {
        let entitled = await LiveStoreClient(productIDs: ID.all).currentEntitlement()
        XCTAssertFalse(entitled)
    }

    func testMuaXongThiCoQuyen() async throws {
        let client = LiveStoreClient(productIDs: ID.all)

        let outcome = try await purchase(client, ID.yearly)

        XCTAssertEqual(outcome, .success)
        await waitForEntitlement(client, toBe: true)
    }

    func testAskToBuyTraVePending() async throws {
        session.askToBuyEnabled = true
        let client = LiveStoreClient(productIDs: ID.all)

        let outcome = try await purchase(client, ID.yearly)

        XCTAssertEqual(outcome, .pending, "Ask to Buy chưa duyệt thì là pending, không phải lỗi")
        let entitled = await client.currentEntitlement()
        XCTAssertFalse(entitled)
    }

    func testHoanTienThiMatQuyen() async throws {
        let client = LiveStoreClient(productIDs: ID.all)
        _ = try await purchase(client, ID.yearly)
        await waitForEntitlement(client, toBe: true)

        try refund(ID.yearly)

        await waitForEntitlement(client, toBe: false)
    }

    func testHetHanThiMatQuyen() async throws {
        let client = LiveStoreClient(productIDs: ID.all)
        _ = try await purchase(client, ID.yearly)
        await waitForEntitlement(client, toBe: true)

        try session.expireSubscription(productIdentifier: ID.yearly)

        await waitForEntitlement(client, toBe: false)
    }

    func testChuaMuaBaoGioThiDuDieuKienTrial() async throws {
        let eligible = await LiveStoreClient(productIDs: ID.all).isEligibleForIntroOffer()
        XCTAssertTrue(eligible)
    }

    // MARK: - Gói trọn đời (non-consumable) — hành vi mới, fake không thay được

    /// Giao dịch non-consumable phải hiện trong `Transaction.currentEntitlements` và cấp Pro — cả ở client lẫn
    /// qua `Entitlements` (đường app thật dùng).
    func testMuaGoiTronDoiCapQuyen() async throws {
        let client = LiveStoreClient(productIDs: ID.all)

        let outcome = try await purchase(client, ID.lifetime)

        XCTAssertEqual(outcome, .success)
        await waitForEntitlement(client, toBe: true)

        let suite = "LiveStoreClientTests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        addTeardownBlock { UserDefaults().removePersistentDomain(forName: suite) }
        let entitlements = Entitlements(client: client, defaults: defaults, internalDeviceFlag: MemoryCounterStore())
        XCTAssertFalse(entitlements.isPro)
        await entitlements.refresh()
        XCTAssertTrue(entitlements.isPro, "mua trọn đời xong mà Entitlements không lên Pro")
    }

    /// Loại quyền đọc từ giao dịch thật: chưa mua ⇒ `nil`; mua năm ⇒ `.year`; mua thêm trọn đời ⇒ `.lifetime`
    /// (trọn đời thắng subscription còn hạn).
    func testLoaiQuyenTheoGiaoDichTronDoiThang() async throws {
        let client = LiveStoreClient(productIDs: ID.all)
        let none = await client.currentEntitlementKind()
        XCTAssertNil(none)

        _ = try await purchase(client, ID.yearly)
        await waitForKind(client, toBe: .year)

        _ = try await purchase(client, ID.lifetime)
        await waitForKind(client, toBe: .lifetime)
    }

    /// Hoàn tiền gói trọn đời ⇒ giao dịch bị thu hồi ⇒ mất Pro (không có "hết hạn" cho mua đứt — refund là
    /// đường duy nhất mất quyền).
    func testHoanTienGoiTronDoiMatQuyen() async throws {
        let client = LiveStoreClient(productIDs: ID.all)
        _ = try await purchase(client, ID.lifetime)
        await waitForEntitlement(client, toBe: true)

        try refund(ID.lifetime)

        await waitForEntitlement(client, toBe: false)
    }

    /// Gói trọn đời không có dùng thử: `freeTrialDays == nil`; và app chỉ bán trọn đời thì "đủ điều kiện dùng
    /// thử" là `false` (không có subscription group nào để hỏi).
    func testGoiTronDoiKhongCoDungThu() async throws {
        let products = try await LiveStoreClient(productIDs: ID.all).products()
        let lifetime = try XCTUnwrap(products.first { $0.id == ID.lifetime })
        XCTAssertNil(lifetime.freeTrialDays)

        let onlyLifetime = LiveStoreClient(productIDs: [ID.lifetime])
        let eligible = await onlyLifetime.isEligibleForIntroOffer()
        XCTAssertFalse(eligible)
        let onlyLifetimeProducts = try await onlyLifetime.products()
        XCTAssertEqual(onlyLifetimeProducts.map(\.kind), [.lifetime])
    }

    // MARK: - Helper

    private func refund(_ productID: String) throws {
        let transaction = try XCTUnwrap(session.allTransactions().first { $0.productIdentifier == productID },
                                        "không thấy giao dịch của \(productID)")
        try session.refundTransaction(identifier: UInt(transaction.identifier))
    }

    /// `purchase` có TRẦN thời gian. Mua trong `SKTestSession` xong trong < 1s; nếu StoreKit bị chặn (vd hộp
    /// thoại "Sign in to Apple Account" của sandbox thật — xem `AppEnvironment.isUnitTestHost`) thì `purchase`
    /// chờ vô hạn và cả suite treo (đo ở app nguồn: 17 phút). Có trần thì test fail to tiếng sau vài giây, đúng chỗ.
    private func purchase(_ client: LiveStoreClient, _ id: String,
                          timeout: TimeInterval = 15) async throws -> PurchaseOutcome {
        // Chạy đua bằng continuation, KHÔNG dùng task group: group luôn chờ mọi task con kết thúc,
        // mà `purchase` bị chặn thì không phản hồi huỷ ⇒ trần vô tác dụng. Task thua bị bỏ mặc.
        final class Once { var done = false }
        let once = Once()
        return try await withCheckedThrowingContinuation { cont in
            Task { @MainActor in
                let result: Result<PurchaseOutcome, Error>
                do { result = .success(try await client.purchase(id)) } catch { result = .failure(error) }
                guard !once.done else { return }
                once.done = true
                cont.resume(with: result)
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: UInt64(timeout * 1_000_000_000))
                guard !once.done else { return }
                once.done = true
                cont.resume(throwing: PurchaseTimeout(seconds: timeout))
            }
        }
    }

    private struct PurchaseTimeout: Error, CustomStringConvertible {
        let seconds: TimeInterval
        var description: String {
            "purchase() không trả về sau \(Int(seconds))s — StoreKit bị chặn (hộp thoại đăng nhập?)"
        }
    }

    /// Như `waitForEntitlement` nhưng cho loại quyền (giao dịch vừa mua có thể chưa hiện ngay trong
    /// `currentEntitlements`).
    private func waitForKind(_ client: LiveStoreClient, toBe expected: ProProduct.Kind?,
                             timeout: TimeInterval = 20,
                             file: StaticString = #filePath, line: UInt = #line) async {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if await client.currentEntitlementKind() == expected { return }
            try? await Task.sleep(nanoseconds: 20_000_000)   // 20ms
        }
        let actual = await client.currentEntitlementKind()
        XCTAssertEqual(actual, expected, "loại quyền không đổi sang \(String(describing: expected)) trong \(timeout)s",
                       file: file, line: line)
    }

    /// Chờ tới khi quyền đổi sang giá trị mong đợi. `SKTestSession` áp dụng refund/hết hạn KHÔNG
    /// đồng bộ mà không phát tín hiệu hoàn thành nào, nên phải hỏi lại — nhưng hỏi có TRẦN. Mua
    /// cũng vậy: sau `clearTransactions` ở `setUp`, giao dịch vừa mua có thể chưa hiện trong
    /// `currentEntitlements` tới ~0,5s dù `purchase` đã trả về (đo ở app nguồn).
    /// Ngủ một khoảng cố định thì hoặc phí thời gian, hoặc fail ngắt quãng trên máy chậm; poll
    /// vừa trả lời ngay khi trạng thái tới, vừa fail to tiếng thay vì treo khi hỏng thật.
    private func waitForEntitlement(_ client: LiveStoreClient,
                                    toBe expected: Bool,
                                    timeout: TimeInterval = 20,
                                    file: StaticString = #filePath,
                                    line: UInt = #line) async {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if await client.currentEntitlement() == expected { return }
            try? await Task.sleep(nanoseconds: 20_000_000)   // 20ms
        }
        let actual = await client.currentEntitlement()
        XCTAssertEqual(actual, expected,
                       "quyền không đổi sang \(expected) trong \(timeout)s", file: file, line: line)
    }
}
