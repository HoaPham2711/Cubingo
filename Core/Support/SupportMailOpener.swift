import UIKit

/// Trừu tượng hoá đúng phần `UIApplication` mà `SupportMailOpener` cần — chữ ký khớp NGUYÊN VĂN
/// `UIApplication.open(_:options:completionHandler:)` nên `extension UIApplication: URLOpening {}`
/// không cần viết lại thân hàm. Tồn tại chỉ để test được (`FakeURLOpener` ở
/// `SupportMailOpenerTests.swift`) — không đổi hành vi thật.
///
/// `@MainActor` + completion `@MainActor @Sendable` là chữ ký SDK iOS 17 của `UIApplication.open`;
/// khai closure thường thì conformance lệch sendability (warning Swift 5, LỖI ở Swift 6).
@MainActor
protocol URLOpening {
    func open(_ url: URL, options: [UIApplication.OpenExternalURLOptionsKey: Any],
              completionHandler completion: (@MainActor @Sendable (Bool) -> Void)?)
}
extension UIApplication: URLOpening {}

/// Trừu tượng hoá phần `UIPasteboard` cần dùng — cùng lý do trên.
protocol StringPasteboard: AnyObject {
    var string: String? { get set }
}
extension UIPasteboard: StringPasteboard {}

/// Cửa DUY NHẤT "mở mailto rồi fallback copy clipboard khi máy không có Mail app".
///
/// Trước khi gộp, nút "Contact us" và nút "Email us instead" của form phản hồi mỗi nơi tự viết lại
/// đúng logic này — và đã LỆCH NHAU ngay từ đầu: một nơi báo toast "Copied" khi fallback, nơi kia
/// copy clipboard trong im lặng, dù comment ngay trên nó ghi "đừng để nút bấm vào không làm gì".
/// Gộp về một chỗ để không còn chỗ lệch thứ hai.
///
/// Cố ý KHÔNG đụng vào `SupportMail.url(...)` — hàm đó PHẢI giữ thuần (không biết gì về UIKit),
/// đã có test riêng gác percent-encoding. File này chỉ lo phần "thực thi" (chạm
/// `UIApplication`/`UIPasteboard`), tách khỏi phần "dựng URL" (thuần, ở `SupportMail.swift`).
enum SupportMailOpener {
    /// `onCopiedFallback` chạy trên main actor CHỈ khi phải fallback sang clipboard — call site tự
    /// quyết định hiển thị thế nào (alert, toast...), hàm này chỉ lo QUYẾT ĐỊNH khi nào cần gọi.
    ///
    /// Trả `false` (không làm gì: không mở, không copy, không gọi `onCopiedFallback`) khi không có
    /// gì để mở — app không cấu hình địa chỉ hỗ trợ, hoặc không dựng được URL. Call site nên ẩn
    /// nút ngay từ đầu (`SupportConfig.email == nil`); giá trị trả về chỉ là lưới an toàn.
    @MainActor
    @discardableResult
    static func openOrCopyToClipboard(support: SupportConfig, diagnostics: DiagnosticsSnapshot,
                                       message: String? = nil,
                                       opener: URLOpening? = nil,
                                       pasteboard: StringPasteboard = UIPasteboard.general,
                                       onCopiedFallback: @escaping () -> Void) -> Bool {
        guard let address = support.email,
              let url = SupportMail.url(support: support, diagnostics: diagnostics, message: message) else { return false }
        open(url, copyingOnFailure: address, opener: opener, pasteboard: pasteboard,
             onCopiedFallback: onCopiedFallback)
        return true
    }

    /// Mở MỘT url bất kỳ (không riêng mailto) rồi fallback copy `copyingOnFailure` vào clipboard
    /// khi `opener.open` báo thất bại (không app nào xử lý được scheme đó). Dùng chung bởi
    /// "Contact us" (qua `openOrCopyToClipboard` ở trên, mailto) và mọi liên kết ngoài khác cần
    /// lối thoát — trước đây một nút gọi thẳng `UIApplication.shared.open`, bỏ qua trừu tượng
    /// `URLOpening` này và không có lối thoát khi thất bại (nút chết im lặng, đúng thứ hàm này
    /// sinh ra để chặn).
    @MainActor
    static func open(_ url: URL, copyingOnFailure copyText: String,
                     opener: URLOpening? = nil,
                     pasteboard: StringPasteboard = UIPasteboard.general,
                     onCopiedFallback: @escaping () -> Void) {
        // `nil` = `UIApplication.shared`, lấy TRONG thân hàm: default argument được tính ở ngữ cảnh
        // không cô lập, còn `shared` là main-actor (warning Swift 5, LỖI ở Swift 6).
        (opener ?? UIApplication.shared).open(url, options: [:]) { ok in
            guard !ok else { return }
            pasteboard.string = copyText
            onCopiedFallback()
        }
    }
}

/// Nút "Contact us" — MỘT đường cho mọi nơi trong app cần lối liên hệ (chủ đề + câu báo khi
/// fallback clipboard), để các chỗ không lệch nhau như từng lệch giữa nút liên hệ và form phản
/// hồi (xem comment `SupportMailOpener`).
enum SupportContact {
    /// Câu xác nhận khi máy không có Mail app và địa chỉ đã được copy vào clipboard.
    static var copiedAddressMessage: String {
        String(localized: "This device has no Mail app set up. We copied our support email address to your clipboard instead.")
    }

    /// `false` khi app không có địa chỉ hỗ trợ (không làm gì) — xem `SupportMailOpener`.
    @MainActor
    @discardableResult
    static func contactUs(support: SupportConfig, diagnostics: DiagnosticsSnapshot,
                          onCopiedFallback: @escaping () -> Void) -> Bool {
        SupportMailOpener.openOrCopyToClipboard(support: support, diagnostics: diagnostics,
                                                 onCopiedFallback: onCopiedFallback)
    }
}
