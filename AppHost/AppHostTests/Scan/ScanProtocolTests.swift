@testable import AppHost
import XCTest

final class ScanProtocolTests: XCTestCase {
    func testGiaoThucVaLapMat() {
        let steps = ScanProtocol.cube3
        XCTAssertEqual(steps.count, 7)
        XCTAssertEqual(steps.map(\.instruction), [.start, .turnLeft, .turnLeft, .turnLeft, .backToFirst,
                                                  .tiltTopToYou, .tiltBottomToYou])
        XCTAssertEqual(steps.map(\.face), [.f, .r, .b, .l, nil, .u, .d])

        var rng = CubeRandom(seed: 9)
        let f = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
        let samples = ScanFixtures.samples(for: f, palette: .manualDefault, .daylight, seed: 3)
        var grids: [CubeFace: [CubeRGB]] = [:]
        for face in CubeFace.allCases { grids[face] = Array(samples[(face.rawValue * 9)..<(face.rawValue * 9 + 9)]) }
        XCTAssertEqual(ScanProtocol.assemble(grids), samples)
    }

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

final class ScanStabilizerTests: XCTestCase {
    private let frame = Array(repeating: CubeRGB(r: 0.5, g: 0.2, b: 0.1), count: 9)

    func testOnDinhSauNuaGiay() {
        var s = ScanStabilizer()
        var fired: [Int] = []
        for i in 0..<10 where s.feed(frame, at: Double(i) * 0.1) { fired.append(i) }
        XCTAssertEqual(fired, [6])

        var s2 = ScanStabilizer()
        var fired2: [Int] = []
        for i in 0..<14 {
            var f = frame
            if i == 3 { f[4] = CubeRGB(r: 0.1, g: 0.5, b: 0.2) }
            if s2.feed(f, at: Double(i) * 0.1) { fired2.append(i) }
        }
        // Khung 3 lệch, khung 4 lại lệch so với khung 3 ⇒ đếm lại từ khung 4.
        XCTAssertEqual(fired2, [10])

        s.reset()
        XCTAssertFalse(s.feed(frame, at: 5.0))
        XCTAssertTrue(s.feed(frame, at: 5.7))
    }
}
