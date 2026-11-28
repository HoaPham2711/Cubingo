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

    /// 54 mẫu theo thứ tự Kociemba.
    static var samples54: [CubeRGB] { CubeFace.allCases.flatMap { grid($0) } }

    /// Ảnh camera thấy ở một bước quét (thứ tự đọc ảnh).
    static func image(_ step: ScanStep) -> [CubeRGB] {
        let s = samples54
        return step.image.map { s[$0] }
    }

    /// Trạng thái dựng sẵn của màn quét để chụp ảnh UI.
    enum Preset { case midScan, turning }

    /// Đặt bởi `AppPreview` (route `scan` / `scanTurn`).
    static var preset: Preset?

    /// Ảnh camera khi quét kiểm tra mặt `face` trong màn giải (cùng phép chiếu với `GuideCheckFlow`).
    static func checkImage(_ face: CubeFace) -> [CubeRGB] {
        let s = samples54
        return ScanOrientation.imageIndices(GuideCheckFlow.orientation(face)).map { s[$0] }
    }

    /// Đã chụp 2 mặt, đang nhận màu mặt 3 (`midScan`) / đã chụp 3 mặt, đang chờ xoay (`turning`).
    @MainActor
    static func apply(to m: ScanCaptureModel, camera: ScanCamera) {
        guard let preset, m.capturedCount == 0 else { return }
        let k = preset == .midScan ? 2 : 3
        for st in ScanProtocol.cube3.prefix(k) {
            for _ in 0..<3 { m.observe(image(st)) }
            m.capture()
        }
        camera.freezeSeed(image(ScanProtocol.cube3[2]))
        m.observe(image(ScanProtocol.cube3[2]))
    }

    /// Kết quả quét đầy đủ của trạng thái mẫu (route `review`).
    static var scanResult: ScanResult { ScanClusterer.cluster(samples54, n: 3) }

    /// Như `scanResult` nhưng một ô bị đọc sai màu (route `review` có thông báo lỗi để chụp).
    static var scanResultWithMistake: ScanResult {
        let r = scanResult
        var f = r.facelets
        let i = (0..<54).first { $0 % 9 != 4 && f.stickers[$0] != f.stickers[CubeFace.u.rawValue * 9 + 4] }!
        f.stickers[i] = f.center(.u)
        var conf = r.confidence
        conf[i] = 1
        return ScanResult(facelets: f, palette: r.palette, confidence: conf, ambiguousCenters: nil)
    }
}
#endif
