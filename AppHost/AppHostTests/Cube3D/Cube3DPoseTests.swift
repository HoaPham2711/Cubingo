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

    // Ô đánh dấu (lệch khi kiểm tra) đỏ liên tục tới khi bỏ đánh dấu.
    func testODanhDauDoLienTuc() {
        let c = controller(paint: Cube3DPaint(colors: [18: red, 19: red]))
        c.update(state: .solved(n: 3), palette: .manualDefault, animation: nil, speed: .medium, highlight: nil,
                 paint: Cube3DPaint(colors: [18: red, 19: red]), glow: .f, marked: [19], onEnd: {})
        XCTAssertEqual(c.displayedStickerRGB(19), Cube3DController.flashRGB)
        c.update(state: .solved(n: 3), palette: .manualDefault, animation: nil, speed: .medium, highlight: nil,
                 paint: Cube3DPaint(colors: [18: red, 19: red]), glow: .f, marked: [], onEnd: {})
        XCTAssertEqual(c.displayedStickerRGB(19), red)
    }

    // Khung cao hơn rộng (màn giải trên iPhone) ⇒ camera lùi xa để khối không tràn hai bên.
    func testCameraLuiXaKhiKhungCao() {
        XCTAssertEqual(Cube3DController.cameraDistance(for: CGSize(width: 300, height: 300)), 8.2, accuracy: 1e-4)
        XCTAssertEqual(Cube3DController.cameraDistance(for: CGSize(width: 300, height: 600)), 16.4, accuracy: 1e-4)
        XCTAssertEqual(Cube3DController.cameraDistance(for: CGSize(width: 600, height: 300)), 8.2, accuracy: 1e-4)
        XCTAssertEqual(Cube3DController.cameraDistance(for: .zero), 8.2, accuracy: 1e-4)
    }

    // Bấm Pause giữa lúc đang quay ⇒ khối dừng ngay ở trạng thái đích, không gọi onEnd.
    func testDungNgayKhiPause() {
        let c = controller(paint: nil)
        let m = CubeMove(.face(.d), 2)
        let target = CubeFacelets.solved(n: 3).applying(m)
        var ended = 0
        c.update(state: target, palette: .manualDefault, animation: Cube3DAnimation(move: m, reverse: false, token: 1),
                 speed: .slow, highlight: nil, onEnd: { ended += 1 })
        XCTAssertNotEqual(c.displayedFacelets, target)
        c.finish(token: 1, state: target, palette: .manualDefault, highlight: nil)
        XCTAssertEqual(c.displayedFacelets, target)
        XCTAssertFalse(c.isAnimating)
        XCTAssertEqual(ended, 0)
    }

    // Kéo lại khi khối đang trôi về chỗ ⇒ bắt đầu từ hướng đang thấy, không giật về góc chuẩn.
    func testKeoLaiKhongGiat() {
        let c = controller(paint: nil)
        c.setDrag(CGSize(width: 120, height: 60))
        let dragged = c.currentOrientation
        c.setDrag(.zero)
        c.resetView(duration: 0.4)
        c.setDrag(CGSize(width: 1, height: 0))
        let d = abs(simd_dot(dragged.vector, c.currentOrientation.vector))
        XCTAssertGreaterThan(d, 0.999)
    }

    // Đang kéo tay ⇒ không diễn lại động tác (khối không nhảy dưới tay).
    func testKhongDienLaiKhiDangKeo() {
        let s = ScanProtocol.cube3
        let c = controller(paint: nil, pose: Cube3DPose(orientation: s[1].orientation, token: 0))
        c.setDrag(CGSize(width: 40, height: 0))
        c.setPose(Cube3DPose(orientation: s[1].orientation, replayFrom: s[0].orientation, token: 1), animated: true)
        XCTAssertEqual(c.replaysPlayed, 0)
        c.setDrag(.zero)
        c.setPose(Cube3DPose(orientation: s[1].orientation, replayFrom: s[0].orientation, token: 2), animated: true)
        XCTAssertEqual(c.replaysPlayed, 1)
    }
}
