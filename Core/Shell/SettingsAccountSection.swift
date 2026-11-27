import SwiftUI
// `import StoreKit` chỉ ở ĐÚNG ba file: `Core/Purchases/LiveStoreClient.swift` (quyền + mua),
// `Core/Engage/Review/ReviewPromptHost.swift` (`requestReview`) và file này — CHỈ dùng modifier
// `manageSubscriptionsSheet` (sheet hệ thống của StoreKit cho SwiftUI): UI thuần, không đọc/ghi trạng thái quyền, không
// có đường nào bọc nó sau protocol mà vẫn giữ hành vi sheet hệ thống (`docs/ARCHITECTURE.md` §"Quy tắc biên").
import StoreKit

/// State UI của nhóm Account (paywall, sheet quản lý gói, alert khôi phục). Tách khỏi hàng vì các modifier trình
/// bày (`fullScreenCover`, `.alert`) phải gắn ở view gốc của màn — gắn lên `Section`/hàng trong `List` thì hàng lười
/// bị dỡ khi cuộn khỏi màn là mất luôn chỗ neo.
@MainActor
final class SettingsAccountState: ObservableObject {
    @Published var showPaywall = false
    @Published var showManageSubscriptions = false
    /// Ba nhánh `RestoreOutcome` phải phân biệt được ở alert (`RestoreAlert.make`): gộp `.failed` (mất
    /// mạng) chung với `.noPurchasesFound` sẽ báo sai với người ĐÃ trả tiền rằng họ chưa từng mua.
    /// Cờ "đang khôi phục" KHÔNG ở đây mà ở `Entitlements.isRestoring` — dùng chung với paywall.
    @Published var restoreAlert: RestoreAlert?
}

/// Nhóm Account của Settings: trạng thái gói · Nâng cấp (mở paywall) hoặc Quản lý gói · Khôi phục mua hàng.
///
/// Chỉ dựng khi `SettingsModel.showsAccount(config:)` — paywall tắt = app miễn phí hoàn toàn, không hiện gì về Pro.
/// Phần trình bày đi kèm: `.settingsAccountPresentations(...)` gắn ở view gốc của màn.
struct SettingsAccountSection: View {
    @ObservedObject var entitlements: Entitlements
    @ObservedObject var state: SettingsAccountState
    let reviewPrompter: ReviewPrompter

    var body: some View {
        Section {
            // if/else thay cho ternary literal: hai nhánh là hai `LocalizedStringKey` chắc chắn được extract.
            if entitlements.isPro {
                Text("Pro active").foregroundColor(DSColor.textSecondary)
                // "Không tìm thấy chỗ huỷ" là nguồn 1-sao lớn nhất của app subscription. Mua trọn đời thì không có
                // gói nào để quản lý (sheet hệ thống trống) ⇒ ẩn (`canManageSubscription`).
                if entitlements.canManageSubscription {
                    Button("Manage subscription") { state.showManageSubscriptions = true }
                        .foregroundColor(DSColor.textPrimary)
                }
            } else {
                Text("Free plan").foregroundColor(DSColor.textSecondary)
                Button {
                    state.showPaywall = true
                } label: {
                    HStack {
                        Text("Upgrade to Pro").foregroundColor(DSColor.textPrimary)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption).foregroundColor(DSColor.textTertiary)
                    }
                }
            }
            // `Entitlements.restore()` gọi `StoreClient.sync()` thật rồi đối chiếu lại quyền — Apple yêu cầu có lối
            // Khôi phục ở nơi dễ thấy như thế này.
            Button { restore() } label: {
                HStack {
                    Text("Restore purchases").foregroundColor(DSColor.textPrimary)
                    if entitlements.isRestoring {
                        Spacer()
                        ProgressView()
                    }
                }
            }
            .disabled(entitlements.isRestoring)
        } header: {
            Text("Account")
        }
    }

    private func restore() {
        guard !entitlements.isRestoring else { return }
        let entitlements = entitlements, state = state, reviewPrompter = reviewPrompter
        Task { @MainActor in
            let outcome = await entitlements.restore()
            // `.restored`: không alert — `isPro` đổi phản ứng ngay trên hàng phía trên.
            state.restoreAlert = SettingsModel.restoreAlert(for: outcome)
            // Chỉ `.failed` (mất mạng/App Store) là bực mình app gây ra — `.noPurchasesFound` là kết quả hợp lệ
            // (chưa từng mua), không nên chặn hỏi đánh giá vì nó.
            if SettingsModel.countsAsReviewFriction(outcome) { reviewPrompter.noteRestoreFailed() }
        }
    }
}

extension View {
    /// Paywall, sheet quản lý gói và alert khôi phục của nhóm Account. Gắn ở view gốc của màn Settings.
    func settingsAccountPresentations(state: SettingsAccountState, entitlements: Entitlements,
                                      paywall: PaywallContent, reviewPrompter: ReviewPrompter) -> some View {
        modifier(SettingsAccountPresentations(state: state, entitlements: entitlements, paywall: paywall,
                                              reviewPrompter: reviewPrompter))
    }
}

private struct SettingsAccountPresentations: ViewModifier {
    @ObservedObject var state: SettingsAccountState
    let entitlements: Entitlements
    let paywall: PaywallContent
    let reviewPrompter: ReviewPrompter

    func body(content: Content) -> some View {
        content
            .fullScreenCover(isPresented: $state.showPaywall) {
                // `fullScreenCover` KHÔNG tự kế thừa environment object ⇒ truyền tường minh.
                PaywallView(entitlements: entitlements, content: paywall,
                            onDismissedWithoutPurchase: reviewPrompter.notePaywallDismissed)
                    .onAppear { Track.log(.paywallView(source: "settings")) }
            }
            .manageSubscriptionsSheet(isPresented: $state.showManageSubscriptions)
            .alert(state.restoreAlert?.title ?? "",
                   isPresented: Binding(get: { state.restoreAlert != nil },
                                        set: { if !$0 { state.restoreAlert = nil } })) {
                Button("Close", role: .cancel) { state.restoreAlert = nil }
            } message: {
                Text(verbatim: state.restoreAlert?.message ?? "")
            }
    }
}
