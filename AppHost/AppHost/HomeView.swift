import SwiftUI

/// Màn Home: banner "có bản mới" (khi checker báo) + nội dung Home của app (chưa có thì một trạng thái rỗng giữ chỗ).
struct HomeView: View {
    @ObservedObject var updateChecker: UpdateChecker
    /// Mở App Store (hoặc copy link khi không mở được) — app cấp để Home không tự giữ UIKit.
    let openStore: (URL) -> Void

    /// Phiên bản đã log `update_prompt` "shown" — một lần cho mỗi phiên bản được mời trong vòng đời màn (banner tự
    /// không log; `onAppear` bắn lại mỗi lần đổi tab/quay lại).
    @State private var loggedUpdateShown: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    // iPad: tiêu đề lớn trong cột (đi cặp `readableColumnNavigationTitle`); iPhone: không vẽ gì.
                    ReadableColumnTitle(Text("Home"))
                    if updateChecker.showsHomeBanner,
                       case .available(let version, let url, let notes) = updateChecker.status {
                        UpdateBanner(version: version, notes: notes,
                                     onUpdate: {
                                         Track.log(.updatePrompt(action: "open_store"))
                                         openStore(url)
                                     },
                                     onDismiss: { updateChecker.dismissBanner() })
                        .onAppear { logShown(version) }
                    }
                    EmptyStateView(systemImage: "square.grid.2x2",
                                   title: String(localized: "Nothing here yet"),
                                   message: String(localized: "Your content will appear here."))
                        .padding(.top, 40)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .readableContentWidth()
            }
            .background(DSColor.pageBackground.ignoresSafeArea())
            .readableColumnNavigationTitle(Text("Home"))
            .trackScreen("home")
        }
    }

    private func logShown(_ version: String) {
        guard UpdateEvaluator.shouldLogUpdateShown(loggedVersion: loggedUpdateShown, offeredVersion: version) else { return }
        loggedUpdateShown = version
        Track.log(.updatePrompt(action: "shown"))
    }
}
