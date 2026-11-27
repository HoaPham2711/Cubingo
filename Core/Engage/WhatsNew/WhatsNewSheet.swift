import SwiftUI

/// Nơi khách bấm nút thẻ — param `surface` của `whats_new_cta`: `sheet` = thẻ trên sheet, `list` = danh sách đẩy từ
/// "+N more" của sheet (cả hai thuộc MỘT lần hiện ⇒ có `from_version`), `settings` = danh sách mở từ Settings (không
/// thuộc lần hiện nào ⇒ không `from_version`).
enum WhatsNewSurface: String {
    case sheet, list, settings
}

/// Sheet "What's new": tiêu đề, dòng phụ `Since X.Y.Z` / `Recent updates` (không đếm số bản), ≤ 3 thẻ,
/// "+N more · See all updates" (push danh sách đầy đủ TRONG stack của sheet), nút "Continue".
///
/// Sheet KHÔNG tự đóng chính nó: "Continue" và nút thẻ đều đi qua closure của người present (đặt
/// `presentation = nil`) ⇒ mọi lối đóng đều qua `onDismiss` của `.sheet(item:)` — nơi duy nhất gọi `sheetDidDismiss`
/// và chạy hành động thẻ. Modifier `.whatsNewSheet(presenter:resolve:run:)` nối sẵn đúng như vậy.
struct WhatsNewSheet: View {
    let presentation: WhatsNewPresenter.Presentation
    /// Toàn bộ catalog + bản đang cài — cho danh sách "See all updates".
    let cards: [WhatsNewCard]
    let current: AppVersion
    /// Đích nút thẻ của app — thẻ không có đích lúc vẽ thì không có nút.
    let resolve: WhatsNewResolver
    /// `WhatsNewPresenter.sheetDidAppear` — gọi từ `onAppear` của nội dung sheet.
    let onAppear: () -> Void
    /// Khách bấm nút thẻ (trên sheet hoặc trong danh sách đẩy từ sheet).
    let onAction: (WhatsNewCard, WhatsNewResolvedAction, WhatsNewSurface) -> Void
    let onContinue: () -> Void

    @State private var path: [Route] = []

    private enum Route: Hashable { case all }

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header
                    VStack(spacing: 12) {
                        ForEach(presentation.cards) { card in
                            WhatsNewCardView(card: card, resolved: card.resolvedAction(resolve)) {
                                onAction(card, $0, .sheet)
                            }
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 32)
                .padding(.bottom, 16)
                .readableContentWidth(DSLayout.formWidth)
            }
            .scrollBounceBehavior(.basedOnSize)
            .safeAreaInset(edge: .bottom) { bottomBar }
            .background(DSColor.pageBackground.ignoresSafeArea())
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: Route.self) { _ in
                WhatsNewListView(
                    // Nhãn "New for you" theo ĐÚNG lần hiện này (kể cả lần hiện thủ công — không ghi lastShownFrom).
                    sections: WhatsNewListModel.sections(cards: cards, current: current,
                                                         lastShownFrom: presentation.fromParam),
                    resolve: resolve, source: .sheet,
                    onRun: { card, action in onAction(card, action, .list) })
            }
        }
        .tint(DSColor.accent)
        .onAppear(perform: onAppear)
        .trackOverlayScreen("whats_new")
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("What's new")
                .font(.largeTitle.bold())
                .foregroundColor(DSColor.textPrimary)
            Group {
                if let from = presentation.from {
                    Text("Since \(from.description)")
                } else {
                    Text("Recent updates")
                }
            }
            .font(.subheadline)
            .foregroundColor(DSColor.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isHeader)
    }

    private var moreButton: some View {
        Button { path.append(.all) } label: {
            HStack(spacing: 6) {
                Text("+\(presentation.moreCount) more · See all updates")
                    .font(.subheadline.weight(.semibold))
                    .multilineTextAlignment(.leading)
                Image(systemName: "chevron.right")
                    .font(.footnote.weight(.semibold))
            }
            .foregroundColor(DSColor.accent)
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("whatsNew.more")
    }

    /// "+N more" nằm trong thanh dưới cố định, ngay trên Continue — KHÔNG trong vùng cuộn: form sheet iPad ngang
    /// thấp (~3 thẻ) và Dynamic Type lớn trên iPhone đều đẩy nó xuống dưới Continue, khách không biết còn thẻ để xem.
    private var bottomBar: some View {
        VStack(alignment: .leading, spacing: 12) {
            if presentation.moreCount > 0 { moreButton }
            continueButton
        }
        .padding(.horizontal, 20)
        .padding(.top, 8)
        .padding(.bottom, 12)
        .readableContentWidth(DSLayout.formWidth)
        .background(DSColor.pageBackground.ignoresSafeArea(edges: .bottom))
    }

    private var continueButton: some View {
        Button(action: onContinue) {
            Text("Continue")
                .font(.headline)
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .padding(.horizontal, 16)
                .foregroundColor(DSColor.onAccent)
                .background(Capsule().fill(DSColor.accent))
                .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("whatsNew.continue")
    }
}

/// Một thẻ trên sheet: icon, tiêu đề, body, nút capsule `ctaTitle`. Cỡ chữ trợ năng ⇒ icon lên trên để chữ và nút
/// có cả bề ngang (Dynamic Type `.accessibility2` không cắt nút).
struct WhatsNewCardView: View {
    let card: WhatsNewCard
    /// `nil` ⇒ thẻ không có action, hoặc đích không còn dùng được (trạng thái app đổi sau lúc chọn thẻ) ⇒ không vẽ
    /// nút chết.
    let resolved: WhatsNewResolvedAction?
    let onTap: (WhatsNewResolvedAction) -> Void

    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        let layout = typeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 12))
            : AnyLayout(HStackLayout(alignment: .top, spacing: 14))
        layout {
            WhatsNewIcon(systemImage: card.systemImage)
            VStack(alignment: .leading, spacing: 6) {
                // Chữ thẻ đã qua `String(localized:)` trong catalog của app.
                Text(card.title)
                    .font(.headline)
                    .foregroundColor(DSColor.textPrimary)
                Text(card.body)
                    .font(.subheadline)
                    .foregroundColor(DSColor.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
                if let resolved {
                    Button { onTap(resolved) } label: {
                        Text(card.ctaTitle)
                            .font(.subheadline.weight(.semibold))
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 8)
                            .foregroundColor(DSColor.onAccent)
                            .background(Capsule().fill(DSColor.accent))
                            .contentShape(Capsule())
                    }
                    .buttonStyle(.plain)
                    .padding(.top, 4)
                    .accessibilityIdentifier("whatsNew.cta.\(card.id)")
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(16)
        .background(RoundedRectangle(cornerRadius: DSRadius.card).fill(DSColor.cardBackground))
    }
}

/// Ô icon dùng chung cho thẻ sheet và dòng danh sách.
struct WhatsNewIcon: View {
    let systemImage: String
    var size: CGFloat = 44

    var body: some View {
        Image(systemName: systemImage)
            .font(.system(size: size * 0.45, weight: .semibold))
            .foregroundColor(DSColor.accent)
            .frame(width: size, height: size)
            .background(RoundedRectangle(cornerRadius: size * 0.27).fill(DSColor.accent.opacity(0.15)))
            .accessibilityHidden(true)
    }
}
