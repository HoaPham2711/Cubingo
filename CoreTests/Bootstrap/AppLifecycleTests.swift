@testable import AppHost
import SwiftUI
import XCTest

/// `AppLifecycle.handle`: nền ⇒ dấu "đang làm việc" thành do-nền (iOS kill app nền không phải sự cố), active ⇒ hết
/// do-nền + `onActive` đúng một lần. Kiểm qua store dấu thật trên thư mục tạm riêng.
final class AppLifecycleTests: XCTestCase {
    private var dir: URL!
    private var store: ActiveWorkMarkerStore!

    override func setUp() {
        super.setUp()
        dir = FileManager.default.temporaryDirectory.appendingPathComponent("AppLifecycleTests-\(UUID().uuidString)")
        store = ActiveWorkMarkerStore(directory: dir)
    }

    override func tearDown() {
        try? FileManager.default.removeItem(at: dir)
        super.tearDown()
    }

    func testNenDanhDauBackgroundedKhongGoiOnActive() {
        store.begin(kind: "work", workID: "1")
        var active = 0
        AppLifecycle.handle(.background, markers: store) { active += 1 }
        XCTAssertEqual(active, 0)
        // Dấu đã thành do-nền ⇒ lần mở sau không tính là sự cố.
        XCTAssertNil(store.takeIncident())
    }

    func testActiveBoBackgroundedVaGoiOnActiveDungMotLan() {
        store.begin(kind: "work", workID: "1")
        AppLifecycle.handle(.background, markers: store) {}
        var active = 0
        AppLifecycle.handle(.active, markers: store) { active += 1 }
        XCTAssertEqual(active, 1)
        XCTAssertEqual(store.takeIncident()?.workID, "1", "lên lại foreground ⇒ dấu lại tính là sự cố nếu chết")
    }

    func testInactiveKhongLamGi() {
        store.begin(kind: "work", workID: "1")
        var active = 0
        AppLifecycle.handle(.inactive, markers: store) { active += 1 }
        XCTAssertEqual(active, 0)
        XCTAssertEqual(store.takeIncident()?.workID, "1")
    }
}
