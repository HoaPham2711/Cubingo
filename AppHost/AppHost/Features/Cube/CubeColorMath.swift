import Foundation

/// Màu sRGB đo được, mỗi kênh 0…1.
struct CubeRGB: Hashable {
    var r, g, b: Double

    init(r: Double, g: Double, b: Double) {
        self.r = r
        self.g = g
        self.b = b
    }

    init(hex: UInt32) {
        r = Double((hex >> 16) & 0xFF) / 255
        g = Double((hex >> 8) & 0xFF) / 255
        b = Double(hex & 0xFF) / 255
    }
}

/// Toán màu: sRGB → tuyến tính → XYZ (D65) → CIE Lab; ΔE76; cân trắng von Kries.
enum CubeColorMath {
    static func linear(_ c: Double) -> Double {
        c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4)
    }

    static func gamma(_ c: Double) -> Double {
        let v = min(max(c, 0), 1)
        return v <= 0.0031308 ? v * 12.92 : 1.055 * pow(v, 1 / 2.4) - 0.055
    }

    /// (L*, a*, b*).
    static func lab(_ c: CubeRGB) -> SIMD3<Double> {
        let r = linear(c.r), g = linear(c.g), b = linear(c.b)
        let x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
        let y = 0.2126 * r + 0.7152 * g + 0.0722 * b
        let z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
        func f(_ t: Double) -> Double {
            let e = 6.0 / 29.0
            return t > e * e * e ? cbrt(t) : t / (3 * e * e) + 4.0 / 29.0
        }
        let fx = f(x), fy = f(y), fz = f(z)
        return SIMD3(116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))
    }

    static func deltaE(_ a: CubeRGB, _ b: CubeRGB) -> Double {
        let d = lab(a) - lab(b)
        return (d * d).sum().squareRoot()
    }

    /// C* = √(a*² + b*²).
    static func chroma(_ c: CubeRGB) -> Double {
        let l = lab(c)
        return (l.y * l.y + l.z * l.z).squareRoot()
    }

    /// Góc hue h° của Lab, 0…360.
    static func hue(_ c: CubeRGB) -> Double {
        let l = lab(c)
        let h = atan2(l.z, l.y) * 180 / .pi
        return h < 0 ? h + 360 : h
    }

    /// Cân trắng von Kries trên RGB tuyến tính: `white` thành TRẮNG (1, 1, 1), các mẫu khác nhân cùng hệ số — vừa bỏ
    /// ám màu của đèn vừa chuẩn hoá độ sáng (camera tự chỉnh sáng làm mọi màu tối đi ⇒ tên màu theo L* lệch).
    static func whiteBalanced(_ samples: [CubeRGB], white: CubeRGB) -> [CubeRGB] {
        let wr = linear(white.r), wg = linear(white.g), wb = linear(white.b)
        guard wr > 1e-6, wg > 1e-6, wb > 1e-6 else { return samples }
        let kr = 1 / wr, kg = 1 / wg, kb = 1 / wb
        return samples.map {
            CubeRGB(r: gamma(linear($0.r) * kr), g: gamma(linear($0.g) * kg), b: gamma(linear($0.b) * kb))
        }
    }
}
