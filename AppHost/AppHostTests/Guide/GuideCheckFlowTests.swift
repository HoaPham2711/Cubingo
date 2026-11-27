@testable import AppHost
import XCTest

final class GuideCheckFlowTests: XCTestCase {
    private func scrambled(_ seed: UInt64) -> CubeFacelets {
        var rng = CubeRandom(seed: seed)
        return CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
    }

    /// Lưới 9 mẫu của một mặt, từ bảng màu + nhiễu nhỏ.
    private func samples(_ f: CubeFacelets, _ face: CubeFace, seed: UInt64) -> [CubeRGB] {
        let all = ScanFixtures.samples(for: f, palette: .manualDefault, tint: CubeRGB(r: 1, g: 1, b: 1), noise: 0.04,
                                       seed: seed)
        return Array(all[(face.rawValue * 9)..<(face.rawValue * 9 + 9)])
    }

    func testPhanLoaiMauGanNhat() {
        let f = scrambled(1)
        for face in CubeFace.allCases {
            let got = GuideCheckFlow.classify(samples(f, face, seed: UInt64(face.rawValue)), palette: .manualDefault)
            XCTAssertEqual(got, (0..<9).map { f.color(face, $0) }, "\(face)")
        }
    }

    func testKhopVaLechTheoSpec() {
        let start = scrambled(2)
        let stages = SolverBeginner.solve(start, base: start.center(.u))
        let afterMiddle = stages[2].end
        let middle = GuideCheck.spec(.middle)
        XCTAssertEqual(GuideCheckFlow.outcome(samples: samples(afterMiddle, .f, seed: 3), palette: .manualDefault,
                                              spec: middle, expected: afterMiddle), .match)
        var wrong = samples(afterMiddle, .f, seed: 3)
        wrong[3] = CubePalette.manualDefault.rgb(CubeColor(raw: (afterMiddle.color(.f, 3).raw + 1) % 6))
        XCTAssertEqual(GuideCheckFlow.outcome(samples: wrong, palette: .manualDefault, spec: middle,
                                              expected: afterMiddle), .mismatch)
        // Chữ thập: lưới D chụp nghiêng 270° vẫn khớp.
        let afterCross = stages[0].end
        var d = samples(afterCross, .d, seed: 4)
        for _ in 0..<3 { let old = d; for r in 0..<3 { for c in 0..<3 { d[r * 3 + c] = old[(2 - c) * 3 + r] } } }
        XCTAssertEqual(GuideCheckFlow.outcome(samples: d, palette: .manualDefault, spec: GuideCheck.spec(.cross),
                                              expected: afterCross), .match)
    }

    @MainActor
    func testKhopThiSangChangSau() {
        let flow = FlowModel()
        let start = scrambled(5)
        flow.choose(.cube3)
        flow.didReview(start, palette: .manualDefault)
        let base = CubePalette.manualDefault.baseColor
        flow.begin(GuideSession(mode: .teach, stages: SolverBeginner.solve(start, base: base), base: base))
        let s = flow.session!
        while s.phase == .step { s.next() }
        flow.startCheck()
        XCTAssertEqual(flow.path.last, .check)
        flow.checkMatched()
        XCTAssertEqual(flow.path.last, .guide(.teach))
        XCTAssertEqual(s.phase, .step)
        XCTAssertGreaterThan(s.stageIndex, 0)
    }

    @MainActor
    func testLechThiReplanGiuBase() {
        let flow = FlowModel()
        let start = scrambled(6)
        flow.choose(.cube3)
        flow.didReview(start, palette: .manualDefault)
        let base = CubePalette.manualDefault.baseColor
        flow.begin(GuideSession(mode: .teach, stages: SolverBeginner.solve(start, base: base), base: base))
        let s = flow.session!
        while s.phase == .step { s.next() }
        flow.startCheck()
        // Lệch ⇒ quét lại cả khối ⇒ kiểm tra ⇒ lời giải mới từ trạng thái mới.
        flow.startRescan()
        XCTAssertEqual(flow.path.last, .scan)
        let fresh = scrambled(66)
        flow.didReview(fresh, palette: .manualDefault)
        let plan = SolverBeginner.solve(fresh, base: base)
        XCTAssertEqual(flow.session?.stageIndex, plan.firstIndex { !$0.steps.isEmpty })
        XCTAssertEqual(flow.session?.stepIndex, 0)
        XCTAssertEqual(flow.session?.base, base)
        XCTAssertEqual(flow.session?.state, fresh)
        XCTAssertEqual(flow.path.last, .guide(.teach))
        XCTAssertEqual(flow.path.filter { $0 == .guide(.teach) }.count, 1)
        XCTAssertFalse(flow.isRechecking)
    }

    @MainActor
    func testQuetLaiNhanMauKhacVanGiuMauNen() {
        // Lần quét lại cầm khối khác hướng ⇒ màu trắng mang nhãn khác; màu nền vẫn là trắng.
        let flow = FlowModel()
        let start = scrambled(7)
        flow.choose(.cube3)
        flow.didReview(start, palette: .manualDefault)
        let base = CubePalette.manualDefault.baseColor
        flow.begin(GuideSession(mode: .teach, stages: SolverBeginner.solve(start, base: base), base: base))
        flow.startCheck()
        flow.startRescan()
        let swap: [UInt8: UInt8] = [0: 3, 3: 0, 1: 1, 2: 2, 4: 4, 5: 5]
        var colors: [CubeColor: CubeRGB] = [:]
        for (k, v) in CubePalette.manualDefault.colors { colors[CubeColor(raw: swap[k.raw]!)] = v }
        let fresh = CubeFacelets(n: 3, stickers: scrambled(77).stickers.map { CubeColor(raw: swap[$0.raw]!) })
        flow.didReview(fresh, palette: CubePalette(colors: colors))
        XCTAssertEqual(flow.session?.base, CubeColor(raw: 3), "trắng giờ là nhãn 3")
        XCTAssertEqual(flow.palette?.colorName(flow.session!.base), .white)
    }
}
