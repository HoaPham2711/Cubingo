@testable import AppHost
import XCTest

/// Phát hiện của review cả nhánh (Đợt A) — mỗi test tái hiện một lỗi người dùng gặp được.
@MainActor
final class ReviewFixTests: XCTestCase {
    private func scrambled(_ seed: UInt64) -> CubeFacelets {
        var rng = CubeRandom(seed: seed)
        return CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
    }

    private func grids(_ f: CubeFacelets, tint: CubeRGB = CubeRGB(r: 1, g: 1, b: 1)) -> [CubeFace: [CubeRGB]] {
        let s = ScanFixtures.samples(for: f, palette: .manualDefault, tint: tint, noise: 0.03, seed: 1)
        var g: [CubeFace: [CubeRGB]] = [:]
        for face in CubeFace.allCases { g[face] = Array(s[(face.rawValue * 9)..<(face.rawValue * 9 + 9)]) }
        return g
    }

    // #1 "Scan again" quay về màn quét cũ đã có kết quả ⇒ phải chụp lại được.
    func testQuetLaiSauKhiCoKetQua() {
        let g = grids(scrambled(1))
        let m = ScanCaptureModel()
        for face: CubeFace in [.f, .r, .b, .l, .f, .u, .d] { m.capture(g[face]!) }
        XCTAssertNotNil(m.result)
        m.reset()
        XCTAssertNil(m.result)
        XCTAssertEqual(m.capturedCount, 0)
        XCTAssertTrue(m.allowsAutoCapture(g[.f]!))
        XCTAssertTrue(m.capture(g[.f]!))
    }

    // #2 Khung không phải khối (bàn, trần) không được tự chụp; chụp nhầm thì hoàn tác được.
    func testKhungKhongPhaiKhoiVaHoanTac() {
        let flat = Array(repeating: CubeRGB(r: 0.55, g: 0.5, b: 0.45), count: 9)
        let m = ScanCaptureModel()
        XCTAssertFalse(m.allowsAutoCapture(flat), "9 ô gần như cùng màu ⇒ không phải mặt khối")
        let g = grids(scrambled(2))
        m.capture(g[.f]!)
        m.capture(g[.r]!)
        XCTAssertEqual(m.capturedCount, 2)
        m.undoLast()
        XCTAssertEqual(m.capturedCount, 1)
        XCTAssertEqual(m.step.face, .r)
        XCTAssertTrue(m.capture(g[.r]!))
        // Mặt đã giải (9 ô cùng màu thật) vẫn chụp tay được.
        let solved = grids(.solved(n: 3))
        let m2 = ScanCaptureModel()
        XCTAssertTrue(m2.capture(solved[.f]!))
    }

    // #3 Quét kiểm tra chỉ tự chụp khi tâm khớp tâm của mặt được yêu cầu.
    func testKiemTraChiTuChupDungMat() {
        let f = scrambled(3)
        let g = grids(f)
        let spec = GuideCheck.spec(.cross)
        XCTAssertFalse(GuideCheckFlow.isRequestedSide(g[.f]!, palette: .manualDefault, white: nil, spec: spec, expected: f))
        XCTAssertTrue(GuideCheckFlow.isRequestedSide(g[.d]!, palette: .manualDefault, white: nil, spec: spec, expected: f))
    }

    // #4 Quét kiểm tra dưới đèn vàng ấm phải cân trắng như lần quét đầu.
    func testKiemTraDenAmCoCanTrang() {
        let warm = ScanFixtures.warmLamp.tint
        let start = scrambled(4)
        // Bảng màu đo từ lần quét đầu dưới cùng ánh đèn.
        let samples = ScanFixtures.samples(for: start, palette: .manualDefault, tint: warm, noise: 0.03, seed: 2)
        let scan = ScanClusterer.cluster(samples, n: 3)
        XCTAssertNotNil(scan.whiteReference)
        let stages = SolverBeginner.solve(start, base: scan.palette.baseColor)
        let afterTopFace = stages[4].end
        let check = Array(ScanFixtures.samples(for: afterTopFace, palette: .manualDefault, tint: warm, noise: 0.03,
                                               seed: 5)[(CubeFace.u.rawValue * 9)..<(CubeFace.u.rawValue * 9 + 9)])
        XCTAssertEqual(GuideCheckFlow.outcome(samples: check, palette: scan.palette, white: scan.whiteReference,
                                              spec: GuideCheck.spec(.topFace), expected: afterTopFace), .match)
    }

    // #5 Bấm Next khi hoạt ảnh trước chưa xong ⇒ khối 3D cuối cùng vẫn là trạng thái mới nhất.
    // ~1 s (chờ hoạt ảnh thật chạy xong) — cần để bắt race giữa hai Task hoạt ảnh.
    func testHoatAnhChongNhauVanDungTrangThai() async throws {
        let c = Cube3DController()
        let s1 = CubeFacelets.solved(n: 3).applying(CubeMove.parse("U2")!)
        let s2 = s1.applying(CubeMove.parse("R")!)
        c.update(state: s1, palette: .manualDefault, animation: Cube3DAnimation(move: CubeMove.parse("U2")![0],
                 reverse: false, token: 1), speed: .fast, highlight: nil, onEnd: {})
        try await Task.sleep(nanoseconds: 50_000_000)
        c.update(state: s2, palette: .manualDefault, animation: Cube3DAnimation(move: CubeMove.parse("R")![0],
                 reverse: false, token: 2), speed: .fast, highlight: nil, onEnd: {})
        try await Task.sleep(nanoseconds: 900_000_000)
        XCTAssertEqual(c.displayedFacelets, s2)
    }

    // #6 Câu của B phải nói rõ "nhìn từ phía trước".
    func testCauMatSauNoiRoGocNhin() {
        XCTAssertTrue(GuideText.sentence(CubeMove.parse("B")![0]).contains("as seen from the front"))
        XCTAssertTrue(GuideText.sentence(CubeMove.parse("B'")![0]).contains("as seen from the front"))
    }

    // #7 Bấm Teach me hai lần chỉ mở một màn chỉ bước.
    func testBamTeachMeHaiLan() async {
        let flow = FlowModel()
        flow.choose(.cube3)
        flow.didReview(scrambled(7), palette: .manualDefault)
        let solver = SolverQuick(tables: { solverTestTables })
        await flow.startGuide(.teach, quickSolver: solver)
        await flow.startGuide(.teach, quickSolver: solver)
        XCTAssertEqual(flow.path.filter { if case .guide = $0 { return true } else { return false } }.count, 1)
    }
}
