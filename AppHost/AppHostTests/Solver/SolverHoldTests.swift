@testable import AppHost
import XCTest

final class SolverHoldTests: XCTestCase {
    private func c(_ r: UInt8) -> CubeColor { CubeColor(raw: r) }

    func testHoldVaXoay() {
        let s = CubeFacelets.solved(n: 3)
        XCTAssertTrue(SolverHold.hold(of: s) == (c(0), c(2)))
        let rot = SolverHold.rotations(from: s, top: c(3), preferFront: c(2))
        XCTAssertEqual(rot.map(\.notation), ["z2"])
        XCTAssertTrue(SolverHold.hold(of: s.applying(rot)) == (c(3), c(2)))
        XCTAssertEqual(SolverHold.rotations(from: s, top: c(0), preferFront: c(2)), [])
    }

    func testMoiHuongDeuDatDuoc() {
        let s = CubeFacelets.solved(n: 3)
        for top in CubeColor.all {
            for front in CubeColor.all where front != top && front.raw != (top.raw + 3) % 6 {
                let rot = SolverHold.rotations(from: s, top: top, preferFront: front)
                XCTAssertLessThanOrEqual(rot.count, 2)
                XCTAssertTrue(SolverHold.hold(of: s.applying(rot)) == (top, front), "top \(top.raw) front \(front.raw)")
            }
            // preferFront không đặt được (trùng top) ⇒ vẫn đưa đúng top, ít bước nhất.
            let rot = SolverHold.rotations(from: s, top: top, preferFront: top)
            XCTAssertEqual(s.applying(rot).center(.u), top)
            XCTAssertLessThanOrEqual(rot.count, 1)
        }
    }
}
