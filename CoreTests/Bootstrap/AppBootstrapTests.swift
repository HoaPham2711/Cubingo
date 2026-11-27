@testable import AppHost
import SwiftUI
import XCTest

/// Gác chuỗi khởi động: chạy đúng thứ tự khai báo, bỏ bước theo môi trường (host unit test / route `-uiPreview`), thứ
/// tự chuẩn của lõi và cổng StoreKit. Cấu hình dựng tường minh (`AppConfig(info:)`) — không đọc cấu hình thật.
final class AppBootstrapTests: XCTestCase {

    override func tearDown() {
        Track.removeUsageObserver()
        super.tearDown()
    }

    private func ledger() -> FeatureUsageLedger {
        let suite = "AppBootstrapTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        addTeardownBlock { defaults.removePersistentDomain(forName: suite) }
        return FeatureUsageLedger(cards: [], defaults: defaults)
    }

    func testChayDungThuTuKhaiBao() {
        var log: [String] = []
        let ran = AppBootstrap.run([.init(name: "a") { log.append("a") }, .init(name: "b") { log.append("b") }],
                                   isUnitTestHost: false, uiPreviewRoute: nil)
        XCTAssertEqual(ran, ["a", "b"]); XCTAssertEqual(log, ["a", "b"])
    }

    func testHostTestBoBuocDanhDau() {
        var log: [String] = []
        let ran = AppBootstrap.run([.init(name: "tips") { log.append("tips") },
                                    .init(name: "telemetry", skipInUnitTestHost: false) { log.append("telemetry") }],
                                   isUnitTestHost: true, uiPreviewRoute: nil)
        XCTAssertEqual(ran, ["telemetry"])
        XCTAssertEqual(log, ["telemetry"], "bước bị bỏ không được chạy closure")
    }

    func testPreviewBoBuocDanhDau() {
        var log: [String] = []
        let steps: [LaunchStep] = [.init(name: "a", skipInUnitTestHost: false, skipInUIPreview: true) { log.append("a") },
                                   .init(name: "b", skipInUnitTestHost: false) { log.append("b") }]
        XCTAssertEqual(AppBootstrap.run(steps, isUnitTestHost: false, uiPreviewRoute: "home"), ["b"])
        XCTAssertEqual(log, ["b"])
        // Không có route ⇒ chạy đủ.
        XCTAssertEqual(AppBootstrap.run(steps, isUnitTestHost: false, uiPreviewRoute: nil), ["a", "b"])
    }

    /// R16 (không còn bước "attribution" riêng — `TelemetryBootstrap.start` tự khởi động) + R17 (`purgeTmp` ngay sau
    /// `takeIncident`, trước mọi bước có thể ghi tmp).
    func testBuocChuanDungThuTu() {
        let names = AppBootstrap.standardSteps(config: .init(info: [:]), usageLedger: nil, tmpDirs: []).map(\.name)
        XCTAssertEqual(names, ["takeIncident", "purgeTmp", "telemetry", "firstLaunchSim", "tips"])
    }

    /// Có ledger What's New ⇒ ghi nhận "đã dùng" gắn TRƯỚC telemetry (không lỡ event nào của lần mở).
    func testBuocChuanCoLedgerGanQuanSatTruocTelemetry() {
        let names = AppBootstrap.standardSteps(config: .init(info: [:]), usageLedger: ledger(), tmpDirs: []).map(\.name)
        XCTAssertEqual(names, ["takeIncident", "purgeTmp", "usageObserver", "telemetry", "firstLaunchSim", "tips"])
    }

    /// Chỉ `telemetry` chạy được trong host (bản thân nó no-op ở đó): host không đọc/xoá dấu sự cố, không dọn tmp,
    /// không gắn quan sát, không ghi datastore TipKit. StoreKit/mạng không phải bước khởi động — xem `skipsStoreKit`.
    func testBuocChuanTrongHostTestKhongChamStoreTipTmp() {
        let ran = AppBootstrap.run(AppBootstrap.standardSteps(config: .init(info: [:]), usageLedger: ledger(), tmpDirs: []),
                                   isUnitTestHost: true, uiPreviewRoute: nil)
        XCTAssertEqual(ran, ["telemetry"])
        XCTAssertFalse(ran.contains("tips")); XCTAssertFalse(ran.contains("purgeTmp")); XCTAssertFalse(ran.contains("takeIncident"))
    }

    /// Route `-uiPreview`: không dọn tmp, không ghi datastore TipKit (và không giả lập lần đầu — nó xoá cờ onboarding
    /// mà route vừa ép).
    func testBuocChuanTrongPreviewKhongDonTmpKhongTip() {
        let steps = AppBootstrap.standardSteps(config: .init(info: [:]), usageLedger: nil, tmpDirs: [])
        let ran = AppBootstrap.run(steps, isUnitTestHost: false, uiPreviewRoute: "home")
        XCTAssertEqual(ran, ["takeIncident", "telemetry"])
    }

    func testBoStoreKitKhiHostTestHoacPreviewKhongCanStore() {
        XCTAssertTrue(AppBootstrap.skipsStoreKit(isUnitTestHost: true, uiPreviewRoute: nil, routesNeedingStore: ["paywall"]))
        XCTAssertTrue(AppBootstrap.skipsStoreKit(isUnitTestHost: true, uiPreviewRoute: "paywall", routesNeedingStore: ["paywall"]))
        XCTAssertTrue(AppBootstrap.skipsStoreKit(isUnitTestHost: false, uiPreviewRoute: "home", routesNeedingStore: ["paywall"]))
        XCTAssertFalse(AppBootstrap.skipsStoreKit(isUnitTestHost: false, uiPreviewRoute: "paywall", routesNeedingStore: ["paywall"]))
        XCTAssertFalse(AppBootstrap.skipsStoreKit(isUnitTestHost: false, uiPreviewRoute: nil, routesNeedingStore: ["paywall"]))
    }

    /// Mạng lúc mở app (kiểm tra cập nhật): không bao giờ trong host test, không trong route preview.
    func testBoMangKhiHostTestHoacPreview() {
        XCTAssertTrue(AppBootstrap.skipsNetwork(isUnitTestHost: true, uiPreviewRoute: nil))
        XCTAssertTrue(AppBootstrap.skipsNetwork(isUnitTestHost: false, uiPreviewRoute: "home"))
        XCTAssertFalse(AppBootstrap.skipsNetwork(isUnitTestHost: false, uiPreviewRoute: nil))
    }

    /// Chính tiến trình này là host unit test ⇒ giá trị mặc định (đọc môi trường thật) phải bỏ StoreKit.
    func testMacDinhTrongHostTestBoStoreKit() {
        XCTAssertTrue(AppEnvironment.isUnitTestHost)
        XCTAssertTrue(AppBootstrap.skipsStoreKit(routesNeedingStore: ["paywall"]))
        XCTAssertTrue(AppBootstrap.skipsNetwork())
    }
}

/// Bộ quyết định "onboarding xong": side effect của app chạy TRƯỚC khi bật cờ.
final class AppRootGateTests: XCTestCase {
    func testWillFinishChayTruocKhiBatCo() {
        var log: [String] = []
        AppRootGate<EmptyView, EmptyView>.completeOnboarding(willFinish: { log.append("willFinish") },
                                                            markSeen: { log.append("markSeen") })
        XCTAssertEqual(log, ["willFinish", "markSeen"])
    }

    func testKhoaCoLaKhoaCuaWhatsNew() {
        XCTAssertEqual(AppRootGate<EmptyView, EmptyView>.flagKey, WhatsNewHost.hasSeenOnboardingKey)
        XCTAssertEqual(WhatsNewHost.hasSeenOnboardingKey, "hasSeenOnboarding")
    }
}
