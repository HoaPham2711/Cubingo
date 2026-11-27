import XCTest
@testable import AppHost

/// `mailto:` là bãi mìn percent-encoding: xuống dòng, dấu cách, tiếng Việt và ký tự `&` đều
/// phá URL nếu encode sai — triệu chứng là Mail mở ra với body cụt hoặc URL không mở được gì cả.
/// Địa chỉ nhận do app cấu hình (`SupportConfig`); test dựng cấu hình tường minh, không đọc
/// cấu hình thật của template.
final class SupportMailTests: XCTestCase {

    private let chanDoan = DiagnosticsSnapshot(
        appVersion: "1.2", build: "42", deviceModel: "iPhone15,3", systemVersion: "18.0",
        locale: "vi_VN", freeDiskMB: 100)

    private func config(subject: String = "Hi", email: String? = "help@example.com") -> SupportConfig {
        SupportConfig(email: email, subject: subject)
    }

    func testDungDiaChiHoTroTuCauHinh() throws {
        let url = try XCTUnwrap(SupportMail.url(support: config(), diagnostics: chanDoan))
        XCTAssertTrue(url.absoluteString.hasPrefix("mailto:help@example.com?"))
    }

    func testXuongDongTrongBodyDuocEncode() throws {
        let s = try XCTUnwrap(SupportMail.url(support: config(), diagnostics: chanDoan)).absoluteString
        XCTAssertFalse(s.contains("\n"), "xuống dòng thô làm URL cụt ở Mail")
        XCTAssertTrue(s.contains("%0A") || s.contains("%0D%0A"))
    }

    func testTiengVietVaKyTuDacBietTrongSubject() throws {
        let s = try XCTUnwrap(SupportMail.url(support: config(subject: "Lỗi & sự cố"),
                                               diagnostics: chanDoan)).absoluteString
        XCTAssertFalse(s.contains("Lỗi"), "phải percent-encode, không để nguyên")
        // `&` trong subject mà không encode sẽ bị hiểu là dấu tách tham số → mất body.
        XCTAssertEqual(s.components(separatedBy: "&").count, 2, "chỉ được đúng một dấu & phân tách subject/body")
    }

    func testBodyChuaChanDoan() throws {
        let url = try XCTUnwrap(SupportMail.url(support: config(), diagnostics: chanDoan))
        let body = try XCTUnwrap(URLComponents(url: url, resolvingAgainstBaseURL: false)?
            .queryItems?.first(where: { $0.name == "body" })?.value)
        XCTAssertTrue(body.contains("iPhone15,3"))
    }

    private func body(_ url: URL) throws -> String {
        try XCTUnwrap(URLComponents(url: url, resolvingAgainstBaseURL: false)?
            .queryItems?.first(where: { $0.name == "body" })?.value)
    }

    /// Gửi phản hồi hỏng rồi chuyển sang Mail: nội dung user vừa gõ phải theo sang, đứng trước chẩn đoán.
    func testBodyMangNoiDungUserGoVaVanCoChanDoan() throws {
        let url = try XCTUnwrap(SupportMail.url(support: config(), diagnostics: chanDoan, message: "app bi dung & treo"))
        let b = try body(url)
        XCTAssertTrue(b.hasPrefix("app bi dung & treo"))
        XCTAssertTrue(b.contains("iPhone15,3"))
    }

    func testNoiDungUserBiCatOTran() throws {
        let dai = String(repeating: "é", count: SupportMail.maxMessageCharacters + 500)
        let b = try body(XCTUnwrap(SupportMail.url(support: config(), diagnostics: chanDoan, message: dai)))
        XCTAssertTrue(b.hasPrefix(String(repeating: "é", count: SupportMail.maxMessageCharacters) + "\n"))
    }

    // MARK: - Không có địa chỉ

    /// App không cấu hình địa chỉ ⇒ không dựng URL (không bao giờ ra `mailto:` rỗng người nhận).
    func testKhongCoDiaChiThiKhongDungURL() {
        for email in [nil, "", "   \n"] as [String?] {
            XCTAssertNil(SupportMail.url(support: config(email: email), diagnostics: chanDoan), "email=\(email ?? "nil")")
        }
    }

    func testSupportConfigDocDiaChiTuAppConfig() {
        let co = SupportConfig(config: AppConfig(info: ["SupportEmail": "  help@example.com "]))
        XCTAssertEqual(co.email, "help@example.com")
        let khong = SupportConfig(config: AppConfig(info: [:]))
        XCTAssertNil(khong.email)
        XCTAssertFalse(khong.subject.isEmpty)
    }

    /// Chủ đề không được cứng tên app: không có `displayName` thì cũng không có gì tên app lọt vào.
    func testChuDeKhongChuaTenApp() {
        let c = SupportConfig(config: AppConfig(info: ["CFBundleDisplayName": "Zorblax"]))
        XCTAssertFalse(c.subject.contains("Zorblax"))
    }
}
