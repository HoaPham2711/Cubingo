import UIKit

/// Hỏi UIKit xem cửa sổ chính có đang present modal nào không — dùng chung cho bộ canh yên của mời đánh giá
/// (`ReviewScheduler`) và điều kiện hiện sheet "có gì mới".
enum ModalPresentationProbe {
    /// True nếu cửa sổ chính đang có bất kỳ view controller nào được present modally (bảng chia sẻ hệ thống, QuickLook,
    /// paywall, màn toàn cảnh, ...). Alert/sheet present từ view gốc khi có modal đè sẽ bị nuốt.
    static func isModalPresented() -> Bool {
        let scene = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive }
        guard let root = scene?.windows.first(where: \.isKeyWindow)?.rootViewController else {
            return false
        }
        var top = root
        while let presented = top.presentedViewController { top = presented }
        return top !== root
    }
}
