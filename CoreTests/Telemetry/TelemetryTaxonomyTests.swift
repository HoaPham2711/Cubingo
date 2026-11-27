@testable import AppHost
import XCTest

/// Kiểm chéo giữa các catalog event: `violations` chỉ nhìn một catalog, hàm ở đây nhìn cả bộ (lõi + app).
/// Fixture là mảng chuỗi thuần/enum riêng của file này — không đụng tên của test khác.
final class TelemetryTaxonomyTests: XCTestCase {

    private enum CatalogGia: String, EventNameCatalog {
        case mot = "gia_mot"
        case hai = "gia_hai"
    }

    /// Tên tự do cho mẫu: `AppEvent` chỉ dựng từ `RawRepresentable`, còn test cần tên không thuộc catalog nào.
    private struct TenTuDo: RawRepresentable {
        let rawValue: String
    }

    private func mau(_ ten: String, _ p: [String: ParamValue] = [:]) -> AppEvent {
        AppEvent(TenTuDo(rawValue: ten), p)
    }

    func testTenTrungGiuaHaiCatalogBiBat() {
        let v = TelemetryTaxonomy.crossCatalogViolations(catalogs: [["a_b"], ["a_b"]], samples: [mau("a_b")])
        XCTAssertEqual(v.count, 1, "\(v)")
        XCTAssertTrue(v.first?.contains("a_b") == true, "\(v)")
    }

    /// Trùng ngay trong MỘT catalog cũng bị báo (không phải chỉ giữa hai catalog).
    func testTenTrungTrongMotCatalogBiBat() {
        let v = TelemetryTaxonomy.crossCatalogViolations(catalogs: [["a_b", "a_b"]], samples: [mau("a_b")])
        XCTAssertEqual(v.count, 1, "\(v)")
        XCTAssertTrue(v.first?.contains("a_b") == true, "\(v)")
    }

    func testMauMoCoiBiBat() {
        let v = TelemetryTaxonomy.crossCatalogViolations(
            catalogs: [["a_b"]], samples: [mau("a_b"), mau("x_y")])
        XCTAssertEqual(v.count, 1, "\(v)")
        XCTAssertTrue(v.first?.contains("x_y") == true, "\(v)")
    }

    func testKhoaViTriBiBat() {
        for manh in TelemetryTaxonomy.locationKeyFragments {
            let e = mau("a_b", ["User_\(manh.uppercased())_x": .int(1)])
            let v = TelemetryTaxonomy.crossCatalogViolations(catalogs: [["a_b"]], samples: [e])
            XCTAssertFalse(v.isEmpty, "mảnh '\(manh)' phải bị bắt")
            XCTAssertTrue(v.contains { $0.contains("a_b") && $0.contains("User_\(manh.uppercased())_x") }, "\(v)")
        }
        // Danh sách mảnh giữ đúng như luật cũ trong ShellEventTaxonomyTests.
        XCTAssertEqual(TelemetryTaxonomy.locationKeyFragments, ["lat", "lon", "coord", "gps", "location"])
    }

    func testKhoaSachKhongBiBat() {
        let e = mau("a_b", ["count": .int(1), "source": .string("home")])
        XCTAssertEqual(TelemetryTaxonomy.crossCatalogViolations(catalogs: [["a_b"]], samples: [e]), [])
    }

    func testCatalogGiaHopLeVaTachBiet() {
        let v = TelemetryTaxonomy.crossCatalogViolations(
            catalogs: [CatalogGia.allCases.map(\.rawValue), ["khac_mot"]],
            samples: [AppEvent(CatalogGia.mot), AppEvent(CatalogGia.hai), mau("khac_mot")])
        XCTAssertEqual(v, [])
    }

    func testCatalogLoiTuNoSach() {
        let v = TelemetryTaxonomy.crossCatalogViolations(
            catalogs: [ShellEventName.allCases.map(\.rawValue)], samples: AppEvent.shellSamples)
        XCTAssertEqual(v, [])
    }
}
