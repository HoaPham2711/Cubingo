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

    // Review #1: lật 180° (U → D) phải đi qua tư thế giữa theo đúng chiều "lật về phía mình".
    func testLat180DiQuaTuTheGiua() {
        let s = ScanProtocol.cube3
        XCTAssertEqual(ScanOrientation.frontFace(ScanProtocol.flipMidpoint), .r)
        let path = Cube3DPose.waypoints(from: s[4].orientation, to: s[5].orientation, via: ScanProtocol.flipMidpoint)
        XCTAssertEqual(path.count, 2)
        var prev = s[4].orientation
        for q in path {
            XCTAssertLessThan(Cube3DPose.angle(prev, q), Float.pi / 2 + 0.01)
            prev = q
        }
        // Ngược lại (hoàn tác D → U) cũng qua tư thế giữa; bước 90° thì không cần.
        XCTAssertEqual(Cube3DPose.waypoints(from: s[5].orientation, to: s[4].orientation,
                                            via: ScanProtocol.flipMidpoint).count, 2)
        XCTAssertEqual(Cube3DPose.waypoints(from: s[0].orientation, to: s[1].orientation,
                                            via: ScanProtocol.flipMidpoint).count, 1)
    }

    // Review #5: màu sống đổi một ô ⇒ chỉ gán lại vật liệu một ô.
    func testChiGanVatLieuOThayDoi() {
        var paint = Cube3DPaint(colors: [18: red])
        let c = controller(paint: paint)
        let before = c.materialAssignments
        paint.colors[19] = red
        c.update(state: .solved(n: 3), palette: .manualDefault, animation: nil, speed: .medium, highlight: nil,
                 paint: paint, glow: .f, onEnd: {})
        XCTAssertEqual(c.materialAssignments - before, 1)
    }

    // Review #4: nháy mới thay nháy cũ ⇒ ô của lần nháy cũ trả về màu thường ngay.
    func testNhayMoiXoaNhayCu() async throws {
        let c = controller(paint: Cube3DPaint(colors: [18: red, 19: red]))
        c.play(Cube3DEffect(kind: .flash([18]), token: 1))
        try await Task.sleep(nanoseconds: 50_000_000)
        XCTAssertEqual(c.displayedStickerRGB(18), Cube3DController.flashRGB)
        c.play(Cube3DEffect(kind: .flash([19]), token: 2))
        XCTAssertEqual(c.displayedStickerRGB(18), red)
        c.play(Cube3DEffect(kind: .shake, token: 3))
        try await Task.sleep(nanoseconds: 50_000_000)
        XCTAssertEqual(c.displayedStickerRGB(19), Cube3DController.flashRGB, "lắc không huỷ nháy")
    }
}
