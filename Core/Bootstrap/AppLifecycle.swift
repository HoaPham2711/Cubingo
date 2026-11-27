import SwiftUI

/// Phản ứng chung với `scenePhase` — app gọi trong `.onChange(of: scenePhase)` ở view gốc.
///
/// - `.background` ⇒ dấu "đang làm việc" thành do-nền: iOS kill app nền là chuyện bình thường, không phải sự cố.
/// - `.active` ⇒ hết do-nền, rồi `onActive` của app đúng một lần: `entitlements.refresh()` (hết hạn subscription KHÔNG
///   bắn `Transaction.updates`; sửa thẻ trong Settings hệ thống phải thấy Pro về), kiểm tra cập nhật,
///   `reviewPrompter.noteAppBecameActive()`… — app tự bỏ phần StoreKit/mạng theo `AppBootstrap.skipsStoreKit/skipsNetwork`.
/// - `.inactive` ⇒ không làm gì (thoáng qua khi kéo Control Center, hộp thoại hệ thống).
enum AppLifecycle {
    static func handle(_ phase: ScenePhase, markers: ActiveWorkMarkerStore = .shared, onActive: () -> Void) {
        switch phase {
        case .background:
            markers.setBackgrounded(true)
        case .active:
            markers.setBackgrounded(false)
            onActive()
        default:
            break
        }
    }
}
