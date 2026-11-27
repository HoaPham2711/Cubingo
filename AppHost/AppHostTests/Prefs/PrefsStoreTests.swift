@testable import AppHost
import XCTest

@MainActor
final class PrefsStoreTests: XCTestCase {
    private var suite: String!
    private var defaults: UserDefaults!

    override func setUp() {
        suite = "test.prefs.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suite)
    }

    override func tearDown() {
        defaults.removePersistentDomain(forName: suite)
    }

    func testMacDinhVaLuuLai() {
        let store = PrefsStore(defaults: defaults)
        XCTAssertEqual(store.speed, .medium)
        XCTAssertTrue(store.haptics)
        XCTAssertTrue(store.showNotation)
        store.speed = .fast
        store.haptics = false
        store.showNotation = false
        let again = PrefsStore(defaults: defaults)
        XCTAssertEqual(again.speed, .fast)
        XCTAssertFalse(again.haptics)
        XCTAssertFalse(again.showNotation)
    }

    func testThoiLuongXoayTheoTocDo() {
        XCTAssertEqual(PrefsSpeed.slow.quarterTurnSeconds, 0.9)
        XCTAssertEqual(PrefsSpeed.medium.quarterTurnSeconds, 0.5)
        XCTAssertEqual(PrefsSpeed.fast.quarterTurnSeconds, 0.25)
    }
}
