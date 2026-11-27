#if INTERNAL
@testable import AppHost
import XCTest

/// Override Free/Pro của build INTERNAL phải thắng giao dịch StoreKit (giao dịch cục bộ không huỷ được).
@MainActor
final class EntitlementsInternalOverrideTests: XCTestCase {

    private func defaults() throws -> UserDefaults {
        let name = "ent-ovr-\(UUID().uuidString)"
        let d = try XCTUnwrap(UserDefaults(suiteName: name))
        addTeardownBlock { d.removePersistentDomain(forName: name) }
        return d
    }

    private func make(_ fake: FakeStoreClient, _ d: UserDefaults) -> Entitlements {
        Entitlements(client: fake, defaults: d, internalDeviceFlag: MemoryCounterStore())
    }

    func testEpFreeThangGiaoDichConHieuLucVaSongQuaMoLaiApp() async throws {
        let d = try defaults()
        let fake = FakeStoreClient()
        fake.entitled = true
        let e = make(fake, d)
        await e.refresh()
        XCTAssertTrue(e.isPro)

        await e.setInternalProOverride(.free)
        XCTAssertFalse(e.isPro)
        await e.refresh()
        XCTAssertFalse(e.isPro, "refresh StoreKit không được ghi đè Ép Free")

        let reopened = make(fake, d)
        XCTAssertFalse(reopened.isPro, "cache lúc init cũng phải theo override")
        await reopened.refresh()
        XCTAssertFalse(reopened.isPro)
        XCTAssertEqual(reopened.internalProOverride, .free)
    }

    func testEpProKhiKhongCoGiaoDich() async throws {
        let e = make(FakeStoreClient(), try defaults())
        await e.setInternalProOverride(.pro)
        await e.refresh()
        XCTAssertTrue(e.isPro)
    }

    /// Override KHÔNG bịa loại quyền: Ép Pro mà không có giao dịch ⇒ loại `nil` (vẫn hiện "Manage subscription",
    /// như mọi Pro chưa rõ loại); Ép Pro trên giao dịch trọn đời thật ⇒ giữ `.lifetime`; Ép Free ⇒ không loại.
    func testOverrideKhongBiaLoaiQuyen() async throws {
        let e = make(FakeStoreClient(), try defaults())
        await e.setInternalProOverride(.pro)
        await e.refresh()
        XCTAssertNil(e.entitlementKind)
        XCTAssertTrue(e.canManageSubscription)

        let fake = FakeStoreClient()
        fake.entitled = true
        fake.entitledKind = .lifetime
        let owner = make(fake, try defaults())
        await owner.setInternalProOverride(.pro)
        await owner.refresh()
        XCTAssertEqual(owner.entitlementKind, .lifetime)
        XCTAssertFalse(owner.canManageSubscription)

        await owner.setInternalProOverride(.free)
        XCTAssertNil(owner.entitlementKind)
        await owner.refresh()
        XCTAssertNil(owner.entitlementKind)
        XCTAssertFalse(owner.canManageSubscription)
    }

    func testVeStoreKitThiLayLaiQuyenThat() async throws {
        let fake = FakeStoreClient()
        fake.entitled = true
        let e = make(fake, try defaults())
        await e.setInternalProOverride(.free)
        XCTAssertFalse(e.isPro)
        await e.setInternalProOverride(.storeKit)
        XCTAssertTrue(e.isPro)
        XCTAssertEqual(e.internalProOverride, .storeKit)
    }
}
#endif
