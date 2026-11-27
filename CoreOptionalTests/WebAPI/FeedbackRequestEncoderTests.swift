import XCTest
@testable import AppHost

/// Hợp đồng body của `POST /api/v1/feedback`: JSON phẳng đúng sáu field. Sai tên field hay sai kiểu là máy chủ trả
/// 422 và user chỉ thấy "Something went wrong". Đổi hợp đồng = đổi schema phía máy chủ cùng lúc.
final class FeedbackRequestEncoderTests: XCTestCase {

    private func giaiMa(_ d: Data) throws -> [String: Any] {
        try XCTUnwrap(JSONSerialization.jsonObject(with: d) as? [String: Any])
    }

    func testJSONPhangDungSauField() throws {
        let draft = FeedbackDraft(type: .feature, message: "thêm xuất PDF", email: "a@b.co", diagnostics: "app version: 1.0")
        let json = try giaiMa(FeedbackRequestEncoder.body(for: draft, appVersion: "1.4.0",
                                                          clientTime: Date(timeIntervalSince1970: 0)))
        XCTAssertEqual(Set(json.keys), ["type", "message", "email", "diagnostics", "appVersion", "clientTime"])
        XCTAssertEqual(json["type"] as? String, "feature")
        XCTAssertEqual(json["message"] as? String, "thêm xuất PDF")
        XCTAssertEqual(json["email"] as? String, "a@b.co")
        XCTAssertEqual(json["diagnostics"] as? String, "app version: 1.0")
        XCTAssertEqual(json["appVersion"] as? String, "1.4.0")
    }

    /// Máy chủ đòi số NGUYÊN mili-giây: gửi giây hay số lẻ là 422.
    func testClientTimeLaMiliGiayNguyen() throws {
        let json = try giaiMa(FeedbackRequestEncoder.body(
            for: FeedbackDraft(type: .bug, message: "x", email: nil, diagnostics: "d"),
            appVersion: "1.0", clientTime: Date(timeIntervalSince1970: 1_790_000_000.1234)))
        let ms = try XCTUnwrap(json["clientTime"] as? NSNumber)
        XCTAssertEqual(ms.int64Value, 1_790_000_000_123)
        XCTAssertEqual(ms.doubleValue, Double(ms.int64Value))
    }

    /// Hình dạng body không dao động theo input: không có email vẫn gửi `"email": ""`.
    func testEmailNilThanhChuoiRong() throws {
        let json = try giaiMa(FeedbackRequestEncoder.body(
            for: FeedbackDraft(type: .bug, message: "x", email: nil, diagnostics: "d"),
            appVersion: "1.0", clientTime: Date()))
        XCTAssertEqual(json["email"] as? String, "")
    }

    /// Validate TRƯỚC khi ra mạng và đúng theo `FeedbackDraft.validate()` (cùng trần byte UTF-8): để máy chủ bắt thì
    /// tốn một vòng round-trip và user không biết mình sai chỗ nào.
    func testDraftKhongHopLeThiNemTruocKhiRaMang() {
        func loi(_ d: FeedbackDraft) -> FeedbackValidationError? {
            do { _ = try FeedbackRequestEncoder.body(for: d, appVersion: "1.0", clientTime: Date()); return nil }
            catch { return error as? FeedbackValidationError }
        }
        XCTAssertEqual(loi(FeedbackDraft(type: .bug, message: "  ", email: nil, diagnostics: "d")), .messageEmpty)
        XCTAssertEqual(loi(FeedbackDraft(type: .bug, message: String(repeating: "a", count: FeedbackDraft.maxMessageLength + 1),
                                         email: nil, diagnostics: "d")), .messageTooLong)
        XCTAssertEqual(loi(FeedbackDraft(type: .bug, message: "x", email: nil,
                                         diagnostics: String(repeating: "a", count: FeedbackDraft.maxDiagnosticsLength + 1))),
                       .diagnosticsTooLong)
        XCTAssertEqual(loi(FeedbackDraft(type: .bug, message: "x", email: "khong-phai-email", diagnostics: "d")), .emailInvalid)
        // Đúng trần thì qua; trần đo bằng byte UTF-8: "ế" là 3 byte nên 1334 ký tự (4002 byte) vượt trần 4000.
        XCTAssertNil(loi(FeedbackDraft(type: .bug, message: String(repeating: "a", count: FeedbackDraft.maxMessageLength),
                                       email: nil, diagnostics: "d")))
        XCTAssertEqual(loi(FeedbackDraft(type: .bug, message: String(repeating: "ế", count: 1334), email: nil, diagnostics: "d")),
                       .messageTooLong)
    }

    // MARK: - appVersion 1...64 như máy chủ

    private func appVersionGui(_ v: String) throws -> String {
        let json = try giaiMa(FeedbackRequestEncoder.body(
            for: FeedbackDraft(type: .bug, message: "x", email: nil, diagnostics: "d"),
            appVersion: v, clientTime: Date()))
        return try XCTUnwrap(json["appVersion"] as? String)
    }

    func testAppVersionDai65BiCat64() throws {
        XCTAssertEqual(try appVersionGui(String(repeating: "1", count: 65)).utf8.count, 64)
        XCTAssertEqual(try appVersionGui(String(repeating: "1", count: 64)).count, 64)
        XCTAssertEqual(try appVersionGui("1.4.0"), "1.4.0")
    }

    /// Cắt theo ký tự, không xé đôi ký tự nhiều byte.
    func testAppVersionCatKhongXeKyTu() throws {
        let gui = try appVersionGui(String(repeating: "é", count: 40)) // 80 byte
        XCTAssertEqual(gui, String(repeating: "é", count: 32))
    }
}
