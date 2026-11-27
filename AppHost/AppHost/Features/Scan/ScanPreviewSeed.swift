import Foundation

#if targetEnvironment(simulator)
/// Nguồn giả cho màn quét trên Simulator (không có camera): một trạng thái mẫu cố định (`CubeRandom(seed: 2026)`,
/// bảng màu `manualDefault`, ánh sáng ban ngày), quyền camera luôn có.
enum ScanPreviewSeed {
    static let state: CubeFacelets = {
        var rng = CubeRandom(seed: 2026)
        let centers = Dictionary(uniqueKeysWithValues: CubeFace.allCases.map { ($0, CubeColor($0)) })
        return CubeRandom.state(using: &rng).facelets(centers: centers)
    }()

    static let cameraAuth = ScanCameraAuth(status: { .authorized }, request: { true })

    /// Lưới 9 mẫu của một mặt: RGB chuẩn × 0,88 (phơi sáng) + lệch nhỏ tất định theo ô.
    static func grid(_ face: CubeFace) -> [CubeRGB] {
        (0..<9).map { i in
            let c = CubePalette.manualDefault.rgb(state.color(face, i))
            let j = Double((i * 7 + face.rawValue * 3) % 5) * 0.006
            return CubeRGB(r: min(c.r * 0.88 + j, 1), g: min(c.g * 0.88 + j, 1), b: min(c.b * 0.88 + j, 1))
        }
    }

    /// Kết quả quét đầy đủ của trạng thái mẫu (route `review`).
    static var scanResult: ScanResult {
        var grids: [CubeFace: [CubeRGB]] = [:]
        for f in CubeFace.allCases { grids[f] = grid(f) }
        return ScanClusterer.cluster(ScanProtocol.assemble(grids), n: 3)
    }
}
#endif
