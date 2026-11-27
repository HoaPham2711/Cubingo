import UIKit

/// Bộ canh "màn yên" của lời mời đánh giá: gài một `ReviewMoment`, đợi tới khi app active và cửa sổ chính
/// không còn modal nào, rồi mới hỏi `ReviewPrompter.decide`.
///
/// Vì sao không hỏi ngay: hỏi lúc có modal đè (bảng chia sẻ hệ thống, paywall, màn toàn cảnh…) thì alert present từ view gốc
/// bị SwiftUI nuốt, và bản đầu tiên kiểm modal đúng một lần rồi BỎ LƯỢT nên lời mời gần như không bao giờ bắn. Gài
/// moment rồi poll là cách duy nhất không bỏ lượt.
///
/// Moment chờ chồng nhau được gộp (`ReviewMoment.merged`). Quá `timeout` mà màn hình vẫn không yên ⇒ bỏ lượt và
/// ghi `review_skip(no_quiet_moment)`.
///
/// `isQuiet` và `present` do app cấp (UIKit tách khỏi logic để test được): production truyền
/// `ReviewScheduler.liveIsQuiet` cho `isQuiet`. `present` được gọi NGAY SAU khi `pendingAsk` được gán (hộp hỏi do
/// `reviewPromptHost` quan sát `pendingAsk` mà hiện) — chỗ để app thêm hiệu ứng phụ, không phải chỗ hiện hộp.
@MainActor
final class ReviewScheduler {
    /// Chu kỳ poll + hạn chờ của bộ canh yên.
    static let pollInterval: TimeInterval = 0.5
    static let timeout: TimeInterval = 10 * 60

    /// Thay cho `Timer`: nhận chu kỳ và việc phải làm mỗi nhịp, trả về hàm HUỶ nhịp. Test bơm bộ gõ nhịp tay.
    typealias TickDriver = (_ interval: TimeInterval, _ tick: @escaping @MainActor () -> Void) -> () -> Void

    private let prompter: ReviewPrompter
    private let isQuiet: () -> Bool
    private let present: () -> Void
    private let now: () -> Date
    private let schedule: TickDriver

    /// Moment mời đánh giá đang chờ màn hình "yên".
    private var pendingMoment: ReviewMoment?
    private var cancelTicks: (() -> Void)?
    private var armedAt: Date?
    /// `bypassPolicy` chỉ cho nút thử của build INTERNAL: bỏ qua policy, hiện hộp thẳng.
    private var bypassPolicy = false

    init(prompter: ReviewPrompter,
         isQuiet: @escaping () -> Bool,
         present: @escaping () -> Void,
         now: @escaping () -> Date = Date.init,
         schedule: @escaping TickDriver = ReviewScheduler.liveSchedule) {
        self.prompter = prompter
        self.isQuiet = isQuiet
        self.present = present
        self.now = now
        self.schedule = schedule
    }

    /// App đang active VÀ cửa sổ chính không present modal nào.
    static func liveIsQuiet() -> Bool {
        UIApplication.shared.applicationState == .active && !ModalPresentationProbe.isModalPresented()
    }

    nonisolated static func liveSchedule(_ interval: TimeInterval,
                                         _ tick: @escaping @MainActor () -> Void) -> () -> Void {
        let timer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { _ in
            MainActor.assumeIsolated { tick() }
        }
        return { timer.invalidate() }
    }

    /// Gài một moment: đợi tới khi yên rồi mới hỏi policy.
    func arm(_ moment: ReviewMoment, bypassPolicy: Bool = false) {
        pendingMoment = pendingMoment?.merged(with: moment) ?? moment
        self.bypassPolicy = self.bypassPolicy || bypassPolicy
        armedAt = now()
        guard cancelTicks == nil else { return }
        cancelTicks = schedule(Self.pollInterval) { [weak self] in self?.quietTick() }
    }

    private func quietTick() {
        guard let moment = pendingMoment else { stop(); return }
        if let t = armedAt, now().timeIntervalSince(t) > Self.timeout {
            stop()
            Track.log(.reviewSkip(reason: SkipReason.noQuietMoment.rawValue))
            return
        }
        // Đợi không còn modal UIKit nào đè: alert present từ view gốc khi có modal đè sẽ bị nuốt.
        guard isQuiet() else { return }
        let bypass = bypassPolicy
        stop()
        if bypass { prompter.pendingAsk = moment; present(); return }
        switch prompter.decide(moment) {
        case .ask:
            // Chỉ GÁN khi hỏi — gán vô cớ vẫn bắn `@Published` và re-render toàn app.
            prompter.pendingAsk = moment
            present()
        case .skip(.internalBuild):
            break   // build nội bộ: không làm bẩn số liệu
        case .skip(let r):
            Track.log(.reviewSkip(reason: r.rawValue))
        }
    }

    private func stop() {
        cancelTicks?()
        cancelTicks = nil
        pendingMoment = nil
        bypassPolicy = false
        armedAt = nil
    }
}
