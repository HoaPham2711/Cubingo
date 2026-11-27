// `import StoreKit` chỉ ở ĐÚNG ba file: `Core/Purchases/LiveStoreClient.swift` (quyền + mua), file này (CHỈ để lấy
// `requestReview` của SwiftUI — hộp đánh giá hệ thống) và `Core/Shell/SettingsAccountSection.swift`
// (`manageSubscriptionsSheet`). Hai file UI không đọc/ghi trạng thái quyền (`docs/ARCHITECTURE.md` §"Quy tắc biên").
import StoreKit
import SwiftUI

/// Phần logic của hộp hỏi trước, tách khỏi SwiftUI để test được (đồng hồ và lời gọi hệ thống bơm vào).
enum ReviewPromptFlow {
    /// `requestReview()` chỉ được gọi SAU khi alert đã đóng hẳn: gọi ngay trong action thì alert còn đang
    /// dismiss và StoreKit có thể nuốt hộp hệ thống.
    static let requestDelay: TimeInterval = 0.5

    /// Hộp hỏi trước vừa hiện: ghi `review_ask` kèm nguồn của moment.
    static func asked(_ moment: ReviewMoment) {
        Track.log(.reviewAsk(source: moment.analyticsSource))
    }

    /// Ghi câu trả lời hộp hỏi trước; `Rate` ⇒ hộp hệ thống sau `requestDelay`. `Not Now` không chạm hộp hệ
    /// thống, nên không tiêu quota 3 lần/365 ngày của iOS.
    @MainActor
    static func answer(_ a: ReviewAnswer,
                       prompter: ReviewPrompter,
                       after: (TimeInterval, @escaping () -> Void) -> Void = { delay, work in
                           DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: work)
                       },
                       requestReview: @escaping () -> Void) {
        prompter.noteAnswer(a)
        Track.log(.reviewAnswer(outcome: a.rawValue))
        guard a == .rate else { return }
        after(requestDelay) {
            Track.log(.reviewPrompt)
            requestReview()
        }
    }
}

private struct ReviewPromptHost: ViewModifier {
    @ObservedObject var prompter: ReviewPrompter
    let appName: String
    /// `requestReview()` chỉ được gọi từ view gốc (đúng khuyến nghị StoreKit: gọi nhiều nơi dễ đụng quota
    /// 3 lần/365 ngày mà không kiểm soát được).
    @Environment(\.requestReview) private var requestReview

    func body(content: Content) -> some View {
        content
            .onChange(of: prompter.pendingAsk) { _, moment in
                if let moment { ReviewPromptFlow.asked(moment) }
            }
            // Hộp hỏi trước TRUNG TÍNH — không tách theo cảm nhận (guideline 5.6.1). `pendingAsk` chỉ được đặt
            // khi màn hình đã yên (`ReviewScheduler`), nên alert present từ gốc không bị modal nuốt.
            .alert("Rate \(appName)?",
                   isPresented: Binding(get: { prompter.pendingAsk != nil },
                                        set: { if !$0 { prompter.pendingAsk = nil } })) {
                Button("Not Now", role: .cancel) {
                    ReviewPromptFlow.answer(.later, prompter: prompter, requestReview: { requestReview() })
                }
                Button("Rate") {
                    ReviewPromptFlow.answer(.rate, prompter: prompter, requestReview: { requestReview() })
                }
            } message: {
                Text("A quick rating on the App Store helps other people find \(appName).")
            }
    }
}

extension View {
    /// Gắn ở view GỐC: hiện alert hỏi trước khi `prompter.pendingAsk` được gán, rồi gọi hộp đánh giá hệ thống
    /// khi user bấm Rate. `appName` do app cấp (thường `AppConfig.displayName`) — lõi không giữ tên app nào.
    func reviewPromptHost(prompter: ReviewPrompter, appName: String) -> some View {
        modifier(ReviewPromptHost(prompter: prompter, appName: appName))
    }
}
