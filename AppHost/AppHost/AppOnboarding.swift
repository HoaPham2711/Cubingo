import SwiftUI

/// Tour onboarding: các trang dựng bằng `OnboardingInfoPage`, theo thứ tự khai báo của `Page` — mở bằng Welcome, kết
/// bằng Ready.
enum AppOnboarding {
    enum Page: Hashable, CaseIterable {
        case welcome
        case ready
    }

    /// Xem lại (Settings) bỏ Welcome (logo + dòng công khai analytics user đã thấy) — luồng replay vẫn không rỗng vì
    /// luôn còn Ready (kể cả khi app không thêm trang nào).
    static func flow(_ context: OnboardingFlow<Page>.Context) -> OnboardingFlow<Page> {
        OnboardingFlow(context: context, allPages: Page.allCases, skippedOnReplay: [.welcome])
    }

    /// `initialPage`: trang mở đầu (route preview mở giữa tour); `nil` ⇒ trang đầu của luồng.
    static func view(_ context: OnboardingFlow<Page>.Context, appName: String, initialPage: Page? = nil,
                     onFinish: @escaping () -> Void) -> some View {
        OnboardingView(flow: flow(context), initialPage: initialPage, onFinish: onFinish) { page in
            pageView(page, appName: appName)
        }
    }

    @ViewBuilder
    private static func pageView(_ page: Page, appName: String) -> some View {
        switch page {
        case .welcome:
            OnboardingInfoPage(
                title: String(localized: "Welcome to \(appName)"),
                illustration: illustration("sparkles"),
                rows: [
                    .init(icon: "hand.wave", title: String(localized: "Get started quickly"),
                          subtitle: String(localized: "Everything you need is one tap away.")),
                    .init(icon: "lock.shield", title: String(localized: "Your data stays yours"),
                          subtitle: String(localized: "Usage statistics are anonymous. You can turn them off in Settings.")),
                ])
        case .ready:
            OnboardingInfoPage(
                title: String(localized: "You're all set"),
                illustration: illustration("checkmark.circle"),
                rows: [
                    .init(icon: "gearshape", title: String(localized: "Make it yours"),
                          subtitle: String(localized: "Adjust preferences any time in Settings.")),
                    .init(icon: "questionmark.circle", title: String(localized: "Help is close"),
                          subtitle: String(localized: "Replay this tour or contact us from Settings.")),
                ])
        }
    }

    private static func illustration(_ symbol: String) -> AnyView {
        AnyView(Image(systemName: symbol)
            .font(.system(size: 72, weight: .regular))
            .foregroundColor(DSColor.accent))
    }
}
