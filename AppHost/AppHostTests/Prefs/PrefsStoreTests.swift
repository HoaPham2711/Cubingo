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
        // Người dùng thử máy thật: 0,5 s quá nhanh để kịp nhìn ⇒ chậm hơn ở mọi mức.
        XCTAssertEqual(PrefsSpeed.slow.quarterTurnSeconds, 1.4)
        XCTAssertEqual(PrefsSpeed.medium.quarterTurnSeconds, 0.9)
        XCTAssertEqual(PrefsSpeed.fast.quarterTurnSeconds, 0.5)
        // Dừng một nhịp có mũi tên trước khi quay.
        XCTAssertEqual(PrefsSpeed.medium.leadInSeconds, 0.45, accuracy: 1e-9)
    }
}
