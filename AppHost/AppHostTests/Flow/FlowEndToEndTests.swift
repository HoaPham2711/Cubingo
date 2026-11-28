@testable import AppHost
import XCTest

/// Đi hết luồng bằng logic thật (không UI): quét 6 bước từ mẫu màu ⇒ kiểm tra ⇒ chọn cách giải ⇒ chỉ bước tới xong.
/// Bằng chứng tích hợp cho Đợt A (các màn chỉ là lớp mỏng gọi đúng các hàm này).
@MainActor
final class FlowEndToEndTests: XCTestCase {
    private func scanned(_ seed: UInt64) -> (CubeFacelets, ScanResult) {
        var rng = CubeRandom(seed: seed)
        let f = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
        let samples = ScanFixtures.samples(for: f, palette: .manualDefault, .warmLamp, seed: seed)
        let capture = ScanCaptureModel()
        ScanFixtures.scanAll(capture, samples)
        return (f, capture.result!)
    }

    func testTeachMeTuQuetToiGiaiXong() async {
        let (f, result) = scanned(901)
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didScan(result)
        XCTAssertEqual(flow.path, [.scan, .review(manual: false)])
        let review = ScanReviewModel(scan: flow.scan!)
        guard case .ok(let cube) = review.validate() else { return XCTFail("quét phải hợp lệ") }
        XCTAssertEqual(cube, f)
        flow.didReview(cube, palette: review.palette)
        XCTAssertEqual(flow.palette?.colorName(flow.palette!.baseColor), .white)
        await flow.startGuide(.teach, quickSolver: SolverQuick(tables: { solverTestTables }))
        let s = flow.session!
        var stagesSeen = 0
        var guardCount = 0
        while s.phase != .finished, guardCount < 2000 {
            switch s.phase {
            case .step: s.next()
            case .stageDone:
                stagesSeen += 1
                // Quét kiểm tra mặt của chặng bằng mẫu màu của trạng thái thật ⇒ khớp.
                let spec = GuideCheck.spec(s.currentStage.kind)
                let samples = (0..<9).map { flow.palette!.rgb(s.state.color(spec.face, $0)) }
                XCTAssertEqual(GuideCheckFlow.outcome(samples: samples, palette: flow.palette!, spec: spec,
                                                      expected: s.state), .match)
                flow.startCheck()
                flow.checkMatched()
            case .finished: break
            }
            guardCount += 1
        }
        XCTAssertTrue(s.state.isSolved)
        XCTAssertGreaterThan(stagesSeen, 3)
        flow.didFinishGuide()
        XCTAssertEqual(flow.path.last, .done)
        flow.startOver()
        XCTAssertEqual(flow.path, [])
    }

    func testJustSolveItTuQuetToiGiaiXong() async {
        let (_, result) = scanned(902)
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didScan(result)
        let review = ScanReviewModel(scan: flow.scan!)
        guard case .ok(let cube) = review.validate() else { return XCTFail("quét phải hợp lệ") }
        flow.didReview(cube, palette: review.palette)
        await flow.startGuide(.quick, quickSolver: SolverQuick(tables: { solverTestTables }))
        let s = flow.session!
        XCTAssertLessThanOrEqual(s.stepCount, 30)
        while s.phase != .finished { s.next() }
        XCTAssertTrue(s.state.isSolved)
        XCTAssertEqual(s.movesDone, s.stepCount)
    }
}
