import SwiftUI

/// Tour onboarding — Cubingo không có tour (spec mục 4.1): mở app vào thẳng màn chọn khối. Luồng rỗng ⇒
/// `OnboardingView` kết thúc ngay; luồng xem lại rỗng ⇒ Settings ẩn hàng "Show app tour".
enum AppOnboarding {
    enum Page: Hashable, CaseIterable {}

    static func flow(_ context: OnboardingFlow<Page>.Context) -> OnboardingFlow<Page> {
        OnboardingFlow(context: context, allPages: [])
    }

    /// `initialPage`: trang mở đầu (route preview mở giữa tour); `nil` ⇒ trang đầu của luồng.
    static func view(_ context: OnboardingFlow<Page>.Context, appName: String, initialPage: Page? = nil,
                     onFinish: @escaping () -> Void) -> some View {
        OnboardingView(flow: flow(context), initialPage: initialPage, onFinish: onFinish) { _ in
            EmptyView()
        }
    }
}
