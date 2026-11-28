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
        // Màn chọn cách giải nằm dưới màn giải (không có RealityView) ⇒ quay lại từ màn giải vẫn về đó.
        XCTAssertEqual(flow.path, [.mode, .guide(.teach)])
        XCTAssertFalse(flow.isRechecking)
        XCTAssertTrue(flow.session === session)
        flow.startRescan()
        flow.didScan(ScanPreviewSeed.scanResult)
        XCTAssertEqual(flow.path, [.mode, .guide(.teach)])
        XCTAssertFalse(flow.isRechecking)
        assertOneRealityView(flow)
    }

    func testKhongConRouteCheck() {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didReview(ScanPreviewSeed.state, palette: .manualDefault)
        flow.begin(GuidePreviewSeed.stageDone())
        let before = flow.path
        flow.checkMatched()
        XCTAssertEqual(flow.path, before)
        XCTAssertEqual(flow.session?.phase, .step)
        assertOneRealityView(flow)
    }

    // Review #2: "Scan again" ở màn kiểm tra ⇒ quét mới từ đầu (đổi thế hệ màn quét).
    func testScanAgainQuetMoi() {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didScan(ScanPreviewSeed.scanResultWithMistake)
        let g = flow.scanGeneration
        flow.rescanFromReview()
        XCTAssertEqual(flow.path, [.scan])
        XCTAssertNotEqual(flow.scanGeneration, g)
    }

    // Review #3: bấm ✓ lặp ở 6/6 không chồng màn hay phá luồng quét lại.
    func testDidScanLapKhongChong() {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didScan(ScanPreviewSeed.scanResultWithMistake)
        flow.didScan(ScanPreviewSeed.scanResultWithMistake)
        XCTAssertEqual(flow.path, [.scan, .review(manual: false)])

        let f2 = FlowModel()
        f2.choose(.cube3)
        f2.didReview(ScanPreviewSeed.state, palette: .manualDefault)
        f2.begin(GuidePreviewSeed.stageDone())
        f2.startRescan()
        f2.didScan(ScanPreviewSeed.scanResult)
        f2.didScan(ScanPreviewSeed.scanResult)
        XCTAssertEqual(f2.path, [.mode, .guide(.teach)])
    }
}
