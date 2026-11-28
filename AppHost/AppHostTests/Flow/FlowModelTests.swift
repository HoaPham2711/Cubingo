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

    private func assertOneRealityView(_ f: FlowModel, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertLessThanOrEqual(f.path.filter(\.hasRealityView).count, 1, "\(f.path)", file: file, line: line)
    }

    func testQuetHopLeDiThangSangMode() {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didScan(ScanPreviewSeed.scanResult)
        XCTAssertEqual(flow.path, [.mode])
        XCTAssertNotNil(flow.cube)
        assertOneRealityView(flow)
    }

    func testQuetLoiMoReviewRoiThayPath() {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didScan(ScanPreviewSeed.scanResultWithMistake)
        XCTAssertEqual(flow.path, [.scan, .review(manual: false)])
        assertOneRealityView(flow)
        flow.didReview(ScanPreviewSeed.state, palette: .manualDefault)
        XCTAssertEqual(flow.path, [.mode])
        assertOneRealityView(flow)
    }

    func testQuayLaiTuModeQuetLai() {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didScan(ScanPreviewSeed.scanResult)
        flow.rescanFromMode()
        XCTAssertEqual(flow.path, [.scan])
        XCTAssertNil(flow.cube)
        flow.scanBack()
        XCTAssertEqual(flow.path, [])
    }

    func testQuetLaiKhiLechVaBoDo() {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didReview(ScanPreviewSeed.state, palette: .manualDefault)
        flow.begin(GuidePreviewSeed.stageDone())
        let session = flow.session
        XCTAssertTrue(flow.path.contains(.guide(.teach)))
        assertOneRealityView(flow)
        flow.startRescan()
        XCTAssertEqual(flow.path, [.scan])
        assertOneRealityView(flow)
        flow.scanBack()
        XCTAssertEqual(flow.path, [.guide(.teach)])
        XCTAssertFalse(flow.isRechecking)
        XCTAssertTrue(flow.session === session)
        flow.startRescan()
        flow.didScan(ScanPreviewSeed.scanResult)
        XCTAssertEqual(flow.path, [.guide(.teach)])
        XCTAssertFalse(flow.isRechecking)
        assertOneRealityView(flow)
    }
}
