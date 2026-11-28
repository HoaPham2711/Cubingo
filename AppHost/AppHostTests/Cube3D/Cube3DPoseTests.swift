@testable import AppHost
import simd
import XCTest

@MainActor
final class Cube3DPoseTests: XCTestCase {
    private let red = CubeRGB(r: 0.8, g: 0.1, b: 0.15)

    private func controller(paint: Cube3DPaint?, pose: Cube3DPose? = nil) -> Cube3DController {
        let c = Cube3DController()
        c.update(state: .solved(n: 3), palette: .manualDefault, animation: nil, speed: .medium, highlight: nil,
                 paint: paint, glow: .f, onEnd: {})
        c.setPose(pose, animated: false)
        return c
    }

    func testPaintToMauVaOTrong() {
        let c = controller(paint: Cube3DPaint(colors: [18: red]))
        XCTAssertEqual(c.displayedStickerRGB(18), red)
        XCTAssertEqual(c.displayedStickerRGB(0), Cube3DController.blankRGB)
    }

    func testKhongPaintThiTheoBangMau() {
        let c = controller(paint: nil)
        XCTAssertEqual(c.displayedStickerRGB(0), CubePalette.manualDefault.rgb(CubeFacelets.solved(n: 3).stickers[0]))
    }

    func testFaceletIndexKhopFacelets() {
        var rng = CubeRandom(seed: 5)
        let f = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
        let s = Cube3DScene(f)
        var seen = Set<Int>()
        for (i, c) in s.cubies.enumerated() {
            for (local, color) in c.stickers {
                let idx = s.faceletIndex(cubie: i, local: local)
                XCTAssertEqual(f.stickers[idx], color)
                seen.insert(idx)
            }
        }
        XCTAssertEqual(seen, Set(0..<54))
    }

    func testPoseDichDen() {
        let q = ScanProtocol.cube3[1].orientation
        let c = controller(paint: nil, pose: Cube3DPose(orientation: q))
        let want = Cube3DController.restOrientation * q
        let got = c.targetOrientation
        XCTAssertLessThan(min(simd_length(got.vector - want.vector), simd_length(got.vector + want.vector)), 1e-4)
    }
}
