import simd
import SwiftUI

enum GuideCheckOutcome: Equatable { case match, mismatch }

/// Kết quả nút ✓ khi quét kiểm tra: sai mặt (không chấm), khớp, hay lệch (kèm chỉ số facelet lệch để nháy đỏ).
enum GuideCheckPress: Equatable {
    case wrongSide
    case match
    case mismatch([Int])
}

/// Quét kiểm tra một mặt sau chặng: gán mỗi ô màu gần nhất của bảng màu (ΔE76) rồi so với trạng thái mong đợi.
enum GuideCheckFlow {
    static func classify(_ samples: [CubeRGB], palette: CubePalette) -> [CubeColor] {
        let keys = palette.colors.keys.sorted { $0.raw < $1.raw }
        return samples.map { s in
            keys.min { CubeColorMath.deltaE(s, palette.rgb($0)) < CubeColorMath.deltaE(s, palette.rgb($1)) }!
        }
    }

    /// Như `classify` nhưng cân trắng trước bằng mốc của lần quét đầu (bảng màu đo sau cân trắng).
    static func classify(_ samples: [CubeRGB], palette: CubePalette, white: CubeRGB?) -> [CubeColor] {
        classify(white.map { CubeColorMath.whiteBalanced(samples, white: $0) } ?? samples, palette: palette)
    }

    /// Mặt đang thấy có đúng là mặt được yêu cầu không (tâm khớp) — gác tự chụp ở chế độ kiểm tra.
    static func isRequestedSide(_ s: [CubeRGB], palette: CubePalette, white: CubeRGB?, spec: GuideCheckSpec,
                                expected: CubeFacelets) -> Bool {
        guard s.count == 9 else { return false }
        return classify(s, palette: palette, white: white)[4] == expected.center(spec.face)
    }

    static func outcome(samples: [CubeRGB], palette: CubePalette, white: CubeRGB?, spec: GuideCheckSpec,
                        expected: CubeFacelets) -> GuideCheckOutcome {
        GuideCheck.matches(classify(samples, palette: palette, white: white), expected: expected, spec: spec)
            ? .match : .mismatch
    }

    static func outcome(samples: [CubeRGB], palette: CubePalette, spec: GuideCheckSpec,
                        expected: CubeFacelets) -> GuideCheckOutcome {
        GuideCheck.matches(classify(samples, palette: palette), expected: expected, spec: spec) ? .match : .mismatch
    }

    // MARK: - Quét kiểm tra ngay trong màn giải

    /// Động tác đưa mặt cần kiểm vào camera, từ cách cầm của màn giải (mặt trên lên trên, mặt trước hướng về mình).
    static func checkTurn(_ face: CubeFace) -> ScanTurn {
        switch face {
        case .u: return .tiltTowardYou
        case .d: return .tiltAwayFromYou
        default: return .none
        }
    }

    static func orientation(_ face: CubeFace) -> simd_quatf { ScanOrientation.rotation(checkTurn(face)) }

    /// Ảnh camera (thứ tự đọc ảnh) ⇒ lưới 9 ô của `face` theo thứ tự đọc của mặt.
    static func faceGrid(_ image: [CubeRGB], face: CubeFace) -> [CubeRGB] {
        var grid = image
        for (k, idx) in ScanOrientation.imageIndices(orientation(face)).enumerated() where k < image.count {
            grid[idx - face.rawValue * 9] = image[k]
        }
        return grid
    }

    static func press(image: [CubeRGB], palette: CubePalette, white: CubeRGB?, spec: GuideCheckSpec,
                      expected: CubeFacelets) -> GuideCheckPress {
        guard image.count == 9 else { return .wrongSide }
        let grid = classify(faceGrid(image, face: spec.face), palette: palette, white: white)
        guard grid[4] == expected.center(spec.face) else { return .wrongSide }
        if GuideCheck.matches(grid, expected: expected, spec: spec) { return .match }
        let want = (0..<9).map { expected.color(spec.face, $0) }
        var g = grid
        var best: [Int]?
        for _ in 0..<(spec.anyRotation ? 4 : 1) {
            let bad = spec.indices.filter { g[$0] != want[$0] }
            if best == nil || bad.count < best!.count { best = bad }
            let old = g
            for r in 0..<3 { for c in 0..<3 { g[r * 3 + c] = old[(2 - c) * 3 + r] } }
        }
        return .mismatch((best ?? []).map { spec.face.rawValue * 9 + $0 })
    }

    /// Màu cho khối 3D khi kiểm tra: mọi ô theo trạng thái mong đợi, riêng mặt `face` nhận màu camera sống.
    static func paint(state: CubeFacelets, palette: CubePalette, face: CubeFace, live: [CubeRGB]) -> Cube3DPaint {
        var c: [Int: CubeRGB] = [:]
        for i in state.stickers.indices { c[i] = palette.rgb(state.stickers[i]) }
        if live.count == 9 {
            for (k, idx) in ScanOrientation.imageIndices(orientation(face)).enumerated() { c[idx] = live[k] }
        }
        return Cube3DPaint(colors: c)
    }
}
