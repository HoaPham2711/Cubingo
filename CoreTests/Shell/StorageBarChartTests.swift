import XCTest
import SwiftUI
@testable import AppHost

/// Phần tính thuần của `StorageBarChart` (`StorageBarMath`) — ba lỗi biên đã biết: nhãn "Zero KB", segment tràn
/// thanh khi nhiều lát nằm ở sàn, "100%" đứng cạnh "<1%".
final class StorageBarChartTests: XCTestCase {

    func testTongBeRongKhongVuot() {
        let bytes: [Int64] = [1_000_000_000] + Array(repeating: 10, count: 19)   // 19 lát bé + 1 lát lớn
        let w = StorageBarMath.widths(bytes: bytes, total: 200)
        XCTAssertEqual(w.count, 20)
        XCTAssertLessThanOrEqual(w.reduce(0, +), 200 + 1e-9)
        // Cả khi có khe hở giữa các segment, như view thật.
        let g = StorageBarMath.widths(bytes: bytes, total: 200, gap: 2)
        XCTAssertLessThanOrEqual(g.reduce(0, +) + 2 * 19, 200 + 1e-9)
        // Quá nhiều lát tại sàn (20 × 3 > 50) vẫn không tràn.
        let hep = StorageBarMath.widths(bytes: Array(repeating: 1, count: 20), total: 50)
        XCTAssertLessThanOrEqual(hep.reduce(0, +), 50 + 1e-9)
    }

    func testLatKhongByteKhongChiemCho() {
        let w = StorageBarMath.widths(bytes: [500, 0, 500], total: 100)
        XCTAssertEqual(w[1], 0)
        XCTAssertGreaterThan(w[0], 0)
        // Lát > 0 bé vẫn có ít nhất sàn khi còn chỗ.
        let sau = StorageBarMath.widths(bytes: [1_000_000, 1], total: 100)
        XCTAssertGreaterThanOrEqual(sau[1], 3 - 1e-9)
    }

    func testPhanTramCongDu100() {
        let l = StorageBarMath.percentLabels(bytes: [1, 1, 1])   // 33,33…% mỗi lát
        let so = l.compactMap { Int($0.dropLast()) }
        XCTAssertEqual(so.reduce(0, +), 100)
        // Bẫy cũ: 99,9 % + 0,1 % ⇒ không "100%" cạnh "<1%".
        let b = StorageBarMath.percentLabels(bytes: [999, 1])
        XCTAssertEqual(b[1], "<1%")
        XCTAssertNotEqual(b[0], "100%")
        XCTAssertEqual(b[0], "99%")
        XCTAssertEqual(StorageBarMath.percentLabels(bytes: [3, 0]), ["100%", "0%"])
    }

    func testNhanKichThuocKhongBaoGioLaZeroKB() {
        let s = StorageBarMath.sizeLabel(0)
        XCTAssertFalse(s.contains("Zero"), s)
        // Không giả định locale (chữ số/khoảng trắng/đơn vị đổi theo máy): chỉ cần có số 0 đã định dạng.
        XCTAssertTrue(s.contains(0.formatted()), s)
        XCTAssertFalse(StorageBarMath.sizeLabel(-5).contains("Zero"))
    }

    /// Formatter là hệ thập phân (`.file`) ⇒ "<1 KB" đúng cho < 1000 B; từ 1000 B đã là "1 KB".
    func testNhoHon1KBTheoHeThapPhan() {
        XCTAssertEqual(StorageBarMath.sizeLabel(900), String(localized: "<1 KB"))
        XCTAssertEqual(StorageBarMath.sizeLabel(999), String(localized: "<1 KB"))
        XCTAssertNotEqual(StorageBarMath.sizeLabel(1000), String(localized: "<1 KB"))
        XCTAssertNotEqual(StorageBarMath.sizeLabel(1023), String(localized: "<1 KB"))
    }

    func testKhongChiaChoKhongKhiTongBangKhong() {
        XCTAssertEqual(StorageBarMath.widths(bytes: [0, 0], total: 100), [0, 0])
        XCTAssertEqual(StorageBarMath.widths(bytes: [], total: 100), [])
        XCTAssertEqual(StorageBarMath.percentLabels(bytes: [0, 0]), ["0%", "0%"])
        // Byte âm coi như 0, không crash.
        XCTAssertEqual(StorageBarMath.widths(bytes: [-5, -1], total: 100), [0, 0])
        XCTAssertEqual(StorageBarMath.percentLabels(bytes: [-5, 10]), ["0%", "100%"])
        XCTAssertEqual(StorageBarMath.widths(bytes: [10], total: 0), [0])
    }
}
