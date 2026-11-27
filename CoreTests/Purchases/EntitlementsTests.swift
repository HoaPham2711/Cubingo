@testable import AppHost
import XCTest

@MainActor
final class EntitlementsTests: XCTestCase {

    private func freshDefaults() throws -> UserDefaults {
        let name = "ent-test-\(UUID().uuidString)"
        let d = try XCTUnwrap(UserDefaults(suiteName: name))
        addTeardownBlock { d.removePersistentDomain(forName: name) }
        return d
    }

    /// Kho cờ "máy nội bộ" trên bộ nhớ — test không chạm Keychain thật của host.
    private func make(_ client: StoreClient, paywallEnabled: Bool = true,
                      defaults: UserDefaults? = nil) throws -> Entitlements {
        Entitlements(client: client, paywallEnabled: paywallEnabled, defaults: try defaults ?? freshDefaults(),
                     internalDeviceFlag: MemoryCounterStore())
    }

    func testMacDinhKhongPro() throws {
        let e = try make(FakeStoreClient())
        XCTAssertFalse(e.isPro)
    }

    func testMoLaiAppCacheVanSong() async throws {
        let d = try freshDefaults()
        let fake = FakeStoreClient()
        fake.entitled = true

        let first = try make(fake, defaults: d)
        await first.refresh()
        XCTAssertTrue(first.isPro)

        // Mở lại app: cache phải còn, nếu không người đã trả tiền bị nháy về free ở khung hình đầu.
        let second = try make(fake, defaults: d)
        XCTAssertTrue(second.isPro, "cache chống nháy phải sống qua lần khởi động sau")
    }

    // MARK: - Paywall tắt (app miễn phí hoàn toàn)

    func testPaywallTatThiLuonProVaKhongGoiStore() async throws {
        let fake = FakeStoreClient()
        let e = try make(fake, paywallEnabled: false)

        e.start()
        await e.refresh()
        // Cho mọi Task mà start() có thể đã tạo kịp chạy — bắt cả lời gọi bất đồng bộ, không chỉ lời gọi đồng bộ.
        try await Task.sleep(nanoseconds: 50_000_000)

        XCTAssertTrue(e.isPro)
        XCTAssertEqual(fake.callCount, 0, "paywall tắt ⇒ không một lời gọi StoreKit nào")
    }

    func testPaywallTatThiMuaVaKhoiPhucKhongGoiStore() async throws {
        let fake = FakeStoreClient()
        let d = try freshDefaults()
        let e = try make(fake, paywallEnabled: false, defaults: d)

        await e.loadProducts()
        await e.subscribe(TestProducts.yearlyID)
        await e.purchase(TestProducts.yearlyID)
        let outcome = await e.restore()
        await e.syncStoreEnvironment()

        XCTAssertEqual(fake.callCount, 0)
        XCTAssertTrue(fake.purchasedIDs.isEmpty)
        XCTAssertEqual(outcome, .restored, "app miễn phí: user đã có mọi thứ")
        XCTAssertTrue(e.isPro)
        XCTAssertNil(e.purchaseError)
        XCTAssertNil(d.object(forKey: Entitlements.key), "không ghi cache quyền khi paywall tắt")
    }

    /// Cache cũ "không Pro" (app từng bật paywall rồi tắt) không được khoá gì ở app miễn phí.
    func testPaywallTatThangCacheKhongPro() throws {
        let d = try freshDefaults()
        d.set(false, forKey: Entitlements.key)
        let e = try make(FakeStoreClient(), paywallEnabled: false, defaults: d)
        XCTAssertTrue(e.isPro)
    }

    func testDungTuCauHinhTatPaywallThiLuonPro() {
        let config = AppConfig(info: ["FeaturePaywall": "NO", "ProductIDs": "test.a test.b"])
        let e = Entitlements.live(config: config)
        e.start()
        XCTAssertTrue(e.isPro)
        XCTAssertFalse(e.paywallEnabled)
    }

    // MARK: - refresh

    func testRefreshRongThiHaQuyen() async throws {
        let d = try freshDefaults()
        let fake = FakeStoreClient()
        fake.entitled = true
        let e = try make(fake, defaults: d)
        await e.refresh()
        XCTAssertTrue(e.isPro)

        // Hết hạn / hoàn tiền: currentEntitlements rỗng là câu trả lời CÓ THẨM QUYỀN.
        fake.entitled = false
        await e.refresh()

        XCTAssertFalse(e.isPro)
        XCTAssertFalse(d.bool(forKey: Entitlements.key), "cache phải đi theo, không được giữ Pro cũ")
    }

    func testRefreshGhiCacheKhiCoQuyen() async throws {
        let d = try freshDefaults()
        let fake = FakeStoreClient()
        fake.entitled = true

        let e = try make(fake, defaults: d)
        await e.refresh()

        XCTAssertTrue(d.bool(forKey: Entitlements.key))
    }

    func testKhoiDongLanhDocCacheTruocKhiRefreshTraLoi() throws {
        let d = try freshDefaults()
        d.set(true, forKey: Entitlements.key)

        let e = try make(FakeStoreClient(), defaults: d)

        XCTAssertTrue(e.isPro, "khung hình đầu phải giữ Pro, không nháy Pro→free")
    }

    /// `start()` cố ý chạy song song listener và refresh khởi động. Nếu refresh khởi động
    /// đọc quyền TRƯỚC (`false`) nhưng kết thúc (ghi) SAU một refresh khác đã đọc `true`, thì
    /// người vừa trả tiền ở máy khác bị ghi đè về free — LẦN KẾT THÚC SAU thắng, không phải LẦN
    /// ĐỌC SAU. `refreshGeneration` phải chặn được cú ghi đè bằng dữ liệu cũ này.
    func testRefreshChongLapKetThucSauKhongDuocGhiDeDuLieuMoiHon() async throws {
        let fake = FakeStoreClient()
        fake.entitled = false
        let e = try make(fake)

        // refreshA khởi động trước, bị gate ngay trong currentEntitlement() — nó đã CHỤP "false".
        fake.gateNextEntitlementCall()
        let refreshA = Task { await e.refresh() }
        await fake.waitUntilEntitlementGated()

        // Trong lúc refreshA còn treo: user mua ở máy khác. refreshB đọc "true" và chạy XONG trước.
        fake.entitled = true
        await e.refresh()
        XCTAssertTrue(e.isPro, "refreshB phải ghi Pro trước khi refreshA tỉnh dậy")

        // Thả refreshA: nó tỉnh dậy với "false" đã chụp TRƯỚC đó rồi cố ghi — phải bị bỏ vì cũ hơn.
        fake.releaseGatedEntitlement()
        await refreshA.value

        XCTAssertTrue(e.isPro, "refresh() kết thúc sau (refreshA) mang dữ liệu CŨ không được ghi đè refreshB")
    }

    // MARK: - loadProducts

    func testLoadProductsLoiKhongDungToiQuyen() async throws {
        let fake = FakeStoreClient()
        fake.entitled = true
        let e = try make(fake)
        await e.refresh()

        fake.productsError = StoreError.productsUnavailable
        await e.loadProducts()

        XCTAssertEqual(e.loadState, .failed)
        XCTAssertTrue(e.products.isEmpty)
        XCTAssertTrue(e.isPro, "mất mạng khi tải GIÁ không được đụng tới QUYỀN")
    }

    func testLoadProductsThanhCongDatReady() async throws {
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.monthly, TestProducts.yearly]
        let e = try make(fake)

        await e.loadProducts()

        XCTAssertEqual(e.loadState, .ready)
        XCTAssertEqual(e.products.count, 2)
    }

    // MARK: - Danh sách sản phẩm: chỉ trọn đời / chỉ subscription / rỗng

    func testDanhSachChiCoGoiTronDoi() async throws {
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.lifetime]
        fake.eligibleForIntroOffer = false   // không có subscription ⇒ client thật trả false
        let e = try make(fake)

        await e.refresh()
        await e.loadProducts()

        XCTAssertEqual(e.loadState, .ready)
        XCTAssertEqual(e.products.map(\.kind), [.lifetime])
        XCTAssertNil(e.products.first?.freeTrialDays)
        XCTAssertFalse(e.isEligibleForTrial)
        XCTAssertFalse(e.isPro)
    }

    func testDanhSachChiCoSubscription() async throws {
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.monthly, TestProducts.yearly]
        let e = try make(fake)

        await e.refresh()
        await e.loadProducts()

        XCTAssertEqual(e.loadState, .ready)
        XCTAssertEqual(e.products.map(\.kind), [.month, .year])
        XCTAssertTrue(e.isEligibleForTrial)
    }

    /// Rỗng = "không có sản phẩm" (như `LiveStoreClient` định nghĩa), KHÔNG phải `.ready` với 0 gói — nếu không
    /// paywall hiện sẵn sàng mà không có gói nào, CTA vẫn bật và lần bấm sau tính tiền một id không hiển thị.
    func testDanhSachRongThiCoiNhuKhongCoSanPham() async throws {
        let fake = FakeStoreClient()
        fake.stubProducts = []
        let e = try make(fake)

        await e.loadProducts()
        XCTAssertEqual(e.loadState, .failed)
        XCTAssertEqual(e.productsErrorCode, "products_unavailable")

        await e.subscribe(TestProducts.yearlyID)
        XCTAssertTrue(fake.purchasedIDs.isEmpty, "không có gói thì không được gọi mua")
        XCTAssertNotNil(e.purchaseError)
        XCTAssertFalse(e.isPro)
    }

    // MARK: - Gói trọn đời

    func testGoiTronDoiCapQuyenPro() async throws {
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.yearly, TestProducts.lifetime]
        fake.purchaseResult = .success(.success)
        let e = try make(fake)
        await e.loadProducts()

        // Giao dịch non-consumable nằm trong currentEntitlements ⇒ client báo có quyền.
        fake.entitled = true
        await e.subscribe(TestProducts.lifetimeID)

        XCTAssertEqual(fake.purchasedIDs, [TestProducts.lifetimeID])
        XCTAssertTrue(e.isPro)
    }

    /// Mua trọn đời rồi mở lại app: quyền đến từ refresh như mọi gói khác (không có hạn, không hết hạn).
    func testGoiTronDoiSongQuaRefresh() async throws {
        let d = try freshDefaults()
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.lifetime]
        fake.entitled = true
        let e = try make(fake, defaults: d)
        await e.loadProducts()
        await e.purchase(TestProducts.lifetimeID)
        XCTAssertTrue(e.isPro)

        let reopened = try make(fake, defaults: d)
        await reopened.refresh()
        XCTAssertTrue(reopened.isPro)
    }

    // MARK: - subscribe (nút mua không bao giờ im lặng)

    func testSubscribeKhiKhongTaiDuocGoiThiBaoLoiKemMa() async throws {
        let fake = FakeStoreClient()
        fake.productsError = URLError(.notConnectedToInternet)
        let e = try make(fake)
        await e.loadProducts()
        XCTAssertEqual(e.loadState, .failed)
        let truoc = fake.productsCallCount

        await e.subscribe(TestProducts.yearlyID)

        XCTAssertEqual(fake.productsCallCount, truoc + 1, "bấm khi chưa có gói phải thử tải lại")
        XCTAssertTrue(fake.purchasedIDs.isEmpty, "không có gói thì không được gọi mua")
        let msg = try XCTUnwrap(e.purchaseError, "bấm mua mà không có gói phải hiện alert, không im lặng")
        XCTAssertTrue(msg.contains("NSURLErrorDomain#-1009"), msg)
        XCTAssertFalse(e.isPurchasing)
    }

    func testSubscribeKhiGoiChuaTaiMaTaiLaiDuocThiChuaMuaNgay() async throws {
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.yearly]
        let e = try make(fake)
        XCTAssertEqual(e.loadState, .loading)

        await e.subscribe(TestProducts.yearlyID)

        XCTAssertEqual(e.loadState, .ready)
        XCTAssertTrue(fake.purchasedIDs.isEmpty, "user chưa thấy giá thì chưa được tính tiền")
        XCTAssertNil(e.purchaseError)
    }

    func testSubscribeKhiGoiSanSangThiMua() async throws {
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.yearly]
        fake.purchaseResult = .success(.success)
        let e = try make(fake)
        await e.loadProducts()
        fake.entitled = true

        await e.subscribe(TestProducts.yearlyID)

        XCTAssertEqual(fake.purchasedIDs, [TestProducts.yearlyID])
        XCTAssertTrue(e.isPro)
    }

    /// Id không nằm trong danh sách đã tải (paywall không hiển thị nó) ⇒ coi như "không có sản phẩm": không gọi
    /// mua, có alert. API nhận chuỗi id nên mọi app đều có thể gọi nhầm — không được tính tiền thứ user chưa thấy giá.
    func testSubscribeIdKhongCoTrongDanhSachThiKhongMua() async throws {
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.monthly, TestProducts.yearly]
        let e = try make(fake)
        await e.loadProducts()

        await e.subscribe(TestProducts.lifetimeID)

        XCTAssertTrue(fake.purchasedIDs.isEmpty, "id không hiển thị thì không được gọi mua")
        let msg = try XCTUnwrap(e.purchaseError)
        XCTAssertTrue(msg.contains("products_unavailable"), msg)
        XCTAssertFalse(e.isPurchasing)
        XCTAssertEqual(e.loadState, .ready, "danh sách đã tải vẫn còn nguyên")
    }

    /// Đối chứng: id có trong danh sách đã tải thì mua như thường.
    func testSubscribeIdCoTrongDanhSachThiMua() async throws {
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.monthly, TestProducts.yearly]
        let e = try make(fake)
        await e.loadProducts()

        await e.subscribe(TestProducts.monthlyID)

        XCTAssertEqual(fake.purchasedIDs, [TestProducts.monthlyID])
        XCTAssertNil(e.purchaseError)
    }

    func testMuaLoiHeThongThiAlertKemMaLoi() async throws {
        let fake = FakeStoreClient()
        fake.purchaseResult = .failure(URLError(.timedOut))
        let e = try make(fake)

        await e.purchase(TestProducts.yearlyID)

        let msg = try XCTUnwrap(e.purchaseError)
        XCTAssertTrue(msg.contains("NSURLErrorDomain#-1001"), msg)
    }

    func testErrorCode() {
        XCTAssertEqual(Entitlements.errorCode(StoreError.productsUnavailable), "products_unavailable")
        XCTAssertEqual(Entitlements.errorCode(StoreError.unverified), "unverified")
        XCTAssertEqual(Entitlements.errorCode(URLError(.notConnectedToInternet)), "NSURLErrorDomain#-1009")
    }

    // MARK: - purchase

    func testMuaThanhCongThiLenPro() async throws {
        let fake = FakeStoreClient()
        fake.purchaseResult = .success(.success)
        let e = try make(fake)

        // StoreKit cấp quyền xong thì refresh mới thấy — mô phỏng đúng thứ tự đó.
        fake.entitled = true
        await e.purchase(TestProducts.yearlyID)

        XCTAssertTrue(e.isPro)
        XCTAssertEqual(fake.purchasedIDs, [TestProducts.yearlyID])
        XCTAssertFalse(e.isPurchasing)
    }

    func testMuaPendingKhongCapQuyenVaBaoChoDuyet() async throws {
        let fake = FakeStoreClient()
        fake.purchaseResult = .success(.pending)
        let e = try make(fake)

        await e.purchase(TestProducts.yearlyID)

        XCTAssertFalse(e.isPro, "Ask to Buy chưa được duyệt thì chưa có quyền")
        XCTAssertTrue(e.isPending)
        XCTAssertNil(e.purchaseError, "pending KHÔNG phải lỗi")
    }

    func testMuaBiHuyThiKhongSinhLoi() async throws {
        let fake = FakeStoreClient()
        fake.purchaseResult = .success(.cancelled)
        let e = try make(fake)

        await e.purchase(TestProducts.yearlyID)

        XCTAssertFalse(e.isPro)
        XCTAssertNil(e.purchaseError, "bấm Huỷ là ý định của user, không được báo lỗi")
        XCTAssertFalse(e.isPending)
    }

    func testChuKySaiThiKhongCapQuyen() async throws {
        let fake = FakeStoreClient()
        fake.purchaseResult = .failure(StoreError.unverified)
        fake.entitled = false
        let e = try make(fake)

        await e.purchase(TestProducts.yearlyID)

        XCTAssertFalse(e.isPro)
        XCTAssertNotNil(e.purchaseError)
    }

    // MARK: - dismiss

    func testDismissPendingHaCo() async throws {
        let fake = FakeStoreClient()
        fake.purchaseResult = .success(.pending)
        let e = try make(fake)
        await e.purchase(TestProducts.yearlyID)
        XCTAssertTrue(e.isPending)

        e.dismissPending()

        XCTAssertFalse(e.isPending)
    }

    func testPendingDuocDuyetThiHaCoChoDuyet() async throws {
        let fake = FakeStoreClient()
        fake.purchaseResult = .success(.pending)
        let e = try make(fake)
        await e.purchase(TestProducts.yearlyID)
        XCTAssertTrue(e.isPending)

        // Ask to Buy được duyệt: listener gọi refresh(), quyền về.
        fake.entitled = true
        await e.refresh()

        XCTAssertFalse(e.isPending, "duyệt xong mà còn kẹt isPending thì alert chờ-duyệt chồng lên trạng thái đã Pro")
        XCTAssertTrue(e.isPro)
    }

    // MARK: - restore

    func testRestoreTimThayThiBatPro() async throws {
        let fake = FakeStoreClient()
        fake.entitled = true
        let e = try make(fake)

        let result = await e.restore()

        XCTAssertEqual(result, .restored)
        XCTAssertTrue(e.isPro)
        XCTAssertEqual(fake.syncCallCount, 1)
    }

    func testRestoreKhongThayThiBaoKhongCoGiaoDich() async throws {
        let fake = FakeStoreClient()
        fake.entitled = false
        let e = try make(fake)

        let result = await e.restore()

        XCTAssertEqual(result, .noPurchasesFound)
        XCTAssertFalse(e.isPro)
    }

    func testRestoreLoiSyncVanKhongSap() async throws {
        let fake = FakeStoreClient()
        fake.syncError = StoreError.purchaseFailed("network")
        fake.entitled = false
        let e = try make(fake)

        let result = await e.restore()

        XCTAssertEqual(result, .failed, "mất mạng giữa chừng KHÔNG được lẫn với chưa từng mua")
        XCTAssertEqual(fake.syncCallCount, 1, "phải thử sync thật, không được đoán")
    }

    func testRestoreLoiSyncKhongHaQuyenNguoiDangCoPro() async throws {
        let fake = FakeStoreClient()
        fake.entitled = true
        let e = try make(fake)
        await e.refresh()
        XCTAssertTrue(e.isPro)

        fake.syncError = StoreError.purchaseFailed("network")
        let result = await e.restore()

        XCTAssertEqual(result, .failed)
        XCTAssertTrue(e.isPro, "lỗi mạng giữa chừng không được hạ quyền người đang có Pro")
    }

    // MARK: - trial

    func testTrialEligibilityTheoClient() async throws {
        let fake = FakeStoreClient()
        fake.eligibleForIntroOffer = false
        let e = try make(fake)

        await e.refresh()

        XCTAssertFalse(e.isEligibleForTrial)
    }
}
