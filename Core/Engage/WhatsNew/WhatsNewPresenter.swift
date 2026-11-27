import Foundation

/// Quyết định KHI NÀO sheet What's New hiện và ghi trạng thái đúng chỗ. Sở hữu ở cấp App (dựng bằng
/// `WhatsNewHost.make`) để lối nhận link ngoài thấy được sheet đang mở; truyền TƯỜNG MINH xuống view gốc (không qua
/// environment). View gốc gọi `evaluate` khi đủ điều kiện, present sheet theo `presentation`, báo
/// `sheetDidAppear`/`sheetDidDismiss` (modifier `.whatsNewSheet` làm sẵn phần present).
///
/// Luật ghi `lastSeen` — sai chỗ là sheet hiện mỗi lần mở app hoặc không bao giờ hiện:
/// - Cài mới: `onboardingFinished()` ghi `lastSeen = current` (gọi TRƯỚC khi app bật cờ "đã xem onboarding").
/// - `.none(markSeen: true)` ⇒ ghi ngay. `.show` ⇒ CHỈ ghi trong `sheetDidAppear()`. Bị chặn ⇒ không ghi.
/// - Không bao giờ ghi lùi (`WhatsNewState.recordSeen`).
///
/// `isEnabled == false` (host unit test, route `-uiPreview` không thuộc `whatsNew*`, bản cài hỏng) ⇒ mọi hàm không làm
/// gì, không đụng ledger/state — presenter tắt chỉ giữ tham chiếu, không đọc/ghi UserDefaults.
@MainActor
final class WhatsNewPresenter: ObservableObject {

    /// Một lần hiện sheet. `id` mới mỗi lần để `.sheet(item:)` dựng lại.
    struct Presentation: Identifiable {
        let id = UUID()
        let cards: [WhatsNewCard]
        let moreCount: Int
        /// `nil` ⇒ khách cũ chưa có `lastSeen` ("Recent updates").
        let from: AppVersion?
        /// Lần hiện mở thủ công (công cụ của build INTERNAL) ⇒ không ghi trạng thái, không telemetry.
        var isDebug = false

        /// Param `from_version` của telemetry: `"unknown"` khi khách cũ chưa có mốc.
        var fromParam: String { from?.description ?? WhatsNewState.unknownFrom }
    }

    /// Chạy việc seed ledger (đọc dấu vết trong lock) — mặc định ở queue nền; test inject bản chạy đồng bộ.
    typealias SeedRunner = (@escaping () -> Void) async -> Void
    /// Hẹn `work` chạy trên main sau `delay` giây — mặc định đồng hồ thật; test inject bản tự bắn (không sleep).
    typealias WatchdogScheduler = (_ delay: TimeInterval, _ work: @escaping @MainActor () -> Void) -> Void

    /// Đặt `presentation` mà sau ngần này giây SwiftUI vẫn chưa present (nội dung sheet chưa `onAppear`) ⇒ huỷ.
    /// Sheet bình thường `onAppear` trong < 0,5 s; modal khác chen vào cùng lúc thì SwiftUI bỏ qua `.sheet(item:)` mà
    /// item vẫn khác nil ⇒ cổng "đang có cover" của app kẹt true: chặn mọi `evaluate` sau (và mọi luồng khác của app
    /// chờ màn hình rảnh).
    static let watchdogDelay: TimeInterval = 2

    /// Không `private(set)`: view gốc gắn `$presenter.presentation` vào `.sheet(item:)`, SwiftUI đặt về nil khi khách
    /// đóng. Mỗi lần đặt một lần hiện MỚI (kể cả lần hiện thủ công) ⇒ hẹn watchdog cho đúng lần đó.
    @Published var presentation: Presentation? {
        didSet {
            if let shown = presentation, shown.id != oldValue?.id { armWatchdog(for: shown.id) }
        }
    }

    let isEnabled: Bool

    /// Catalog + bản đang cài — danh sách đầy đủ (`WhatsNewListView`) đọc cùng nguồn với selector.
    let cards: [WhatsNewCard]
    let current: AppVersion
    /// = cờ "đã xem onboarding" đọc MỘT lần lúc khởi tạo: onboarding vừa xong trong tiến trình này vẫn là cài mới.
    private let isExistingUser: Bool
    private let ledger: FeatureUsageLedger
    private let state: WhatsNewState
    private let probe: UsageProbe
    private let runSeed: SeedRunner
    private let scheduleWatchdog: WatchdogScheduler

    private var didSeed = false
    private var isEvaluating = false
    /// Sheet đã `onAppear` và chưa `onDismiss` — chỉ lúc này mới chắc SwiftUI sẽ gọi `onDismiss` để chạy link giữ lại.
    private var sheetVisible = false
    /// Việc bên ngoài (mở link ngoài) chờ sheet đóng hẳn.
    private var pendingExternal: (() -> Void)?
    /// Nút thẻ khách đã bấm — chạy khi sheet đóng hẳn (`sheetDidDismiss` trả về), trừ khi link ngoài thắng.
    private var chosenAction: WhatsNewResolvedAction?
    /// App đã mở một link vào app trong lượt dùng này (từ lúc vào foreground) — chặn What's New hiện đè lên màn của
    /// link, kể cả khi app đã mở xong màn đó (link của app thường xoá ngay sau khi giao). Gỡ khi app vào nền.
    private(set) var appLinkOpenedThisActivation = false

    init(cards: [WhatsNewCard], current: AppVersion, hasSeenOnboarding: Bool, ledger: FeatureUsageLedger,
         state: WhatsNewState, probe: UsageProbe, isEnabled: Bool,
         runSeed: @escaping SeedRunner = WhatsNewPresenter.seedInBackground,
         scheduleWatchdog: @escaping WatchdogScheduler = WhatsNewPresenter.scheduleOnMain) {
        self.cards = cards
        self.current = current
        self.isExistingUser = hasSeenOnboarding
        self.ledger = ledger
        self.state = state
        self.probe = probe
        self.isEnabled = isEnabled
        self.runSeed = runSeed
        self.scheduleWatchdog = scheduleWatchdog
    }

    /// Tắt trong host unit test; trên Simulator tắt khi đang chạy route `-uiPreview` không thuộc `whatsNew*` (route
    /// chụp màn thường ép trạng thái "đã xem onboarding" ⇒ không chặn thì sheet đè mọi ảnh chụp).
    /// `previewRoute` = `AppEnvironment.uiPreviewRoute` (device luôn `nil`).
    nonisolated static func isEnabled(isUnitTestHost: Bool, previewRoute: String?) -> Bool {
        if isUnitTestHost { return false }
        guard let route = previewRoute else { return true }
        return route.hasPrefix("whatsNew")
    }

    /// Mặc định: seed ở queue nền — `seedFromDiskIfNeeded` có thể đọc file trong lock của ledger, không được chặn main.
    nonisolated static func seedInBackground(_ work: @escaping () -> Void) async {
        await withCheckedContinuation { (done: CheckedContinuation<Void, Never>) in
            DispatchQueue.global(qos: .utility).async {
                work()
                done.resume()
            }
        }
    }

    /// Mặc định của `WatchdogScheduler`: ngủ `delay` rồi chạy trên main.
    nonisolated static func scheduleOnMain(_ delay: TimeInterval, _ work: @escaping @MainActor () -> Void) {
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
            work()
        }
    }

    private func armWatchdog(for id: UUID) {
        guard isEnabled else { return }
        scheduleWatchdog(Self.watchdogDelay) { [weak self] in self?.watchdogFired(for: id) }
    }

    /// Lần hiện `id` vẫn đang đặt mà sheet chưa từng `onAppear` ⇒ SwiftUI đã không present nó. Huỷ, không ghi
    /// lastSeen (chưa ai thấy) — lần `evaluate` sau thử lại.
    private func watchdogFired(for id: UUID) {
        guard presentation?.id == id, !sheetVisible else { return }
        presentation = nil
    }

    /// Đánh giá có hiện sheet không. Lần đầu: seed ledger từ dấu vết trên máy (ngoài main) rồi mới chọn thẻ.
    /// `canPresent` đọc SAU khi seed xong (điều kiện có thể đã đổi trong lúc chờ). `resolve` = đích nút thẻ của app.
    func evaluate(resolve: WhatsNewResolver, canPresent: @autoclosure () -> Bool) async {
        guard isEnabled else { return }
        guard presentation == nil, !isEvaluating else { return }
        isEvaluating = true
        defer { isEvaluating = false }

        if !didSeed {
            let ledger = self.ledger, probe = self.probe
            await runSeed { ledger.seedFromDiskIfNeeded(probe: probe) }
            didSeed = true
        }

        let outcome = WhatsNewSelector.select(lastSeen: state.lastSeen, current: current,
                                              isExistingUser: isExistingUser, cards: cards,
                                              usedCards: ledger.usedCards, resolve: resolve)
        switch outcome {
        case .none(let markSeen):
            if markSeen { state.recordSeen(current) }
        case .show(let shown, let moreCount, let from):
            // KHÔNG ghi lastSeen ở đây: chỉ khi sheet thật sự hiện (`sheetDidAppear`).
            guard canPresent() else { return }
            presentation = Presentation(cards: shown, moreCount: moreCount, from: from)
        }
    }

    /// Có link ngoài đang chờ sheet đóng hẳn — một vế của `canPresent` (`WhatsNewPresentGate`), và để app bỏ hành
    /// động thẻ khi link thắng.
    var hasPendingExternal: Bool { pendingExternal != nil }

    /// `from` của lần hiện sheet gần nhất (nhãn "New for you" của danh sách). Presenter tắt ⇒ `nil`, không đọc
    /// UserDefaults.
    var lastShownFrom: String? { isEnabled ? state.lastShownFrom : nil }

    /// `onAppear` của NỘI DUNG sheet — lúc này mới coi là khách đã xem. Gọi lặp (onAppear bắn lại) ⇒ chỉ lần đầu
    /// của mỗi lần hiện được tính (telemetry không đếm trùng).
    func sheetDidAppear() {
        guard isEnabled, let shown = presentation, !sheetVisible else { return }
        sheetVisible = true
        guard !shown.isDebug else { return }
        state.recordSeen(current)
        state.recordShown(from: shown.from)
        Track.log(.whatsNewShown(cards: shown.cards.map(\.id).joined(separator: ","), more: shown.moreCount,
                                 fromVersion: shown.fromParam, toVersion: current.description))
    }

    /// Khách bấm nút thẻ trên sheet (hoặc danh sách đẩy từ sheet): ghi `whats_new_cta` (trừ lần hiện thủ công), nhớ
    /// hành động, đóng sheet. Hành động KHÔNG chạy ở đây — chạy khi sheet đóng hẳn (`sheetDidDismiss` trả về) để màn
    /// đích không present chồng lên sheet đang trượt xuống.
    func chooseAction(_ card: WhatsNewCard, _ action: WhatsNewResolvedAction, surface: WhatsNewSurface,
                      in shown: Presentation) {
        if !shown.isDebug {
            Track.log(.whatsNewCta(card: card.id, fromVersion: shown.fromParam, toVersion: current.description,
                                   surface: surface.rawValue))
        }
        chosenAction = action
        presentation = nil
    }

    /// Nút trên danh sách mở từ Settings › What's new — không thuộc lần hiện sheet nào ⇒ `from_version` bỏ trống,
    /// surface `settings`. Không có sheet để đợi đóng ⇒ chạy ngay.
    func runFromSettingsList(_ card: WhatsNewCard, _ action: WhatsNewResolvedAction,
                             run: (WhatsNewResolvedAction) -> Void) {
        Track.log(.whatsNewCta(card: card.id, fromVersion: nil, toVersion: current.description,
                               surface: WhatsNewSurface.settings.rawValue))
        run(action)
    }

    /// `onDismiss` của sheet. Dọn trạng thái, chạy việc bên ngoài đã giữ (mở link ngoài) — đúng một lần — rồi trả nút
    /// thẻ đã bấm để app giao `WhatsNewRunner`. Link ngoài tới lúc sheet mở THẮNG nút thẻ (màn của link là cover cấp
    /// App) ⇒ trả `nil`.
    @discardableResult
    func sheetDidDismiss() -> WhatsNewResolvedAction? {
        sheetVisible = false
        presentation = nil
        let work = pendingExternal
        let chosen = chosenAction
        pendingExternal = nil
        chosenAction = nil
        if let work {
            work()
            return nil
        }
        return chosen
    }

    /// Cổng present dựng từ trạng thái của view gốc + vế của presenter (link đang chờ sheet cũ đóng).
    /// `extraBlockers` = mọi lý do riêng của app chưa được present (alert riêng đang bật, luồng nhập dở…).
    func presentGate(sceneActive: Bool, coverShown: Bool, modalPresented: Bool, extraBlockers: Bool,
                     appLinkPending: Bool) -> WhatsNewPresentGate {
        WhatsNewPresentGate(sceneActive: sceneActive, coverShown: coverShown, modalPresented: modalPresented,
                            extraBlockers: extraBlockers, appLinkPending: appLinkPending || appLinkOpenedThisActivation,
                            presenterLinkPending: hasPendingExternal)
    }

    /// App nhận một link vào app (đã kiểm host) — gọi lúc link TỚI, trước khi giao. Từ đó tới khi app vào nền, cổng
    /// present đóng: lượt `evaluate` đang chờ app active (≤ 3 s + 0,6 s) sẽ không hiện sheet đè lên màn của link.
    func noteAppLinkOpened() {
        appLinkOpenedThisActivation = true
    }

    /// App vào nền — lượt dùng kết thúc; lần active sau What's New lại được xét bình thường.
    func sceneDidEnterBackground() {
        appLinkOpenedThisActivation = false
    }

    /// Link ngoài tới. Sheet còn trên màn (từ `sheetDidAppear` tới `sheetDidDismiss`, KỂ CẢ lúc đang trượt xuống sau
    /// khi `presentation` đã về nil) ⇒ giữ `apply`, đóng sheet, trả `true` — `apply` chạy ở `sheetDidDismiss`; nhiều
    /// link tới liền nhau ⇒ link MỚI NHẤT thắng. Không có sheet ⇒ trả `false`, presenter KHÔNG gọi `apply`: người gọi
    /// tự mở link. Sheet đã đặt nhưng chưa kịp hiện ⇒ huỷ hiện (không ghi lastSeen) và trả `false` — SwiftUI có thể
    /// không gọi `onDismiss` cho sheet chưa từng hiện, giữ link lại là mất link.
    func routeIncomingLink(_ apply: @escaping () -> Void) -> Bool {
        guard isEnabled else { return false }
        if presentation != nil { presentation = nil }
        guard sheetVisible else { return false }
        pendingExternal = apply
        return true
    }

    /// Onboarding xong (cài mới) — gọi TRƯỚC khi app bật cờ "đã xem onboarding": cài mới đã có onboarding giới thiệu
    /// app, không hiện What's New.
    func onboardingFinished() {
        guard isEnabled else { return }
        state.recordSeen(current)
    }
}

/// Điều kiện được present sheet — hàm thuần để test từng vế; view gốc đọc giá trị thật mỗi lần kiểm (trước khi chờ
/// và ngay trước khi present, qua `@autoclosure` của `evaluate`).
struct WhatsNewPresentGate: Equatable {
    /// App đang active. Hỏi UIKit (`UIApplication.shared.applicationState`), KHÔNG đọc `scenePhase` trong `Task`:
    /// bản sao view mà `.task` giữ có `@Environment` cũ (lúc launch còn `.inactive`) ⇒ cổng đóng mãi.
    var sceneActive: Bool
    /// App đang có cover/sheet của chính nó (kể cả sheet What's New).
    var coverShown: Bool
    /// `ModalPresentationProbe.isModalPresented()` — modal UIKit (`UIActivityViewController`, preview hệ thống…) mà SwiftUI không biết.
    var modalPresented: Bool
    /// Lý do riêng của app chưa được present (alert riêng, luồng dở…). `true` ⇒ chặn.
    var extraBlockers: Bool
    /// App đã nhận link ngoài, màn của link sắp/đang present.
    var appLinkPending: Bool
    /// `WhatsNewPresenter.hasPendingExternal` — link đang chờ sheet cũ đóng.
    var presenterLinkPending: Bool

    var allowsPresent: Bool {
        sceneActive && !coverShown && !modalPresented && !extraBlockers && !appLinkPending && !presenterLinkPending
    }
}
