@testable import AppHost
import XCTest

final class CubeGeometryTests: XCTestCase {
    private func moves(_ s: String) -> [CubeMove] { CubeMove.parse(s)! }

    func testChuKy() {
        for n in [2, 3] {
            let solved = CubeFacelets.solved(n: n)
            for m in CubeMove.faceMoves + CubeMove.rotations {
                XCTAssertEqual(solved.applying(Array(repeating: m, count: 4)), solved, "n=\(n) \(m.notation)^4")
            }
            let sexy = moves("R U R' U'")
            XCTAssertEqual(solved.applying(Array(repeating: sexy, count: 6).flatMap { $0 }), solved, "n=\(n) sexy^6")
        }
        let s3 = CubeFacelets.solved(n: 3)
        let ru = moves("R U")
        XCTAssertEqual(s3.applying(Array(repeating: ru, count: 105).flatMap { $0 }), s3)
        XCTAssertNotEqual(s3.applying(Array(repeating: ru, count: 35).flatMap { $0 }), s3)
    }

    func testBuocVaNghichDaoTrieuTieu() {
        var rng = CubeTestLCG(seed: 1)
        let all = CubeMove.faceMoves + CubeMove.rotations
        let seq = (0..<200).map { _ in all[rng.next(all.count)] }
        let solved = CubeFacelets.solved(n: 3)
        let scrambled = solved.applying(seq)
        XCTAssertNotEqual(scrambled, solved)
        XCTAssertEqual(scrambled.applying(seq.reversed().map(\.inverse)), solved)
    }

    func testXoayCaKhoiBangTichCacLop() {
        let solved = CubeFacelets.solved(n: 3)
        // x lăn như R: tâm F lên U.
        XCTAssertEqual(solved.applying(moves("x")).center(.u), solved.center(.f))
        XCTAssertEqual(solved.applying(moves("y")).center(.l), solved.center(.f))
        XCTAssertEqual(solved.applying(moves("z")).center(.r), solved.center(.u))
        // Hai lớp ngoài của x trùng với R L'.
        var rng = CubeTestLCG(seed: 9)
        let s = solved.applying((0..<30).map { _ in CubeMove.faceMoves[rng.next(18)] })
        let a = s.applying(moves("x")), b = s.applying(moves("R L'"))
        for face in [CubeFace.r, .l] {
            for i in 0..<9 { XCTAssertEqual(a.color(face, i), b.color(face, i)) }
        }
        XCTAssertTrue(solved.applying(moves("x y z2")).isSolved)
    }

    func testKhoiHaiHai() {
        let s2 = CubeFacelets.solved(n: 2)
        XCTAssertEqual(s2.stickers.count, 24)
        XCTAssertFalse(s2.applying(moves("R")).isSolved)
        XCTAssertEqual(s2.applying(moves("R R R R")), s2)
        XCTAssertTrue(s2.applying(moves("y")).isSolved)
    }
}
