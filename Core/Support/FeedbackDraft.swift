import Foundation

/// Loại phản hồi. `rawValue` đi thẳng lên máy chủ nhận phản hồi và bị schema của nó ép vào đúng
/// ba giá trị này — đổi tên case là đổi hợp đồng với máy chủ, phải sửa schema cùng lúc.
enum FeedbackType: String, CaseIterable, Identifiable {
    case bug, feature, other
    var id: String { rawValue }
}

enum FeedbackValidationError: Error, Equatable {
    case messageEmpty
    case messageTooLong
    case emailInvalid
    case diagnosticsTooLong
}

/// Một phản hồi user sắp gửi. Value type thuần: không biết gì về mạng, SDK hay UI.
struct FeedbackDraft: Equatable {
    /// Khớp schema của máy chủ nhận phản hồi — đổi hai số này là đổi hợp đồng. Có test ghim.
    static let maxMessageLength = 4000
    static let maxDiagnosticsLength = 12000
    /// Chuẩn RFC 5321 cho địa chỉ e-mail; máy chủ cũng chặn ở 320.
    static let maxEmailLength = 320
    /// `appVersion` lên máy chủ phải dài 1...64 ký tự — transport phải cắt về trần này.
    static let maxAppVersionLength = 64

    let type: FeedbackType
    let message: String
    let email: String?
    let diagnostics: String

    func validate() throws {
        let sach = message.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !sach.isEmpty else { throw FeedbackValidationError.messageEmpty }
        // Dùng utf8.count thay vì count: UTF-8 byte count >= code-point count >= grapheme cluster count.
        // Với chữ có dấu tổ hợp, grapheme.count < utf8.count. Kiểm UTF-8 đảm bảo client chặt hơn
        // máy chủ (bất kỳ đơn vị nào máy chủ dùng), tránh bị từ chối mù lúc gửi.
        guard message.utf8.count <= Self.maxMessageLength else { throw FeedbackValidationError.messageTooLong }
        guard diagnostics.utf8.count <= Self.maxDiagnosticsLength else { throw FeedbackValidationError.diagnosticsTooLong }
        // Cùng quy ước byte UTF-8 như hai trần trên (chặt hơn hoặc bằng đơn vị máy chủ dùng).
        if let email, email.utf8.count > Self.maxEmailLength { throw FeedbackValidationError.emailInvalid }
        if let email, !email.isEmpty, !Self.trongNhuEmail(email) {
            throw FeedbackValidationError.emailInvalid
        }
    }

    /// Kiểm tra CỐ Ý lỏng: mục đích chỉ là bắt lỗi gõ nhầm, không phải xác thực hộp thư. Regex
    /// email chặt là cái bẫy kinh điển — nó loại cả địa chỉ hợp lệ.
    static func trongNhuEmail(_ s: String) -> Bool {
        guard let at = s.firstIndex(of: "@"), at != s.startIndex else { return false }
        let sau = s[s.index(after: at)...]
        return sau.contains(".") && !sau.hasPrefix(".") && !sau.hasSuffix(".") && !sau.contains("@")
    }
}
