@testable import AppHost
import XCTest

@MainActor
final class GuideSessionTests: XCTestCase {
    private func scrambled(_ seed: UInt64) -> CubeFacelets {
        var rng = CubeRandom(seed: seed)
        return CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
    }

    private func step(_ s: String) -> SolverStep { SolverStep(move: CubeMove.parse(s)![0], reason: nil, algorithm: nil) }

    /// Trạng thái mong đợi = trạng thái đầu áp mọi bước đã làm (tính độc lập từ chỉ số của phiên).
    private func expectedState(_ s: GuideSession, stages: [SolverStage]) -> CubeFacelets {
        var moves: [CubeMove] = []
        for k in 0..<s.stageIndex { moves += stages[k].steps.map(\.move) }
        let current = stages[s.stageIndex].steps
        moves += current.prefix(s.stepIndex).map(\.move)
        return stages[0].start.applying(moves)
    }

    func testTienHetMotChangVaStageDone() {
        let start = scrambled(1)
        let stages = SolverBeginner.solve(start, base: start.center(.u))
        let s = GuideSession(mode: .teach, stages: stages, base: start.center(.u))
        XCTAssertEqual(s.stageIndex, 0)
        XCTAssertEqual(s.state, start)
        for _ in 0..<stages[0].steps.count { s.next() }
        XCTAssertEqual(s.phase, .stageDone(.cross))
        XCTAssertEqual(s.state, stages[0].end)
        XCTAssertNotNil(s.animation)
    }

    func testBackQuaRanhGioiChangGiuTrangThaiNhatQuan() {
        let start = scrambled(2)
        let stages = SolverBeginner.solve(start, base: start.center(.u))
        let s = GuideSession(mode: .teach, stages: stages, base: start.center(.u))
        for _ in 0..<stages[0].steps.count { s.next() }
        s.continueAfterStage()
        XCTAssertEqual(s.stageIndex, 1)
        XCTAssertEqual(s.stepIndex, 0)
        s.back()
        XCTAssertEqual(s.stageIndex, 0)
        XCTAssertEqual(s.stepIndex, stages[0].steps.count - 1)
        XCTAssertEqual(s.phase, .step)
        XCTAssertEqual(s.animation?.reverse, true)

        var rng = CubeRandom(seed: 5)
        for i in 0..<400 {
            switch Int.random(in: 0..<10, using: &rng) {
            case 0..<5: s.next()
            case 5..<7: s.back()
            case 7: s.replay()
            default: if case .stageDone = s.phase { s.continueAfterStage() } else { s.next() }
            }
            XCTAssertEqual(s.state, expectedState(s, stages: stages), "thao tác \(i)")
            if s.phase == .step { XCTAssertGreaterThan(s.stepCount, 0, "không bao giờ 0 / 0") }
        }
    }

    func testChangRongDuocBoQua() {
        let start = CubeFacelets.solved(n: 3)
        let s1 = SolverStage(kind: .cross, steps: [step("R")], start: start)
        let empty: (SolverStageKind) -> SolverStage = { SolverStage(kind: $0, steps: [], start: s1.end) }
        let s4 = SolverStage(kind: .topCross, steps: [step("R'")], start: s1.end)
        let stages = [s1, empty(.corners), empty(.middle), s4] +
            [SolverStageKind.topFace, .topCorners, .topEdges].map { SolverStage(kind: $0, steps: [], start: s4.end) }
        let s = GuideSession(mode: .teach, stages: stages, base: CubeColor(raw: 3))
        s.next()
        XCTAssertEqual(s.phase, .stageDone(.cross))
        s.continueAfterStage()
        XCTAssertEqual(s.stageIndex, 3)
        XCTAssertEqual(s.stepCount, 1)
        s.next()
        XCTAssertEqual(s.phase, .finished, "không còn chặng nào có bước")
        // Lời giải toàn chặng rỗng (khối đã giải) ⇒ xong ngay.
        let solved = GuideSession(mode: .teach, stages: SolverBeginner.solve(start, base: CubeColor(raw: 0)),
                                  base: CubeColor(raw: 0))
        XCTAssertEqual(solved.phase, .finished)
    }

    func testQuickKetThucLaFinished() {
        var rng = CubeRandom(seed: 3)
        let moves = (0..<20).map { _ in CubeMove.faceMoves[Int.random(in: 0..<18, using: &rng)] }
        let stage = SolverStage(kind: .cross, steps: moves.map { SolverStep(move: $0, reason: nil, algorithm: nil) },
                                start: .solved(n: 3))
        let s = GuideSession(mode: .quick, stages: [stage], base: CubeColor(raw: 0))
        for _ in 0..<19 { s.next() }
        XCTAssertEqual(s.phase, .step)
        s.next()
        XCTAssertEqual(s.phase, .finished)
        XCTAssertEqual(s.movesDone, 20)
        XCTAssertEqual(s.state, stage.end)
    }

    func testReplanTuTrangThaiMoi() {
        let start = scrambled(4)
        let base = start.center(.u)
        let s = GuideSession(mode: .teach, stages: SolverBeginner.solve(start, base: base), base: base)
        for _ in 0..<5 { s.next() }
        let mid = scrambled(44)
        let fresh = SolverBeginner.solve(mid, base: mid.center(.u))
        s.replan(fresh)
        let first = fresh.firstIndex { !$0.steps.isEmpty }!
        XCTAssertEqual(s.stageIndex, first)
        XCTAssertEqual(s.stepIndex, 0)
        XCTAssertEqual(s.state, fresh[first].start)
        XCTAssertEqual(s.base, base, "giữ màu nền của phiên")
        XCTAssertEqual(s.phase, .step)
    }

    func testDemBuocKhongTinhXoayCaKhoi() {
        let steps = ["y", "R", "U", "R'", "U'", "y'", "F", "R", "U", "B"].map(step)
        let stage = SolverStage(kind: .middle, steps: steps, start: .solved(n: 3))
        let s = GuideSession(mode: .teach, stages: [stage], base: CubeColor(raw: 3))
        for _ in steps { s.next() }
        XCTAssertEqual(s.movesDone, 8)
        s.back()
        XCTAssertEqual(s.movesDone, 7)
    }

    func testThoiGianTheoDongHo() {
        var now = Date(timeIntervalSince1970: 1000)
        let s = GuideSession(mode: .quick, stages: [SolverStage(kind: .cross, steps: [step("R")], start: .solved(n: 3))],
                             base: CubeColor(raw: 0), clock: { now })
        now = now.addingTimeInterval(65)
        XCTAssertEqual(s.elapsed, 65, accuracy: 0.001)
    }
}

final class GuideCheckTests: XCTestCase {
    func testKiemChangKhopVaLech() {
        var rng = CubeRandom(seed: 6)
        let f = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
        func grid(_ face: CubeFace) -> [CubeColor] { (0..<9).map { f.color(face, $0) } }
        func rotated(_ g: [CubeColor], _ k: Int) -> [CubeColor] {
            var out = g
            for _ in 0..<k { let old = out; for r in 0..<3 { for c in 0..<3 { out[r * 3 + c] = old[(2 - c) * 3 + r] } } }
            return out
        }
        let cross = GuideCheck.spec(.cross)
        XCTAssertEqual(cross, GuideCheckSpec(face: .d, indices: [1, 3, 5, 7], anyRotation: true))
        XCTAssertTrue(GuideCheck.matches(rotated(grid(.d), 1), expected: f, spec: cross))
        let middle = GuideCheck.spec(.middle)
        XCTAssertEqual(middle, GuideCheckSpec(face: .f, indices: Array(3...8), anyRotation: false))
        XCTAssertTrue(GuideCheck.matches(grid(.f), expected: f, spec: middle))
        var wrong = grid(.f)
        wrong[4] = CubeColor(raw: (wrong[4].raw + 1) % 6)
        XCTAssertFalse(GuideCheck.matches(wrong, expected: f, spec: middle))
        XCTAssertEqual(GuideCheck.spec(.topCorners), GuideCheckSpec(face: .f, indices: [0, 2], anyRotation: false))
        XCTAssertEqual(GuideCheck.spec(.topFace).face, .u)
    }
}
