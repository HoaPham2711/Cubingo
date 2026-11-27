import Foundation

/// Thời điểm cân nhắc mời đánh giá. Không quyết định ngay: `ReviewScheduler.arm` gài rồi đợi màn hình
/// "yên" mới hỏi policy. App gọi 0..2 loại, tuỳ nó có khái niệm đó hay không.
enum ReviewMoment: Equatable {
    /// Đóng màn xem một mục. `reopened` = đây là lần mở thứ 2 trở đi của chính mục đó.
    case contentClosed(dwellSeconds: Int, reopened: Bool)
    /// Hành động tạo giá trị chính của app vừa xong (vd. đầu ra được lưu/chia sẻ thành công).
    case outputDone

    /// `source` của `review_ask`.
    var analyticsSource: String {
        switch self {
        case .contentClosed: return "content"
        case .outputDone: return "output"
        }
    }

    /// Hai moment chờ chồng nhau thì giữ cái nào: `outputDone` thắng — đầu ra xong rồi đóng màn xem
    /// sau 5 s vẫn là thời điểm tốt, và `outputDone` không cần dwell.
    func merged(with newer: ReviewMoment) -> ReviewMoment {
        if self == .outputDone || newer == .outputDone { return .outputDone }
        return newer
    }
}

/// Bực mình + tín hiệu giá trị trong phiên app hiện tại. State TRONG BỘ NHỚ, không bền — reset
/// khi app active. Cố ý khác `ReviewPromptState`: đây là trạng thái nhất thời của một phiên.
struct SessionFriction: Equatable {
    var taskFailed = false
    var restoreFailed = false
    /// Lần gần nhất user đóng paywall hoặc làm một việc huỷ/làm lại — chỉ chặn trong
    /// `ReviewTuning.recentFrictionMinutes`, không chặn cả phiên (chặn cả phiên ⇒ user
    /// free gặp paywall là mất cả lần mở app).
    var lastNegativeAt: Date?
    /// Phiên này đã có hành động giá trị (xem `ReviewSignals.noteValueAction`).
    var hadValueAction = false
    /// Số mục hoàn tất trong phiên (xem `ReviewSignals.noteItemCompleted`). Đủ
    /// `ReviewTuning.completionsForValueSignal` mới tính là tín hiệu giá trị — mục đầu có
    /// thể chỉ là làm thử, làm tiếp sau khi xem kết quả mới cho thấy kết quả dùng được.
    var completedCount = 0
}

enum SkipReason: String, Equatable {
    case dwellTooShort = "dwell_too_short"
    case noValueSignal = "no_value_signal"
    case sessionFriction = "session_friction"
    case recentFriction = "recent_friction"
    case recentFeedback = "recent_feedback"
    case declinedTwice = "declined_twice"
    case yearlyCap = "yearly_cap"
    case askedRecently = "asked_recently"
    case noQuietMoment = "no_quiet_moment"
    case internalBuild = "internal_build"
}

enum ReviewDecision: Equatable {
    case ask
    case skip(SkipReason)
}

/// 9 ngưỡng của luật mời đánh giá. Mặc định là bộ số đã chạy ở app nguồn; app đổi bằng cách truyền
/// `ReviewTuning(...)` vào `ReviewPrompter`.
struct ReviewTuning: Equatable {
    var minDwellSeconds = 15
    /// Số mục hoàn tất trong phiên để tính là tín hiệu giá trị.
    var completionsForValueSignal = 2
    var recentFrictionMinutes = 5
    var feedbackCooldownDays = 7
    var maxAsksPerYear = 3
    var daysAfterRate = 90
    var daysAfterLater = 30
    var declinesBeforePause = 2
    var declinePauseDays = 180
}

/// Toàn bộ luật mời đánh giá, thuần và không phụ thuộc gì. Trả cả LÝ DO bỏ qua để test khẳng
/// định đúng nhánh — không chỉ khẳng định "không hỏi", vì một policy luôn im lặng cũng thoả
/// được điều đó.
///
/// Luật quyết định khi nào hiện hộp hỏi TRƯỚC của app ("Rate <tên app>?"); hộp hệ thống chỉ bật
/// sau khi user bấm Rate. Nhờ vậy "Not Now" không tiêu quota 3 lần/365 ngày của iOS.
enum ReviewPromptPolicy {

    static func decide(moment: ReviewMoment,
                       state: ReviewPromptState,
                       friction: SessionFriction,
                       isInternalBuild: Bool,
                       tuning: ReviewTuning = ReviewTuning(),
                       now: Date) -> ReviewDecision {

        if isInternalBuild { return .skip(.internalBuild) }

        var reopened = false
        if case let .contentClosed(dwell, r) = moment {
            if dwell < tuning.minDwellSeconds { return .skip(.dwellTooShort) }
            reopened = r
        }

        // Đầu ra xong tự nó là hành động giá trị.
        let coGiaTri = moment == .outputDone || friction.hadValueAction || reopened
            || friction.completedCount >= tuning.completionsForValueSignal
        guard coGiaTri else { return .skip(.noValueSignal) }

        if friction.taskFailed || friction.restoreFailed { return .skip(.sessionFriction) }

        if let neg = friction.lastNegativeAt,
           now.timeIntervalSince(neg) < Double(tuning.recentFrictionMinutes) * 60 {
            return .skip(.recentFriction)
        }

        if let fb = state.lastFeedbackSentDate,
           ngay(from: fb, to: now) < Double(tuning.feedbackCooldownDays) {
            return .skip(.recentFeedback)
        }

        if let lan = state.lastAskedDate {
            let qua = ngay(from: lan, to: now)
            if state.consecutiveDeclines >= tuning.declinesBeforePause, qua < Double(tuning.declinePauseDays) {
                return .skip(.declinedTwice)
            }
            if state.askDates.filter({ ngay(from: $0, to: now) < 365 }).count >= tuning.maxAsksPerYear {
                return .skip(.yearlyCap)
            }
            // Đã hiện hộp nhưng chưa trả lời (app bị tắt giữa chừng) ⇒ coi như "Not Now".
            let cho = state.lastAnswer == .rate ? tuning.daysAfterRate : tuning.daysAfterLater
            if qua < Double(cho) { return .skip(.askedRecently) }
        }

        return .ask
    }

    private static func ngay(from a: Date, to b: Date) -> Double {
        b.timeIntervalSince(a) / 86400
    }
}
