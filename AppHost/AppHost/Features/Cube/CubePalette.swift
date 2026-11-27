import Foundation

/// Bảng màu của MỘT khối thật (đo khi quét hoặc chọn khi nhập tay): nhãn 0…5 ⇒ RGB, tên đọc được.
struct CubePalette: Equatable {
    let colors: [CubeColor: CubeRGB]

    init(colors: [CubeColor: CubeRGB]) {
        self.colors = colors
    }

    func rgb(_ c: CubeColor) -> CubeRGB { colors[c] ?? CubeRGB(r: 0.5, g: 0.5, b: 0.5) }

    func colorName(_ c: CubeColor) -> CubeColorName { CubeColorName.nearest(rgb(c)) }

    /// Tên hiển thị; hai màu cùng tên ⇒ màu L* cao hơn "light …", thấp hơn "dark …".
    func name(_ c: CubeColor) -> String {
        let mine = colorName(c)
        let same = colors.keys.filter { colorName($0) == mine }
        guard same.count > 1 else { return mine.localized(shade: nil) }
        let l = CubeColorMath.lab(rgb(c)).x
        let isLightest = same.allSatisfy { CubeColorMath.lab(rgb($0)).x <= l }
        return mine.localized(shade: isLightest ? .light : .dark)
    }

    /// Màu nền chặng 1 của Teach me: chroma thấp nhất trong các màu L* > 60; không có ⇒ màu L* cao nhất.
    var baseColor: CubeColor {
        let keys = colors.keys.sorted { $0.raw < $1.raw }
        let bright = keys.filter { CubeColorMath.lab(rgb($0)).x > 60 }
        if let c = bright.min(by: { CubeColorMath.chroma(rgb($0)) < CubeColorMath.chroma(rgb($1)) }) { return c }
        return keys.max { CubeColorMath.lab(rgb($0)).x < CubeColorMath.lab(rgb($1)).x }!
    }

    /// Bảng mặc định cho nhập tay: U R F D L B = trắng, đỏ, xanh lá, vàng, cam, xanh dương.
    static let manualDefault = CubePalette(colors: [
        CubeColor(raw: 0): CubeColorName.white.standardRGB,
        CubeColor(raw: 1): CubeColorName.red.standardRGB,
        CubeColor(raw: 2): CubeColorName.green.standardRGB,
        CubeColor(raw: 3): CubeColorName.yellow.standardRGB,
        CubeColor(raw: 4): CubeColorName.orange.standardRGB,
        CubeColor(raw: 5): CubeColorName.blue.standardRGB,
    ])
}
