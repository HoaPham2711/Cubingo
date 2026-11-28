import Foundation

/// Tự chạy ở màn chỉ bước: sau mỗi hoạt ảnh, chờ một nhịp rồi tự làm bước kế tiếp; dừng ở cuối chặng / khi xong.
enum GuideAutoplay {
    /// Nhịp chờ sau khi một bước quay xong (đủ để người dùng làm theo trên khối thật).
    static func gap(_ speed: PrefsSpeed) -> Double { speed.quarterTurnSeconds * 1.2 }

    /// Bật/tắt tự chạy kèm số thế hệ: mỗi lần dừng tăng thế hệ ⇒ lượt chờ của lần chạy trước không tự làm thêm bước
    /// (Pause rồi Play lại giữa nhịp chờ).
    struct Clock: Equatable {
        private(set) var isOn = false
        private(set) var generation = 0

        mutating func start() { isOn = true }

        mutating func stop() {
            isOn = false
            generation += 1
        }

        /// Lượt chờ bắt đầu ở thế hệ `g` còn được làm bước kế không.
        func mayTick(_ g: Int) -> Bool { isOn && g == generation }
    }

    /// Làm một bước nếu còn bước trong chặng. `false` ⇒ dừng tự chạy.
    @MainActor @discardableResult
    static func tick(_ s: GuideSession) -> Bool {
        guard s.phase == .step, s.currentStep != nil else { return false }
        s.next()
        return true
    }
}
