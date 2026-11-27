@testable import AppHost
import XCTest

@MainActor
final class FlowModeTests: XCTestCase {
    private func scrambled(_ seed: UInt64) -> CubeFacelets {
        var rng = CubeRandom(seed: seed)
        return CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
    }

    func testUocLuongKhongTinhXoayCaKhoi() {
        let rot = ["y", "x'", "z2"].map { SolverStep(move: CubeMove.parse($0)![0], reason: nil, algorithm: nil) }
        let face = (0..<40).map { SolverStep(move: CubeMove.faceMoves[$0 % 18], reason: nil, algorithm: nil) }
        let a = SolverStage(kind: .cross, steps: rot + Array(face[0..<10]), start: .solved(n: 3))
        let b = SolverStage(kind: .corners, steps: Array(face[10..<40]), start: a.end)
        XCTAssertEqual(FlowMode.estimate(teach: [a, b]), 40)
    }

    func testStartGuideTeachDayRoute() async {
        let flow = FlowModel()
        flow.choose(.cube3)
        let cube = scrambled(1)
        flow.didReview(cube, palette: .manualDefault)
        await flow.startGuide(.teach, quickSolver: SolverQuick(tables: { solverTestTables }))
        XCTAssertEqual(flow.path.last, .guide(.teach))
        XCTAssertEqual(flow.session?.mode, .teach)
        XCTAssertEqual(flow.session?.base, CubePalette.manualDefault.baseColor)
        XCTAssertNil(flow.alert)
    }

    func testStartGuideQuickDayRouteMotChang() async {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didReview(scrambled(2), palette: .manualDefault)
        await flow.startGuide(.quick, quickSolver: SolverQuick(tables: { solverTestTables }))
        XCTAssertEqual(flow.path.last, .guide(.quick))
        XCTAssertEqual(flow.session?.stages.count, 1)
        XCTAssertFalse(flow.isSolving)
    }

    func testStartGuideQuickLoiThiKhongDayRoute() async {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didReview(scrambled(3), palette: .manualDefault)
        let before = flow.path
        let broken = SolverQuick(tables: { throw SolverQuickError.timedOut })
        await flow.startGuide(.quick, quickSolver: broken)
        XCTAssertEqual(flow.path, before)
        XCTAssertEqual(flow.alert, .solverFailed)
        XCTAssertNil(flow.session)
        XCTAssertFalse(flow.isSolving)
    }

    func testXongPhienThiSangManXong() async {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didReview(CubeFacelets.solved(n: 3).applying(CubeMove.parse("R U")!), palette: .manualDefault)
        await flow.startGuide(.quick, quickSolver: SolverQuick(tables: { solverTestTables }))
        let s = flow.session!
        while s.phase != .finished { s.next() }
        flow.didFinishGuide()
        XCTAssertEqual(flow.path.last, .done)
    }
}
