import SwiftUI
import UIKit

/// Khung chính của app (sau onboarding): `RootShellView` với các tab của `AppTab`, tour xem lại, đánh giá What's New.
/// Mọi đối tượng nghiệp vụ truyền TƯỜNG MINH qua `init` (không `@EnvironmentObject`: cover không kế thừa environment).
struct AppShellView: View {
    let config: AppConfig
    @ObservedObject var entitlements: Entitlements
    @ObservedObject var updateChecker: UpdateChecker
    let reviewPrompter: ReviewPrompter
    let reviewScheduler: ReviewScheduler
    @ObservedObject var whatsNew: WhatsNewPresenter
    /// Yêu cầu đổi tab từ nơi không giữ `nav` (nút thẻ What's New) — xem `AppTabRouter`.
    @ObservedObject var tabRouter: AppTabRouter
    /// `nil` ⇒ Settings chỉ có "Contact us" (không form phản hồi). Chọn ở `AppHostApp` theo khối tuỳ chọn Web API.
    let feedbackTransport: FeedbackTransport?
    /// Link vào app (Universal Link) đã nhận ở cấp App, chưa mở. Khung chính giao nó cho `onAppLink` rồi xoá — kể cả link
    /// tới lúc còn onboarding (giao khi khung chính hiện). Khác `nil` ⇒ cổng What's New đóng.
    @Binding var pendingLink: AppLink?
    /// Mở màn của link — `AppHostApp` truyền `AppLinkActions.perform` (đổi tab qua `tabRouter`).
    let onAppLink: (AppLink) -> Void

    @StateObject private var nav: ShellNavigationModel<AppTab, AppSidebarExtra>
    @State private var showTour = false
    /// Cover/sheet của route preview đang mở (chỉ Simulator đặt được) — tính vào cổng What's New.
    @State private var previewCoverShown = false
    @State private var copiedFallbackMessage: String?
    @Environment(\.scenePhase) private var scenePhase

    init(config: AppConfig, entitlements: Entitlements, updateChecker: UpdateChecker, reviewPrompter: ReviewPrompter,
         reviewScheduler: ReviewScheduler, whatsNew: WhatsNewPresenter,
         tabRouter: AppTabRouter, feedbackTransport: FeedbackTransport?, pendingLink: Binding<AppLink?>,
         onAppLink: @escaping (AppLink) -> Void) {
        self.config = config
        self.entitlements = entitlements
        self.updateChecker = updateChecker
        self.reviewPrompter = reviewPrompter
        self.reviewScheduler = reviewScheduler
        self.whatsNew = whatsNew
        self.tabRouter = tabRouter
        self.feedbackTransport = feedbackTransport
        _pendingLink = pendingLink
        self.onAppLink = onAppLink
        let nav = ShellNavigationModel<AppTab, AppSidebarExtra>(initial: AppPreview.current?.initialTab ?? .home)
        _nav = StateObject(wrappedValue: nav)
    }

    /// Luồng xem lại tour — rỗng thì KHÔNG mở cover (nháy nền đen + log `tour_replay` sai) và ẩn hàng ở Settings.
    private var replayFlowIsEmpty: Bool { AppOnboarding.flow(.replay).isEmpty }

    var body: some View {
        RootShellView(nav: nav, appName: config.displayName,
                      content: { tab in content(for: tab) },
                      sidebarRows: { tab in sidebarRows(for: tab) },
                      detailExtra: { extra in detailExtra(extra) })
            .appTourSheet(isPresented: $showTour, source: "settings") {
                AppOnboarding.view(.replay, appName: config.displayName) { showTour = false }
            }
            .appPreviewPresentations(paywall: AppPaywall.content(config: config),
                                     config: config, feedbackTransport: feedbackTransport,
                                     isShown: $previewCoverShown)
            .alert("Copied", isPresented: Binding(get: { copiedFallbackMessage != nil },
                                                  set: { if !$0 { copiedFallbackMessage = nil } })) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(verbatim: copiedFallbackMessage ?? "")
            }
            // Nút thẻ What's New (sheet ở cấp App hoặc danh sách trong Settings) xin đổi tab ⇒ chọn ở đây, rồi xoá yêu cầu.
            .onChange(of: tabRouter.requested, initial: true) { _, tab in
                guard let tab else { return }
                nav.select(tab)
                tabRouter.clear()
            }
            // Link vào app: xoá TRƯỚC rồi mới giao (giao có thể đặt link mới — không được xoá mất nó).
            .onChange(of: pendingLink, initial: true) { _, link in
                guard let link else { return }
                pendingLink = nil
                onAppLink(link)
            }
            .task { await evaluateWhatsNew() }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { Task { await evaluateWhatsNew() } }
            }
    }

    @ViewBuilder
    private func content(for tab: AppTab) -> some View {
        switch tab {
        case .home:
            HomeView(
                updateChecker: updateChecker, openStore: openStore)
                .internalDebugSheet(entitlements: entitlements, reviewPrompter: reviewPrompter,
                                    arm: { reviewScheduler.arm($0, bypassPolicy: true) })
        case .settings:
            SettingsView(
                deps: SettingsDependencies(config: config, entitlements: entitlements, updateChecker: updateChecker,
                                           reviewPrompter: reviewPrompter, paywall: AppPaywall.content(config: config),
                                           feedbackTransport: feedbackTransport, diagnosticsExtras: {
                                               []
                                           }),
                appSections: {
                    // App thêm nhóm Settings riêng ở đây.
                },
                helpRows: {
                    NavigationLink(value: SettingsRoute.whatsNew) {
                        Text("What's New").foregroundColor(DSColor.textPrimary)
                    }
                },
                internalSection: {
                    AppInternalSettingsSection(entitlements: entitlements, reviewPrompter: reviewPrompter,
                                               arm: { reviewScheduler.arm($0, bypassPolicy: true) })
                },
                destination: { route in settingsDestination(route) },
                onReplayTour: { if !replayFlowIsEmpty { showTour = true } },
                replayTourAvailable: !replayFlowIsEmpty)
        }
    }

    /// Hàng chỉ sidebar iPad có, chèn dưới hàng của `tab` (rỗng nếu tab không có).
    @ViewBuilder
    private func sidebarRows(for tab: AppTab) -> some View {
        // App chèn hàng sidebar riêng dưới `tab` ở đây.
    }

    /// Cột chi tiết khi chọn một mục phụ của sidebar iPad.
    @ViewBuilder
    private func detailExtra(_ extra: AppSidebarExtra) -> some View {
        // App dựng cột chi tiết cho mục phụ `extra` ở đây (`AppSidebarExtra` = `Never` ⇒ không bao giờ gọi).
    }

    @ViewBuilder
    private func settingsDestination(_ route: SettingsRoute) -> some View {
        switch route {
        case .whatsNew:
            WhatsNewListView(sections: WhatsNewListModel.sections(cards: whatsNew.cards, current: whatsNew.current,
                                                                  lastShownFrom: whatsNew.lastShownFrom),
                             resolve: AppWhatsNew.resolve, source: .settings,
                             onRun: { card, action in
                                 whatsNew.runFromSettingsList(card, action) { AppWhatsNew.perform($0, tabs: tabRouter) }
                             })
        case .feedback, .custom:
            // Lõi chỉ đẩy `.feedback` khi có transport (form do lõi dựng); app giữ chỗ không có đích riêng.
            EmptyView()
        }
    }

    private func openStore(_ url: URL) {
        SupportMailOpener.open(url, copyingOnFailure: url.absoluteString) {
            copiedFallbackMessage = String(localized:
                "Couldn't open the App Store. We copied the link to your clipboard instead.")
        }
    }

    // MARK: - What's New

    /// Đọc giá trị THẬT mỗi lần gọi (qua `@autoclosure` của `evaluate`). Hỏi UIKit, KHÔNG đọc `scenePhase`: `.task`
    /// giữ bản sao view lúc bắt đầu chạy, `@Environment` của bản sao là giá trị cũ (lúc mở còn `.inactive`).
    private var whatsNewGate: WhatsNewPresentGate {
        whatsNew.presentGate(sceneActive: UIApplication.shared.applicationState == .active,
                             coverShown: showTour || previewCoverShown || whatsNew.presentation != nil,
                             modalPresented: ModalPresentationProbe.isModalPresented(),
                             extraBlockers: false, appLinkPending: pendingLink != nil)
    }

    /// Lúc mở `.task` có thể chạy khi app còn `.inactive` ⇒ chờ ngắn (≤ 3 s) thay vì bỏ lượt; đủ điều kiện thì chờ
    /// thêm ~0,6 s cho cover/alert vừa mở kịp hiện rồi mới giao presenter (presenter kiểm lại cổng trước khi present).
    private func evaluateWhatsNew() async {
        guard whatsNew.isEnabled, whatsNew.presentation == nil else { return }
        for _ in 0..<30 where UIApplication.shared.applicationState != .active {
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        guard whatsNewGate.allowsPresent else { return }
        try? await Task.sleep(nanoseconds: 600_000_000)
        await whatsNew.evaluate(resolve: AppWhatsNew.resolve, canPresent: whatsNewGate.allowsPresent)
    }
}

/// Đích nút thẻ What's New của app: ánh xạ `WhatsNewAction.key` ⇒ đích. Không khoá nào có đích ⇒ `nil` (thẻ hiện
/// không nút).
enum AppWhatsNew {
    static let resolve: WhatsNewResolver = { action in
        return nil
    }

    /// Chạy nút đã bấm. Điều hướng đi qua `tabs` (sheet What's New gắn ở cấp App, không giữ `nav`); `AppShellView`
    /// nghe `tabs.requested` và gọi `nav.select`. Khoá lạ ⇒ không làm gì.
    @MainActor
    static func perform(_ action: WhatsNewResolvedAction, tabs: AppTabRouter) {
        // App ánh xạ `action.key` ⇒ đích ở đây (vd `tabs.open(.home)`).
    }
}

/// Đích của link vào app (`AppLinkRouter` đã kiểm host): ánh xạ đường dẫn ⇒ màn. Đường dẫn lạ ⇒ không làm gì (app mở
/// ở màn đang đứng).
enum AppLinkActions {
    @MainActor
    static func perform(_ link: AppLink, tabs: AppTabRouter) {
        // App ánh xạ `link.path` ⇒ màn ở đây (vd `if link.path.first == "x" { tabs.open(.home) }`).
    }
}

/// Cầu đổi tab cho nơi không giữ `ShellNavigationModel` (vd sheet What's New gắn ở cấp App). `AppHostApp` sở hữu MỘT
/// bản; `AppShellView` nghe `requested`, gọi `nav.select` rồi `clear()`.
@MainActor
final class AppTabRouter: ObservableObject {
    @Published private(set) var requested: AppTab?

    func open(_ tab: AppTab) { requested = tab }
    func clear() { requested = nil }
}
