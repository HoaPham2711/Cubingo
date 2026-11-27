@testable import AppHost
import XCTest

@MainActor
final class FlowModelTests: XCTestCase {
    func testChiChonDuocKhoiDangCo() {
        let flow = FlowModel()
        flow.choose(.cube2)
        XCTAssertTrue(flow.path.isEmpty)
        XCTAssertNil(flow.puzzle)
        flow.choose(.cube3)
        XCTAssertEqual(flow.path, [.scan])
        XCTAssertEqual(flow.puzzle, .cube3)
        XCTAssertEqual(FlowPuzzle.allCases.filter(\.isAvailable), [.cube3])
    }

    func testStartOverXoaHet() {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.path.append(.mode)
        flow.startOver()
        XCTAssertTrue(flow.path.isEmpty)
        XCTAssertNil(flow.puzzle)
    }
}
