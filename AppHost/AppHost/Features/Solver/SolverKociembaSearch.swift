import Foundation

/// Một lần tìm hai pha (IDA* pha 1 tới nhóm ⟨U, D, R2, L2, F2, B2⟩ rồi IDA* pha 2) — đồng bộ, một luồng, dùng một
/// lần. Tìm tiếp lời giải ngắn hơn cho tới khi có lời giải ≤ `maxLength`, hết giờ, hoặc hết độ sâu pha 1.
final class SolverKociembaSearch {
    enum Stop: Error { case cancelled, timedOut }

    typealias K = SolverKociembaCoords

    private let t: SolverKociembaTables
    private let start: CubeCubies
    private let maxLength: Int
    private let deadline: ContinuousClock.Instant
    private let isCancelled: () -> Bool
    private let moveCubes = CubeMove.faceMoves.map { CubeCubies.move($0) }

    /// Trần tuyệt đối của lời giải trả về.
    static let hardLimit = 30

    private var path1 = [Int](repeating: 0, count: 32)
    private var path2 = [Int](repeating: 0, count: 32)
    private(set) var best: [Int]?
    private var nodes = 0
    private(set) var timedOut = false

    init(tables: SolverKociembaTables, start: CubeCubies, maxLength: Int, deadline: ContinuousClock.Instant,
         isCancelled: @escaping () -> Bool) {
        t = tables
        self.start = start
        self.maxLength = maxLength
        self.deadline = deadline
        self.isCancelled = isCancelled
    }

    /// Chạy tới khi dừng. Ném `Stop.cancelled` khi bị huỷ; hết giờ ⇒ `timedOut = true`, trả `best` hiện có.
    func run() throws -> [Int]? {
        let tw = K.twist(start), fl = K.flip(start), sl = K.sliceSorted(start) / 24
        let h0 = phase1Heuristic(tw, fl, sl)
        do {
            for depth in h0...20 {
                if let best, depth >= best.count { break }
                if try phase1(tw, fl, sl, n: 0, togo: depth) { break }
            }
        } catch Stop.timedOut {
            timedOut = true
        }
        return best
    }

    private func phase1Heuristic(_ tw: Int, _ fl: Int, _ sl: Int) -> Int {
        max(Int(t.twistSlicePrune[tw * 495 + sl]), Int(t.flipSlicePrune[fl * 495 + sl]))
    }

    private func phase2Heuristic(_ co: Int, _ ud: Int, _ s2: Int) -> Int {
        max(Int(t.cornersSlicePrune[co * 24 + s2]), Int(t.udEdgesSlicePrune[ud * 24 + s2]))
    }

    private func tick() throws {
        nodes += 1
        guard nodes & 1023 == 0 else { return }
        if isCancelled() { throw Stop.cancelled }
        if ContinuousClock.now >= deadline { throw Stop.timedOut }
    }

    /// Bỏ bước cùng mặt liên tiếp, và với hai mặt đối diện chỉ cho một thứ tự (U trước D…).
    private static func allowed(_ m: Int, after last: Int?) -> Bool {
        guard let last else { return true }
        let f = m / 3, lf = last / 3
        return f != lf && lf - f != 3
    }

    private static let isPhase2Move: [Bool] = (0..<18).map { SolverKociembaCoords.phase2Moves.contains($0) }

    /// `true` ⇒ dừng hẳn (đã có lời giải đủ ngắn).
    private func phase1(_ tw: Int, _ fl: Int, _ sl: Int, n: Int, togo: Int) throws -> Bool {
        try tick()
        if togo == 0 {
            guard tw == 0, fl == 0, sl == 0 else { return false }
            // Bước cuối pha 1 là bước pha 2 ⇒ lời giải này đã được xét ở độ sâu nhỏ hơn.
            if n > 0, Self.isPhase2Move[path1[n - 1]] { return false }
            return try phase2Start(n1: n)
        }
        let last: Int? = n > 0 ? path1[n - 1] : nil
        for m in 0..<18 where Self.allowed(m, after: last) {
            let tw2 = Int(t.twistMove[tw * 18 + m])
            let fl2 = Int(t.flipMove[fl * 18 + m])
            let sl2 = Int(t.sliceSortedMove[sl * 24 * 18 + m]) / 24
            guard phase1Heuristic(tw2, fl2, sl2) <= togo - 1 else { continue }
            path1[n] = m
            if try phase1(tw2, fl2, sl2, n: n + 1, togo: togo - 1) { return true }
        }
        return false
    }

    private func phase2Start(n1: Int) throws -> Bool {
        var c = start
        for i in 0..<n1 { c = c.multiplied(moveCubes[path1[i]]) }
        let co = K.corners(c), ud = K.udEdges(c), s2 = K.sliceSorted(c) % 24
        let limit = min((best?.count ?? Self.hardLimit + 1) - 1, Self.hardLimit) - n1
        let h0 = phase2Heuristic(co, ud, s2)
        guard h0 <= limit else { return false }
        for d2 in h0...max(h0, limit) where d2 <= limit {
            if try phase2(co, ud, s2, n1: n1, n: 0, togo: d2) {
                let merged = Self.merged(Array(path1[0..<n1]) + Array(path2[0..<d2]))
                if merged.count < (best?.count ?? Int.max) { best = merged }
                return merged.count <= maxLength
            }
        }
        return false
    }

    private func phase2(_ co: Int, _ ud: Int, _ s2: Int, n1: Int, n: Int, togo: Int) throws -> Bool {
        try tick()
        if togo == 0 { return co == 0 && ud == 0 && s2 == 0 }
        // Bước đầu pha 2 được trùng mặt với bước cuối pha 1 (gộp ở `merged`): R + R2 = R'.
        let last: Int? = n > 0 ? path2[n - 1] : nil
        for i in 0..<10 {
            let m = K.phase2Moves[i]
            guard Self.allowed(m, after: last) else { continue }
            let co2 = Int(t.cornersMove[co * 10 + i])
            let ud2 = Int(t.udEdgesMove[ud * 10 + i])
            let s22 = Int(t.sliceSortedMove[s2 * 18 + m]) % 24
            guard phase2Heuristic(co2, ud2, s22) <= togo - 1 else { continue }
            path2[n] = m
            if try phase2(co2, ud2, s22, n1: n1, n: n + 1, togo: togo - 1) { return true }
        }
        return false
    }

    /// Gộp bước cùng mặt liền nhau (R + R2 = R', R + R' = ∅).
    static func merged(_ moves: [Int]) -> [Int] {
        var out: [Int] = []
        for m in moves {
            if let top = out.last, top / 3 == m / 3 {
                out.removeLast()
                let turns = (top % 3 + 1 + m % 3 + 1) % 4
                if turns != 0 { out.append((m / 3) * 3 + turns - 1) }
            } else {
                out.append(m)
            }
        }
        return out
    }
}
