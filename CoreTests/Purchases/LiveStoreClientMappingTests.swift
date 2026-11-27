@testable import AppHost
import StoreKit
import XCTest

/// Phần THUẦN của `LiveStoreClient` (map sản phẩm StoreKit → `ProProduct`, lọc quyền), test được không cần
/// `SKTestSession`. Đường StoreKit thật (mua, hoàn tiền, hết hạn) là việc của `LiveStoreClientTests` với fixture
/// `CoreProducts.storekit`. `import StoreKit` ở đây chỉ để dựng giá trị enum/struct của Apple làm đầu vào.
@MainActor
final class LiveStoreClientMappingTests: XCTestCase {

    private func kind(_ type: Product.ProductType, _ unit: Product.SubscriptionPeriod.Unit?,
                      _ value: Int?) -> ProProduct.Kind? {
        LiveStoreClient.kind(productType: type, subscriptionUnit: unit, subscriptionValue: value)
    }

    /// Non-consumable ⇒ trọn đời, bất kể tham số chu kỳ.
    func testNonConsumableLaTronDoi() {
        XCTAssertEqual(kind(.nonConsumable, nil, nil), .lifetime)
        XCTAssertEqual(kind(.nonConsumable, .month, 3), .lifetime)
    }

    func testSubscriptionThangNamTheoChuKy() {
        XCTAssertEqual(kind(.autoRenewable, .month, 1), .month)
        XCTAssertEqual(kind(.autoRenewable, .year, 1), .year)
    }

    /// Loại không bán được như Pro ⇒ bỏ (không đoán): consumable, non-renewing, chu kỳ tuần/ngày, và chu kỳ
    /// nhiều tháng/nhiều năm — gắn nhãn "monthly"/"/ month" cho gói 3 tháng là nói sai kỳ thanh toán.
    func testLoaiKhongHoTroThiBo() {
        XCTAssertNil(kind(.consumable, nil, nil))
        XCTAssertNil(kind(.nonRenewable, nil, nil))
        XCTAssertNil(kind(.autoRenewable, nil, nil))
        XCTAssertNil(kind(.autoRenewable, .week, 1))
        XCTAssertNil(kind(.autoRenewable, .day, 1))
        XCTAssertNil(kind(.autoRenewable, .month, 3))
        XCTAssertNil(kind(.autoRenewable, .month, 6))
        XCTAssertNil(kind(.autoRenewable, .year, 2))
        XCTAssertNil(kind(.autoRenewable, .month, nil))
    }

    /// Gói mua đứt không bao giờ mang số ngày dùng thử — copy "free trial" trên nó là sai giá (Guideline 3.1.2).
    func testTronDoiKhongBaoGioCoNgayDungThu() {
        XCTAssertNil(LiveStoreClient.freeTrialDays(kind: .lifetime, freeTrialPeriod: (unit: .week, value: 1)))
        XCTAssertNil(LiveStoreClient.freeTrialDays(kind: .lifetime, freeTrialPeriod: (unit: .day, value: 3)))
    }

    func testNgayDungThuQuyTheoNgayTuan() {
        XCTAssertEqual(LiveStoreClient.freeTrialDays(kind: .year, freeTrialPeriod: (unit: .week, value: 1)), 7)
        XCTAssertEqual(LiveStoreClient.freeTrialDays(kind: .month, freeTrialPeriod: (unit: .day, value: 3)), 3)
        XCTAssertNil(LiveStoreClient.freeTrialDays(kind: .year, freeTrialPeriod: nil), "không có offer miễn phí")
        // Kỳ tháng/năm không quy ra ngày (độ dài lịch thay đổi) ⇒ nil, copy rơi về không trial.
        XCTAssertNil(LiveStoreClient.freeTrialDays(kind: .year, freeTrialPeriod: (unit: .month, value: 1)))
    }

    /// Danh sách ĐÃ MAP rỗng ⇒ "không có sản phẩm", không trả `[]` cho UI.
    func testDanhSachDaMapRongThiNemKhongCoSanPham() {
        XCTAssertThrowsError(try LiveStoreClient.requireNonEmpty([])) {
            XCTAssertEqual($0 as? StoreError, .productsUnavailable)
        }
        XCTAssertEqual(try LiveStoreClient.requireNonEmpty([TestProducts.lifetime]), [TestProducts.lifetime])
    }

    /// Giao dịch trọn đời (non-consumable) có trong `currentEntitlements` cấp Pro như subscription; bị hoàn tiền
    /// (revoked) hoặc id ngoài cấu hình thì không.
    func testGiaoDichTronDoiCapQuyenTruKhiBiThuHoi() {
        let ids = [TestProducts.monthlyID, TestProducts.lifetimeID]
        XCTAssertTrue(LiveStoreClient.grantsPro(productID: TestProducts.lifetimeID, revoked: false, productIDs: ids))
        XCTAssertFalse(LiveStoreClient.grantsPro(productID: TestProducts.lifetimeID, revoked: true, productIDs: ids))
        XCTAssertFalse(LiveStoreClient.grantsPro(productID: "other.app.item", revoked: false, productIDs: ids))
    }

    /// Nhiều quyền cùng lúc ⇒ trọn đời thắng (mua đứt không cần quản lý gói), rồi năm, rồi tháng; rỗng ⇒ `nil`.
    func testLoaiQuyenManhNhatTronDoiThang() {
        XCTAssertEqual(LiveStoreClient.strongestKind([.month, .lifetime, .year]), .lifetime)
        XCTAssertEqual(LiveStoreClient.strongestKind([.month, .year]), .year)
        XCTAssertEqual(LiveStoreClient.strongestKind([.month]), .month)
        XCTAssertNil(LiveStoreClient.strongestKind([]))
    }
}
