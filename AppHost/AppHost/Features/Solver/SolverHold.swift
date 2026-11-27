import Foundation

/// Hướng cầm khối: màu tâm trên + màu tâm trước.
enum SolverHold {
    static func hold(of f: CubeFacelets) -> (top: CubeColor, front: CubeColor) {
        (f.center(.u), f.center(.f))
    }

    /// Dãy xoay cả khối ngắn nhất (≤ 2 bước trong x/y/z, ', 2) đưa `top` lên trên. Ưu tiên giữ `preferFront` làm mặt
    /// trước, rồi ít bước nhất; cùng hạng ⇒ thứ tự của `CubeMove.rotations` (tất định).
    static func rotations(from f: CubeFacelets, top: CubeColor, preferFront: CubeColor?) -> [CubeMove] {
        var candidates: [[CubeMove]] = [[]]
        candidates += CubeMove.rotations.map { [$0] }
        for a in CubeMove.rotations {
            for b in CubeMove.rotations where b.axis != a.axis { candidates.append([a, b]) }
        }
        // `candidates` xếp theo độ dài ⇒ dãy đầu tiên giữ được mặt trước là tốt nhất; không có thì dãy đầu tiên.
        var fallback: [CubeMove]?
        for seq in candidates {
            let g = f.applying(seq)
            guard g.center(.u) == top else { continue }
            if preferFront.map({ g.center(.f) == $0 }) ?? true { return seq }
            if fallback == nil { fallback = seq }
        }
        return fallback ?? []
    }
}
