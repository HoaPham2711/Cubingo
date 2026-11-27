import SwiftUI

/// Cổng gốc: chưa xem onboarding ⇒ `onboarding(finish)`, đã xem ⇒ `main()`. Cờ là `@AppStorage` khoá
/// `WhatsNewHost.hasSeenOnboardingKey`, ghi NGAY khi user bấm CTA/Skip — không suy từ dữ liệu đã có (xoá hết dữ liệu
/// không làm onboarding hiện lại).
///
/// `willFinishOnboarding` chạy TRƯỚC khi đổi cờ (VD `whatsNew.onboardingFinished()`: cài mới đã có tour giới thiệu
/// app, không hiện What's New) — thứ tự nằm ở `completeOnboarding` để test được.
///
/// Đồng bộ `AppTipState.onboardingFinished` theo cờ (lúc mở app và khi onboarding xong): không tip nào hiện khi còn tour.
struct AppRootGate<Onboarding: View, Main: View>: View {
    /// Một nguồn với What's New (presenter đọc cùng khoá).
    static var flagKey: String { WhatsNewHost.hasSeenOnboardingKey }

    @AppStorage(WhatsNewHost.hasSeenOnboardingKey) private var hasSeenOnboarding = false
    private let onboarding: (_ finish: @escaping () -> Void) -> Onboarding
    private let main: () -> Main
    private let willFinishOnboarding: () -> Void

    init(@ViewBuilder onboarding: @escaping (_ finish: @escaping () -> Void) -> Onboarding,
         @ViewBuilder main: @escaping () -> Main, willFinishOnboarding: @escaping () -> Void = {}) {
        self.onboarding = onboarding
        self.main = main
        self.willFinishOnboarding = willFinishOnboarding
    }

    /// "Side effect trước, cờ sau": đổi cờ trước thì root đã chuyển sang `main` và presenter What's New có thể đánh
    /// giá lúc chưa ghi `lastSeen` ⇒ cài mới thấy sheet ngay sau tour.
    static func completeOnboarding(willFinish: () -> Void, markSeen: () -> Void) {
        willFinish()
        markSeen()
    }

    var body: some View {
        Group {
            if hasSeenOnboarding {
                main()
            } else {
                onboarding {
                    Self.completeOnboarding(willFinish: willFinishOnboarding, markSeen: { hasSeenOnboarding = true })
                }
            }
        }
        .task(id: hasSeenOnboarding) { AppTipState.onboardingFinished = hasSeenOnboarding }
    }
}
