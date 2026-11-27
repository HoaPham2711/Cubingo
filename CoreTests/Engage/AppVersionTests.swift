import XCTest
@testable import AppHost

final class AppVersionTests: XCTestCase {
    private func v(_ s: String) -> AppVersion { AppVersion(s)! }

    func testSoTheoSoKhongTheoChuoi() {
        XCTAssertGreaterThan(v("1.10.0"), v("1.9.2"))
        XCTAssertGreaterThan(v("2.0"), v("1.99.99"))
    }

    func testThieuThanhPhanCoiLaKhong() {
        XCTAssertEqual(v("1.2"), v("1.2.0"))
        XCTAssertFalse(v("1.2") < v("1.2.0"))
        XCTAssertFalse(v("1.2.0") < v("1.2"))
        XCTAssertLessThan(v("1.2"), v("1.2.1"))
    }

    func testChuoiRacTraVeNil() {
        XCTAssertNil(AppVersion(""))
        XCTAssertNil(AppVersion("1..2"))
        XCTAssertNil(AppVersion("1.2b"))
        XCTAssertNil(AppVersion("abc"))
        XCTAssertNil(AppVersion("-1.0"))
    }

    func testBoKhoangTrangDauCuoi() {
        XCTAssertEqual(AppVersion(" 1.2.3 "), v("1.2.3"))
    }

    /// Các ca biên của so sánh theo số.
    func testCaBien() {
        XCTAssertEqual(v("1.14"), v("1.14.0"))
        XCTAssertGreaterThan(v("1.10.0"), v("1.9.9"))
        XCTAssertLessThan(v("1.9.9"), v("1.10.0"))
        XCTAssertNil(AppVersion("1.14.0 (12)"))
    }

    /// Tiêu đề nhóm danh sách What's New + param telemetry.
    func testMoTaGiuDungSoThanhPhan() {
        XCTAssertEqual(v("1.13.0").description, "1.13.0")
        XCTAssertEqual(v("1.14").description, "1.14")
    }
}
