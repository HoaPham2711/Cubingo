import Foundation

/// Tín hiệu cho `ReviewPrompter` từ những chỗ KHÔNG cầm prompter (các màn sâu trong app) — đi qua
/// `NotificationCenter` để khỏi luồn prompter qua cả chục view.
enum ReviewSignals {
    static let valueAction = Notification.Name("ReviewSignals.valueAction")
    static let negativeAction = Notification.Name("ReviewSignals.negativeAction")
    static let itemCompleted = Notification.Name("ReviewSignals.itemCompleted")

    /// User vừa làm một việc chứng tỏ app có ích với họ (lưu, chia sẻ, đặt một thiết lập có chủ đích…).
    /// App quyết định hành động nào đáng kể.
    static func noteValueAction(center: NotificationCenter = .default) {
        center.post(name: valueAction, object: nil)
    }

    /// Một mục vừa hoàn tất. Mỗi mục báo đúng MỘT lần — policy đếm số mục, không phải số lần báo.
    static func noteItemCompleted(center: NotificationCenter = .default) {
        center.post(name: itemCompleted, object: nil)
    }

    /// User vừa làm một việc huỷ/làm lại (xoá, bắt đầu lại…) — không phải lúc xin sao.
    static func noteNegativeAction(center: NotificationCenter = .default) {
        center.post(name: negativeAction, object: nil)
    }
}

/// Cầu nối giữa `ReviewPromptPolicy` (thuần) và thế giới thật. Giữ mỏng có chủ ý: mọi luật nằm
/// ở policy, đây chỉ lo bộ đếm bền (`ReviewPromptState`) và trạng thái trong phiên
/// (`SessionFriction`).
///
/// `@MainActor`: policy chỉ quyết định, còn `pendingAsk` phải đổi trên main thread để SwiftUI
/// (`reviewPromptHost`) thấy được và hiện hộp hỏi — prompter không tự đụng UI/StoreKit, nhờ đó test
/// được mà không dựng SwiftUI environment.
@MainActor
final class ReviewPrompter: ObservableObject {

    /// `reviewPromptHost` quan sát cái này để hiện hộp "Rate <tên app>?". Mang moment để log `source`.
    @Published var pendingAsk: ReviewMoment?

    private let defaults: UserDefaults
    private let tuning: ReviewTuning
    /// Đọc MỘT LẦN lúc khởi tạo, không đọc lại mỗi lần `shouldAsk` — cờ build không đổi trong
    /// đời sống app. Mặc định lấy từ `InternalBuild.isEnabled`; test bơm `false` để không bị luật "build nội
    /// bộ không bao giờ tự hỏi" chặn — vì `ReviewPrompterTests` build ở config `Debug`, mà
    /// `Debug` CŨNG có cờ `INTERNAL`.
    private let isInternalBuild: Bool
    private let clock: () -> Date
    private var friction = SessionFriction()
    private var observers: [NSObjectProtocol] = []

    init(defaults: UserDefaults = .standard,
         notificationCenter: NotificationCenter = .default,
         tuning: ReviewTuning = ReviewTuning(),
         clock: @escaping () -> Date = Date.init,
         isInternalBuild: Bool = InternalBuild.isEnabled) {
        self.defaults = defaults
        self.tuning = tuning
        self.isInternalBuild = isInternalBuild
        self.clock = clock
        // `queue: .main` + `assumeIsolated`: post có thể từ nền (vd. việc xong trên hàng đợi
        // writer), handler luôn chạy trên main.
        observers.append(notificationCenter.addObserver(forName: ReviewSignals.valueAction,
                                                        object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.friction.hadValueAction = true }
        })
        observers.append(notificationCenter.addObserver(forName: ReviewSignals.negativeAction,
                                                        object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.friction.lastNegativeAt = self?.clock() }
        })
        observers.append(notificationCenter.addObserver(forName: ReviewSignals.itemCompleted,
                                                        object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.friction.completedCount += 1 }
        })
    }

    /// Gọi ở `scenePhase == .active`: bực mình / tín hiệu giá trị là của một phiên.
    func noteAppBecameActive() {
        friction = SessionFriction()
    }

    func noteTaskFailed()       { friction.taskFailed = true }
    func noteRestoreFailed()    { friction.restoreFailed = true }
    func notePaywallDismissed() { friction.lastNegativeAt = clock() }

    func noteFeedbackSent() {
        var s = ReviewPromptState.load(from: defaults)
        s.lastFeedbackSentDate = clock()
        s.save(to: defaults, now: clock())
    }

    /// Ghi lần mở một mục; trả `true` nếu mục này ĐÃ từng mở trước đó.
    func noteItemOpened(id: String) -> Bool {
        var s = ReviewPromptState.load(from: defaults)
        let daMo = s.openedItemIDs.contains(id)
        s.openedItemIDs.removeAll { $0 == id }
        s.openedItemIDs.append(id)
        s.save(to: defaults, now: clock())
        return daMo
    }

    /// Quyết định **và đồng thời ghi lại lần hỏi** khi `.ask`. Gộp hai việc là cố ý: tách ra
    /// thì call site nào quên ghi sẽ khiến mọi lần sau đều hỏi lại.
    func decide(_ moment: ReviewMoment) -> ReviewDecision {
        let now = clock()
        var s = ReviewPromptState.load(from: defaults)
        let d = ReviewPromptPolicy.decide(moment: moment, state: s, friction: friction,
                                          isInternalBuild: apDungLuatInternal, tuning: tuning, now: now)
        #if INTERNAL
        debugLastDecision = (moment, d, now)
        #endif
        guard d == .ask else { return d }
        s.askDates.append(now)
        // Chưa trả lời ⇒ nil (policy coi như "Not Now") — không để câu trả lời của lần TRƯỚC
        // quyết định khoảng chờ của lần này nếu app bị tắt khi hộp đang mở.
        s.lastAnswer = nil
        s.save(to: defaults, now: now)
        return d
    }

    /// Luật "build nội bộ không tự hỏi" có áp không — công tắc debug tắt được để thử như user Store.
    private var apDungLuatInternal: Bool {
        #if INTERNAL
        return isInternalBuild && !defaults.bool(forKey: Self.simulateStoreUserKey)
        #else
        return isInternalBuild
        #endif
    }

    func noteAnswer(_ a: ReviewAnswer) {
        var s = ReviewPromptState.load(from: defaults)
        s.lastAnswer = a
        s.consecutiveDeclines = a == .rate ? 0 : s.consecutiveDeclines + 1
        s.save(to: defaults, now: clock())
    }

    #if INTERNAL
    // MARK: - Debug: thử luật thật trên build nội bộ.

    /// Bật ⇒ build Internal chạy luật y như bản App Store (bỏ `.skip(.internalBuild)`). Key KHÔNG mang
    /// tiền tố `review.` để "Reset như user mới" không xoá luôn công tắc này.
    static let simulateStoreUserKey = "reviewDebug.simulateStoreUser"

    /// Lần quyết định gần nhất — bảng debug hiện để biết moment vừa rồi bị chặn vì đâu.
    private(set) var debugLastDecision: (moment: ReviewMoment, decision: ReviewDecision, at: Date)?

    var debugSnapshot: (state: ReviewPromptState, friction: SessionFriction) {
        (ReviewPromptState.load(from: defaults), friction)
    }

    /// Đưa về trạng thái user mới chưa từng được hỏi: xoá MỌI key `review.` và trạng thái trong phiên.
    func debugResetAsNewUser() {
        for k in defaults.dictionaryRepresentation().keys where k.hasPrefix(ReviewPromptState.defaultsPrefix) {
            defaults.removeObject(forKey: k)
        }
        friction = SessionFriction()
        debugLastDecision = nil
        objectWillChange.send()
    }
    #endif
}
