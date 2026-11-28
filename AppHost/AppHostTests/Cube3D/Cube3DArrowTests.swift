@testable import AppHost
import simd
import XCTest

/// Mũi tên thẳng ngang / dọc trên mặt thấy được, chỉ chiều các ô của lớp chạy (khớp câu chữ của `GuideText`).
final class Cube3DArrowTests: XCTestCase {
    private func seg(_ s: String) -> Cube3DArrow.Segment { Cube3DArrow.segment(CubeMove.parse(s)![0], half: 1.5) }

    func testMatPhaiDiLenXuong() {
        let r = seg("R")
        XCTAssertGreaterThan(r.end.y, r.start.y, "R: mặt phải lên")
        XCTAssertEqual(r.start.x, 1, accuracy: 1e-4)
        XCTAssertGreaterThan(r.start.z, 1.5, "nằm trên mặt trước")
        XCTAssertLessThan(seg("R'").end.y, seg("R'").start.y)
        XCTAssertLessThan(seg("L").end.y, seg("L").start.y, "L: mặt trái xuống")
    }

    func testTangTrenDuoiNgang() {
        let u = seg("U")
        XCTAssertLessThan(u.end.x, u.start.x, "U: tầng trên sang trái")
        XCTAssertEqual(u.start.y, 1, accuracy: 1e-4)
        XCTAssertGreaterThan(seg("D").end.x, seg("D").start.x, "D: tầng dưới sang phải")
        XCTAssertLessThan(seg("y").end.x, seg("y").start.x, "y: cả khối sang trái")
        XCTAssertEqual(seg("y").start.y, 0, accuracy: 1e-4)
    }

    func testMatTruocSauTrenMatTren() {
        let f = seg("F")
        XCTAssertGreaterThan(f.start.y, 1.5, "nằm trên mặt trên")
        XCTAssertGreaterThan(f.end.x, f.start.x, "F (thuận chiều): hàng sát mặt trước chạy sang phải")
        XCTAssertEqual(f.start.z, 1, accuracy: 1e-4)
        XCTAssertLessThan(seg("B").end.x, seg("B").start.x)
    }

    func testBuocKep() {
        XCTAssertTrue(seg("U2").double)
        XCTAssertFalse(seg("U").double)
    }
}
