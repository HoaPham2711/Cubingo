@testable import AppHost
import XCTest

/// Loại quyền (`entitlementKind` + `canManageSubscription`) và trạng thái "Restore đang chạy" của `Entitlements`.
@MainActor
final class EntitlementsKindRestoreTests: XCTestCase {

    private func freshDefaults() throws -> UserDefaults {
        let name = "ent-kind-\(UUID().uuidString)"
        let d = try XCTUnwrap(UserDefaults(suiteName: name))
        addTeardownBlock { d.removePersistentDomain(forName: name) }
        return d
    }

    private func make(_ client: StoreClient, paywallEnabled: Bool = true,
                      defaults: UserDefaults) -> Entitlements {
        Entitlements(client: client, paywallEnabled: paywallEnabled, defaults: defaults,
                     internalDeviceFlag: MemoryCounterStore())
    }

    // MARK: - Loại quyền

    /// Mua đứt không có gói để quản lý/huỷ ⇒ không hiện "Manage subscription".
    func testMuaTronDoiThiKhongQuanLyGoi() async throws {
        let fake = FakeStoreClient()
        fake.entitled = true
        fake.entitledKind = .lifetime
        let e = make(fake, defaults: try freshDefaults())

        await e.refresh()

        XCTAssertTrue(e.isPro)
        XCTAssertEqual(e.entitlementKind, .lifetime)
        XCTAssertFalse(e.canManageSubscription)
    }

    func testGoiNamThiCoQuanLyGoi() async throws {
        let fake = FakeStoreClient()
        fake.entitled = true
        fake.entitledKind = .year
        let e = make(fake, defaults: try freshDefaults())

        await e.refresh()

        XCTAssertEqual(e.entitlementKind, .year)
        XCTAssertTrue(e.canManageSubscription)
    }

    /// Đọc loại có thể chờ mạng ⇒ `refresh()` mở Pro TRƯỚC, loại về sau (paywall đóng không đợi cú gọi mạng).
    func testRefreshMoProTruocKhiDocXongLoai() async throws {
        let fake = FakeStoreClient()
        fake.entitled = true
        fake.entitledKind = .year
        let e = make(fake, defaults: try freshDefaults())
        XCTAssertFalse(e.isPro)
        fake.gateNextKindCall()

        let task = Task { await e.refresh() }
        await fake.waitUntilKindGated()
        XCTAssertTrue(e.isPro, "đang chờ đọc loại mà chưa mở Pro")
        XCTAssertNil(e.entitlementKind, "loại chưa đọc xong")

        fake.releaseGatedKind()
        await task.value
        XCTAssertTrue(e.isPro)
        XCTAssertEqual(e.entitlementKind, .year)
    }

    /// Refresh A đang chờ đọc loại (cũ: năm), refresh B chạy xong với loại mới (tháng) ⇒ A thả ra không ghi đè.
    func testRefreshCuDangChoLoaiKhongGhiDeLoaiMoi() async throws {
        let fake = FakeStoreClient()
        fake.entitled = true
        fake.entitledKind = .year
        let e = make(fake, defaults: try freshDefaults())
        fake.gateNextKindCall()

        let first = Task { await e.refresh() }
        await fake.waitUntilKindGated()
        fake.entitledKind = .month
        await e.refresh()
        XCTAssertEqual(e.entitlementKind, .month)

        fake.releaseGatedKind()
        await first.value
        XCTAssertEqual(e.entitlementKind, .month, "refresh cũ thả ra sau đã ghi đè loại mới")
        XCTAssertTrue(e.isPro)
    }

    /// Pro mà chưa rõ loại (offline chưa đọc được chu kỳ) ⇒ vẫn cho quản lý gói; Free ⇒ không.
    func testProChuaRoLoaiVanQuanLyGoiFreeThiKhong() async throws {
        let fake = FakeStoreClient()
        fake.entitled = true
        let e = make(fake, defaults: try freshDefaults())
        XCTAssertFalse(e.canManageSubscription, "Free không có gì để quản lý")

        await e.refresh()

        XCTAssertNil(e.entitlementKind)
        XCTAssertTrue(e.canManageSubscription)
    }

    /// Loại được cache cùng `defaults` với `isPro` ⇒ mở lại app thấy ngay ở khung hình đầu (không nháy hàng
    /// "Manage subscription" với người mua trọn đời).
    func testLoaiQuyenDuocCacheVaDocLaiLucDung() async throws {
        let d = try freshDefaults()
        let fake = FakeStoreClient()
        fake.entitled = true
        fake.entitledKind = .lifetime
        await make(fake, defaults: d).refresh()
        XCTAssertEqual(d.string(forKey: Entitlements.kindKey), "lifetime")

        let reopened = make(FakeStoreClient(), defaults: d)
        XCTAssertEqual(reopened.entitlementKind, .lifetime, "cache loại phải sống qua lần khởi động sau")
        XCTAssertFalse(reopened.canManageSubscription)

        // Giá trị lạ trong cache ⇒ `nil`, không crash, không đoán.
        d.set("weekly", forKey: Entitlements.kindKey)
        XCTAssertNil(make(FakeStoreClient(), defaults: d).entitlementKind)
    }

    /// Mất quyền (hoàn tiền) ⇒ loại về `nil` VÀ cache loại bị xoá — không còn sót "lifetime" cho lần mở sau.
    func testMatQuyenThiXoaLoaiVaCache() async throws {
        let d = try freshDefaults()
        let fake = FakeStoreClient()
        fake.entitled = true
        fake.entitledKind = .lifetime
        let e = make(fake, defaults: d)
        await e.refresh()
        XCTAssertEqual(e.entitlementKind, .lifetime)

        fake.entitled = false
        await e.refresh()

        XCTAssertFalse(e.isPro)
        XCTAssertNil(e.entitlementKind)
        XCTAssertNil(d.object(forKey: Entitlements.kindKey), "cache loại phải bị xoá khi mất quyền")
    }

    /// Paywall tắt (app miễn phí): không có loại quyền, không ghi cache, không gọi store.
    func testPaywallTatThiKhongCoLoaiQuyen() async throws {
        let d = try freshDefaults()
        d.set("lifetime", forKey: Entitlements.kindKey)
        let fake = FakeStoreClient()
        fake.entitled = true
        fake.entitledKind = .year
        let e = make(fake, paywallEnabled: false, defaults: d)

        XCTAssertNil(e.entitlementKind, "cache cũ không được nổi lên ở app miễn phí")
        await e.refresh()
        _ = await e.restore()

        XCTAssertNil(e.entitlementKind)
        XCTAssertEqual(d.string(forKey: Entitlements.kindKey), "lifetime", "paywall tắt ⇒ không ghi/xoá cache")
        XCTAssertEqual(fake.callCount, 0)
    }

    // MARK: - Restore đang chạy

    func testRestoreDangChayThiCoCo() async throws {
        let fake = FakeStoreClient()
        fake.entitled = true
        fake.gateNextSync()
        let e = make(fake, defaults: try freshDefaults())
        XCTAssertFalse(e.isRestoring)

        let task = Task { await e.restore() }
        await fake.waitUntilSyncGated()
        XCTAssertTrue(e.isRestoring, "đang chờ sync() ⇒ cờ phải bật")

        fake.releaseGatedSync()
        let outcome = await task.value

        XCTAssertEqual(outcome, .restored)
        XCTAssertFalse(e.isRestoring, "restore xong ⇒ cờ phải tắt")
    }

    /// Lỗi sync cũng phải hạ cờ — nếu không nút Restore khoá vĩnh viễn tới lần mở app sau.
    func testRestoreLoiCungTatCo() async throws {
        let fake = FakeStoreClient()
        fake.syncError = StoreError.purchaseFailed("network")
        fake.gateNextSync()
        let e = make(fake, defaults: try freshDefaults())

        let task = Task { await e.restore() }
        await fake.waitUntilSyncGated()
        XCTAssertTrue(e.isRestoring)
        fake.releaseGatedSync()

        let outcome = await task.value
        XCTAssertEqual(outcome, .failed)
        XCTAssertFalse(e.isRestoring)
    }

    /// Bấm Restore lần hai khi lượt đầu chưa xong ⇒ KHÔNG gọi `sync()` lần nữa (thêm một hộp thoại mật khẩu), cả
    /// hai nhận cùng kết quả; cờ chỉ hạ khi lượt chung kết thúc.
    func testRestoreChongKhongGoiStoreHaiLan() async throws {
        let fake = FakeStoreClient()
        fake.entitled = false
        fake.gateNextSync()
        let e = make(fake, defaults: try freshDefaults())

        let first = Task { await e.restore() }
        await fake.waitUntilSyncGated()
        let second = Task { await e.restore() }
        // Thả gate từ một Task xếp hàng SAU `second` trên main actor (thực thi FIFO): `second` chắc chắn đã vào
        // `restore()` và đang chờ lượt chung trước khi sync() được thả — không đoán bằng sleep/yield.
        let release = Task {
            XCTAssertTrue(e.isRestoring)
            fake.releaseGatedSync()
        }
        await release.value
        let a = await first.value
        let b = await second.value

        XCTAssertEqual(fake.syncCallCount, 1, "lượt chồng không được gọi store lần hai")
        XCTAssertEqual(a, .noPurchasesFound)
        XCTAssertEqual(b, .noPurchasesFound)
        XCTAssertFalse(e.isRestoring)

        // Lượt sau khi đã xong là lượt MỚI — phải gọi store lại.
        _ = await e.restore()
        XCTAssertEqual(fake.syncCallCount, 2)
    }
}
