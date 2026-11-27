@testable import AppHost
import XCTest

final class SmokeTests: XCTestCase {
    func testCoInternalBatOCauHinhTest() {
        XCTAssertTrue(InternalBuild.isEnabled)
    }
    func testBundleIDHostLaBanInternal() {
        // So với khoá Info `AppBundleIDInternal`, không so hậu tố: bundle id internal do cấu hình đặt.
        XCTAssertEqual(Bundle.main.bundleIdentifier,
                       Bundle.main.object(forInfoDictionaryKey: "AppBundleIDInternal") as? String)
    }

    /// Quyết định 7 của plan: paywall tắt = app miễn phí hoàn toàn — Settings không có mục Account, mọi thứ mở.
    /// Cấu hình dựng tường minh (ruling R2), không đọc giá trị thật của template.
    @MainActor
    func testPaywallTatThiSettingsKhongCoAccount() {
        let tat = AppConfig(info: ["FeaturePaywall": "NO", "ProductIDs": "a b"])
        let bat = AppConfig(info: ["FeaturePaywall": "YES", "ProductIDs": "a b"])
        XCTAssertFalse(SettingsModel.showsAccount(config: tat))
        XCTAssertTrue(SettingsModel.showsAccount(config: bat))
        // `Entitlements` vẫn dựng được khi tắt (Settings/paywall nhận nó) và coi như Pro, không chạm StoreKit.
        let e = Entitlements.live(config: tat)
        XCTAssertFalse(e.paywallEnabled)
        XCTAssertTrue(e.isPro)
    }

    /// Route preview của app: tên ổn định (lệnh chụp ảnh dùng chuỗi), chỉ `onboarding` hiện tour, không route nào chạm
    /// StoreKit thật (paywall vẽ bằng store giả của Simulator).
    func testRoutePreviewCuaApp() {
        // Sáu route của khung luôn có; route riêng của tính năng (nếu có) đứng sau.
        let shellRoutes = ["home", "onboarding", "settings", "paywall", "whatsNew", "feedback"]
        XCTAssertEqual(AppPreview.allCases.map(\.rawValue), shellRoutes)
        XCTAssertEqual(AppPreview.allCases.filter(\.isOnboarding), [.onboarding])
        XCTAssertEqual(AppPreview.routesNeedingStore, [])
        XCTAssertEqual(AppPreview.settings.initialTab, .settings)
        XCTAssertEqual(AppPreview.home.initialTab, .home)
        XCTAssertNil(AppPreview.onboarding.onboardingInitialPage)
    }

    #if targetEnvironment(simulator)
    /// Store giả của route `paywall` không được trôi khỏi file `.storekit` (resource của test bundle): cùng id, giá,
    /// có/không dùng thử — ảnh chụp paywall là bằng chứng "ba gói với giá mẫu".
    @MainActor
    func testStoreGiaCuaPreviewKhopFileStorekit() throws {
        let url = try XCTUnwrap(Bundle(for: SmokeTests.self).url(forResource: "Products", withExtension: "storekit"))
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        var sk: [[String: Any]] = json["products"] as? [[String: Any]] ?? []
        for g in json["subscriptionGroups"] as? [[String: Any]] ?? [] {
            sk += g["subscriptions"] as? [[String: Any]] ?? []
        }
        let ids = sk.compactMap { $0["productID"] as? String }
        let preview = AppPreviewStore.products(productIDs: ids)
        XCTAssertEqual(preview.count, 3)
        XCTAssertEqual(Set(preview.map(\.id)), Set(ids))
        for p in preview {
            let item = try XCTUnwrap(sk.first { $0["productID"] as? String == p.id })
            XCTAssertEqual(p.displayPrice, "$" + (item["displayPrice"] as? String ?? ""), p.id)
            let trial = (item["introductoryOffer"] as? [String: Any])?["subscriptionPeriod"] as? String
            XCTAssertEqual(p.freeTrialDays, trial == "P1W" ? 7 : nil, p.id)
        }
    }
    #endif

    /// Paywall: link điều khoản dựng từ host web của cấu hình (Guideline 3.1.2), MỘT nhóm, ít hàng (đọc xong trong
    /// một màn — `PaywallContent`).
    func testPaywallMauDungTuCauHinh() {
        let c = AppPaywall.content(config: AppConfig(info: ["WebHost": "host.test"]))
        XCTAssertEqual(c.termsURL?.absoluteString, "https://host.test/terms/")
        XCTAssertEqual(c.privacyURL?.absoluteString, "https://host.test/privacy/")
        XCTAssertEqual(c.sections.count, 1)
        XCTAssertTrue((2...4).contains(c.sections.first?.rows.count ?? 0))
        XCTAssertNil(AppPaywall.content(config: AppConfig(info: [:])).termsURL)
    }

    /// Tour: mở đầu bằng Welcome, kết bằng Ready. Xem lại bỏ Welcome nhưng KHÔNG rỗng ⇒ hàng "Show app tour" có mặt.
    func testTourXemLaiKhongRong() {
        let first = AppOnboarding.flow(.firstRun).pages
        XCTAssertEqual(first.first, .welcome)
        XCTAssertEqual(first.last, .ready)
        let replay = AppOnboarding.flow(.replay)
        XCTAssertFalse(replay.isEmpty)
        XCTAssertFalse(replay.pages.contains(.welcome))
    }

    /// Nút thẻ What's New với khoá không có đích: resolver trả `nil`, runner không đổi tab.
    @MainActor
    func testWhatsNewKhoaLaKhongCoDichKhongDoiTab() {
        XCTAssertNil(AppWhatsNew.resolve(WhatsNewAction(key: "no_such_key")))
        let router = AppTabRouter()
        AppWhatsNew.perform(WhatsNewResolvedAction(key: "no_such_key"), tabs: router)
        XCTAssertNil(router.requested)
    }
}
