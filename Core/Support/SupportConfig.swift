import Foundation

/// Cấu hình liên hệ hỗ trợ của app. Địa chỉ đến từ `app.config.toml` qua `AppConfig`; lõi không
/// giữ địa chỉ nào của riêng nó.
///
/// `email == nil` nghĩa là app không có hộp thư hỗ trợ: mọi lối vào qua mail (`SupportMail`,
/// `SupportMailOpener`, nút "Email us instead") phải tự thoái lui êm — không dựng `mailto:` rỗng
/// người nhận, không báo "đã copy địa chỉ" khi không có địa chỉ nào. Call site nên ẩn nút đó.
struct SupportConfig: Equatable {
    let email: String?
    let subject: String

    init(config: AppConfig) {
        self.init(email: config.supportEmail, subject: String(localized: "Support request"))
    }

    /// Dựng tường minh (test, app có chủ đề riêng). Địa chỉ được cắt khoảng trắng; rỗng ⇒ `nil`.
    init(email: String?, subject: String) {
        let sach = email?.trimmingCharacters(in: .whitespacesAndNewlines)
        self.email = (sach?.isEmpty ?? true) ? nil : sach
        self.subject = subject
    }
}
