@testable import AppHost
import XCTest

final class ScanClustererTests: XCTestCase {
    private func state(_ seed: UInt64) -> CubeFacelets {
        var rng = CubeRandom(seed: seed)
        return CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
    }

    func testHungarianNhoDungToiUu() {
        let cost: [[Double]] = [[9, 2, 7, 8], [6, 4, 3, 7], [5, 8, 1, 8], [7, 6, 9, 4]]
        let a = ScanHungarian.assign(cost: cost)
        XCTAssertEqual(a, [1, 0, 2, 3])
        XCTAssertEqual(Set(a).count, 4)
        XCTAssertEqual(ScanHungarian.assign(cost: [[1]]), [0])
    }

    func testPhanNhomDungMoiDieuKien() {
        for cond in ScanFixtures.all {
            for i in 0..<40 {
                let f = state(UInt64(200 + i))
                let samples = ScanFixtures.samples(for: f, palette: .manualDefault, cond, seed: UInt64(i))
                let r = ScanClusterer.cluster(samples, n: 3)
                XCTAssertEqual(r.facelets, f, "\(cond.name) #\(i)")
                for c in CubeColor.all { XCTAssertEqual(r.facelets.stickers.filter { $0 == c }.count, 9) }
                XCTAssertNil(r.ambiguousCenters, "\(cond.name) #\(i)")
                XCTAssertEqual(r.confidence.count, 54)
            }
        }
    }

    /// Dưới đèn vàng ấm tâm trắng có C* ≈ 27: vẫn phải được dùng làm mốc cân trắng, không thì ô trắng bị gọi "yellow".
    func testDenAmTrangVanLaTrang() {
        for i in 0..<10 {
            let f = state(UInt64(700 + i))
            let r = ScanClusterer.cluster(ScanFixtures.samples(for: f, palette: .manualDefault, .warmLamp, seed: UInt64(i)), n: 3)
            XCTAssertEqual(r.palette.colorName(CubeColor(raw: 0)), .white, "#\(i)")
            XCTAssertEqual(r.palette.colorName(CubeColor(raw: 3)), .yellow, "#\(i)")
            XCTAssertEqual(r.palette.baseColor, CubeColor(raw: 0))
        }
    }

    func testDenAmVanTachDoCam() {
        let red = CubeColor(raw: 1), orange = CubeColor(raw: 4)
        for i in 0..<40 {
            let f = state(UInt64(300 + i))
            let samples = ScanFixtures.samples(for: f, palette: .manualDefault, tint: ScanFixtures.warmLamp.tint,
                                               noise: 0.06, seed: UInt64(1000 + i))
            let got = ScanClusterer.cluster(samples, n: 3).facelets
            for j in 0..<54 {
                if f.stickers[j] == red { XCTAssertNotEqual(got.stickers[j], orange, "#\(i) ô \(j)") }
                if f.stickers[j] == orange { XCTAssertNotEqual(got.stickers[j], red, "#\(i) ô \(j)") }
            }
        }
    }

    func testBangMauLa() {
        var colors = CubePalette.manualDefault.colors
        colors[CubeColor(raw: 1)] = CubeColorName.purple.standardRGB
        colors[CubeColor(raw: 4)] = CubeColorName.pink.standardRGB
        colors[CubeColor(raw: 5)] = CubeColorName.black.standardRGB
        let palette = CubePalette(colors: colors)
        for i in 0..<20 {
            let f = state(UInt64(400 + i))
            let r = ScanClusterer.cluster(ScanFixtures.samples(for: f, palette: palette, .daylight, seed: UInt64(i)), n: 3)
            XCTAssertEqual(r.facelets, f)
            XCTAssertEqual(r.palette.colorName(CubeColor(raw: 1)), .purple)
            XCTAssertEqual(r.palette.colorName(CubeColor(raw: 4)), .pink)
            XCTAssertEqual(r.palette.colorName(CubeColor(raw: 5)), .black)
        }
    }

    func testHaiTamQuaGiong() {
        let f = state(500)
        var samples = ScanFixtures.samples(for: f, palette: .manualDefault, .daylight, seed: 1)
        let r = samples[CubeFace.r.rawValue * 9 + 4]
        samples[CubeFace.l.rawValue * 9 + 4] = CubeRGB(r: r.r + 0.01, g: r.g - 0.01, b: r.b)
        let result = ScanClusterer.cluster(samples, n: 3)
        XCTAssertNotNil(result.ambiguousCenters)
        if let (a, b) = result.ambiguousCenters {
            XCTAssertEqual(Set([a, b]), [CubeColor(.r), CubeColor(.l)])
        }
    }

    func testDoTinCayThapOOBiLech() {
        let f = state(600)
        var samples = ScanFixtures.samples(for: f, palette: .manualDefault, .daylight, seed: 2)
        // Một ô đỏ bị đèn biến thành giữa đỏ và cam.
        let i = (0..<54).first { $0 % 9 != 4 && f.stickers[$0] == CubeColor(raw: 1) }!
        samples[i] = CubeRGB(r: 0.88, g: 0.2, b: 0.1)
        let r = ScanClusterer.cluster(samples, n: 3)
        let lowest = (0..<54).min { r.confidence[$0] < r.confidence[$1] }!
        XCTAssertEqual(lowest, i)
        XCTAssertEqual(r.confidence[4], 100)
    }
}
