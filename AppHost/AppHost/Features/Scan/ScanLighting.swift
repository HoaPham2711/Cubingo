import Foundation

enum ScanLightTip: Equatable { case tooDark, glare }

/// Mẹo ánh sáng khi quét: quá tối (L* trung bình < 25), hoặc chói (≥ 3 ô cháy sáng — mọi kênh ≥ 0,99). Không dùng
/// "L* cao + gần xám" vì đó cũng là ô trắng bình thường dưới nắng.
enum ScanLighting {
    static func tip(_ s: [CubeRGB]) -> ScanLightTip? {
        guard !s.isEmpty else { return nil }
        let meanL = s.map { CubeColorMath.lab($0).x }.reduce(0, +) / Double(s.count)
        if meanL < 25 { return .tooDark }
        if s.filter({ $0.r >= 0.99 && $0.g >= 0.99 && $0.b >= 0.99 }).count >= 3 { return .glare }
        return nil
    }
}
