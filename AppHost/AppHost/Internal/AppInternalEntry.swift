import SwiftUI

// Lối vào công cụ nội bộ của app — chỗ DUY NHẤT trong app được viết `#if INTERNAL`. Call site gọi wrapper dưới đây
// không điều kiện; ở `Release` wrapper trả `self`/`EmptyView` và nội dung debug (`LogFileView`,
// `ReviewPromptDebugSection`, `AppDebugTools`) không được biên dịch — cổng `verify_release_clean.sh` soi binary.

extension View {
    /// Nhấn giữ 1,5 s trên view ⇒ sheet công cụ nội bộ (INTERNAL); `self` nguyên vẹn ở `Release`.
    @ViewBuilder
    func internalDebugSheet(entitlements: Entitlements, reviewPrompter: ReviewPrompter,
                            arm: @escaping (ReviewMoment) -> Void) -> some View {
        #if INTERNAL
        modifier(InternalLongPressSheet {
            NavigationStack {
                List {
                    AppDebugTools(entitlements: entitlements, reviewPrompter: reviewPrompter,
                                  arm: arm)
                }
                    .navigationTitle(Text(verbatim: "Debug"))
            }
        })
        #else
        self
        #endif
    }
}

/// Nhóm công cụ nội bộ cắm vào khe `internalSection` của Settings. Ở `Release` là `EmptyView`.
struct AppInternalSettingsSection: View {
    let entitlements: Entitlements
    let reviewPrompter: ReviewPrompter
    let arm: (ReviewMoment) -> Void

    var body: some View {
        #if INTERNAL
        AppDebugTools(entitlements: entitlements, reviewPrompter: reviewPrompter,
                      arm: arm)
        #else
        EmptyView()
        #endif
    }
}

/// Cấu hình công cụ nội bộ lúc mở app — `AppHostApp.init()` gọi TRƯỚC `AppBootstrap.run` (bước `firstLaunchSim` đọc
/// `FirstLaunchSimulation.extraKeys`). Khoá "lần đầu" riêng của app ngoài cờ onboarding đăng ký ở đây. Thân rỗng ở
/// `Release`.
enum AppInternalLaunch {
    static func configure() {
        // App đăng ký khoá "lần đầu" riêng ở đây, trong `#if INTERNAL` (`FirstLaunchSimulation.extraKeys`).
    }
}

#if INTERNAL
/// Các section debug: override Free/Pro, giả lập lần đầu mở app, luật mời đánh giá, xem log. Đặt trong `List`/`Form`.
struct AppDebugTools: View {
    @ObservedObject var entitlements: Entitlements
    let reviewPrompter: ReviewPrompter
    let arm: (ReviewMoment) -> Void
    @State private var simulateFirstLaunch = FirstLaunchSimulation.isEnabled

    var body: some View {
        Section {
            if entitlements.paywallEnabled {
                Picker(selection: Binding(get: { entitlements.internalProOverride },
                                          set: { o in Task { await entitlements.setInternalProOverride(o) } })) {
                    ForEach(Entitlements.InternalProOverride.allCases, id: \.self) { o in
                        dtext(o.rawValue).tag(o)
                    }
                } label: { dtext("Quyền Pro") }
            }
            Toggle(isOn: $simulateFirstLaunch) { dtext("Giả lập lần đầu mở app") }
                .onChange(of: simulateFirstLaunch) { _, on in FirstLaunchSimulation.setEnabled(on) }
            if let url = AppLog.fileURL {
                NavigationLink { LogFileView(url: url) } label: { dtext("Xem log") }
            }
        } header: {
            dtext("Internal")
        }
        ReviewPromptDebugSection(prompter: reviewPrompter, arm: arm)
    }
}
#endif
