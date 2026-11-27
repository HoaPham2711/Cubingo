import Combine
import XCTest
@testable import AppHost

/// Khi nào sheet What's New hiện và trạng thái ghi đúng chỗ (cài mới, khách cũ chưa có mốc, watchdog, link ngoài tới
/// lúc sheet mở, seed). Thẻ dựng tay, UserDefaults suite riêng, ledger + probe inject — KHÔNG dùng ledger của app
/// (nó ghi `UserDefaults.standard` của host).
@MainActor
final class WhatsNewPresenterTests: XCTestCase {

    private var suiteName = ""
    private var defaults: UserDefaults!

    override func setUp() {
        super.setUp()
        suiteName = "WhatsNewPresenterTests.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)!
        watchdogs = []
    }

    override func tearDown() {
        Track.reset()
        defaults.removePersistentDomain(forName: suiteName)
        defaults = nil
        super.tearDown()
    }

    // MARK: - Dựng dữ liệu

    nonisolated private static func v(_ s: String) -> AppVersion { AppVersion(s)! }

    /// Resolver của test resolve mọi khoá ⇒ thẻ luôn đủ điều kiện nếu trong khoảng bản.
    nonisolated private static func card(_ id: String, _ version: CardVersion = .unreleased, priority: Int = 5,
                             usedOnDisk: @escaping (UsageProbe) -> Bool = { _ in false }) -> WhatsNewCard {
        WhatsNewCard(id: id, version: version, priority: priority, systemImage: "star", title: id, body: id, ctaTitle: id,
                     action: WhatsNewAction(key: "go"), usedOnDisk: usedOnDisk)
    }

    /// Resolver giả: mọi khoá đều có đích.
    private let resolve: WhatsNewResolver = { WhatsNewResolvedAction(key: $0.key) }

    nonisolated private static func act(_ key: String) -> WhatsNewResolvedAction { WhatsNewResolvedAction(key: key) }

    nonisolated private static var noTraces: ClosureUsageProbe { ClosureUsageProbe([:]) }

    /// Số lần presenter giao việc seed cho executor (executor test chạy đồng bộ ⇒ tất định).
    private var seedRuns = 0

    private func state() -> WhatsNewState { WhatsNewState(defaults: defaults) }

    private func presenter(cards: [WhatsNewCard] = [card("a")], current: String = "1.15.0",
                           hasSeenOnboarding: Bool = true, isEnabled: Bool = true,
                           probe: UsageProbe = WhatsNewPresenterTests.noTraces,
                           runSeed: WhatsNewPresenter.SeedRunner? = nil) -> WhatsNewPresenter {
        WhatsNewPresenter(cards: cards, current: Self.v(current), hasSeenOnboarding: hasSeenOnboarding,
                          ledger: FeatureUsageLedger(cards: cards, defaults: defaults), state: state(),
                          probe: probe, isEnabled: isEnabled,
                          runSeed: runSeed ?? { [unowned self] work in self.seedRuns += 1; work() },
                          scheduleWatchdog: { [unowned self] delay, work in self.watchdogs.append((delay, work)) })
    }

    /// Watchdog presenter đã hẹn (delay + việc) — test tự "bắn" thay cho đồng hồ thật (không sleep).
    private var watchdogs: [(delay: TimeInterval, work: @MainActor () -> Void)] = []

    /// Bắn watchdog thứ `i`; chưa hẹn ⇒ test đỏ (không crash index — crash làm mất kết quả cả class).
    private func fireWatchdog(_ i: Int, file: StaticString = #filePath, line: UInt = #line) {
        guard watchdogs.indices.contains(i) else {
            return XCTFail("watchdog #\(i) chưa được hẹn", file: file, line: line)
        }
        watchdogs[i].work()
    }

    // MARK: - Cài mới (đã có onboarding ⇒ không hiện)

    func test_onboardingFinished_writesLastSeen_andRebuiltPresenterDoesNotShow() async {
        let fresh = presenter(hasSeenOnboarding: false)
        fresh.onboardingFinished()
        XCTAssertEqual(state().lastSeen, Self.v("1.15.0"))

        // Lần mở sau: `hasSeenOnboarding` đã true ⇒ khách "cũ" nhưng lastSeen == current ⇒ không hiện.
        let rebuilt = presenter(hasSeenOnboarding: true)
        await rebuilt.evaluate(resolve: resolve, canPresent: true)
        XCTAssertNil(rebuilt.presentation)
        XCTAssertEqual(state().lastSeen, Self.v("1.15.0"))
    }

    func test_freshInstall_sameProcess_afterTour_doesNotShow() async {
        // Presenter cấp App sống qua tour: isExistingUser đọc một lần = false, lastSeen vừa ghi = current.
        let p = presenter(hasSeenOnboarding: false)
        p.onboardingFinished()
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertNil(p.presentation)
    }

    // MARK: - .none(markSeen:)

    func test_noneMarkSeen_writesImmediately() async {
        // Khách cũ từ 1.14, không thẻ nào trong (1.14, 1.15] ⇒ .none(markSeen: true) ⇒ ghi ngay.
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter(cards: [Self.card("old", .released("1.13.0"))])
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertNil(p.presentation)
        XCTAssertEqual(state().lastSeen, Self.v("1.15.0"))
    }

    func test_canPresentFalse_noPresentation_lastSeenUnchanged() async {
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        await p.evaluate(resolve: resolve, canPresent: false)
        XCTAssertNil(p.presentation)
        XCTAssertEqual(state().lastSeen, Self.v("1.14.0"))
        XCTAssertNil(state().lastShownFrom)
    }

    func test_show_doesNotWriteLastSeenUntilSheetAppears() async {
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter(cards: [Self.card("a"), Self.card("b"), Self.card("c"), Self.card("d")])
        await p.evaluate(resolve: resolve, canPresent: true)
        let shown = try? XCTUnwrap(p.presentation)
        XCTAssertEqual(shown?.cards.map(\.id), ["a", "b", "c"])
        XCTAssertEqual(shown?.moreCount, 1)
        XCTAssertEqual(shown?.from, Self.v("1.14.0"))
        // Chưa onAppear ⇒ chưa coi là đã xem.
        XCTAssertEqual(state().lastSeen, Self.v("1.14.0"))
        XCTAssertNil(state().lastShownFrom)
    }

    // MARK: - sheetDidAppear

    func test_sheetDidAppear_writesLastSeenAndFrom() async {
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertNotNil(p.presentation)
        p.sheetDidAppear()
        XCTAssertEqual(state().lastSeen, Self.v("1.15.0"))
        XCTAssertEqual(state().lastShownFrom, "1.14.0")
    }

    func test_sheetDidAppear_unknownFrom() async {
        // Khách cũ chưa có lastSeen ⇒ from nil ⇒ "unknown".
        let p = presenter(hasSeenOnboarding: true)
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertNotNil(p.presentation)
        XCTAssertNil(p.presentation?.from)
        p.sheetDidAppear()
        XCTAssertEqual(state().lastSeen, Self.v("1.15.0"))
        XCTAssertEqual(state().lastShownFrom, "unknown")
    }

    func test_afterSheetShown_nextEvaluateDoesNotShowAgain() async {
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        await p.evaluate(resolve: resolve, canPresent: true)
        p.sheetDidAppear()
        p.presentation = nil   // SwiftUI đặt binding về nil khi khách đóng
        p.sheetDidDismiss()
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertNil(p.presentation)
    }

    // MARK: - Link ngoài tới khi sheet đang mở

    func test_routeIncomingLink_whileSheetOpen_defersUntilDismiss() async {
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        await p.evaluate(resolve: resolve, canPresent: true)
        p.sheetDidAppear()

        var applied = 0
        XCTAssertTrue(p.routeIncomingLink { applied += 1 })
        XCTAssertNil(p.presentation, "phải đóng sheet")
        XCTAssertEqual(applied, 0, "chưa được mở link khi sheet còn đang đóng")

        p.sheetDidDismiss()
        XCTAssertEqual(applied, 1)
        p.sheetDidDismiss()   // onDismiss lặp không chạy lại
        XCTAssertEqual(applied, 1)
    }

    func test_routeIncomingLink_whenNoSheet_returnsFalse() async {
        let p = presenter()
        var applied = 0
        XCTAssertFalse(p.routeIncomingLink { applied += 1 })
        XCTAssertEqual(applied, 0, "presenter không tự gọi — người gọi tự mở link")
        p.sheetDidDismiss()
        XCTAssertEqual(applied, 0)
    }

    func test_routeIncomingLink_presentationNotYetAppeared_cancelsAndReturnsFalse() async {
        // presentation đã đặt nhưng sheet chưa kịp onAppear: SwiftUI có thể không gọi onDismiss ⇒ đừng giữ link.
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        await p.evaluate(resolve: resolve, canPresent: true)
        var applied = 0
        XCTAssertFalse(p.routeIncomingLink { applied += 1 })
        XCTAssertNil(p.presentation)
        XCTAssertEqual(state().lastSeen, Self.v("1.14.0"), "bị chặn ⇒ không ghi")
        p.sheetDidDismiss()
        XCTAssertEqual(applied, 0)
    }

    func test_routeIncomingLink_twoLinksWhileSheetUp_lastWins_runsOnceAtDismiss() async {
        // Link 2 tới lúc sheet ĐANG ĐÓNG (presentation đã nil, chưa onDismiss): vẫn phải hoãn, không đặt thẳng.
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        await p.evaluate(resolve: resolve, canPresent: true)
        p.sheetDidAppear()

        var ran: [String] = []
        XCTAssertTrue(p.routeIncomingLink { ran.append("L1") })
        XCTAssertNil(p.presentation)
        XCTAssertTrue(p.routeIncomingLink { ran.append("L2") }, "sheet còn trên màn ⇒ không được đặt link thẳng")
        XCTAssertEqual(ran, [])

        p.sheetDidDismiss()
        XCTAssertEqual(ran, ["L2"], "link mới nhất thắng, chạy đúng một lần")
        p.sheetDidDismiss()
        XCTAssertEqual(ran, ["L2"])
        XCTAssertFalse(p.routeIncomingLink {}, "sheet đã đóng hẳn ⇒ đặt thẳng")
    }

    // MARK: - evaluate: chống chạy chồng + đọc canPresent sau seed

    func test_reentrantEvaluate_seedsOnce_presentsOnce() async {
        state().recordSeen(Self.v("1.14.0"))
        var runs = 0
        var sets = 0
        let cards = [Self.card("a")]
        let p = WhatsNewPresenter(cards: cards, current: Self.v("1.15.0"), hasSeenOnboarding: true,
                                  ledger: FeatureUsageLedger(cards: cards, defaults: defaults), state: state(),
                                  probe: Self.noTraces, isEnabled: true,
                                  runSeed: { work in runs += 1; await Task.yield(); await Task.yield(); work() })
        let sub = p.$presentation.dropFirst().sink { if $0 != nil { sets += 1 } }
        let r = resolve
        async let first: Void = p.evaluate(resolve: r, canPresent: true)
        async let second: Void = p.evaluate(resolve: r, canPresent: true)
        _ = await (first, second)
        sub.cancel()
        XCTAssertEqual(runs, 1, "evaluate chạy chồng ⇒ seed 2 lần")
        XCTAssertEqual(sets, 1, "evaluate chạy chồng ⇒ đặt presentation 2 lần")
    }

    func test_canPresent_readAfterSeed() async {
        state().recordSeen(Self.v("1.14.0"))
        var allowed = true
        let cards = [Self.card("a")]
        let p = WhatsNewPresenter(cards: cards, current: Self.v("1.15.0"), hasSeenOnboarding: true,
                                  ledger: FeatureUsageLedger(cards: cards, defaults: defaults), state: state(),
                                  probe: Self.noTraces, isEnabled: true,
                                  runSeed: { work in work(); allowed = false })
        await p.evaluate(resolve: resolve, canPresent: allowed)
        XCTAssertNil(p.presentation, "điều kiện đổi trong lúc seed ⇒ phải đọc lại sau seed")
        XCTAssertEqual(state().lastSeen, Self.v("1.14.0"))
    }

    /// `evaluate` giao resolver của app cho selector: thẻ bản cũ mà app không có đích bị bỏ, thẻ có đích ở lại.
    func test_evaluate_passesResolverToSelector() async {
        state().recordSeen(Self.v("1.13.0"))
        let missing = WhatsNewCard(id: "missing", version: .released("1.14.0"), priority: 9, systemImage: "star",
                                   title: "m", body: "m", ctaTitle: "m", action: WhatsNewAction(key: "nowhere"))
        let p = presenter(cards: [missing, Self.card("a", .released("1.14.0")), Self.card("headline", priority: 1)])
        await p.evaluate(resolve: { $0.key == "nowhere" ? nil : WhatsNewResolvedAction(key: $0.key) },
                         canPresent: true)
        XCTAssertEqual(p.presentation?.cards.map(\.id), ["headline", "a"])
    }

    // MARK: - Tắt

    func test_disabled_doesNothing_noSeed() async {
        let p = presenter(hasSeenOnboarding: true, isEnabled: false)
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertNil(p.presentation)
        XCTAssertEqual(seedRuns, 0)
        XCTAssertNil(defaults.object(forKey: FeatureUsageLedger.diskSeededKey))
        p.onboardingFinished()
        XCTAssertNil(defaults.object(forKey: WhatsNewState.lastSeenKey))
        XCTAssertFalse(p.routeIncomingLink {})
    }

    func test_isEnabled_rules() {
        XCTAssertTrue(WhatsNewPresenter.isEnabled(isUnitTestHost: false, previewRoute: nil))
        XCTAssertFalse(WhatsNewPresenter.isEnabled(isUnitTestHost: true, previewRoute: nil))
        XCTAssertFalse(WhatsNewPresenter.isEnabled(isUnitTestHost: false, previewRoute: "home"))
        XCTAssertTrue(WhatsNewPresenter.isEnabled(isUnitTestHost: false, previewRoute: "whatsNewSheet"))
        XCTAssertFalse(WhatsNewPresenter.isEnabled(isUnitTestHost: true, previewRoute: "whatsNewSheet"))
    }

    // MARK: - seed ledger

    func test_firstEvaluate_seedsLedger_once_andFiltersSeededCard() async {
        state().recordSeen(Self.v("1.14.0"))
        let used = Self.card("seeded", priority: 9, usedOnDisk: { $0.hasTrace("trace_a") })
        let p = presenter(cards: [used, Self.card("a")], probe: ClosureUsageProbe(["trace_a": { true }]))
        await p.evaluate(resolve: resolve, canPresent: false)
        XCTAssertEqual(seedRuns, 1)
        XCTAssertTrue(defaults.bool(forKey: FeatureUsageLedger.diskSeededKey))
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertEqual(seedRuns, 1, "seed chỉ ở lần evaluate đầu")
        XCTAssertEqual(p.presentation?.cards.map(\.id), ["a"], "thẻ đã dùng (seed từ đĩa) bị bỏ")
    }

    func test_defaultSeedRunner_runsOffMainThread() async {
        state().recordSeen(Self.v("1.14.0"))
        var seededOnMain: Bool?
        let probeCard = Self.card("p", usedOnDisk: { _ in seededOnMain = Thread.isMainThread; return false })
        let cards = [probeCard]
        let p = WhatsNewPresenter(cards: cards, current: Self.v("1.15.0"), hasSeenOnboarding: true,
                                  ledger: FeatureUsageLedger(cards: cards, defaults: defaults), state: state(),
                                  probe: Self.noTraces, isEnabled: true)
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertEqual(seededOnMain, false, "seed đọc file trong lock ⇒ không được chạy trên main")
        XCTAssertEqual(p.presentation?.cards.map(\.id), ["p"])
    }

    // MARK: - hạ bản

    func test_downgrade_doesNotWriteBackwards() async {
        state().recordSeen(Self.v("1.16.0"))
        let p = presenter(current: "1.15.0")
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertNil(p.presentation)
        XCTAssertEqual(state().lastSeen, Self.v("1.16.0"))
        p.onboardingFinished()
        XCTAssertEqual(state().lastSeen, Self.v("1.16.0"))
    }

    func test_state_brokenLastSeen_readsNil() {
        defaults.set("abc", forKey: WhatsNewState.lastSeenKey)
        XCTAssertNil(state().lastSeen)
    }

    // MARK: - Cờ cho canPresent, telemetry, lần hiện thủ công

    func test_hasPendingExternal_trueOnlyWhileLinkWaitsForDismiss() async {
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        XCTAssertFalse(p.hasPendingExternal)
        await p.evaluate(resolve: resolve, canPresent: true)
        p.sheetDidAppear()
        XCTAssertFalse(p.hasPendingExternal, "sheet mở, chưa có link")
        XCTAssertTrue(p.routeIncomingLink {})
        XCTAssertTrue(p.hasPendingExternal, "link chờ sheet đóng ⇒ canPresent phải false")
        p.sheetDidDismiss()
        XCTAssertFalse(p.hasPendingExternal, "đã chạy link ⇒ hết chờ")
    }

    func test_sheetDidAppear_logsShownOnce_withParams() async {
        let sink = RecordingSink()
        Track.install(sink)
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter(cards: [Self.card("a", priority: 9), Self.card("b", priority: 8), Self.card("c", priority: 7),
                                  Self.card("d", priority: 6)])
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertEqual(sink.names, [], "chỉ bắn khi sheet thật sự hiện")
        p.sheetDidAppear()
        p.sheetDidAppear()   // onAppear bắn lại (pop từ danh sách về) ⇒ không đếm trùng
        XCTAssertEqual(sink.events.map(\.name), ["whats_new_shown"])
        XCTAssertEqual(sink.events.first?.parameters,
                       ["cards": .string("a,b,c"), "more": .int(1), "from_version": .string("1.14.0"),
                        "to_version": .string("1.15.0")])
    }

    func test_sheetDidAppear_unknownFrom_logsUnknown() async {
        let sink = RecordingSink()
        Track.install(sink)
        let p = presenter(hasSeenOnboarding: true)
        await p.evaluate(resolve: resolve, canPresent: true)
        p.sheetDidAppear()
        XCTAssertEqual(sink.events.first?.parameters["from_version"], .string("unknown"))
        XCTAssertEqual(p.presentation?.fromParam, "unknown")
    }

    func test_debugPresentation_writesNothing_logsNothing_butDefersLinks() async {
        let sink = RecordingSink()
        Track.install(sink)
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        p.presentation = WhatsNewPresenter.Presentation(cards: [Self.card("a")], moreCount: 0, from: nil, isDebug: true)
        p.sheetDidAppear()
        XCTAssertEqual(state().lastSeen, Self.v("1.14.0"), "lần hiện thủ công (INTERNAL) không được đổi trạng thái thật")
        XCTAssertNil(state().lastShownFrom)
        XCTAssertEqual(sink.names, [])
        XCTAssertTrue(p.routeIncomingLink {}, "sheet debug vẫn là sheet thật — link phải chờ onDismiss")
    }

    func test_lastShownFrom_disabledPresenterReadsNothing() async {
        defaults.set("1.12.0", forKey: WhatsNewState.lastShownFromKey)
        XCTAssertEqual(presenter().lastShownFrom, "1.12.0")
        XCTAssertNil(presenter(isEnabled: false).lastShownFrom)
    }

    func test_presentGate_everyConditionBlocks() {
        let open = WhatsNewPresentGate(sceneActive: true, coverShown: false, modalPresented: false, extraBlockers: false,
                                       appLinkPending: false, presenterLinkPending: false)
        XCTAssertTrue(open.allowsPresent)
        var g = open; g.sceneActive = false; XCTAssertFalse(g.allowsPresent, "app không active")
        g = open; g.coverShown = true; XCTAssertFalse(g.allowsPresent, "đang có cover/sheet của app")
        g = open; g.modalPresented = true; XCTAssertFalse(g.allowsPresent, "đang có modal UIKit")
        g = open; g.extraBlockers = true; XCTAssertFalse(g.allowsPresent, "app báo còn việc chặn (alert riêng…)")
        g = open; g.appLinkPending = true; XCTAssertFalse(g.allowsPresent, "app đã nhận link ngoài, màn của link sắp hiện")
        g = open; g.presenterLinkPending = true; XCTAssertFalse(g.allowsPresent, "link chờ sheet cũ đóng")
    }

    // MARK: - Watchdog: presentation không bao giờ hiện

    func test_watchdog_sheetNeverAppears_cancels_noLastSeen_retriesNextEvaluate() async {
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertNotNil(p.presentation)
        XCTAssertEqual(watchdogs.map(\.delay), [WhatsNewPresenter.watchdogDelay])
        XCTAssertEqual(WhatsNewPresenter.watchdogDelay, 2, accuracy: 0.5)

        fireWatchdog(0)   // ~2 s sau: SwiftUI chưa từng present (modal khác chen vào)
        XCTAssertNil(p.presentation, "presentation kẹt ⇒ cổng cover của app kẹt true, chặn mọi evaluate sau")
        XCTAssertEqual(state().lastSeen, Self.v("1.14.0"), "chưa hiện ⇒ không ghi lastSeen")
        XCTAssertNil(state().lastShownFrom)

        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertNotNil(p.presentation, "lần evaluate sau thử lại")
    }

    func test_watchdog_sheetAppeared_keepsPresentation() async {
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        await p.evaluate(resolve: resolve, canPresent: true)
        p.sheetDidAppear()
        watchdogs.forEach { $0.work() }
        XCTAssertNotNil(p.presentation, "sheet đã hiện ⇒ watchdog không được đóng")
    }

    func test_watchdog_stale_doesNotCancelNewerPresentation() async {
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        await p.evaluate(resolve: resolve, canPresent: true)
        XCTAssertFalse(p.routeIncomingLink {})   // huỷ lần hiện chưa kịp appear
        await p.evaluate(resolve: resolve, canPresent: true)
        let second = p.presentation?.id
        XCTAssertNotNil(second)
        XCTAssertEqual(watchdogs.count, 2)
        fireWatchdog(0)
        XCTAssertEqual(p.presentation?.id, second, "watchdog của lần hiện cũ không được đóng lần mới")
        fireWatchdog(1)
        XCTAssertNil(p.presentation)
    }

    func test_watchdog_armedForDebugPresentationToo() {
        let p = presenter()
        p.presentation = WhatsNewPresenter.Presentation(cards: [Self.card("a")], moreCount: 0, from: nil, isDebug: true)
        XCTAssertEqual(watchdogs.count, 1)
        fireWatchdog(0)
        XCTAssertNil(p.presentation)
    }

    // MARK: - Nút thẻ, thứ tự đóng, link thắng, cổng

    private func shownPresenter(sink: RecordingSink? = nil) async -> WhatsNewPresenter {
        if let sink { Track.install(sink) }
        state().recordSeen(Self.v("1.14.0"))
        let p = presenter()
        await p.evaluate(resolve: resolve, canPresent: true)
        p.sheetDidAppear()
        return p
    }

    func test_chooseAction_logsCta_closesSheet_actionReturnedAtDismissOnce() async {
        let sink = RecordingSink()
        let p = await shownPresenter(sink: sink)
        let shown = try! XCTUnwrap(p.presentation)
        p.chooseAction(Self.card("a"), Self.act("settings"), surface: .sheet, in: shown)
        XCTAssertNil(p.presentation, "nút thẻ đóng sheet")
        XCTAssertEqual(sink.events.last?.name, "whats_new_cta")
        XCTAssertEqual(sink.events.last?.parameters,
                       ["card": .string("a"), "from_version": .string("1.14.0"), "to_version": .string("1.15.0"),
                        "surface": .string("sheet")])
        XCTAssertEqual(p.sheetDidDismiss(), Self.act("settings"), "hành động chạy SAU khi sheet đóng hẳn")
        XCTAssertNil(p.sheetDidDismiss(), "onDismiss lặp không chạy lại")
    }

    func test_chooseAction_debugSheet_noTelemetry_butActionStillRuns() async {
        let sink = RecordingSink()
        Track.install(sink)
        let p = presenter()
        let debug = WhatsNewPresenter.Presentation(cards: [Self.card("a")], moreCount: 0, from: nil, isDebug: true)
        p.presentation = debug
        p.sheetDidAppear()
        p.chooseAction(Self.card("a"), Self.act("help"), surface: .list, in: debug)
        XCTAssertEqual(sink.names, [], "lần hiện thủ công (INTERNAL) không được ghi telemetry CTA")
        XCTAssertNil(p.presentation)
        XCTAssertEqual(p.sheetDidDismiss(), Self.act("help"))
    }

    func test_dismissWithoutChoice_returnsNil() async {
        let p = await shownPresenter()
        p.presentation = nil   // Continue / kéo xuống
        XCTAssertNil(p.sheetDidDismiss())
    }

    func test_linkWinsOverChosenAction() async {
        let p = await shownPresenter()
        p.chooseAction(Self.card("a"), Self.act("help"), surface: .sheet, in: p.presentation!)
        var applied = 0
        XCTAssertTrue(p.routeIncomingLink { applied += 1 }, "sheet còn đang trượt xuống ⇒ link chờ")
        XCTAssertNil(p.sheetDidDismiss(), "link tới lúc sheet mở thắng nút thẻ")
        XCTAssertEqual(applied, 1)
    }

    func test_dismiss_resetsStateBeforeReturningAction() async {
        let p = await shownPresenter()
        p.chooseAction(Self.card("a"), Self.act("pick"), surface: .sheet, in: p.presentation!)
        let action = p.sheetDidDismiss()
        XCTAssertEqual(action, Self.act("pick"))
        // Runner chạy sau: presenter đã sạch ⇒ link tới lúc này được đặt thẳng, không bị giữ.
        XCTAssertFalse(p.routeIncomingLink {})
        XCTAssertFalse(p.hasPendingExternal)
    }

    func test_gate_readsPresenterPendingLink() async {
        let p = await shownPresenter()
        let open = p.presentGate(sceneActive: true, coverShown: false, modalPresented: false, extraBlockers: false,
                                 appLinkPending: false)
        XCTAssertTrue(open.allowsPresent)
        XCTAssertFalse(open.presenterLinkPending)
        XCTAssertTrue(p.routeIncomingLink {})
        let held = p.presentGate(sceneActive: true, coverShown: false, modalPresented: false, extraBlockers: false,
                                 appLinkPending: false)
        XCTAssertTrue(held.presenterLinkPending)
        XCTAssertFalse(held.allowsPresent, "link chờ sheet cũ đóng ⇒ không được hiện sheet mới")
        XCTAssertEqual(p.presentGate(sceneActive: false, coverShown: true, modalPresented: true, extraBlockers: true,
                                     appLinkPending: true),
                       WhatsNewPresentGate(sceneActive: false, coverShown: true, modalPresented: true,
                                           extraBlockers: true, appLinkPending: true, presenterLinkPending: true))
    }

    func test_settingsListCta_logsWithoutFromVersion_andRuns() {
        let sink = RecordingSink()
        Track.install(sink)
        defaults.set("1.12.0", forKey: WhatsNewState.lastShownFromKey)
        let p = presenter()
        var ran: [WhatsNewResolvedAction] = []
        p.runFromSettingsList(Self.card("listed"), Self.act("settings")) { ran.append($0) }
        XCTAssertEqual(ran, [Self.act("settings")])
        XCTAssertEqual(sink.events.map(\.name), ["whats_new_cta"])
        XCTAssertEqual(sink.events.first?.parameters,
                       ["card": .string("listed"), "to_version": .string("1.15.0"), "surface": .string("settings")],
                       "danh sách Settings không gắn với lần hiện sheet nào ⇒ không gửi from_version")
    }

    // MARK: - Danh sách trong sheet, thay presentation trực tiếp

    func test_chooseAction_fromListInsideSheet_logsSurfaceList_withThisShowingFrom() async {
        let sink = RecordingSink()
        let p = await shownPresenter(sink: sink)
        p.chooseAction(Self.card("b"), Self.act("help"), surface: .list, in: p.presentation!)
        XCTAssertEqual(sink.events.last?.name, "whats_new_cta")
        XCTAssertEqual(sink.events.last?.parameters,
                       ["card": .string("b"), "from_version": .string("1.14.0"), "to_version": .string("1.15.0"),
                        "surface": .string("list")],
                       "danh sách đẩy từ sheet: surface list + from_version của ĐÚNG lần hiện đó")
    }

    func test_watchdog_presentationReplacedDirectly_oldWatchdogDoesNotCancelNew() {
        let p = presenter()
        p.presentation = WhatsNewPresenter.Presentation(cards: [Self.card("a")], moreCount: 0, from: nil, isDebug: true)
        let b = WhatsNewPresenter.Presentation(cards: [Self.card("b")], moreCount: 0, from: nil, isDebug: true)
        p.presentation = b   // gán thẳng B lên A (không qua nil)
        XCTAssertEqual(watchdogs.count, 2, "lần hiện mới ⇒ hẹn watchdog riêng")
        fireWatchdog(0)
        XCTAssertEqual(p.presentation?.id, b.id, "watchdog của A không được huỷ B")
        fireWatchdog(1)
        XCTAssertNil(p.presentation)
    }
}
