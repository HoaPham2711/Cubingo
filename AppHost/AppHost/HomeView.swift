import SwiftUI

/// Màn gốc: `NavigationStack` của luồng (gốc là màn chọn khối) + banner "có bản mới" ở đầu khi checker báo.
/// Các màn của luồng là đích `FlowRoute`; route chưa có màn trả `EmptyView()` (task sau thay).
struct HomeView: View {
    @ObservedObject var updateChecker: UpdateChecker
    /// Mở App Store (hoặc copy link khi không mở được) — app cấp để Home không tự giữ UIKit.
    let openStore: (URL) -> Void
    @ObservedObject var flow: FlowModel
    let deps: FlowDependencies
    let onOpenSettings: () -> Void

    /// Phiên bản đã log `update_prompt` "shown" — một lần cho mỗi phiên bản được mời trong vòng đời màn.
    @State private var loggedUpdateShown: String?

    var body: some View {
        NavigationStack(path: $flow.path) {
            FlowPickerView(flow: flow, onOpenSettings: onOpenSettings)
                .safeAreaInset(edge: .top) { updateBanner }
                .navigationDestination(for: FlowRoute.self) { route in
                    destination(route)
                }
        }
    }

    @ViewBuilder
    private var updateBanner: some View {
        if updateChecker.showsHomeBanner,
           case .available(let version, let url, let notes) = updateChecker.status {
            UpdateBanner(version: version, notes: notes,
                         onUpdate: {
                             Track.log(.updatePrompt(action: "open_store"))
                             openStore(url)
                         },
                         onDismiss: { updateChecker.dismissBanner() })
            .padding(.horizontal, 16)
            .readableContentWidth()
            .onAppear { logShown(version) }
        }
    }

    @ViewBuilder
    private func destination(_ route: FlowRoute) -> some View {
        switch route {
        case .scan:
            ScanEntryView(flow: flow, deps: deps)
                .id(flow.scanGeneration)
        case .review(let manual):
            ScanReviewView(flow: flow, deps: deps, manual: manual)
        case .mode:
            FlowModeView(flow: flow, deps: deps)
        case .guide:
            if let session = flow.session, let palette = flow.palette {
                GuideView(session: session, palette: palette, prefs: deps.prefs,
                          onFinish: { flow.didFinishGuide() },
                          check: session.mode == .teach
                              ? GuideCheckHooks(deps: deps, white: flow.whiteReference,
                                                onMatched: { flow.checkMatched() },
                                                onSkipped: { flow.checkSkipped() },
                                                onRescan: { flow.startRescan() })
                              : nil)
            }
        case .done:
            GuideDoneView(flow: flow, deps: deps)
        }
    }

    private func logShown(_ version: String) {
        guard UpdateEvaluator.shouldLogUpdateShown(loggedVersion: loggedUpdateShown, offeredVersion: version) else { return }
        loggedUpdateShown = version
        Track.log(.updatePrompt(action: "shown"))
    }
}
