@testable import AppHost
import XCTest

/// Ghim hành vi vòng đời của `Entitlements.start()`: listener phải gắn TRƯỚC khi đọc quyền,
/// nếu không giao dịch App Store đẩy về đúng lúc khởi động sẽ bị rơi mất.
@MainActor
final class EntitlementsLifecycleTests: XCTestCase {

    private func make(_ fake: FakeStoreClient) throws -> Entitlements {
        let name = "ent-life-\(UUID().uuidString)"
        let d = try XCTUnwrap(UserDefaults(suiteName: name))
        addTeardownBlock { d.removePersistentDomain(forName: name) }
        return Entitlements(client: fake, defaults: d, internalDeviceFlag: MemoryCounterStore())
    }

    func testStartGanListenerTruocKhiDocQuyen() async throws {
        let fake = FakeStoreClient()
        let e = try make(fake)

        e.start()
        // Chờ refresh() khởi động lắng xuống ở "chưa có quyền". Không có bước này thì refresh()
        // khởi động (chạy song song, vô điều kiện) mới là thứ bật isPro — và test vẫn xanh kể cả
        // khi listener bị xoá khỏi start().
        try await waitUntil { e.loadState != .loading }
        XCTAssertFalse(e.isPro, "chưa có giao dịch nào thì chưa được có quyền")

        // Từ đây, đường DUY NHẤT làm isPro lên true là listener.
        fake.entitled = true
        fake.emitTransactionUpdate()

        try await waitUntil { e.isPro }
        XCTAssertTrue(e.isPro, "giao dịch về sau khi start phải được nghe thấy, không rơi")
    }

    /// Khe hở cụ thể: giao dịch đến TRONG LÚC refresh khởi động còn đang đọc quyền. Listener gắn sau lần đọc đó
    /// thì tín hiệu rơi mất, refresh khởi động ghi "không quyền" đã chụp từ trước ⇒ người vừa trả tiền thấy Free.
    func testGiaoDichVeTrongKheRefreshKhoiDongKhongBiNuot() async throws {
        let fake = FakeStoreClient()
        let e = try make(fake)

        fake.gateNextEntitlementCall()
        e.start()
        // Lần đọc quyền ĐẦU TIÊN của start() đã chụp "false" và đang treo.
        await fake.waitUntilEntitlementGated()

        fake.entitled = true
        fake.emitTransactionUpdate()
        fake.releaseGatedEntitlement()

        try await waitUntil { e.isPro && e.loadState != .loading }
        XCTAssertTrue(e.isPro, "giao dịch đến trong khe khởi động phải được nghe thấy")
    }

    func testStartGoiHaiLanKhongGanListenerHaiLan() async throws {
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.yearly]
        let e = try make(fake)

        e.start()
        try await waitUntil { e.loadState == .ready }
        let callsAfterFirstStart = fake.productsCallCount

        e.start()
        // Cho lần start thứ hai đủ thời gian gây hại nếu guard hỏng.
        try await Task.sleep(nanoseconds: 100_000_000)

        XCTAssertEqual(fake.productsCallCount, callsAfterFirstStart,
                       "start() lần hai phải bị guard chặn, không chạy lại vòng khởi động")
    }

    /// Chờ điều kiện đúng, tối đa 2s — tránh test bập bênh vì Task chạy không đồng bộ.
    private func waitUntil(_ condition: @MainActor () -> Bool) async throws {
        for _ in 0..<200 {
            if condition() { return }
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        XCTFail("điều kiện không đạt trong 2s")
    }
}
