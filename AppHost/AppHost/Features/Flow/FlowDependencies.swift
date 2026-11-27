import UIKit

/// Phản hồi rung của luồng.
enum FlowHaptic { case capture, success, warning }

/// Phụ thuộc tường minh của luồng — dựng MỘT lần ở `AppHostApp`, truyền qua `init`.
struct FlowDependencies {
    let prefs: PrefsStore
    /// Rung (bản thật tự kiểm `prefs.haptics`).
    let haptic: @MainActor (FlowHaptic) -> Void
    /// Bộ giải "Just solve it" (bảng nạp lười ở lần gọi đầu).
    let quickSolver: SolverQuick
    /// Quyền camera (Simulator: luôn có — nguồn giả `ScanPreviewSeed`).
    let cameraAuth: ScanCameraAuth
}

/// Rung thật bằng UIKit; tắt trong Settings ⇒ không làm gì.
enum FlowHaptics {
    @MainActor
    static func live(prefs: PrefsStore) -> @MainActor (FlowHaptic) -> Void {
        { [weak prefs] kind in
            guard prefs?.haptics == true else { return }
            switch kind {
            case .capture: UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            case .success: UINotificationFeedbackGenerator().notificationOccurred(.success)
            case .warning: UINotificationFeedbackGenerator().notificationOccurred(.warning)
            }
        }
    }
}
