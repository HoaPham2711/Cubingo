#if INTERNAL
import SwiftUI

/// Section "Review prompt" cho màn debug của app: thử luật mời đánh giá thật trên build nội bộ — giả lập user App
/// Store, reset về user mới chưa từng được hỏi, xem sổ + trạng thái phiên + luật sẽ trả gì ngay lúc này.
///
/// Lõi không biết `ReviewScheduler` của app (nó cần cổng "đang rảnh" và hàm present của vỏ app) nên việc gài thử
/// đi qua closure `arm`: app truyền `{ scheduler.arm($0, bypassPolicy: true) }`. Đặt trong một `Form`/`List` (trả
/// về `Section`).
struct ReviewPromptDebugSection: View {
    @ObservedObject var prompter: ReviewPrompter
    let arm: (ReviewMoment) -> Void
    @AppStorage(ReviewPrompter.simulateStoreUserKey) private var simulateStoreUser = false
    @State private var showResetConfirm = false
    /// Tăng để đọc lại sổ (UserDefaults không tự báo SwiftUI).
    @State private var tick = 0

    init(prompter: ReviewPrompter, arm: @escaping (ReviewMoment) -> Void) {
        self.prompter = prompter
        self.arm = arm
    }

    var body: some View {
        let _ = tick
        let snap = prompter.debugSnapshot
        let now = Date()
        Section {
            Toggle(isOn: $simulateStoreUser) {
                VStack(alignment: .leading, spacing: 2) {
                    dtext("Chạy luật như user App Store")
                    dtext("Tắt = build nội bộ không bao giờ tự hỏi (mặc định)")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            Button(role: .destructive) {
                showResetConfirm = true
            } label: {
                Label { dtext("Reset như user mới (chưa từng rate)") }
                icon: { Image(systemName: "arrow.counterclockwise") }
            }
            Button {
                arm(.outputDone)
            } label: {
                Label { dtext("Gài thử hộp mời đánh giá (bỏ qua luật)") }
                icon: { Image(systemName: "star.fill") }
            }

            dong("Đã hỏi (365 ngày)", soLanHoi(snap.state, now: now))
            dong("Trả lời cuối", snap.state.lastAnswer?.rawValue ?? "—")
            dong("Not Now liên tiếp", "\(snap.state.consecutiveDeclines)")
            dong("Feedback gần nhất", snap.state.lastFeedbackSentDate.map { cach($0, now) } ?? "—")
            dong("Mục đã mở", "\(snap.state.openedItemIDs.count)")
            dong("Phiên: hành động giá trị", snap.friction.hadValueAction ? "có" : "chưa")
            dong("Phiên: bực mình gần", snap.friction.lastNegativeAt.map { cach($0, now) } ?? "—")
            dong("Phiên: tác vụ / restore lỗi",
                 "\(snap.friction.taskFailed ? "có" : "không") / \(snap.friction.restoreFailed ? "có" : "không")")
            dong("Luật lúc này · output xong", moTa(du(.outputDone, snap, now)))
            dong("Luật lúc này · đóng nội dung 30 s",
                 moTa(du(.contentClosed(dwellSeconds: 30, reopened: false), snap, now)))
            if let last = prompter.debugLastDecision {
                dong("Quyết định gần nhất",
                     "\(last.moment.analyticsSource) → \(moTa(last.decision)) · \(cach(last.at, now))")
            }
            Button { tick += 1 } label: {
                Label { dtext("Đọc lại") } icon: { Image(systemName: "arrow.clockwise") }
            }
        } header: {
            dtext("Review prompt")
        } footer: {
            dtext("Thử như user mới: bật \"Chạy luật như user App Store\" → Reset → làm một hành động giá trị "
                  + "hoặc xong output rồi đóng hết modal ⇒ hộp hỏi trước hiện. "
                  + "Not Now không đụng quota iOS; Rate ⇒ StoreKit tự quyết có hiện hộp sao hay không.")
        }
        // `.alert`, không `.confirmationDialog`: từ iOS 26 nó hiện dạng popover neo vào view gắn modifier.
        .alert(Text(verbatim: "Reset như user mới?"), isPresented: $showResetConfirm) {
            Button(role: .cancel) {} label: { dtext("Huỷ") }
            Button(role: .destructive) {
                prompter.debugResetAsNewUser()
                tick += 1
            } label: { dtext("Reset") }
        } message: {
            dtext("Xoá sổ mời đánh giá (lần hỏi, câu trả lời, feedback, mục đã mở) và trạng thái phiên.")
        }
    }

    /// Luật sẽ trả gì nếu moment xảy ra NGAY BÂY GIỜ — không ghi sổ.
    private func du(_ m: ReviewMoment, _ snap: (state: ReviewPromptState, friction: SessionFriction),
                    _ now: Date) -> ReviewDecision {
        ReviewPromptPolicy.decide(moment: m, state: snap.state, friction: snap.friction,
                                  isInternalBuild: !simulateStoreUser, now: now)
    }

    private func moTa(_ d: ReviewDecision) -> String {
        switch d {
        case .ask: return "HỎI"
        case .skip(let r): return "bỏ qua: \(r.rawValue)"
        }
    }

    private func soLanHoi(_ s: ReviewPromptState, now: Date) -> String {
        let trongNam = s.askDates.filter { now.timeIntervalSince($0) < 365 * 86400 }
        guard let cuoi = trongNam.max() else { return "0" }
        return "\(trongNam.count) · gần nhất \(cach(cuoi, now))"
    }

    private func cach(_ d: Date, _ now: Date) -> String {
        let giay = Int(now.timeIntervalSince(d))
        if giay < 60 { return "\(giay) s trước" }
        if giay < 3600 { return "\(giay / 60) phút trước" }
        if giay < 86400 { return "\(giay / 3600) giờ trước" }
        return "\(giay / 86400) ngày trước"
    }

    private func dong(_ title: String, _ value: String) -> some View {
        HStack {
            dtext(title)
            Spacer()
            dtext(value).foregroundStyle(.secondary).multilineTextAlignment(.trailing)
        }
        .font(.callout)
    }
}
#endif
