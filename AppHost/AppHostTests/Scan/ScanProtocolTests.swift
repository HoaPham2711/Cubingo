@testable import AppHost
import XCTest

final class ScanProtocolTests: XCTestCase {
    func testMeoAnhSang() {
        var rng = CubeRandom(seed: 10)
        let f = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
        XCTAssertEqual(ScanLighting.tip(ScanFixtures.samples(for: f, palette: .manualDefault, .dim, seed: 1)), .tooDark)
        XCTAssertNil(ScanLighting.tip(ScanFixtures.samples(for: f, palette: .manualDefault, .daylight, seed: 1)))
        XCTAssertNil(ScanLighting.tip(ScanFixtures.samples(for: .solved(n: 3), palette: .manualDefault, .daylight, seed: 1)),
                     "mặt trắng dưới nắng không phải chói")
        var glare = Array(ScanFixtures.samples(for: f, palette: .manualDefault, .daylight, seed: 1)[18..<27])
        for i in 0..<4 { glare[i] = CubeRGB(r: 1, g: 1, b: 1) }
        XCTAssertEqual(ScanLighting.tip(glare), .glare)
    }
}
