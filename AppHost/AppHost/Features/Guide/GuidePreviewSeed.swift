import Foundation

#if targetEnvironment(simulator)
/// Phiên chỉ bước dựng sẵn cho route preview (từ trạng thái mẫu của `ScanPreviewSeed`, bảng màu `manualDefault`).
@MainActor
enum GuidePreviewSeed {
    static var base: CubeColor { CubePalette.manualDefault.baseColor }

    static func teachSession() -> GuideSession {
        GuideSession(mode: .teach, stages: SolverBeginner.solve(ScanPreviewSeed.state, base: base), base: base)
    }

    /// Giữa chặng 3 (tầng giữa).
    static func midMiddleLayer() -> GuideSession {
        let s = teachSession()
        var guardCount = 0
        while s.currentStage.kind.rawValue < SolverStageKind.middle.rawValue, guardCount < 1000 {
            if case .stageDone = s.phase { s.continueAfterStage() } else { s.next() }
            guardCount += 1
        }
        for _ in 0..<min(5, max(s.stepCount - 1, 0)) { s.next() }
        return s
    }

    /// Vừa xong chặng 1.
    static func stageDone() -> GuideSession {
        let s = teachSession()
        while s.phase == .step { s.next() }
        return s
    }

    /// Just solve it đã xong (màn ăn mừng).
    static func finishedQuick() -> GuideSession {
        let moves = CubeMove.parse("R U R' F2 L D' B U2 R' F")!
        let start = CubeFacelets.solved(n: 3).applying(moves.reversed().map(\.inverse))
        let steps = moves.map { SolverStep(move: $0, reason: nil, algorithm: nil) }
        let s = GuideSession(mode: .quick, stages: [SolverStage(kind: .cross, steps: steps, start: start)], base: base)
        while s.phase != .finished { s.next() }
        return s
    }
}
#endif
