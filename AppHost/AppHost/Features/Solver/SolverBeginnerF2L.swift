import Foundation

/// Teach me chặng 1–3: chữ thập (cách "daisy"), góc tầng 1, tầng giữa. Mọi quyết định dựa trên VỊ TRÍ (không dựa vào
/// nhãn màu) ⇒ bảng màu nào cũng ra cùng bước. Chặng đã đạt ⇒ không bước nào (kể cả bước xoay).
enum SolverBeginnerF2L {
    typealias P = SolverPieces

    // MARK: - Mục tiêu (dùng cả ở chặng sau)

    /// Áp xoay cả khối để base xuống D rồi kiểm — mục tiêu không phụ thuộc hướng cầm.
    static func baseDown(_ f: CubeFacelets, base: CubeColor) -> CubeFacelets {
        f.applying(SolverHold.rotations(from: f, top: P.opposite(of: base, in: f), preferFront: nil))
    }

    static func crossDone(_ f: CubeFacelets) -> Bool {
        let base = f.center(.d)
        return [1, 3, 5, 7].allSatisfy { f.color(.d, $0) == base }
            && [CubeFace.f, .r, .b, .l].allSatisfy { f.color($0, 7) == f.center($0) }
    }

    /// Góc ở vị trí `p` (4…7, tầng D) đúng chỗ, đúng hướng.
    static func cornerSlotDone(_ f: CubeFacelets, _ p: Int) -> Bool {
        let idx = P.corners[p]
        return idx.allSatisfy { f.stickers[$0] == f.stickers[($0 / 9) * 9 + 4] }
    }

    /// Cạnh ở vị trí `p` đúng chỗ, đúng hướng.
    static func edgeSlotDone(_ f: CubeFacelets, _ p: Int) -> Bool {
        P.edges[p].allSatisfy { f.stickers[$0] == f.stickers[($0 / 9) * 9 + 4] }
    }

    static func firstLayerDone(_ f: CubeFacelets) -> Bool { crossDone(f) && (4..<8).allSatisfy { cornerSlotDone(f, $0) } }
    static func middleDone(_ f: CubeFacelets) -> Bool { firstLayerDone(f) && (8..<12).allSatisfy { edgeSlotDone(f, $0) } }

    // MARK: - Chặng 1: daisy rồi hạ xuống chữ thập

    /// Ô U quanh tâm (vị trí "cánh hoa").
    private static let petalSlots: Set<Int> = [1, 3, 5, 7]
    /// Bước được dùng để dựng daisy (không dùng D) — thứ tự ưu tiên khi cùng độ dài.
    private static let daisyMoves: [CubeMove] = [CubeFace.f, .r, .b, .l, .u].flatMap { f in
        [1, 3, 2].map { CubeMove(.face(f), $0) }
    }

    static func cross(_ f: CubeFacelets, base: CubeColor) -> SolverStage {
        var b = SolverStageBuilder(kind: .cross, start: f)
        guard !crossDone(baseDown(f, base: base)) else { return b.stage }
        b.hold(top: P.opposite(of: base, in: f))

        // Daisy: mỗi lượt tìm (sâu dần ≤ 4) dãy làm tăng số cánh mà không mất cánh nào.
        while true {
            let edges = baseEdges(b.state, base: base)
            let petals = edges.filter { petalSlots.contains($0.base) }
            guard petals.count < 4 else { break }
            guard let seq = daisySearch(edges) else { preconditionFailure("daisy không tìm được bước") }
            let before = Set(petals.map { b.state.stickers[$0.side] })
            let after = b.state.applying(seq)
            let added = baseEdges(after, base: base).filter { petalSlots.contains($0.base) }
                .map { after.stickers[$0.side] }
                .first { !before.contains($0) }!
            b.group(seq, reason: .makeDaisy(edge: added))
        }
        // Hạ từng cánh: U tới khi màu bên nằm trên tâm cùng màu, rồi xoay mặt đó 2 lần.
        for _ in 0..<4 {
            var pick: (k: Int, face: CubeFace, color: CubeColor)?
            for k in [0, 1, 3, 2] {
                let g = k == 0 ? b.state : b.state.applying(CubeMove(.face(.u), k))
                for e in baseEdges(g, base: base) where petalSlots.contains(e.base) {
                    let face = P.face(ofSticker: e.side)
                    if g.stickers[e.side] == g.center(face) {
                        pick = (k, face, g.stickers[e.side])
                        break
                    }
                }
                if pick != nil { break }
            }
            guard let pick else { break }
            b.group(SolverStageBuilder.turns(.face(.u), pick.k) + [CubeMove(.face(pick.face), 2)],
                    reason: .dropToCross(edge: pick.color))
        }
        return b.stage
    }

    /// Cạnh có màu base: (chỉ số ô base, chỉ số ô bên).
    private static func baseEdges(_ f: CubeFacelets, base: CubeColor) -> [(base: Int, side: Int)] {
        P.edges.compactMap { idx in
            if f.stickers[idx[0]] == base { return (idx[0], idx[1]) }
            if f.stickers[idx[1]] == base { return (idx[1], idx[0]) }
            return nil
        }
    }

    /// Đích của mỗi ô sau từng bước daisy (`dest[m][i]` = chỗ mới của ô i) — theo dõi 4 cạnh rẻ hơn áp cả facelet.
    private static let daisyDest: [[Int]] = daisyMoves.map { m in
        let perm = CubeGeometry.of(n: 3).permutation(m)
        var dest = [Int](repeating: 0, count: 54)
        for (t, j) in perm.enumerated() { dest[j] = t }
        return dest
    }

    private static func daisySearch(_ edges: [(base: Int, side: Int)]) -> [CubeMove]? {
        let start = edges.map(\.base)
        let wasPetal = start.map { petalSlots.contains($0) }
        let need = wasPetal.filter { $0 }.count + 1
        var path: [Int] = []
        func dfs(_ pos: [Int], depth: Int) -> Bool {
            if depth == 0 {
                let now = pos.map { petalSlots.contains($0) }
                return now.filter { $0 }.count >= need && zip(wasPetal, now).allSatisfy { !$0 || $1 }
            }
            for (mi, m) in daisyMoves.enumerated() {
                if let last = path.last, daisyMoves[last].face == m.face { continue }
                path.append(mi)
                if dfs(pos.map { daisyDest[mi][$0] }, depth: depth - 1) { return true }
                path.removeLast()
            }
            return false
        }
        for depth in 1...4 where dfs(start, depth: depth) {
            return path.map { daisyMoves[$0] }
        }
        return nil
    }

    // MARK: - Chặng 2: góc tầng 1 (lặp right trigger)

    static func corners(_ f: CubeFacelets, base: CubeColor) -> SolverStage {
        var b = SolverStageBuilder(kind: .corners, start: f)
        guard !firstLayerDone(baseDown(f, base: base)) else { return b.stage }
        b.hold(top: P.opposite(of: base, in: f))
        let rightTrigger = SolverAlgorithm.rightTrigger
        for _ in 0..<4 {
            // Khe chưa xong gần nhất ⇒ đưa về DFR.
            guard let k = b.firstTurns(.y, { g in !cornerSlotDone(g, 4) }) else { break }
            b.group(SolverStageBuilder.turns(.y, k), reason: nil)
            let want: Set<CubeColor> = [base, b.state.center(.f), b.state.center(.r)]
            let target = (b.state.center(.f), b.state.center(.r))
            var p = P.cornerPosition(b.state, colors: want)!
            if p >= 4 {
                // Góc kẹt ở tầng D (khe khác, hoặc khe này nhưng xoắn): nhấc lên tầng U.
                let lift = [0, 1, 3, 2].first { j in
                    let g = j == 0 ? b.state : b.state.applying(CubeMove(.y, j))
                    return P.cornerPosition(g, colors: want) == 4
                }!
                b.group(SolverStageBuilder.turns(.y, lift), reason: nil)
                b.algorithm(rightTrigger, reason: .liftCorner)
                b.group(SolverStageBuilder.turns(.y, (4 - lift) % 4), reason: nil)
                p = P.cornerPosition(b.state, colors: want)!
            }
            precondition(p < 4, "góc phải ở tầng U")
            let u = b.firstTurns(.face(.u)) { P.cornerPosition($0, colors: want) == 0 }!
            var setup = SolverStageBuilder.turns(.face(.u), u)
            for _ in 0..<6 where !cornerSlotDone(b.state, 4) {
                b.algorithm(rightTrigger, setup: setup, reason: .placeCorner(target.0, target.1))
                setup = []
            }
            precondition(cornerSlotDone(b.state, 4), "right trigger phải đặt xong góc trong 5 lần")
        }
        return b.stage
    }

    // MARK: - Chặng 3: tầng giữa

    static func middle(_ f: CubeFacelets, base: CubeColor) -> SolverStage {
        var b = SolverStageBuilder(kind: .middle, start: f)
        guard !middleDone(baseDown(f, base: base)) else { return b.stage }
        b.hold(top: P.opposite(of: base, in: f))
        let top = b.state.center(.u)
        for _ in 0..<12 where !middleDone(b.state) {
            // Cạnh tầng U không mang màu đỉnh (vị trí 0…3).
            if let e = (0..<4).first(where: { !P.colors(b.state, P.edges[$0]).contains(top) }) {
                let side = b.state.stickers[P.edges[e][1]]
                let up = b.state.stickers[P.edges[e][0]]
                let k = b.firstTurns(.y) { $0.center(.f) == side }!
                b.group(SolverStageBuilder.turns(.y, k), reason: nil)
                // Cạnh tới UF (ô bên ở F).
                let u = b.firstTurns(.face(.u)) { g in g.stickers[P.edges[1][1]] == side && g.stickers[P.edges[1][0]] == up }!
                let toRight = up == b.state.center(.r)
                b.algorithm(toRight ? .rightInsert : .leftInsert, setup: SolverStageBuilder.turns(.face(.u), u),
                            reason: .insertEdge(side, up, toRight: toRight))
            } else {
                // Không còn cạnh nào ở U: đẩy cạnh sai chỗ/lật ở tầng giữa lên.
                let k = b.firstTurns(.y) { !edgeSlotDone($0, 8) }!
                b.group(SolverStageBuilder.turns(.y, k), reason: nil)
                b.algorithm(.rightInsert, reason: .popEdge)
            }
        }
        return b.stage
    }
}
