@testable import AppHost
import XCTest

final class GuideTextTests: XCTestCase {
    private func m(_ s: String) -> CubeMove { CubeMove.parse(s)![0] }

    func testCauCuaMoiBuoc() {
        XCTAssertEqual(GuideText.sentence(m("R")), "Turn the right side up")
        XCTAssertEqual(GuideText.sentence(m("R'")), "Turn the right side down")
        XCTAssertEqual(GuideText.sentence(m("R2")), "Turn the right side twice")
        XCTAssertEqual(GuideText.sentence(m("U")), "Turn the top to the left")
        XCTAssertEqual(GuideText.sentence(m("B")), "Turn the back counterclockwise")
        XCTAssertEqual(GuideText.sentence(m("x")), "Roll the whole cube forward so the front goes up")
        XCTAssertEqual(GuideText.sentence(m("y'")), "Turn the whole cube to the right")
        XCTAssertEqual(GuideText.sentence(m("z")), "Tip the whole cube to the right")
        let all = CubeMove.faceMoves + CubeMove.rotations
        XCTAssertEqual(Set(all.map(GuideText.sentence)).count, 27, "mỗi bước một câu riêng")
        XCTAssertFalse(all.contains { GuideText.sentence($0).isEmpty })
    }

    /// Bảng màu tráo: base "blue", top "green", không có trắng/vàng.
    private var swapped: CubePalette {
        CubePalette(colors: [
            CubeColor(raw: 0): CubeColorName.blue.standardRGB, CubeColor(raw: 1): CubeColorName.red.standardRGB,
            CubeColor(raw: 2): CubeColorName.purple.standardRGB, CubeColor(raw: 3): CubeColorName.green.standardRGB,
            CubeColor(raw: 4): CubeColorName.orange.standardRGB, CubeColor(raw: 5): CubeColorName.pink.standardRGB,
        ])
    }

    func testChuoiDungBangMauDoDuoc() {
        let p = swapped
        let base = CubeColor(raw: 0), top = CubeColor(raw: 3)
        XCTAssertEqual(GuideText.stageTitle(.cross, base: p.name(base), top: p.name(top)), "blue cross")
        XCTAssertEqual(GuideText.stageTitle(.topFace, base: p.name(base), top: p.name(top)), "green face")
        XCTAssertEqual(GuideText.stageHeader(.middle, base: "blue", top: "green"), "Stage 3 · Middle layer")
        XCTAssertTrue(GuideText.hold(top: p.name(top), front: p.name(CubeColor(raw: 2))).contains("green on top"))
        let c = CubeColor.all
        let reasons: [SolverReason] = [
            .hold(top: top, front: c[2]), .makeDaisy(edge: c[1]), .dropToCross(edge: c[2]), .liftCorner,
            .placeCorner(c[1], c[2]), .insertEdge(c[1], c[2], toRight: true), .insertEdge(c[4], c[5], toRight: false),
            .popEdge, .makeTopCross, .orientTopCorners, .placeTopCorners, .placeTopEdges, .alignTop,
        ]
        var all: [String] = reasons.map { GuideText.reason($0, palette: p, base: base, top: top) }
        all += SolverStageKind.allCases.map { GuideText.stageGoal($0, base: p.name(base), top: p.name(top)) }
        all += SolverStageKind.allCases.map { GuideText.stageTitle($0, base: p.name(base), top: p.name(top)) }
        for s in all {
            XCTAssertFalse(s.isEmpty)
            XCTAssertFalse(s.localizedCaseInsensitiveContains("white"), s)
            XCTAssertFalse(s.localizedCaseInsensitiveContains("yellow"), s)
            XCTAssertLessThanOrEqual(s.count, 90, s)
        }
        XCTAssertEqual(GuideText.reason(.dropToCross(edge: c[1]), palette: p, base: base, top: top),
                       "Line up the blue-red edge over its center, then turn that side twice")
        XCTAssertTrue(GuideText.reason(.makeDaisy(edge: c[1]), palette: p, base: base, top: top).contains("green center"))
        for k in SolverStageKind.allCases {
            XCTAssertLessThanOrEqual(GuideText.stageGoal(k, base: "blue", top: "green").count, 70)
        }
    }

    func testTenThuatToanVaTienDo() {
        XCTAssertEqual(GuideText.algorithmName(.sune), "Sune")
        XCTAssertEqual(GuideText.algorithmName(.rightTrigger), "Right trigger")
        XCTAssertEqual(Set(SolverAlgorithm.allCases.map(GuideText.algorithmName)).count, 7)
        XCTAssertEqual(GuideText.progress(step: 3, of: 8), "3 / 8")
        XCTAssertEqual(GuideText.quickProgress(step: 7, of: 21), "Move 7 / 21")
    }
}
