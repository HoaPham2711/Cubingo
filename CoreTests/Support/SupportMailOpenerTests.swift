import XCTest
@testable import AppHost

/// Bug thật đã gặp: hai nơi (một nút "Contact us" và nút "Email us instead"
/// ở form phản hồi) từng tự viết lại logic "mở mailto, fallback copy clipboard khi không có Mail
/// app" — và lệch nhau ngay từ đầu (một nơi báo toast, nơi kia im lặng). Test ở đây gác đúng
/// hành vi DUY NHẤT mà mọi call site giờ cùng dùng qua `SupportMailOpener`.
@MainActor
final class SupportMailOpenerTests: XCTestCase {

    private final class FakeURLOpener: URLOpening {
        private(set) var lastURL: URL?
        var resultToReturn = true
        func open(_ url: URL, options: [UIApplication.OpenExternalURLOptionsKey: Any],
                  completionHandler completion: (@MainActor @Sendable (Bool) -> Void)?) {
            lastURL = url
            completion?(resultToReturn)
        }
    }

    private final class FakePasteboard: StringPasteboard {
        var string: String?
    }

    private let chanDoan = DiagnosticsSnapshot(
        appVersion: "1.2", build: "42", deviceModel: "iPhone15,3", systemVersion: "18.0",
        locale: "en_US", freeDiskMB: 100)

    private let support = SupportConfig(email: "help@example.com", subject: "Support request")

    func testMoDuocThiKhongCopyClipboardVaKhongGoiFallback() {
        let opener = FakeURLOpener()
        opener.resultToReturn = true
        let pasteboard = FakePasteboard()
        var soLanGoiFallback = 0
        SupportMailOpener.openOrCopyToClipboard(support: support, diagnostics: chanDoan,
                                                 opener: opener, pasteboard: pasteboard) {
            soLanGoiFallback += 1
        }
        XCTAssertNotNil(opener.lastURL)
        XCTAssertNil(pasteboard.string)
        XCTAssertEqual(soLanGoiFallback, 0)
    }

    /// Nhánh đã lệch giữa hai call site trước khi gộp: máy không có Mail app phải copy địa chỉ
    /// vào clipboard **và** báo cho call site biết để hiện phản hồi nhìn thấy được.
    func testKhongMoDuocThiCopyClipboardVaGoiFallback() {
        let opener = FakeURLOpener()
        opener.resultToReturn = false
        let pasteboard = FakePasteboard()
        var soLanGoiFallback = 0
        SupportMailOpener.openOrCopyToClipboard(support: support, diagnostics: chanDoan,
                                                 opener: opener, pasteboard: pasteboard) {
            soLanGoiFallback += 1
        }
        XCTAssertEqual(pasteboard.string, "help@example.com")
        XCTAssertEqual(soLanGoiFallback, 1)
    }

    /// `open(_:copyingOnFailure:...)` là hàm chung cho mọi liên kết ngoài cần lối thoát khi thất
    /// bại (không app nào xử lý được scheme) — trước đây nút gọi thẳng `UIApplication.shared.open`
    /// và im lặng chết.
    func testOpenLinkBatKyThatBaiThiCopyClipboardVaGoiFallback() {
        let opener = FakeURLOpener()
        opener.resultToReturn = false
        let pasteboard = FakePasteboard()
        let url = URL(string: "https://example.com/item?action=open")!
        var soLanGoiFallback = 0
        SupportMailOpener.open(url, copyingOnFailure: url.absoluteString,
                               opener: opener, pasteboard: pasteboard) {
            soLanGoiFallback += 1
        }
        XCTAssertEqual(opener.lastURL, url)
        XCTAssertEqual(pasteboard.string, url.absoluteString)
        XCTAssertEqual(soLanGoiFallback, 1)
    }

    func testOpenLinkBatKyThanhCongThiKhongCopyKhongFallback() {
        let opener = FakeURLOpener()
        opener.resultToReturn = true
        let pasteboard = FakePasteboard()
        let url = URL(string: "https://example.com/item?action=open")!
        var soLanGoiFallback = 0
        SupportMailOpener.open(url, copyingOnFailure: url.absoluteString,
                               opener: opener, pasteboard: pasteboard) {
            soLanGoiFallback += 1
        }
        XCTAssertNil(pasteboard.string)
        XCTAssertEqual(soLanGoiFallback, 0)
    }

    // MARK: - Không có địa chỉ hỗ trợ

    /// App không cấu hình địa chỉ: không mở gì, không copy gì, không báo "đã copy địa chỉ" (sai
    /// sự thật), không crash; hàm trả `false` để call site biết nút này không nên có.
    func testKhongCoDiaChiThiKhongLamGiVaTraFalse() {
        let opener = FakeURLOpener()
        let pasteboard = FakePasteboard()
        var soLanGoiFallback = 0
        let khong = SupportConfig(email: nil, subject: "Support request")
        let lam = SupportMailOpener.openOrCopyToClipboard(support: khong, diagnostics: chanDoan,
                                                           opener: opener, pasteboard: pasteboard) {
            soLanGoiFallback += 1
        }
        XCTAssertFalse(lam)
        XCTAssertNil(opener.lastURL)
        XCTAssertNil(pasteboard.string)
        XCTAssertEqual(soLanGoiFallback, 0)
    }

    func testCoDiaChiThiTraTrue() {
        let lam = SupportMailOpener.openOrCopyToClipboard(support: support, diagnostics: chanDoan,
                                                           opener: FakeURLOpener(),
                                                           pasteboard: FakePasteboard()) {}
        XCTAssertTrue(lam)
    }
}
