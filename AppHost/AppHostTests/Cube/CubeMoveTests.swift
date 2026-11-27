@testable import AppHost
import XCTest

/// LCG cục bộ (Task 2 chưa có `CubeRandom`) — tất định theo seed.
struct CubeTestLCG {
    private var state: UInt64
    init(seed: UInt64) { state = seed }
    mutating func next(_ bound: Int) -> Int {
        state = state &* 6364136223846793005 &+ 1442695040888963407
        return Int((state >> 33) % UInt64(bound))
    }
}

final class CubeMoveTests: XCTestCase {
    private func moves(_ s: String) -> [CubeMove] { CubeMove.parse(s)! }

    func testParseVaNotation() {
        XCTAssertEqual(CubeMove.parse("R U' F2 x y' z2")?.map(\.notation), ["R", "U'", "F2", "x", "y'", "z2"])
        XCTAssertNil(CubeMove.parse("Q"))
        XCTAssertNil(CubeMove.parse("R3"))
        XCTAssertEqual(CubeMove.parse("")?.count, 0)
        XCTAssertEqual(CubeMove.parse("  R   U  ")?.map(\.notation), ["R", "U"])
    }

    func testNghichDaoVaXoayCaKhoi() {
        XCTAssertEqual(moves("R").first?.inverse.notation, "R'")
        XCTAssertEqual(moves("F2").first?.inverse.notation, "F2")
        XCTAssertEqual(moves("y'").first?.inverse.notation, "y")
        XCTAssertTrue(moves("x").first!.isRotation)
        XCTAssertFalse(moves("L").first!.isRotation)
        XCTAssertEqual(CubeMove.faceMoves.count, 18)
        XCTAssertEqual(CubeMove.rotations.count, 9)
    }

    func testRTrenKhoiDaGiaiKhopChuoiKociemba() {
        let s = CubeFacelets.solved(n: 3).applying(moves("R"))
        XCTAssertEqual(s.kociemba, "UUFUUFUUFRRRRRRRRRFFDFFDFFDDDBDDBDDBLLLLLLLLLUBBUBBUBB")
    }

    func testUTrenKhoiDaGiaiKhopChuoiKociemba() {
        let s = CubeFacelets.solved(n: 3).applying(moves("U"))
        XCTAssertEqual(s.kociemba, "UUUUUUUUUBBBRRRRRRRRRFFFFFFDDDDDDDDDFFFLLLLLLLLLBBBBBB")
    }

    func testChuoiKociembaHaiChieu() {
        let s = CubeFacelets.solved(n: 3).applying(moves("R U F' D2 L B'"))
        XCTAssertEqual(CubeFacelets(kociemba: s.kociemba), s)
        XCTAssertNil(CubeFacelets(kociemba: "UUU"))
        XCTAssertNil(CubeFacelets(kociemba: String(repeating: "Q", count: 54)))
    }
}
