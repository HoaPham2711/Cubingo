import Foundation

/// Đường liên hệ hai chiều. Cố ý KHÔNG dùng `MFMailComposeViewController`: nó cũng đòi máy có
/// tài khoản Mail, mà lại kéo theo UIKit delegate và một màn hình nữa để bảo trì.
enum SupportMail {
    /// `nil` khi không dựng được URL — gồm cả khi app không cấu hình địa chỉ hỗ trợ (không bao giờ
    /// ra `mailto:` rỗng người nhận). Call site phải fallback (copy địa chỉ vào clipboard) hoặc ẩn
    /// nút, đừng để user bấm vào một nút không làm gì.
    /// Trần số ký tự của `message` đưa vào body: URL `mailto:` quá dài thì Mail có thể từ chối mở.
    static let maxMessageCharacters = 2000

    /// `message` (nếu có) là nội dung user đã gõ trong form phản hồi mà gửi hỏng — đặt lên đầu body để
    /// họ không phải gõ lại; cắt ở ranh giới ký tự về `maxMessageCharacters`.
    static func url(support: SupportConfig, diagnostics: DiagnosticsSnapshot, message: String? = nil) -> URL? {
        guard let address = support.email else { return nil }
        let nguoiDung = message.map { String($0.prefix(maxMessageCharacters)) } ?? ""
        let body = nguoiDung + "\n\n---\n"
            + String(localized: "Please describe your issue above this line.")
            + "\n\n" + diagnostics.text

        // `URLComponents.queryItems` KHÔNG percent-encode `&` trong giá trị (hành vi đã biết của
        // Foundation) — một `&` sống sót trong subject/body sẽ bị Mail hiểu là dấu tách tham số
        // kế tiếp, cắt cụt phần còn lại (body chẩn đoán biến mất). Vì vậy tự encode thủ công bằng
        // một tập ký tự cho phép HẸP (chỉ chữ+số), rồi gán thẳng vào `percentEncodedQueryItems`
        // để URLComponents không encode chồng lần hai.
        func encode(_ s: String) -> String {
            s.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? ""
        }

        var c = URLComponents()
        c.scheme = "mailto"
        c.path = address
        c.percentEncodedQueryItems = [
            URLQueryItem(name: "subject", value: encode(support.subject)),
            URLQueryItem(name: "body", value: encode(body)),
        ]
        return c.url
    }
}
