#if DEBUG
@testable import AppHost
import XCTest

/// `purchase_success` phải bắn đúng một lần cho mỗi lần quyền chuyển không→có; phễu mua có đúng một lối ra.
@MainActor
final class MonetizationTelemetryTests: XCTestCase {

    private var sink: RecordingSink!
    private var defaults: UserDefaults!
    private let suite = "MonetizationTelemetryTests"

    override func setUp() {
        super.setUp()
        UserDefaults().removePersistentDomain(forName: suite)
        defaults = UserDefaults(suiteName: suite)
        sink = RecordingSink()
        Track.install(sink)
    }

    override func tearDown() {
        Track.reset()
        UserDefaults().removePersistentDomain(forName: suite)
        sink = nil
        defaults = nil
        super.tearDown()
    }

    /// Cờ "máy nội bộ" trên bộ nhớ: test không ghi Keychain thật của host.
    private func make(_ client: StoreClient, paywallEnabled: Bool = true,
                      flag: SecureCounterStore = MemoryCounterStore()) -> Entitlements {
        Entitlements(client: client, paywallEnabled: paywallEnabled, defaults: defaults, internalDeviceFlag: flag)
    }

    func testCapQuyenProBanPurchaseSuccessMotLan() {
        let e = make(FakeStoreClient())
        e.setProForInternalTesting(true)
        XCTAssertEqual(sink.names.filter { $0 == "purchase_success" }.count, 1)
    }

    /// `refresh()` gọi `setPro(true)` mỗi lần app vào foreground với người đã mua. Bắn vô điều
    /// kiện là đếm mỗi lần mở app thành một lần mua.
    func testCapQuyenProLanHaiKhongBanThem() {
        let e = make(FakeStoreClient())
        e.setProForInternalTesting(true)
        e.setProForInternalTesting(true)
        XCTAssertEqual(sink.names.filter { $0 == "purchase_success" }.count, 1,
                       "quyền đã có sẵn thì không phải một lần mua mới")
    }

    /// Cùng bất biến qua đường thật: refresh lặp lại (mỗi lần vào foreground) với người đã mua.
    func testRefreshLapLaiKhongBanThemPurchaseSuccess() async {
        let fake = FakeStoreClient()
        fake.entitled = true
        let e = make(fake)
        await e.refresh()
        await e.refresh()
        await e.refresh()
        XCTAssertEqual(sink.names.filter { $0 == "purchase_success" }.count, 1)
    }

    func testMatQuyenRoiCoLaiThiBanTiep() {
        let e = make(FakeStoreClient())
        e.setProForInternalTesting(true)
        e.setProForInternalTesting(false)
        e.setProForInternalTesting(true)
        XCTAssertEqual(sink.names.filter { $0 == "purchase_success" }.count, 2)
    }

    // MARK: - Phễu mua hàng

    /// Sản phẩm phải được tải trước (như lúc paywall mở): nhãn analytics suy từ `kind` của sản phẩm đã tải.
    private func muaVoi(_ ketQua: Result<PurchaseOutcome, Error>, entitled: Bool = false,
                        trial: Bool = true, id: String = TestProducts.yearlyID) async -> [AppEvent] {
        let fake = FakeStoreClient()
        fake.purchaseResult = ketQua
        fake.eligibleForIntroOffer = trial
        fake.stubProducts = [TestProducts.monthly, TestProducts.yearly, TestProducts.lifetime]
        let e = make(fake)
        await e.refresh()                    // nạp `isEligibleForTrial` như lúc mở paywall
        await e.loadProducts()
        sink.clear()
        fake.entitled = entitled
        await e.purchase(id)
        return sink.events
    }

    /// `purchase_start` có đúng MỘT lối ra — thiếu nhánh nào là tỉ lệ rơi ở bước trả tiền sai.
    func testMuaThanhCongBanStartRoiSuccessKemTrial() async {
        let ev = await muaVoi(.success(.success), entitled: true)
        XCTAssertEqual(ev, [.purchaseStart(product: "yearly", trial: true),
                            .purchaseSuccess(product: "yearly", trial: true)])
    }

    func testHetQuyenDungThuThiTrialFalse() async {
        let ev = await muaVoi(.success(.success), entitled: true, trial: false)
        XCTAssertEqual(ev, [.purchaseStart(product: "yearly", trial: false),
                            .purchaseSuccess(product: "yearly", trial: false)])
    }

    func testHuyMuaBanCancel() async {
        let ev = await muaVoi(.success(.cancelled))
        XCTAssertEqual(ev.map(\.name), ["purchase_start", "purchase_cancel"])
    }

    func testChoDuyetBanPending() async {
        let ev = await muaVoi(.success(.pending))
        XCTAssertEqual(ev.map(\.name), ["purchase_start", "purchase_pending"])
    }

    func testMuaLoiBanFail() async {
        let ev = await muaVoi(.failure(StoreError.unverified))
        XCTAssertEqual(ev.map(\.name), ["purchase_start", "purchase_fail"])
    }

    /// Gói trọn đời: nhãn `lifetime`, và KHÔNG BAO GIỜ là lượt mua có dùng thử — kể cả khi group subscription
    /// còn đủ điều kiện dùng thử (đủ điều kiện là của group, không phải của gói mua đứt).
    func testMuaTronDoiNhanLifetimeKhongTrial() async {
        let ev = await muaVoi(.success(.success), entitled: true, trial: true, id: TestProducts.lifetimeID)
        XCTAssertEqual(ev, [.purchaseStart(product: "lifetime", trial: false),
                            .purchaseSuccess(product: "lifetime", trial: false)])
    }

    /// Nhãn suy từ `kind`, không từ id: id lạ của app (không chứa chữ "monthly") vẫn ra `monthly`.
    func testNhanSanPhamTheoKindKhongTheoId() async {
        let ev = await muaVoi(.success(.cancelled), id: TestProducts.monthlyID)
        XCTAssertEqual(ev.first, .purchaseStart(product: "monthly", trial: true))
    }

    /// Bấm mua khi StoreKit không trả gói: phễu vẫn thấy cú bấm + lý do, không im lặng. Chưa tải được gói nào
    /// ⇒ không biết `kind` ⇒ nhãn `unknown`.
    func testSubscribeKhongCoGoiBanStartRoiFailKemLyDo() async {
        let fake = FakeStoreClient()
        fake.productsError = StoreError.productsUnavailable
        fake.eligibleForIntroOffer = false
        let e = make(fake)
        await e.refresh()
        await e.loadProducts()
        sink.clear()
        await e.subscribe(TestProducts.yearlyID)
        XCTAssertEqual(sink.events, [.purchaseStart(product: "unknown", trial: false),
                                     .purchaseFail(product: "unknown", reason: "products_unavailable")])
    }

    /// Id lạ (không có trong danh sách đã tải): phễu thấy cú bấm + lý do, nhãn `unknown`, đúng một `purchase_fail`.
    func testSubscribeIdLaBanStartRoiFailUnknown() async {
        let fake = FakeStoreClient()
        fake.stubProducts = [TestProducts.monthly, TestProducts.yearly]
        fake.eligibleForIntroOffer = false
        let e = make(fake)
        await e.refresh()
        await e.loadProducts()
        sink.clear()
        await e.subscribe("test.not.listed")
        XCTAssertEqual(sink.events, [.purchaseStart(product: "unknown", trial: false),
                                     .purchaseFail(product: "unknown", reason: "products_unavailable")])
        XCTAssertTrue(fake.purchasedIDs.isEmpty)
    }

    /// Quyền về từ restore không phải một lượt mua có dùng thử — `trial` phải false.
    func testKhoiPhucBanRestoreResultVaSuccessKhongTrial() async {
        let fake = FakeStoreClient()
        let e = make(fake)
        await e.refresh()
        sink.clear()
        fake.entitled = true
        _ = await e.restore()
        XCTAssertEqual(sink.events, [.purchaseSuccess(product: "unknown", trial: false),
                                     .restoreResult(outcome: "restored")])
    }

    func testKhoiPhucKhongCoGiBanNone() async {
        let e = make(FakeStoreClient())
        _ = await e.restore()
        XCTAssertEqual(sink.events, [.restoreResult(outcome: "none")])
    }

    /// Mỗi lần đổi quyền phải cập nhật user property — thiếu nó thì báo cáo không cắt lát được
    /// theo free/Pro.
    func testDoiQuyenThiCapNhatUserProperty() {
        let e = make(FakeStoreClient())
        e.setProForInternalTesting(true)
        XCTAssertEqual(sink.properties.last?.name, "is_pro")
        XCTAssertEqual(sink.properties.last?.value, "true")
    }

    /// Paywall tắt: không phễu mua, không `is_pro` — gán `is_pro=true` cho mọi user của app miễn phí là bơm
    /// rác vào đúng chiều cắt lát Free/Pro của báo cáo.
    func testPaywallTatKhongBanEventVaKhongGanIsPro() async {
        let fake = FakeStoreClient()
        fake.entitled = true
        fake.environment = "sandbox"
        let e = make(fake, paywallEnabled: false)
        e.start()
        await e.refresh()
        await e.subscribe(TestProducts.yearlyID)
        await e.purchase(TestProducts.yearlyID)
        _ = await e.restore()
        await e.syncStoreEnvironment()
        e.setProForInternalTesting(true)
        try? await Task.sleep(nanoseconds: 50_000_000)
        XCTAssertTrue(sink.events.isEmpty, "\(sink.names)")
        XCTAssertTrue(sink.properties.isEmpty, "\(sink.properties.map(\.name))")
    }

    /// TestFlight và App Store cùng đổ về một Firebase Prod — thiếu `store_env` thì doanh thu sandbox
    /// (gia hạn 5 phút/lần) trộn lẫn doanh thu thật và không tách ra được nữa.
    func testGanStoreEnvTheoMoiTruongCuaStore() async {
        let client = FakeStoreClient()
        client.environment = "sandbox"
        let e = make(client)
        await e.syncStoreEnvironment()
        XCTAssertEqual(sink.properties.filter { $0.name == "store_env" }.map(\.value), ["sandbox"])
    }

    func testKhongDocDuocMoiTruongThiKhongGanStoreEnv() async {
        let client = FakeStoreClient()
        client.environment = nil
        let e = make(client)
        await e.syncStoreEnvironment()
        XCTAssertFalse(sink.properties.contains { $0.name == "store_env" },
                       "gán bừa một giá trị là nhuộm bẩn nhóm production")
    }

    /// Máy dev tải app từ App Store mang `store_env = production` y như khách. Cờ Keychain là thứ
    /// duy nhất tách được: một lần thấy sandbox là đủ, và phải còn nguyên khi sau đó máy chạy bản
    /// App Store (kể cả sau gỡ app cài lại — cùng một store).
    func testMayTungChaySandboxMangNhanNoiBoCaKhiVeProduction() async {
        let co = MemoryCounterStore()
        let client = FakeStoreClient()
        client.environment = "sandbox"
        await make(client, flag: co).syncStoreEnvironment()
        XCTAssertEqual(co.value, 1)
        let truoc = sink.properties.count

        client.environment = "production"
        await make(client, flag: co).syncStoreEnvironment()
        let sau = sink.properties.dropFirst(truoc)
        XCTAssertEqual(sau.filter { $0.name == "internal_device" }.map(\.value), ["true"])
        XCTAssertEqual(sau.filter { $0.name == "store_env" }.map(\.value), ["production"])
    }

    /// Chiều ngược lại mới là chỗ mất tiền: gắn nhầm khách thật thành nội bộ là xoá họ khỏi báo cáo.
    func testKhachChiChayProductionKhongMangNhanNoiBo() async {
        let co = MemoryCounterStore()
        let client = FakeStoreClient()
        client.environment = "production"
        await make(client, flag: co).syncStoreEnvironment()
        XCTAssertEqual(co.value, 0)
        XCTAssertFalse(sink.properties.contains { $0.name == "internal_device" })
    }
}
#endif
