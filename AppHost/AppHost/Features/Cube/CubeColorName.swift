import Foundation

/// Tên màu gần nhất của một màu đo được (dùng trong mọi chữ nhắc màu — không giả định bảng màu chuẩn).
enum CubeColorName: String, CaseIterable {
    case white, yellow, orange, red, green, blue, purple, pink, black

    /// C* < 20 ⇒ trắng (L* ≥ 25) hoặc đen; còn lại theo hue h° của Lab; đỏ/tím có L* > 70 ⇒ hồng.
    static func nearest(_ c: CubeRGB) -> CubeColorName {
        let lab = CubeColorMath.lab(c)
        if CubeColorMath.chroma(c) < 20 { return lab.x >= 25 ? .white : .black }
        let h = CubeColorMath.hue(c)
        let byHue: CubeColorName
        switch h {
        case 25..<60: byHue = .orange
        case 60..<105: byHue = .yellow
        case 105..<190: byHue = .green
        case 190..<290: byHue = .blue
        case 290..<345: byHue = .purple
        default: byHue = .red
        }
        if (byHue == .red || byHue == .purple) && lab.x > 70 { return .pink }
        return byHue
    }

    /// Màu chuẩn của tên (nhập tay, bảng chọn màu).
    var standardRGB: CubeRGB {
        switch self {
        case .white: return CubeRGB(hex: 0xFFFFFF)
        case .yellow: return CubeRGB(hex: 0xFFD500)
        case .orange: return CubeRGB(hex: 0xFF5800)
        case .red: return CubeRGB(hex: 0xC41E3A)
        case .green: return CubeRGB(hex: 0x009E60)
        case .blue: return CubeRGB(hex: 0x0051BA)
        case .purple: return CubeRGB(hex: 0x8E44AD)
        case .pink: return CubeRGB(hex: 0xFF8FC8)
        case .black: return CubeRGB(hex: 0x202020)
        }
    }

    private var base: String {
        switch self {
        case .white: return String(localized: "white")
        case .yellow: return String(localized: "yellow")
        case .orange: return String(localized: "orange")
        case .red: return String(localized: "red")
        case .green: return String(localized: "green")
        case .blue: return String(localized: "blue")
        case .purple: return String(localized: "purple")
        case .pink: return String(localized: "pink")
        case .black: return String(localized: "black")
        }
    }

    /// Tên đã localize; hai màu cùng tên trên một khối ⇒ "light …" / "dark …".
    func localized(shade: CubeColorShade?) -> String {
        let name = base
        switch shade {
        case .light: return String(localized: "light \(name)")
        case .dark: return String(localized: "dark \(name)")
        case nil: return name
        }
    }
}

enum CubeColorShade { case light, dark }
