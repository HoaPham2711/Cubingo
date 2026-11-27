@testable import AppHost
import XCTest

final class CubeColorTests: XCTestCase {
    private typealias M = CubeColorMath

    func testLabVaDeltaE() {
        let white = M.lab(CubeRGB(hex: 0xFFFFFF))
        XCTAssertEqual(white.x, 100, accuracy: 0.5)
        XCTAssertEqual(white.y, 0, accuracy: 0.5)
        XCTAssertEqual(white.z, 0, accuracy: 0.5)
        let red = CubeRGB(hex: 0xC41E3A), orange = CubeRGB(hex: 0xFF5800)
        XCTAssertEqual(M.deltaE(red, red), 0)
        XCTAssertGreaterThan(M.deltaE(red, orange), 20)
        XCTAssertEqual(M.lab(red).x, 42.7, accuracy: 0.5)
    }

    func testTenMauChuan() {
        let expected: [CubeColorName] = [.white, .red, .green, .yellow, .orange, .blue]
        for (i, name) in expected.enumerated() {
            XCTAssertEqual(CubeColorName.nearest(CubePalette.manualDefault.rgb(CubeColor(raw: UInt8(i)))), name)
        }
        XCTAssertEqual(CubeColorName.nearest(CubeRGB(hex: 0x8E44AD)), .purple)
        XCTAssertEqual(CubeColorName.nearest(CubeRGB(hex: 0xFF8FC8)), .pink)
        XCTAssertEqual(CubeColorName.nearest(CubeRGB(hex: 0x202020)), .black)
        for name in CubeColorName.allCases { XCTAssertEqual(CubeColorName.nearest(name.standardRGB), name, "\(name)") }
    }

    func testCanTrangDuaTamTrangVeXam() {
        let tint = CubeRGB(r: 1.0, g: 0.9, b: 0.7)
        let raw = CubePalette.manualDefault.colors.keys.sorted { $0.raw < $1.raw }.map { c -> CubeRGB in
            let x = CubePalette.manualDefault.rgb(c)
            return CubeRGB(r: x.r * tint.r, g: x.g * tint.g, b: x.b * tint.b)
        }
        XCTAssertGreaterThan(M.chroma(raw[0]), 10, "trắng ám vàng phải có sắc độ")
        let balanced = M.whiteBalanced(raw, white: raw[0])
        XCTAssertLessThan(M.chroma(balanced[0]), 3)
        XCTAssertEqual(CubeColorName.nearest(balanced[3]), .yellow)
    }

    func testHaiMauCungTenCoShade() {
        var colors = CubePalette.manualDefault.colors
        colors[CubeColor(raw: 2)] = CubeRGB(hex: 0x00A050)
        colors[CubeColor(raw: 5)] = CubeRGB(hex: 0x7FD08F)
        let p = CubePalette(colors: colors)
        XCTAssertEqual(p.name(CubeColor(raw: 2)), "dark green")
        XCTAssertEqual(p.name(CubeColor(raw: 5)), "light green")
        XCTAssertEqual(p.name(CubeColor(raw: 1)), "red")
    }

    func testMauNen() {
        XCTAssertEqual(CubePalette.manualDefault.baseColor, CubeColor(raw: 0))
        var noWhite = CubePalette.manualDefault.colors
        noWhite[CubeColor(raw: 0)] = CubeRGB(hex: 0xFFC0D0)
        XCTAssertEqual(CubePalette(colors: noWhite).baseColor, CubeColor(raw: 0), "hồng nhạt: chroma thấp nhất có L* > 60")
        let dark: [CubeColor: CubeRGB] = [
            CubeColor(raw: 0): CubeRGB(hex: 0x202020), CubeColor(raw: 1): CubeRGB(hex: 0x8E44AD),
            CubeColor(raw: 2): CubeRGB(hex: 0x0051BA), CubeColor(raw: 3): CubeRGB(hex: 0x009E60),
            CubeColor(raw: 4): CubeRGB(hex: 0xC41E3A), CubeColor(raw: 5): CubeRGB(hex: 0x603000),
        ]
        XCTAssertEqual(CubePalette(colors: dark).baseColor, CubeColor(raw: 3), "mọi màu L* ≤ 60 ⇒ màu sáng nhất")
    }
}
