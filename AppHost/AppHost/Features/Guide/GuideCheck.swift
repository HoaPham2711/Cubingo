import Foundation

/// Quét kiểm tra sau một chặng: mặt cần chụp, các ô cần khớp, có cho xoay lưới tự do không.
struct GuideCheckSpec: Equatable {
    let face: CubeFace
    let indices: [Int]
    let anyRotation: Bool
}

enum GuideCheck {
    /// Bảng của plan: chặng nền kiểm mặt D, chặng trên kiểm U/F.
    static func spec(_ k: SolverStageKind) -> GuideCheckSpec {
        switch k {
        case .cross: return GuideCheckSpec(face: .d, indices: [1, 3, 5, 7], anyRotation: true)
        case .corners: return GuideCheckSpec(face: .d, indices: Array(0...8), anyRotation: true)
        case .middle: return GuideCheckSpec(face: .f, indices: Array(3...8), anyRotation: false)
        case .topCross: return GuideCheckSpec(face: .u, indices: [1, 3, 5, 7], anyRotation: true)
        case .topFace: return GuideCheckSpec(face: .u, indices: Array(0...8), anyRotation: true)
        case .topCorners: return GuideCheckSpec(face: .f, indices: [0, 2], anyRotation: false)
        case .topEdges: return GuideCheckSpec(face: .f, indices: Array(0...8), anyRotation: false)
        }
    }

    /// Lưới 9 màu đã chụp (theo nhãn của bảng màu) khớp mặt `spec.face` của `expected` ở các ô `spec.indices`.
    static func matches(_ grid: [CubeColor], expected: CubeFacelets, spec: GuideCheckSpec) -> Bool {
        guard grid.count == 9 else { return false }
        let want = (0..<9).map { expected.color(spec.face, $0) }
        var g = grid
        for _ in 0..<(spec.anyRotation ? 4 : 1) {
            if spec.indices.allSatisfy({ g[$0] == want[$0] }) { return true }
            let old = g
            for r in 0..<3 { for c in 0..<3 { g[r * 3 + c] = old[(2 - c) * 3 + r] } }
        }
        return false
    }
}
