import XCTest
@testable import AppHost

/// Trần độ dài ở đây KHÔNG phải con số tuỳ tiện: nó phải khớp schema của máy chủ nhận phản hồi.
/// Lệch nhau thì user gõ xong, bấm Send, và nhận lỗi từ chối mà không hiểu vì sao — lỗi chỉ lộ
/// trên máy thật, sau khi ship.
final class FeedbackDraftTests: XCTestCase {

    private func draft(message: String = "co loi o day",
                       email: String? = nil,
                       diagnostics: String = "v1.0") -> FeedbackDraft {
        FeedbackDraft(type: .bug, message: message, email: email, diagnostics: diagnostics)
    }

    func testHopLeThiKhongNem() throws {
        XCTAssertNoThrow(try draft().validate())
    }

    func testMessageRongBiChan() {
        XCTAssertThrowsError(try draft(message: "   \n ").validate()) { e in
            XCTAssertEqual(e as? FeedbackValidationError, .messageEmpty)
        }
    }

    func testMessageDungTranVanQua() {
        let vua = String(repeating: "a", count: FeedbackDraft.maxMessageLength)
        XCTAssertNoThrow(try draft(message: vua).validate())
    }

    func testMessageVuotTranBiChan() {
        let qua = String(repeating: "a", count: FeedbackDraft.maxMessageLength + 1)
        XCTAssertThrowsError(try draft(message: qua).validate()) { e in
            XCTAssertEqual(e as? FeedbackValidationError, .messageTooLong)
        }
    }

    /// Email BỎ TRỐNG là hợp lệ — bắt buộc email sẽ chặn mất người chỉ muốn báo lỗi rồi đi.
    func testEmailTrongLaHopLe() {
        XCTAssertNoThrow(try draft(email: nil).validate())
        XCTAssertNoThrow(try draft(email: "").validate())
    }

    func testEmailSaiDinhDangBiChan() {
        XCTAssertThrowsError(try draft(email: "khong-phai-email").validate()) { e in
            XCTAssertEqual(e as? FeedbackValidationError, .emailInvalid)
        }
    }

    /// Cổng chống lệch với schema máy chủ: đổi hai số này là đổi hợp đồng.
    func testTranKhopSchemaMayChu() {
        XCTAssertEqual(FeedbackDraft.maxMessageLength, 4000)
        XCTAssertEqual(FeedbackDraft.maxDiagnosticsLength, 12000)
    }

    /// UTF-8 byte count ≠ grapheme cluster count. Chữ Việt có dấu tổ hợp có
    /// utf8.count > count. Nếu dùng count thì validate cho qua ở client nhưng
    /// máy chủ (bất kỳ đơn vị nào) lại từ chối — validate() phải dùng utf8.count.
    func testMessageUtf8VuotTranGraphemeKhong() {
        // "ệ" = 3 byte UTF-8: 1367 ký tự = 4101 byte, mà số ký tự vẫn < 4000.
        let vietnamesePart = String(repeating: "ệ", count: 1367)
        // Kiểm điều kiện tiền đề trước khi test hành động.
        XCTAssertLessThan(vietnamesePart.count, FeedbackDraft.maxMessageLength)
        XCTAssertGreaterThan(vietnamesePart.utf8.count, FeedbackDraft.maxMessageLength)
        XCTAssertThrowsError(try draft(message: vietnamesePart).validate()) { e in
            XCTAssertEqual(e as? FeedbackValidationError, .messageTooLong)
        }
    }

    func testDiagnosticsVuotTranBiChan() {
        let quaDai = String(repeating: "a", count: FeedbackDraft.maxDiagnosticsLength + 1)
        XCTAssertThrowsError(try draft(diagnostics: quaDai).validate()) { e in
            XCTAssertEqual(e as? FeedbackValidationError, .diagnosticsTooLong)
        }
    }

    func testDiagnosticsDungTranVanQua() {
        let vua = String(repeating: "a", count: FeedbackDraft.maxDiagnosticsLength)
        XCTAssertNoThrow(try draft(diagnostics: vua).validate())
    }

    // MARK: - Trần khớp máy chủ (email <= 320)

    func testTranEmailGhimDung() {
        XCTAssertEqual(FeedbackDraft.maxEmailLength, 320)
        XCTAssertEqual(FeedbackDraft.maxAppVersionLength, 64)
    }

    private func emailDai(_ n: Int) -> String {
        String(repeating: "a", count: n - 6) + "@b.com" // tổng đúng n byte
    }

    func testEmailDung320VanQua() {
        XCTAssertNoThrow(try draft(email: emailDai(320)).validate())
    }

    func testEmailQua320BiTuChoi() {
        XCTAssertThrowsError(try draft(email: emailDai(321)).validate()) { e in
            XCTAssertEqual(e as? FeedbackValidationError, .emailInvalid)
        }
    }
}
