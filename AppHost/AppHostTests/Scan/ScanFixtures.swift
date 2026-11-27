@testable import AppHost
import Foundation

/// Mẫu màu tổng hợp cho test phân nhóm (dữ liệu Swift, không resource). Ảnh/mẫu thật thu ở cổng device sẽ thêm vào đây
/// ở Đợt B.
///
/// Mô hình: mẫu = RGB chuẩn × tint × phơi sáng 0,88 (camera tự chỉnh sáng, trắng không cháy) × (1 + nhiễu) theo
/// từng kênh, nhiễu Gauss có độ lệch `noise` (nhiễu tương đối — ảnh tối không bị nhiễu nuốt).
enum ScanFixtures {
    struct Condition {
        let name: String
        let tint: CubeRGB
        let noise: Double
    }

    static let daylight = Condition(name: "daylight", tint: CubeRGB(r: 1, g: 1, b: 1), noise: 0.03)
    static let warmLamp = Condition(name: "warmLamp", tint: CubeRGB(r: 1.0, g: 0.85, b: 0.6), noise: 0.04)
    static let coolLED = Condition(name: "coolLED", tint: CubeRGB(r: 0.85, g: 0.95, b: 1.05), noise: 0.04)
    static let dim = Condition(name: "dim", tint: CubeRGB(r: 0.35, g: 0.35, b: 0.35), noise: 0.05)
    static let all = [daylight, warmLamp, coolLED, dim]

    static let exposure = 0.88

    static func samples(for f: CubeFacelets, palette: CubePalette, tint: CubeRGB, noise: Double,
                        seed: UInt64) -> [CubeRGB] {
        var rng = CubeRandom(seed: seed)
        func gauss() -> Double {
            let u1 = max(Double.random(in: 0..<1, using: &rng), 1e-12), u2 = Double.random(in: 0..<1, using: &rng)
            return (-2 * log(u1)).squareRoot() * cos(2 * .pi * u2)
        }
        func ch(_ v: Double, _ t: Double) -> Double { min(max(v * t * exposure * (1 + noise * gauss()), 0), 1) }
        return f.stickers.map { c in
            let x = palette.rgb(c)
            return CubeRGB(r: ch(x.r, tint.r), g: ch(x.g, tint.g), b: ch(x.b, tint.b))
        }
    }

    static func samples(for f: CubeFacelets, palette: CubePalette, _ c: Condition, seed: UInt64) -> [CubeRGB] {
        samples(for: f, palette: palette, tint: c.tint, noise: c.noise, seed: seed)
    }
}

extension ScanFixtures.Condition {
    static var daylight: Self { ScanFixtures.daylight }
    static var warmLamp: Self { ScanFixtures.warmLamp }
    static var coolLED: Self { ScanFixtures.coolLED }
    static var dim: Self { ScanFixtures.dim }
}
