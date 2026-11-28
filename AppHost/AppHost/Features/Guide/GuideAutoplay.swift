import Foundation

/// Tự chạy ở màn chỉ bước: sau mỗi hoạt ảnh, chờ một nhịp rồi tự làm bước kế tiếp; dừng ở cuối chặng / khi xong.
enum GuideAutoplay {
    /// Nhịp chờ sau khi một bước quay xong (đủ để người dùng làm theo trên khối thật).
    static func gap(_ speed: PrefsSpeed) -> Double { speed.quarterTurnSeconds * 1.2 }

    /// Làm một bước nếu còn bước trong chặng. `false` ⇒ dừng tự chạy.
    @MainActor @discardableResult
    static func tick(_ s: GuideSession) -> Bool {
        guard s.phase == .step, s.currentStep != nil else { return false }
        s.next()
        return true
    }
}
