import XCTest
@testable import AppHost

/// Dọn thư mục tạm lúc mở app + đo dung lượng (`StorageOtherData`). Mọi test chạy trong một thư mục tạm
/// riêng do chính test tạo và xoá — không đụng `tmp/` thật của app host.
final class StorageOtherDataTests: XCTestCase {

    private var root: URL!

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory
            .appendingPathComponent("StorageOtherDataTests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: root)
    }

    private func write(_ bytes: Int, _ rel: String, in dir: URL) throws -> URL {
        let url = dir.appendingPathComponent(rel)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data(repeating: 0x41, count: bytes).write(to: url)
        return url
    }

    private func exists(_ url: URL) -> Bool { FileManager.default.fileExists(atPath: url.path) }

    // MARK: - purge

    func testPurgeXoaMucCuGiuMucMoi() throws {
        let tmp = root.appendingPathComponent("tmp", isDirectory: true)
        let old = try write(1000, "export_old/file.zip", in: tmp)
        let oldFile = try write(500, "atlas_old.jpg", in: tmp)
        Thread.sleep(forTimeInterval: 0.05)
        let cutoff = Date()
        Thread.sleep(forTimeInterval: 0.05)
        let fresh = try write(200, "export_new/file.zip", in: tmp)

        let freed = StorageOtherData.purge(dirs: [tmp], olderThan: 0, now: cutoff)

        XCTAssertFalse(exists(old.deletingLastPathComponent()))
        XCTAssertFalse(exists(oldFile))
        XCTAssertTrue(exists(fresh))
        XCTAssertEqual(freed, 1500)
        XCTAssertTrue(exists(tmp), "chỉ xoá mục BÊN TRONG, không xoá chính thư mục được giao")
    }

    /// `olderThan` tính lùi từ `now`: mục vừa tạo chưa đủ tuổi thì giữ; cùng mục đó nhìn từ một `now` đủ xa
    /// về sau thì bị xoá.
    func testNguongTuoiTinhLuiTuNow() throws {
        let tmp = root.appendingPathComponent("tmp", isDirectory: true)
        let f = try write(64, "recent.bin", in: tmp)

        XCTAssertEqual(StorageOtherData.purge(dirs: [tmp], olderThan: 60, now: Date()), 0)
        XCTAssertTrue(exists(f), "mới vài ms tuổi, ngưỡng 60 s ⇒ giữ")

        XCTAssertEqual(StorageOtherData.purge(dirs: [tmp], olderThan: 60, now: Date(timeIntervalSinceNow: 120)), 64)
        XCTAssertFalse(exists(f), "nhìn từ 2 phút sau thì đã quá ngưỡng 60 s ⇒ xoá")
    }

    /// `copyItem` giữ ngày tạo/sửa của NGUỒN — file vừa chép vào tmp để nhập trông "10 ngày tuổi". Luật dọn
    /// phải theo ctime, nếu không sẽ xoá file đang nhập.
    func testFileVuaChepTuNguonCuVanDuocGiu() throws {
        let src = try write(300, "src/package.bin", in: root)
        let past = Date(timeIntervalSinceNow: -10 * 86_400)
        try FileManager.default.setAttributes([.creationDate: past, .modificationDate: past], ofItemAtPath: src.path)
        let tmp = root.appendingPathComponent("tmp", isDirectory: true)
        try FileManager.default.createDirectory(at: tmp, withIntermediateDirectories: true)
        let cutoff = Date()
        Thread.sleep(forTimeInterval: 0.05)
        let staged = tmp.appendingPathComponent("import-x.bin")
        try FileManager.default.copyItem(at: src, to: staged)

        _ = StorageOtherData.purge(dirs: [tmp], olderThan: 0, now: cutoff)
        XCTAssertTrue(exists(staged), "file nhập vừa chép phải còn")
    }

    /// Chỉ xét mục CẤP 1: thư mục mới tạo (đang dùng) chứa file chép từ nguồn cũ vẫn giữ cả cụm.
    func testChiXetCap1() throws {
        let tmp = root.appendingPathComponent("tmp", isDirectory: true)
        try FileManager.default.createDirectory(at: tmp, withIntermediateDirectories: true)
        let cutoff = Date()
        Thread.sleep(forTimeInterval: 0.05)
        let inner = try write(100, "export_new/old-looking.jpg", in: tmp)
        let past = Date(timeIntervalSinceNow: -86_400)
        try FileManager.default.setAttributes([.modificationDate: past], ofItemAtPath: inner.path)
        _ = StorageOtherData.purge(dirs: [tmp], olderThan: 0, now: cutoff)
        XCTAssertTrue(exists(inner))
    }

    func testPurgeThuMucKhongTonTaiKhongCrash() {
        XCTAssertEqual(StorageOtherData.purge(dirs: [root.appendingPathComponent("khong-co")],
                                              olderThan: 0, now: Date()), 0)
    }

    /// Symlink cấp 1 trỏ RA NGOÀI thư mục được giao: chỉ gỡ chính cái link, đích bên ngoài phải còn nguyên.
    func testSymlinkKhongDuaRaNgoai() throws {
        let outside = try write(80, "outside/keep.bin", in: root)
        let tmp = root.appendingPathComponent("tmp", isDirectory: true)
        try FileManager.default.createDirectory(at: tmp, withIntermediateDirectories: true)
        let link = tmp.appendingPathComponent("link")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: outside.deletingLastPathComponent())
        Thread.sleep(forTimeInterval: 0.05)

        _ = StorageOtherData.purge(dirs: [tmp], olderThan: 0, now: Date())

        XCTAssertTrue(exists(outside), "không được xoá xuyên qua symlink")
        XCTAssertNil(try? FileManager.default.destinationOfSymbolicLink(atPath: link.path), "link cũ bị gỡ")
    }

    /// Host unit test: `runAtLaunch` không được khởi động việc dọn (nếu không, nó dọn luôn `tmp/` của chính test).
    /// Kiểm đồng bộ qua giá trị trả về — không chờ task nền.
    /// CẢNH BÁO: phá cổng `shouldRun`/`isUnitTestHost` (kể cả bằng mutate.py) thì CHÍNH test này chạy purge thật trên
    /// `tmp/` của app host test.
    func testRunAtLaunchKhongChayTrongHostTest() {
        XCTAssertFalse(StorageOtherData.shouldRun(isUnitTestHost: true))
        XCTAssertTrue(StorageOtherData.shouldRun(isUnitTestHost: false))
        XCTAssertNil(StorageOtherData.runAtLaunch(), "mặc định đọc AppEnvironment.isUnitTestHost ⇒ không tạo task")
    }

    /// `olderThan` âm bị kẹp về 0 — nếu không, mốc cắt nằm ở tương lai và file vừa ghi sau `now` cũng bị xoá.
    func testOlderThanAmBiKepVe0() throws {
        let tmp = root.appendingPathComponent("tmp", isDirectory: true)
        try FileManager.default.createDirectory(at: tmp, withIntermediateDirectories: true)
        let now = Date()
        Thread.sleep(forTimeInterval: 0.05)
        let f = try write(10, "writing.bin", in: tmp)
        XCTAssertEqual(StorageOtherData.purge(dirs: [tmp], olderThan: -3600, now: now), 0)
        XCTAssertTrue(exists(f))
    }

    // MARK: - Inbox của hệ thống

    /// Dọn lúc mở app chừa `<bundle-id>-Inbox` (file "Open in" tới trước khi tiến trình chạy); mục cũ khác vẫn xoá.
    func testDonLucMoAppChuaInbox() throws {
        let tmp = root.appendingPathComponent("tmp", isDirectory: true)
        let inbox = try write(20, "com.example.app-Inbox/doc.pdf", in: tmp)
        let other = try write(30, "old-export.zip", in: tmp)
        Thread.sleep(forTimeInterval: 0.05)

        XCTAssertEqual(StorageOtherData.launchPurge(dirs: [tmp], now: Date()), 30)
        XCTAssertTrue(exists(inbox))
        XCTAssertFalse(exists(other))
    }

    /// `purge` thuần (không bộ loại trừ) vẫn xoá Inbox cũ — hành vi mặc định không đổi.
    func testPurgeMacDinhKhongLoaiTruGi() throws {
        let tmp = root.appendingPathComponent("tmp", isDirectory: true)
        let inbox = try write(20, "x-Inbox/doc.pdf", in: tmp)
        Thread.sleep(forTimeInterval: 0.05)
        XCTAssertEqual(StorageOtherData.purge(dirs: [tmp], olderThan: 0, now: Date()), 20)
        XCTAssertFalse(exists(inbox))
    }

    // MARK: - Chốt chặn gốc dữ liệu được bảo vệ

    /// Dựng một "gốc bảo vệ" giả trong thư mục tạm, có một file cũ bên trong.
    private func makeProtected() throws -> (protectedRoot: URL, oldFile: URL) {
        let p = root.appendingPathComponent("home/Documents", isDirectory: true)
        let f = try write(40, "user.data", in: p)
        Thread.sleep(forTimeInterval: 0.05)
        return (p, f)
    }

    func testDirBangGocBaoVeKhongXoaGi() throws {
        let (p, f) = try makeProtected()
        XCTAssertEqual(StorageOtherData.purge(dirs: [p], olderThan: 0, now: Date(), protectedRoots: [p]), 0)
        XCTAssertTrue(exists(f))
    }

    func testDirLaToTienCuaGocBaoVeKhongXoaGi() throws {
        let (p, f) = try makeProtected()
        let home = p.deletingLastPathComponent()
        let sibling = try write(5, "sibling.bin", in: home)
        Thread.sleep(forTimeInterval: 0.05)
        XCTAssertEqual(StorageOtherData.purge(dirs: [home], olderThan: 0, now: Date(), protectedRoots: [p]), 0)
        XCTAssertTrue(exists(f))
        XCTAssertTrue(exists(sibling), "từ chối cả thư mục, không chỉ chừa nhánh được bảo vệ")
    }

    func testDirLaConCuaGocBaoVeVanDuocDon() throws {
        let (p, _) = try makeProtected()
        let staging = p.appendingPathComponent("staging", isDirectory: true)
        let old = try write(25, "old.bin", in: staging)
        Thread.sleep(forTimeInterval: 0.05)
        XCTAssertEqual(StorageOtherData.purge(dirs: [staging], olderThan: 0, now: Date(), protectedRoots: [p]), 25)
        XCTAssertFalse(exists(old))
        XCTAssertTrue(exists(staging))
    }

    /// Đường dẫn đi qua symlink nhưng thực chất là gốc bảo vệ: `link-to-home/Documents` ≡ `home/Documents`. (Symlink
    /// ở thành phần CUỐI thì `contentsOfDirectory` vốn không đi theo; symlink ở thành phần giữa thì có — nên phải giải
    /// symlink trước khi so.)
    func testDirLaSymlinkToiGocBaoVeKhongXoaGi() throws {
        let (p, f) = try makeProtected()
        let link = root.appendingPathComponent("link-to-home")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: p.deletingLastPathComponent())
        let quaLink = link.appendingPathComponent("Documents", isDirectory: true)
        XCTAssertEqual(StorageOtherData.purge(dirs: [quaLink], olderThan: 0, now: Date(), protectedRoots: [p]), 0)
        XCTAssertEqual(StorageOtherData.purge(dirs: [link], olderThan: 0, now: Date(), protectedRoots: [p]), 0)
        XCTAssertTrue(exists(f))
    }

    /// `work/L/..` với `L` là symlink tới gốc bảo vệ: hệ thống tệp đi theo `L` rồi lên cha của ĐÍCH (`home/`). Chốt
    /// chặn phải thấy đúng đường đó (tổ tiên của gốc bảo vệ ⇒ từ chối) — một phép so theo chữ (`work/`) để lọt rồi
    /// liệt kê `home/` là xoá cả cây `home/Documents`.
    func testChamChamQuaSymlinkKiemVaDonCungMotDuongDan() throws {
        let (p, f) = try makeProtected()
        let home = p.deletingLastPathComponent()
        let sibling = try write(5, "sibling.bin", in: home)
        let work = root.appendingPathComponent("work", isDirectory: true)
        try FileManager.default.createDirectory(at: work, withIntermediateDirectories: true)
        let link = work.appendingPathComponent("L")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: p)
        Thread.sleep(forTimeInterval: 0.05)
        let dir = URL(fileURLWithPath: link.path + "/..", isDirectory: true)

        _ = StorageOtherData.purge(dirs: [dir], olderThan: 0, now: Date(), protectedRoots: [p])

        XCTAssertTrue(exists(f), "gốc bảo vệ không được bị xoá qua `L/..`")
        XCTAssertTrue(exists(p))
        XCTAssertTrue(exists(sibling), "thư mục cha của đích symlink không phải thư mục được giao")
    }

    /// Nơi gọi truyền `protectedRoots: []` không tắt được chốt chặn: gốc mặc định (home, Documents, Library…) luôn được
    /// xét. Chỉ hỏi hàm quyết định thuần — KHÔNG gọi purge lên thư mục dữ liệu thật.
    func testProtectedRootsRongVanGiuGocMacDinh() {
        let fm = FileManager.default
        var that = [URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)]
        for d: FileManager.SearchPathDirectory in [.documentDirectory, .libraryDirectory,
                                                   .applicationSupportDirectory, .cachesDirectory] {
            that.append(fm.urls(for: d, in: .userDomainMask)[0])
        }
        for u in that {
            XCTAssertFalse(StorageOtherData.isAllowedPurgeRoot(u, protectedRoots: []), "\(u.path) phải bị từ chối")
            XCTAssertFalse(StorageOtherData.isAllowedPurgeRoot(u.deletingLastPathComponent(), protectedRoots: []),
                           "tổ tiên của \(u.path) phải bị từ chối")
        }
        XCTAssertTrue(StorageOtherData.isAllowedPurgeRoot(fm.temporaryDirectory, protectedRoots: []))
    }

    /// `protectedRoots: []` vẫn dọn thư mục hợp lệ (danh sách rỗng không chặn nhầm thư mục tạm).
    func testProtectedRootsRongVanDonThuMucTam() throws {
        let tmp = root.appendingPathComponent("tmp", isDirectory: true)
        let old = try write(12, "old.bin", in: tmp)
        Thread.sleep(forTimeInterval: 0.05)
        XCTAssertEqual(StorageOtherData.purge(dirs: [tmp], olderThan: 0, now: Date(), protectedRoots: []), 12)
        XCTAssertFalse(exists(old))
    }

    /// Bí danh `/private`: gốc bảo vệ CHƯA tồn tại trên đĩa (giải symlink không bỏ được `/private`) vẫn phải khớp cùng
    /// thư mục viết dạng có/không `/private`, cả hai chiều. Hàm thuần, đường dẫn không tồn tại — không xoá gì.
    func testBiDanhPrivateVanKhopGocChuaTonTai() {
        let ten = "khong-co-\(UUID().uuidString)"
        let coPrivate = URL(fileURLWithPath: "/private/var/\(ten)", isDirectory: true)
        let khongPrivate = URL(fileURLWithPath: "/var/\(ten)", isDirectory: true)
        XCTAssertFalse(StorageOtherData.isAllowedPurgeRoot(
            coPrivate, protectedRoots: [khongPrivate.appendingPathComponent("Documents", isDirectory: true)]))
        XCTAssertFalse(StorageOtherData.isAllowedPurgeRoot(
            khongPrivate, protectedRoots: [coPrivate.appendingPathComponent("Documents", isDirectory: true)]))
        XCTAssertFalse(StorageOtherData.isAllowedPurgeRoot(coPrivate, protectedRoots: [khongPrivate]))
        XCTAssertTrue(StorageOtherData.isAllowedPurgeRoot(
            coPrivate.appendingPathComponent("staging", isDirectory: true), protectedRoots: [khongPrivate]),
                      "con thật sự của gốc bảo vệ vẫn được phép")
    }

    /// Chính `/private` (bí danh của `/` cho `/var`, `/tmp`…) là tổ tiên của mọi gốc bảo vệ trên thiết bị ⇒ bị từ chối
    /// như `/`. Hàm thuần — không xoá gì.
    func testPrivateVaGocBiTuChoi() {
        for p in ["/private", "/private/", "/"] {
            XCTAssertFalse(StorageOtherData.isAllowedPurgeRoot(URL(fileURLWithPath: p, isDirectory: true),
                                                               protectedRoots: []), "\(p) phải bị từ chối")
        }
        XCTAssertTrue(StorageOtherData.isAllowedPurgeRoot(root.appendingPathComponent("tmp", isDirectory: true),
                                                          protectedRoots: []), "thư mục con thật của tmp vẫn được phép")
    }

    /// Ghim danh sách gốc mặc định (chỉ so đường dẫn, không xoá gì).
    func testGocBaoVeMacDinhCoDuThuMucDuLieu() {
        let fm = FileManager.default
        let have = Set(StorageOtherData.defaultProtectedRoots.map { StorageOtherData.normalized($0).path })
        var want = [URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)]
        for d: FileManager.SearchPathDirectory in [.documentDirectory, .libraryDirectory,
                                                   .applicationSupportDirectory, .cachesDirectory] {
            want.append(fm.urls(for: d, in: .userDomainMask)[0])
        }
        for w in want {
            XCTAssertTrue(have.contains(StorageOtherData.normalized(w).path), "thiếu gốc bảo vệ \(w.path)")
        }
        XCTAssertTrue(StorageOtherData.isAllowedPurgeRoot(fm.temporaryDirectory,
                                                          protectedRoots: StorageOtherData.defaultProtectedRoots),
                      "tmp/ phải được phép dọn")
    }

    // MARK: - bytes

    func testBytesCongCaThuMucConVaFileAn() throws {
        let d = root.appendingPathComponent("tmp", isDirectory: true)
        _ = try write(100, "a/b/c.bin", in: d)
        _ = try write(50, ".hidden", in: d)
        _ = try write(7, "x.bin", in: d)
        XCTAssertEqual(StorageOtherData.bytes(of: d), 157)
        XCTAssertEqual(StorageOtherData.bytes(of: d.appendingPathComponent("x.bin")), 7)
        XCTAssertEqual(StorageOtherData.bytes(of: root.appendingPathComponent("khong-co")), 0)
    }
}
