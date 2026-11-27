@testable import AppHost
import simd
import XCTest

final class Cube3DSceneTests: XCTestCase {
    private func m(_ s: String) -> CubeMove { CubeMove.parse(s)![0] }

    func testCanhKhopFaceletSauMoiBuoc() {
        var rng = CubeRandom(seed: 13)
        var f = CubeFacelets.solved(n: 3)
        var scene = Cube3DScene(f)
        let all = CubeMove.faceMoves + CubeMove.rotations
        for i in 0..<300 {
            let mv = all[Int.random(in: 0..<all.count, using: &rng)]
            scene.apply(mv)
            f = f.applying(mv)
            XCTAssertEqual(scene.facelets(), f, "bước \(i) \(mv.notation)")
        }
    }

    func testThanhVienLop() {
        let scene = Cube3DScene(.solved(n: 3))
        XCTAssertEqual(scene.cubies.count, 26)
        XCTAssertEqual(scene.members(m("R")).count, 9)
        XCTAssertEqual(scene.members(m("x")).count, 26)
        XCTAssertTrue(Set(scene.members(m("U"))).isDisjoint(with: scene.members(m("D"))))
    }

    func testGocQuay() {
        let r = Cube3DScene.axisAngle(m("R"))
        XCTAssertEqual(r.axis, SIMD3<Float>(1, 0, 0))
        XCTAssertEqual(r.radians, -.pi / 2, accuracy: 1e-6)
        let u2 = Cube3DScene.axisAngle(m("U2"))
        XCTAssertEqual(u2.axis, SIMD3<Float>(0, 1, 0))
        XCTAssertEqual(u2.radians, -.pi, accuracy: 1e-6)
        let l = Cube3DScene.axisAngle(m("L"))
        XCTAssertEqual(l.axis, SIMD3<Float>(1, 0, 0))
        XCTAssertEqual(l.radians, .pi / 2, accuracy: 1e-6)
        XCTAssertEqual(Cube3DScene.axisAngle(m("R'")).radians, .pi / 2, accuracy: 1e-6)
    }

    func testDungTuFaceletBatKy() {
        var rng = CubeRandom(seed: 14)
        for _ in 0..<20 {
            let f = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
            XCTAssertEqual(Cube3DScene(f).facelets(), f)
        }
    }
}
