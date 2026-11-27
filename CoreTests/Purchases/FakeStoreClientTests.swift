@testable import AppHost
import XCTest

@MainActor
final class FakeStoreClientTests: XCTestCase {

    func testProductsTraVeStubDaSet() async throws {
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.yearly]

        let got = try await fake.products()

        XCTAssertEqual(got.count, 1)
        XCTAssertEqual(got.first?.id, TestProducts.yearlyID)
        XCTAssertEqual(fake.productsCallCount, 1)
        XCTAssertEqual(fake.callCount, 1)
    }

    func testProductsNemLoiKhiDaSetLoi() async {
        let fake = FakeStoreClient()
        fake.productsError = StoreError.productsUnavailable

        do {
            _ = try await fake.products()
            XCTFail("phải ném lỗi")
        } catch {
            XCTAssertEqual(error as? StoreError, .productsUnavailable)
        }
    }

    func testTransactionUpdatesPhatTinHieuKhiEmit() async {
        let fake = FakeStoreClient()
        let stream = fake.transactionUpdates()

        let received = Task { () -> Bool in
            for await _ in stream { return true }
            return false
        }
        // Cho stream kịp đăng ký continuation trước khi bắn.
        await Task.yield()
        fake.emitTransactionUpdate()

        let value = await received.value
        XCTAssertTrue(value)
    }
}
