import XCTest
@testable import AppHost

/// Dấu "đang làm việc dài" để lần mở sau biết lần chạy trước chết giữa chừng. `kind` là chuỗi
/// tuỳ app (ở đây `"import"`/`"export"`); store duyệt FILE dấu trên đĩa, không dựa danh sách kind.
final class ActiveWorkMarkerTests: XCTestCase {
    private var root: URL!
    /// Thư mục dấu nằm TRONG `root` để test thoát-thư-mục thấy được file lọt ra ngoài.
    private var dir: URL { root.appendingPathComponent("markers", isDirectory: true) }

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory
            .appendingPathComponent("ActiveWorkMarkerTests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: root)
    }

    private func store() -> ActiveWorkMarkerStore { ActiveWorkMarkerStore(directory: dir) }

    func test_khongCoDau_takeIncidentNil() {
        XCTAssertNil(store().takeIncident())
    }

    func test_begin_khongClear_laSuCo() {
        store().begin(kind: "import", workID: "A")
        let m = store().takeIncident()
        XCTAssertEqual(m?.workID, "A")
        XCTAssertEqual(m?.kind, "import")
    }

    func test_begin_clear_khongSuCo() {
        let s = store()
        s.begin(kind: "export", workID: "A")
        s.clear(kind: "export", workID: "A")
        XCTAssertNil(store().takeIncident())
    }

    func test_clearKhacWorkID_khongXoa() {
        let s = store()
        s.begin(kind: "import", workID: "A")
        s.clear(kind: "import", workID: "B")
        XCTAssertEqual(store().takeIncident()?.workID, "A")
    }

    func test_takeIncident_chiTraMotLan() {
        store().begin(kind: "import", workID: "A")
        let s = store()
        XCTAssertNotNil(s.takeIncident())
        XCTAssertNil(s.takeIncident())
        XCTAssertNil(store().takeIncident())
    }

    func test_daXuongNen_khongSuCo() {
        let s = store()
        s.begin(kind: "import", workID: "A")
        s.setBackgrounded(true)
        XCTAssertNil(store().takeIncident())
        // Dấu đã bị xoá, không treo lại cho lần sau.
        XCTAssertNil(store().takeIncident())
    }

    func test_trenNenRoiQuayLai_laSuCo() {
        let s = store()
        s.begin(kind: "import", workID: "A")
        s.setBackgrounded(true)
        s.setBackgrounded(false)
        XCTAssertEqual(store().takeIncident()?.workID, "A")
    }

    func test_beginKhiDangONen_khongSuCo() {
        let s = store()
        s.setBackgrounded(true)
        s.begin(kind: "import", workID: "A")
        XCTAssertNil(store().takeIncident())
    }

    /// Ghi thẳng file dấu với `startedAt` tường minh (không phụ thuộc đồng hồ/ngủ).
    private func writeMarker(_ kind: String, _ id: String, at t: TimeInterval, backgrounded: Bool) throws {
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let enc = JSONEncoder()
        enc.dateEncodingStrategy = .iso8601
        let m = ActiveWorkMarker(workID: id, kind: kind, startedAt: Date(timeIntervalSince1970: t),
                                 backgrounded: backgrounded)
        try enc.encode(m).write(to: dir.appendingPathComponent(ActiveWorkMarkerStore.fileName(forKind: kind)))
    }

    func test_haiLoaiCungLuc_traBanMoiNhat_vaXoaCaHai() throws {
        // "import" đứng trước theo thứ tự chữ cái nhưng CŨ hơn ⇒ lấy phần tử đầu danh sách sẽ sai.
        try writeMarker("import", "S", at: 1_000, backgrounded: false)
        try writeMarker("export", "P", at: 2_000, backgrounded: false)
        XCTAssertEqual(store().takeIncident()?.workID, "P")
        XCTAssertNil(store().takeIncident())
    }

    func test_banMoiONen_banCuTrenNen_traBanCu() throws {
        try writeMarker("import", "S", at: 1_000, backgrounded: false)
        try writeMarker("export", "P", at: 2_000, backgrounded: true)
        XCTAssertEqual(store().takeIncident()?.workID, "S")
        XCTAssertNil(store().takeIncident())
    }

    func test_fileHong_nil_vaXoa() throws {
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let f = dir.appendingPathComponent(ActiveWorkMarkerStore.fileName(forKind: "import"))
        try Data("rác".utf8).write(to: f)
        XCTAssertNil(store().takeIncident())
        XCTAssertFalse(FileManager.default.fileExists(atPath: f.path))
    }

    /// Kind tuỳ ý (không có danh sách cố định): `setBackgrounded(true)` phải đánh dấu CẢ HAI dấu
    /// trên đĩa — một store mới đọc lại không thấy sự cố nào.
    func testXoaMoiDauBatKeLoai() {
        let s = store()
        s.begin(kind: "alpha", workID: "1")
        s.begin(kind: "beta gamma", workID: "2")
        s.setBackgrounded(true)
        XCTAssertNil(store().takeIncident(), "một dấu còn lại chưa được đánh dấu nền")
    }

    /// Kind trở thành tên file ⇒ phải được làm sạch: `/` hay `..` không được dẫn ra ngoài thư mục dấu.
    func testKindCoGachCheoHoacChamChamKhongThoatThuMuc() throws {
        let s = store()
        s.begin(kind: "../escaped", workID: "A")
        s.begin(kind: "a/b", workID: "B")
        s.begin(kind: "..", workID: "C")
        // Không có file nào lọt ra ngoài thư mục dấu (cạnh `markers/` chỉ có chính `markers/`).
        let ngoai = try FileManager.default.contentsOfDirectory(atPath: root.path)
        XCTAssertEqual(ngoai, ["markers"])
        // Cả ba dấu nằm trong thư mục dấu và vẫn đọc lại được nguyên vẹn (kind gốc không bị đổi).
        let files = try FileManager.default.contentsOfDirectory(atPath: dir.path)
        XCTAssertEqual(files.count, 3)
        let m = s.takeIncident()
        XCTAssertNotNil(m)
        XCTAssertTrue(["../escaped", "a/b", ".."].contains(m?.kind ?? ""))
    }

    /// Làm sạch không được gộp hai kind khác nhau vào một file (ghi đè dấu của nhau).
    func testHaiKindKhacNhauKhongVaChamTenFile() {
        XCTAssertNotEqual(ActiveWorkMarkerStore.fileName(forKind: "a/b"), ActiveWorkMarkerStore.fileName(forKind: "a_b"))
        XCTAssertNotEqual(ActiveWorkMarkerStore.fileName(forKind: "a.b"), ActiveWorkMarkerStore.fileName(forKind: "a_b"))
        XCTAssertFalse(ActiveWorkMarkerStore.fileName(forKind: "").hasPrefix("."))
        let s = store()
        s.begin(kind: "a/b", workID: "1")
        s.begin(kind: "a_b", workID: "2")
        s.clear(kind: "a/b", workID: "1")
        XCTAssertEqual(store().takeIncident()?.workID, "2")
    }

    /// File lạ trong thư mục (không phải `.json`) không bị đụng tới.
    func test_fileKhongPhaiJSON_khongBiXoa() throws {
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let f = dir.appendingPathComponent("note.txt")
        try Data("x".utf8).write(to: f)
        XCTAssertNil(store().takeIncident())
        XCTAssertTrue(FileManager.default.fileExists(atPath: f.path))
    }

    /// APFS mặc định không phân biệt hoa/thường: hai kind chỉ khác hoa/thường phải ra hai tên file
    /// khác nhau kể cả khi so `lowercased()`, và không được đè/xoá dấu của nhau.
    func testHaiKindChiKhacHoaThuongKhongVaChamTenFile() {
        let a = ActiveWorkMarkerStore.fileName(forKind: "Import")
        let b = ActiveWorkMarkerStore.fileName(forKind: "import")
        XCTAssertNotEqual(a.lowercased(), b.lowercased())
        let s = store()
        s.begin(kind: "Import", workID: "1")
        s.begin(kind: "import", workID: "2")
        s.clear(kind: "Import", workID: "1")
        XCTAssertEqual(store().takeIncident()?.workID, "2")
    }
}
