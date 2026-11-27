import Foundation

/// Teach me chặng 4–7 trên khối đã xong hai tầng dưới. Mỗi vòng chọn tiền-xoay `U^k` theo luật của phương pháp; luật
/// không áp được ⇒ thử 4 giá trị k, lấy k làm tiến triển nhiều nhất. Phép vét cạn mọi trạng thái tầng cuối (test) là
/// bằng chứng các luật đúng. `base` mặc định = tâm D; khác ⇒ chặng (nếu chưa đạt) mở đầu bằng xoay cả khối.
enum SolverBeginnerLastLayer {
    typealias P = SolverPieces
    typealias F2L = SolverBeginnerF2L

    // MARK: - Mục tiêu

    /// Ô cạnh U (U2 U4 U6 U8) cùng màu tâm U.
    static func topCrossDone(_ f: CubeFacelets) -> Bool {
        F2L.middleDone(f) && [1, 3, 5, 7].allSatisfy { f.color(.u, $0) == f.center(.u) }
    }

    static func topFaceDone(_ f: CubeFacelets) -> Bool {
        F2L.middleDone(f) && (0..<9).allSatisfy { f.color(.u, $0) == f.center(.u) }
    }

    static func topCornersDone(_ f: CubeFacelets) -> Bool {
        topFaceDone(f) && (0..<4).allSatisfy { F2L.cornerSlotDone(f, $0) }
    }

    // MARK: - Chặng 4: chữ thập trên (chấm → chữ L → vạch → chữ thập)

    static func topCross(_ f: CubeFacelets, base: CubeColor? = nil) -> SolverStage {
        let base = base ?? f.center(.d)
        var b = SolverStageBuilder(kind: .topCross, start: f)
        guard !topCrossDone(F2L.baseDown(f, base: base)) else { return b.stage }
        b.hold(top: P.opposite(of: base, in: f))
        for _ in 0..<6 where !topCrossDone(b.state) {
            let k: Int
            switch crossShape(b.state) {
            case .dot: k = 0
            // Chữ L ở trái-sau (U2 phía B, U4 phía L).
            case .ell: k = b.firstTurns(.face(.u)) { crossShape($0) == .ell && up($0, 1) && up($0, 3) } ?? 0
            // Vạch nằm ngang (U4, U6).
            case .line: k = b.firstTurns(.face(.u)) { up($0, 3) && up($0, 5) } ?? 0
            case .cross: k = 0
            }
            b.algorithm(.crossMaker, setup: SolverStageBuilder.turns(.face(.u), k), reason: .makeTopCross)
        }
        return b.stage
    }

    private enum CrossShape { case dot, ell, line, cross }

    private static func up(_ f: CubeFacelets, _ i: Int) -> Bool { f.color(.u, i) == f.center(.u) }

    private static func crossShape(_ f: CubeFacelets) -> CrossShape {
        let on = [1, 3, 5, 7].filter { up(f, $0) }
        switch on.count {
        case 4: return .cross
        case 2: return (on == [1, 7] || on == [3, 5]) ? .line : .ell
        default: return .dot
        }
    }

    // MARK: - Chặng 5: mặt trên (lặp Sune)

    static func topFace(_ f: CubeFacelets, base: CubeColor? = nil) -> SolverStage {
        let base = base ?? f.center(.d)
        var b = SolverStageBuilder(kind: .topFace, start: f)
        guard !topFaceDone(F2L.baseDown(f, base: base)) else { return b.stage }
        b.hold(top: P.opposite(of: base, in: f))
        for _ in 0..<8 where !topFaceDone(b.state) {
            let top = b.state.center(.u)
            let oriented = [0, 2, 6, 8].filter { b.state.color(.u, $0) == top }.count
            // Góc UFL: ô U = U7 (chỉ số 6), ô F = F1 (18), ô L = L3 (38).
            let rule: (CubeFacelets) -> Bool
            switch oriented {
            case 1: rule = { $0.color(.u, 6) == top }
            case 0: rule = { $0.stickers[38] == top }
            default: rule = { $0.stickers[18] == top }
            }
            let k = b.firstTurns(.face(.u), rule)
                ?? bestTurn(b.state, score: { g in [0, 2, 6, 8].filter { g.color(.u, $0) == g.center(.u) }.count },
                            after: SolverAlgorithm.sune.moves)
            b.algorithm(.sune, setup: SolverStageBuilder.turns(.face(.u), k), reason: .orientTopCorners)
        }
        return b.stage
    }

    // MARK: - Chặng 6: góc trên đúng chỗ ("đèn pha")

    /// Mặt bên có hai ô góc hàng trên cùng màu.
    private static func headlights(_ f: CubeFacelets, _ face: CubeFace) -> Bool {
        f.color(face, 0) == f.color(face, 2)
    }

    static func topCorners(_ f: CubeFacelets, base: CubeColor? = nil) -> SolverStage {
        let base = base ?? f.center(.d)
        var b = SolverStageBuilder(kind: .topCorners, start: f)
        guard !topCornersDone(F2L.baseDown(f, base: base)) else { return b.stage }
        b.hold(top: P.opposite(of: base, in: f))
        let sides: [CubeFace] = [.f, .r, .b, .l]
        for _ in 0..<4 where !sides.allSatisfy({ headlights(b.state, $0) }) {
            let k = b.firstTurns(.face(.u)) { headlights($0, .b) } ?? 0
            b.algorithm(.cornerCycle, setup: SolverStageBuilder.turns(.face(.u), k), reason: .placeTopCorners)
        }
        if let k = b.firstTurns(.face(.u), { g in (0..<4).allSatisfy { F2L.cornerSlotDone(g, $0) } }), k != 0 {
            b.group(SolverStageBuilder.turns(.face(.u), k), reason: .alignTop)
        }
        return b.stage
    }

    // MARK: - Chặng 7: cạnh trên đúng chỗ

    private static func sideDone(_ f: CubeFacelets, _ face: CubeFace) -> Bool {
        (0..<3).allSatisfy { f.color(face, $0) == f.center(face) }
    }

    static func topEdges(_ f: CubeFacelets, base: CubeColor? = nil) -> SolverStage {
        let base = base ?? f.center(.d)
        var b = SolverStageBuilder(kind: .topEdges, start: f)
        guard !F2L.baseDown(f, base: base).isSolved else { return b.stage }
        b.hold(top: P.opposite(of: base, in: f))
        for _ in 0..<4 where !b.state.isSolved {
            if let k = b.firstTurns(.y, { sideDone($0, .b) }) {
                b.group(SolverStageBuilder.turns(.y, k), reason: nil)
            }
            b.algorithm(.edgeCycle, reason: .placeTopEdges)
        }
        return b.stage
    }

    // MARK: - Phụ trợ

    /// k (0…3) cho điểm cao nhất sau `U^k` + `after`; hoà ⇒ k nhỏ theo thứ tự 0, 1, 3, 2.
    private static func bestTurn(_ f: CubeFacelets, score: (CubeFacelets) -> Int, after: [CubeMove]) -> Int {
        var best = (k: 0, s: Int.min)
        for k in [0, 1, 3, 2] {
            let g = (k == 0 ? f : f.applying(CubeMove(.face(.u), k))).applying(after)
            let s = score(g)
            if s > best.s { best = (k, s) }
        }
        return best.k
    }
}
