@testable import AppHost
import XCTest

@MainActor
final class ScanCaptureModelTests: XCTestCase {
    private var state: CubeFacelets!
    private var images: [[CubeRGB]] = []

    override func setUp() {
        var rng = CubeRandom(seed: 77)
        state = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
        let samples = ScanFixtures.samples(for: state, palette: .manualDefault, .daylight, seed: 4)
        images = ScanProtocol.cube3.map { st in st.image.map { samples[$0] } }
    }

    /// Đưa ảnh của bước `i` vào camera (vài khung để màu sống hội tụ) rồi bấm ✓.
    private func show(_ m: ScanCaptureModel, _ img: [CubeRGB]) {
        for _ in 0..<30 { m.observe(img) }
    }

    func testQuetDu6MatRaKetQua() {
        let m = ScanCaptureModel()
        for i in 0..<6 {
            show(m, images[i])
            let o = m.capture()
            if i < 5 { XCTAssertEqual(o, .accepted, "bước \(i)") } else {
                guard case .finished(let r) = o else { return XCTFail("\(o)") }
                XCTAssertEqual(r.facelets, state)
            }
        }
        XCTAssertEqual(m.capturedCount, 6)
        XCTAssertEqual(m.result?.facelets, state)
    }

    func testMatTrungBiTuChoi() {
        let m = ScanCaptureModel()
        show(m, images[0])
        XCTAssertEqual(m.capture(), .accepted)
        show(m, images[0])
        XCTAssertEqual(m.capture(), .duplicate(.f))
        XCTAssertEqual(m.stepIndex, 1)
    }

    func testChoXoayRoiMoiNhanMauMoi() {
        let m = ScanCaptureModel()
        show(m, images[0])
        m.capture()
        XCTAssertTrue(m.awaitingTurn)
        show(m, images[0])
        XCTAssertTrue(m.awaitingTurn)
        XCTAssertNil(m.paint.colors[9])
        m.observe(images[1])
        XCTAssertFalse(m.awaitingTurn)
        XCTAssertNotNil(m.paint.colors[9])
        XCTAssertEqual(m.paint.colors[18], images[0][0])
    }

    func testHoanTac() {
        let m = ScanCaptureModel()
        show(m, images[0]); m.capture()
        show(m, images[1]); m.capture()
        m.undoLast()
        XCTAssertEqual(m.stepIndex, 1)
        XCTAssertFalse((9...17).contains { m.paint.colors[$0] != nil })
        XCTAssertEqual(m.glowFace, .r)
        for i in 1..<6 { show(m, images[i]); m.capture() }
        XCTAssertNotNil(m.result)
        m.undoLast()
        XCTAssertNil(m.result)
        XCTAssertEqual(m.stepIndex, 5)
    }

    func testFinishAgainSauKhiDu6() {
        let m = ScanCaptureModel()
        for i in 0..<6 { show(m, images[i]); m.capture() }
        guard case .finished(let r) = m.capture() else { return XCTFail() }
        XCTAssertEqual(r.facelets, state)
    }

    func testChupMatDeuMauVanNhan() {
        let m = ScanCaptureModel()
        let solved = ScanFixtures.samples(for: .solved(n: 3), palette: .manualDefault, .daylight, seed: 2)
        show(m, ScanProtocol.cube3[0].image.map { solved[$0] })
        XCTAssertEqual(m.capture(), .accepted)
    }

    func testLamMuotVaBoKhungThieu() {
        let m = ScanCaptureModel()
        XCTAssertEqual(m.capture(), .notReady)
        let a = Array(repeating: CubeRGB(r: 0.2, g: 0.2, b: 0.2), count: 9)
        let b = Array(repeating: CubeRGB(r: 0.8, g: 0.8, b: 0.8), count: 9)
        m.observe(a)
        m.observe(Array(b.prefix(3)))
        XCTAssertEqual(m.live, a)
        m.observe(b)
        XCTAssertGreaterThan(m.live[0].r, 0.2)
        XCTAssertLessThan(m.live[0].r, 0.8)
    }

    func testPoseVaGlow() {
        let m = ScanCaptureModel()
        for i in 0..<4 { show(m, images[i]); m.capture() }
        XCTAssertEqual(m.glowFace, .u)
        XCTAssertEqual(ScanOrientation.frontFace(m.pose), .u)
    }

    func testA11yMoTaBuoc() {
        let st = ScanProtocol.cube3
        let s = ScanText.accessibility(step: st[1], captured: 1, awaitingTurn: true)
        XCTAssertTrue(s.contains("1 of 6"), s)
        XCTAssertTrue(s.contains("turn the whole cube left"), s)
        let turns: [ScanTurn] = [.none, .left, .tiltTowardYou, .flipTowardYou, .tiltAwayFromYou]
        XCTAssertEqual(Set(turns.map(ScanText.turn)).count, turns.count)
        XCTAssertTrue(ScanText.accessibility(step: st[5], captured: 6, awaitingTurn: true).contains("All 6"))
    }
}
