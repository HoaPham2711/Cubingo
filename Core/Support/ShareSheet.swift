import SwiftUI
import UIKit

/// Wrapper cho `UIActivityViewController` để chia sẻ file ra khỏi app (bảng chia sẻ hệ thống).
struct ShareSheet: UIViewControllerRepresentable {
    let items: [URL]
    /// Gọi với id activity (nil nếu đóng không chọn) và việc chia sẻ có hoàn tất không.
    var onFinish: ((String?, Bool) -> Void)? = nil

    func makeUIViewController(context: Context) -> UIActivityViewController {
        let vc = UIActivityViewController(activityItems: items, applicationActivities: nil)
        vc.completionWithItemsHandler = { type, completed, _, _ in onFinish?(type?.rawValue, completed) }
        return vc
    }

    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}
