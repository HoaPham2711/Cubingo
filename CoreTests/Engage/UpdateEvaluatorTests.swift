import XCTest
@testable import AppHost

final class UpdateEvaluatorTests: XCTestCase {
    private let url = URL(string: "https://apps.apple.com/app/id1234567890")!
    private func rel(_ v: String, minOS: String = "17.0") -> StoreRelease {
        StoreRelease(version: v, minimumOsVersion: minOS, url: url)
    }

    func testBanMoiHonThiAvailable() {
        XCTAssertEqual(UpdateEvaluator.evaluate(installed: "1.0.0", osVersion: "17.5", release: rel("1.1.0")),
                       .available(version: "1.1.0", url: url, notes: nil))
    }

    func testBangHoacCuHonThiUpToDate() {
        XCTAssertEqual(UpdateEvaluator.evaluate(installed: "1.1", osVersion: "17.5", release: rel("1.1.0")), .upToDate)
        XCTAssertEqual(UpdateEvaluator.evaluate(installed: "1.2.0", osVersion: "17.5", release: rel("1.1.9")), .upToDate)
    }

    func testMayKhongLenDuocIOSThiKhongNhac() {
        XCTAssertEqual(UpdateEvaluator.evaluate(installed: "1.0", osVersion: "17.5", release: rel("1.1", minOS: "18.0")),
                       .upToDate)
        XCTAssertEqual(UpdateEvaluator.evaluate(installed: "1.0", osVersion: "18.0", release: rel("1.1", minOS: "18.0")),
                       .available(version: "1.1", url: url, notes: nil))
    }

    func testKhongCoReleaseHoacVersionRacThiUpToDate() {
        XCTAssertEqual(UpdateEvaluator.evaluate(installed: "1.0", osVersion: "17.5", release: nil), .upToDate)
        XCTAssertEqual(UpdateEvaluator.evaluate(installed: "1.0", osVersion: "17.5", release: rel("2.0-beta")), .upToDate)
        XCTAssertEqual(UpdateEvaluator.evaluate(installed: "?", osVersion: "17.5", release: rel("2.0")), .upToDate)
    }

    func testBannerAnSauKhiDismissVaHienLaiKhiCoBanMoiHon() {
        let a11 = UpdateStatus.available(version: "1.1", url: url, notes: nil)
        XCTAssertTrue(UpdateEvaluator.shouldShowBanner(status: a11, dismissedVersion: nil))
        XCTAssertFalse(UpdateEvaluator.shouldShowBanner(status: a11, dismissedVersion: "1.1"))
        XCTAssertFalse(UpdateEvaluator.shouldShowBanner(status: a11, dismissedVersion: "1.1.0"))
        XCTAssertTrue(UpdateEvaluator.shouldShowBanner(status: .available(version: "1.2", url: url, notes: nil),
                                                       dismissedVersion: "1.1"))
        XCTAssertFalse(UpdateEvaluator.shouldShowBanner(status: .upToDate, dismissedVersion: nil))
    }

    // MARK: - Release notes

    func testAvailableMangReleaseNotesCuaStore() {
        var r = rel("1.1")
        r.releaseNotes = "New themes\nBug fixes"
        XCTAssertEqual(UpdateEvaluator.evaluate(installed: "1.0", osVersion: "17.5", release: r),
                       .available(version: "1.1", url: url, notes: "New themes\nBug fixes"))
    }

    func testDismissKhongPhuThuocNotes() {
        let a = UpdateStatus.available(version: "1.1", url: url, notes: "Something new")
        XCTAssertFalse(UpdateEvaluator.shouldShowBanner(status: a, dismissedVersion: "1.1"))
    }

    func testHeadlineLaDongDauKhongRong() {
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "Only one line"), "Only one line")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "Fix A\nFix B"), "Fix A")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "\n  \n\t\n  New themes  \nmore"),
                       "New themes", "bỏ dòng trắng/toàn khoảng trắng ở đầu, cắt khoảng trắng hai đầu")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "\r\n\r\nFirst\r\nSecond"), "First",
                       "notes của Store có thể xuống dòng kiểu CRLF")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "\u{2028}First\u{2028}Second"), "First")
    }

    /// Notes dán từ Word/Notes hay mang ký tự định dạng vô hình (BOM U+FEFF, zero-width U+200B…U+200D, U+2060) —
    /// `whitespacesAndNewlines` không coi chúng là khoảng trắng ⇒ dòng chỉ có BOM thành headline "rỗng" hiển thị.
    func testHeadlineBoQuaKyTuDinhDangVoHinh() {
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "\u{FEFF}\nFirst\nSecond"), "First",
                       "dòng chỉ có BOM là dòng trắng")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "\u{FEFF}First line"), "First line", "BOM đầu chuỗi")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "\u{200B} \u{2060}\n\u{200D}Second\u{200B}"), "Second")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "Café\u{200B}s"), "Café\u{200B}s",
                       "chỉ cắt hai đầu, không xoá ký tự giữa dòng")
        XCTAssertNil(UpdateEvaluator.bannerHeadline(notes: "\u{FEFF}"))
        XCTAssertNil(UpdateEvaluator.bannerHeadline(notes: "\u{FEFF}\n\u{200B}\n \u{2060} "))
    }

    /// Cắt theo Character (cụm grapheme), không theo scalar: emoji có scalar Cf/ẩn BÊN TRONG cụm (cờ vùng dùng tag
    /// U+E0020…E007F, VS16, ZWJ) phải giữ nguyên; Default_Ignorable không thuộc Cf (U+3164, U+115F, CGJ U+034F, VS16
    /// đứng một mình) là vô hình ⇒ dòng chỉ có chúng là dòng trắng.
    func testHeadlineCatTheoGraphemeVaDefaultIgnorable() {
        let england = "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}"
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "Now in the UK \(england)"), "Now in the UK \(england)",
                       "không được cắt đuôi tag của cờ vùng")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: england), england)
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "Love \u{2764}\u{FE0F}"), "Love \u{2764}\u{FE0F}")
        let family = "\u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467}"
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "Family \(family)"), "Family \(family)")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "x\u{200D}"), "x\u{200D}", "ZWJ dính vào x là một Character")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "\u{3164}\nReal line"), "Real line", "Hangul filler vô hình")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "\u{115F}\n\u{034F}\n\u{FE0F}\nReal"), "Real")
        XCTAssertEqual(UpdateEvaluator.bannerHeadline(notes: "\u{00A0}Real\u{3000}"), "Real")
    }

    func testHeadlineNilRongToanKhoangTrangThiNil() {
        XCTAssertNil(UpdateEvaluator.bannerHeadline(notes: nil))
        XCTAssertNil(UpdateEvaluator.bannerHeadline(notes: ""))
        XCTAssertNil(UpdateEvaluator.bannerHeadline(notes: "   "))
        XCTAssertNil(UpdateEvaluator.bannerHeadline(notes: " \n\t\n \r\n  "))
    }

    /// `update_prompt` "shown" (banner Home): lần đầu mời ⇒ log; cùng phiên bản lần sau ⇒ không; phiên bản mới hơn ⇒
    /// log lại; không có gì để mời ⇒ không.
    func testLogHienCapNhatMotLanMoiPhienBan() {
        XCTAssertTrue(UpdateEvaluator.shouldLogUpdateShown(loggedVersion: nil, offeredVersion: "2.0"))
        XCTAssertFalse(UpdateEvaluator.shouldLogUpdateShown(loggedVersion: "2.0", offeredVersion: "2.0"))
        XCTAssertTrue(UpdateEvaluator.shouldLogUpdateShown(loggedVersion: "2.0", offeredVersion: "2.1"))
        XCTAssertFalse(UpdateEvaluator.shouldLogUpdateShown(loggedVersion: nil, offeredVersion: nil))
    }
}
