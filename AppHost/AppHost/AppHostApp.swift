import SwiftUI

/// Vỏ app: nối các khối của `Core/` với các tính năng của app.
///
/// Thứ tự trong `init()` (lý do chi tiết ở `AppBootstrap`):
/// 1. Simulator + route `-uiPreview`: ép trạng thái tất định (cờ onboarding, suite What's New) — TRƯỚC
///    `WhatsNewHost.make` vì nó đọc cờ onboarding đúng một lần. Chỉ ghi UserDefaults.
/// 2. `WhatsNewHost.make` — presenter + ledger dùng chung một danh sách thẻ; probe dấu vết của app (chỉ đọc, chạy nền).
/// 3. Chỗ dựng phụ thuộc của các tính năng (store dựng MỘT lần ở đây, truyền xuống tường minh; nguồn thuộc tính người
///    dùng) — TRƯỚC chuỗi khởi động để thuộc tính người dùng có nguồn khi telemetry chạy.
/// 4. `AppInternalLaunch.configure()` (khoá "lần đầu" của công cụ nội bộ) — trước bước `firstLaunchSim`.
/// 5. `AppBootstrap.run(standardSteps)` — takeIncident → purgeTmp (gồm thư mục tạm của app) → usageObserver(ledger) →
///    telemetry → firstLaunchSim → tips; rồi `UserPropertySync.refresh()` gửi thuộc tính của app một lần.
/// `Entitlements`/`UpdateChecker`/`ReviewPrompter`/presenter sở hữu ở cấp App: `Transaction.updates` phải được nghe từ
/// giây đầu, kể cả lúc đang onboarding. `entitlements.start()` ở `.task` (không trong `init`).
///
/// Đây là file DUY NHẤT nhắc cờ `FEATURE_*` và kiểu của khối tuỳ chọn (`CoreOptional/`).
@main
struct AppHostApp: App {
    private let config: AppConfig
    private let feedbackTransport: FeedbackTransport?
    @StateObject private var entitlements: Entitlements
    @StateObject private var updateChecker: UpdateChecker
    @StateObject private var reviewPrompter: ReviewPrompter
    @StateObject private var whatsNew: WhatsNewPresenter
    @State private var reviewScheduler: ReviewScheduler
    /// Cầu đổi tab cho nút thẻ What's New (sheet gắn ở đây, `nav` nằm trong `AppShellView`).
    @StateObject private var tabRouter = AppTabRouter()
    /// Link vào app (Universal Link) đã nhận, chờ khung chính mở — xem `receiveLink`.
    @State private var pendingLink: AppLink?
    /// Cài đặt + luồng của Cubingo — dựng MỘT lần ở đây, truyền xuống qua `FlowDependencies`.
    @StateObject private var prefs: PrefsStore
    @StateObject private var flow = FlowModel()
    private let flowDeps: FlowDependencies
    @Environment(\.scenePhase) private var scenePhase

    /// Host unit test / route preview không cần sản phẩm ⇒ không chạm StoreKit thật.
    private static var skipsStoreKit: Bool {
        AppBootstrap.skipsStoreKit(routesNeedingStore: AppPreview.routesNeedingStore)
    }

    init() {
        // Dòng đầu tiên: theme phải vào khe TRƯỚC lần đọc token màu đầu tiên (đọc xong là khoá).
        DSTheme.install(AppTheme.theme)
        let config = AppConfig.current
        self.config = config

        #if targetEnvironment(simulator)
        AppPreviewSeed.prepare()
        let whatsNewDefaults = AppPreviewSeed.whatsNewDefaults
        #else
        let whatsNewDefaults = UserDefaults.standard
        #endif
        let usageProbe = ClosureUsageProbe([:])
        let appTmpDirs: [URL] = []
        let (presenter, ledger) = WhatsNewHost.make(cards: WhatsNewCatalog.cards, probe: usageProbe,
                                                    isUnitTestHost: AppEnvironment.isUnitTestHost,
                                                    previewRoute: AppEnvironment.uiPreviewRoute,
                                                    defaults: whatsNewDefaults)

        AppInternalLaunch.configure()
        AppBootstrap.run(AppBootstrap.standardSteps(config: config, usageLedger: ledger, tmpDirs: appTmpDirs,
                                                    telemetryPreConfigure: Self.telemetryPreConfigure))
        UserPropertySync.refresh()

        let prompter = ReviewPrompter()
        // Dựng cả khi paywall tắt: Settings/paywall nhận nó; tắt ⇒ coi như Pro, không lời gọi StoreKit nào.
        #if targetEnvironment(simulator)
        // Route preview có thể ép Pro/miễn phí bằng store giả + suite `uiPreview.*` (không đụng cache thật).
        _entitlements = StateObject(wrappedValue: AppPreviewSeed.entitlements() ?? Entitlements.live(config: config))
        #else
        _entitlements = StateObject(wrappedValue: Entitlements.live(config: config))
        #endif
        _updateChecker = StateObject(wrappedValue: UpdateChecker.makeDefault(appID: config.appStoreID))
        _reviewPrompter = StateObject(wrappedValue: prompter)
        _whatsNew = StateObject(wrappedValue: presenter)
        _reviewScheduler = State(initialValue: ReviewScheduler(prompter: prompter, isQuiet: ReviewScheduler.liveIsQuiet,
                                                               present: {}))
        feedbackTransport = Self.makeFeedbackTransport(config: config)

        let prefs = PrefsStore(defaults: .standard)
        _prefs = StateObject(wrappedValue: prefs)
        flowDeps = FlowDependencies(prefs: prefs, haptic: FlowHaptics.live(prefs: prefs))
    }

    var body: some Scene {
        WindowGroup {
            AppRootGate(onboarding: { finish in
                AppOnboarding.view(.firstRun, appName: config.displayName,
                                   initialPage: AppPreview.current?.onboardingInitialPage, onFinish: finish)
            }, main: {
                AppShellView(config: config, entitlements: entitlements, updateChecker: updateChecker,
                             reviewPrompter: reviewPrompter, reviewScheduler: reviewScheduler, whatsNew: whatsNew,
                             tabRouter: tabRouter, feedbackTransport: feedbackTransport, pendingLink: $pendingLink,
                             onAppLink: { AppLinkActions.perform($0, tabs: tabRouter) },
                             flow: flow, deps: flowDeps)
            }, willFinishOnboarding: {
                // Cài mới đã có tour giới thiệu ⇒ không hiện What's New (ghi lastSeen TRƯỚC khi cờ đổi).
                whatsNew.onboardingFinished()
            })
            // Chế độ giao diện theo theme của app (bản chuẩn: tối — quyết định 11 của plan P2).
            .preferredColorScheme(DSTheme.current.colorScheme)
            // Màu nhấn theo token (tab đang chọn, nút hệ thống) — không để xanh mặc định của iOS.
            .tint(DSColor.accent)
            .reviewPromptHost(prompter: reviewPrompter, appName: config.displayName)
            .whatsNewSheet(presenter: whatsNew, resolve: AppWhatsNew.resolve,
                           run: { AppWhatsNew.perform($0, tabs: tabRouter) })
            .task { if !Self.skipsStoreKit { entitlements.start() } }
            .task { if !AppBootstrap.skipsNetwork() { await updateChecker.checkIfNeeded() } }
            .task { InternalLaunch.afterLaunch() }
            // Universal Link: mở từ link (`onOpenURL`) hoặc app đang chạy nhận link duyệt web (Handoff/Safari).
            .onOpenURL { receiveLink($0) }
            .onContinueUserActivity(NSUserActivityTypeBrowsingWeb) { activity in
                if let url = activity.webpageURL { receiveLink(url) }
            }
            #if targetEnvironment(simulator)
            // Route preview giả một link tới sau khi mở (chụp ảnh kết quả định tuyến).
            .task {
                guard let url = AppPreviewSeed.incomingLink(webHost: config.webHost) else { return }
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                receiveLink(url)
            }
            #endif
            .onChange(of: scenePhase) { _, phase in
                // Lượt dùng kết thúc ⇒ dấu "vừa mở link" (chặn What's New đè màn của link) gỡ.
                if phase == .background { whatsNew.sceneDidEnterBackground() }
                AppLifecycle.handle(phase) {
                    reviewPrompter.noteAppBecameActive()
                    // Hết hạn subscription KHÔNG bắn `Transaction.updates` ⇒ hỏi lại mỗi lần active.
                    if !Self.skipsStoreKit { Task { await entitlements.refresh() } }
                    if !AppBootstrap.skipsNetwork() { Task { await updateChecker.checkIfNeeded() } }
                }
            }
            .internalBadge()
        }
    }

    /// URL ngoài ⇒ `AppLinkRouter` (chỉ `https` đúng host đang chạy) ⇒ `pendingLink`. Sheet What's New đang mở ⇒ đặt
    /// link khi sheet đóng (link mới nhất thắng); đang onboarding ⇒ khung chính mở link khi hiện.
    private func receiveLink(_ url: URL) {
        AppLinkRouter.route(url, expectedHost: config.webHost, whatsNew: whatsNew) { pendingLink = $0 }
    }

    // MARK: - Khối tuỳ chọn Web API (cờ build từ `[features] web_api`, xem Features.generated.yml)

    /// Provider App Check phải đặt TRƯỚC `FirebaseApp.configure()` — hook `TelemetryConfig.preConfigure`.
    private static var telemetryPreConfigure: (() -> Void)? {
        #if FEATURE_WEB_API
        return { AppCheckTokenSource.installProvider() }
        #else
        return nil
        #endif
    }

    /// Form phản hồi chỉ khi có kênh gửi thật (web API) và có host; không thì `nil` ⇒ Settings chỉ có "Contact us".
    private static func makeFeedbackTransport(config: AppConfig) -> FeedbackTransport? {
        #if FEATURE_WEB_API
        guard config.features.webAPI, let base = config.apiBaseURL else { return nil }
        return WebAPIFeedbackTransport(baseURL: base, appVersion: config.version)
        #else
        return nil
        #endif
    }
}
