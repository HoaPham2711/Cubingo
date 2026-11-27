import Foundation

/// Lời giải Teach me trọn vẹn: luôn đúng 7 chặng theo thứ tự; chặng đã đạt ⇒ `steps` rỗng (không bước xoay thừa).
/// `base` (màu nền chặng 1) chọn bằng `CubePalette.baseColor`.
enum SolverBeginner {
    static func solve(_ start: CubeFacelets, base: CubeColor) -> [SolverStage] {
        var stages: [SolverStage] = []
        var f = start
        func add(_ s: SolverStage) {
            stages.append(s)
            f = s.end
        }
        add(SolverBeginnerF2L.cross(f, base: base))
        add(SolverBeginnerF2L.corners(f, base: base))
        add(SolverBeginnerF2L.middle(f, base: base))
        add(SolverBeginnerLastLayer.topCross(f, base: base))
        add(SolverBeginnerLastLayer.topFace(f, base: base))
        add(SolverBeginnerLastLayer.topCorners(f, base: base))
        add(SolverBeginnerLastLayer.topEdges(f, base: base))
        return stages
    }
}
