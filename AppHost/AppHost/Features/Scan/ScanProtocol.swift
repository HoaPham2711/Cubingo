import simd

/// Một bước quét: mặt nó chụp, động tác phải làm TRƯỚC khi chụp, hướng khối lúc chụp, và chỉ số facelet của từng ô
/// ảnh (`image[k]` = facelet của ô ảnh thứ k).
struct ScanStep: Equatable {
    let face: CubeFace
    let turn: ScanTurn
    let orientation: simd_quatf
    let image: [Int]
}

/// Giao thức quét 3×3: F, (xoay trái) R, B, L, (lật mặt trên về phía mình) U, (lật tiếp 180°) D — 6 lần bấm, không
/// quay về mặt đầu. Hướng lưới mỗi mặt là xác định (`ScanOrientation.imageIndices`).
enum ScanProtocol {
    static let cube3: [ScanStep] = {
        let plan: [(CubeFace, ScanTurn)] = [(.f, .none), (.r, .left), (.b, .left), (.l, .left),
                                            (.u, .tiltTowardYou), (.d, .flipTowardYou)]
        var q = ScanOrientation.rotation(.none)
        return plan.map { face, turn in
            q = simd_normalize(ScanOrientation.rotation(turn) * q)
            return ScanStep(face: face, turn: turn, orientation: q, image: ScanOrientation.imageIndices(q))
        }
    }()

    /// Tư thế giữa của bước lật 180° (U → D): lật thêm một nấc từ U ⇒ mặt R hướng vào camera.
    static let flipMidpoint = simd_normalize(ScanOrientation.rotation(.tiltTowardYou) * cube3[4].orientation)

    /// 6 ảnh (theo thứ tự bước) ⇒ 54 mẫu theo thứ tự Kociemba (U R F D L B).
    static func assemble(_ images: [[CubeRGB]]) -> [CubeRGB] {
        var out = [CubeRGB](repeating: CubeRGB(r: 0, g: 0, b: 0), count: 54)
        for (step, img) in zip(cube3, images) {
            for (k, idx) in step.image.enumerated() where k < img.count { out[idx] = img[k] }
        }
        return out
    }
}
