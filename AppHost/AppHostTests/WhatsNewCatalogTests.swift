import XCTest
@testable import AppHost

/// Gác catalog What's New CỦA APP (`WhatsNewCatalog.cards`) bằng hợp đồng chung của lõi. App thêm thẻ ⇒ test này
/// chạy lại hợp đồng; thêm luật riêng của app (thứ tự ưu tiên đã duyệt, thẻ X ghi nhận event Y) thì viết thêm ở đây.
final class WhatsNewCatalogTests: XCTestCase {

    override func tearDown() {
        Track.removeUsageObserver()
        Track.reset()
        super.tearDown()
    }

    /// Bản trần cho thẻ đã đóng dấu = bản của chính app (CFBundleShortVersionString) — chỗ DUY NHẤT đọc bundle thật.
    func testCatalogDatHopDong() throws {
        let raw = try XCTUnwrap(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String)
        let bundle = try XCTUnwrap(AppVersion(raw))
        XCTAssertEqual(WhatsNewCatalog.cards.isEmpty, false, "catalog rỗng ⇒ hợp đồng pass rỗng")
        XCTAssertEqual(WhatsNewCatalogContract.violations(WhatsNewCatalog.cards, bundleVersion: bundle), [])
    }

    /// Không event lõi nào, không dấu vết nào khiến một thẻ bị coi là "đã dùng" (thẻ `welcome` không bao giờ; thẻ có
    /// luật "đã dùng" thật được test riêng cùng tính năng của nó).
    func testTheMauKhongBaoGioBiCoiLaDaDung() {
        let suite = "WhatsNewCatalogTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let ledger = FeatureUsageLedger(cards: WhatsNewCatalog.cards, defaults: defaults)
        Track.installUsageObserver(ledger)
        AppEvent.shellSamples.forEach(Track.log)
        ledger.seedFromDiskIfNeeded(probe: ClosureUsageProbe([:]))
        XCTAssertEqual(ledger.usedCards, [])
    }
}
