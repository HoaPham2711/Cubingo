import XCTest
@testable import AppHost

final class IdleTimerCoordinatorTests: XCTestCase {

    func testMotChuConGiuThiKhongTraVeTuTat() {
        var applied: [Bool] = []
        let c = IdleTimerCoordinator(apply: { applied.append($0) })
        c.set("record", keepAwake: true)
        c.set("export", keepAwake: true)
        c.set("record", keepAwake: false)        // ghi xong nhưng export còn chạy
        XCTAssertEqual(applied, [true])          // KHÔNG được trả về tự tắt ở đây
        XCTAssertTrue(c.keepAwake)
        c.set("export", keepAwake: false)
        XCTAssertEqual(applied, [true, false])
        XCTAssertFalse(c.keepAwake)
    }

    func testKhongGhiTrungLap() {
        var applied: [Bool] = []
        let c = IdleTimerCoordinator(apply: { applied.append($0) })
        c.set("record", keepAwake: true)
        c.set("record", keepAwake: true)
        c.set("record", keepAwake: true)
        XCTAssertEqual(applied, [true])          // chỉ ghi khi giá trị ĐỔI
    }

    func testNhaChuChuaTungGiuKhongLamGi() {
        var applied: [Bool] = []
        let c = IdleTimerCoordinator(apply: { applied.append($0) })
        c.set("export", keepAwake: false)
        XCTAssertEqual(applied, [])
        XCTAssertFalse(c.keepAwake)
    }
}
