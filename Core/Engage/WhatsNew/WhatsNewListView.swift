import SwiftUI

/// Danh sách đầy đủ "What's new" — MỘT màn cho cả "+N more · See all updates" của sheet lẫn Settings › What's new.
/// Nhóm theo bản (mới trên cùng, `WhatsNewListModel`); bản mới hơn lần hiện sheet gần nhất có nhãn "New for you".
/// Dòng có đích dùng được (resolver trả khác nil) bấm được, không thì chỉ chữ (không nút chết).
struct WhatsNewListView: View {
    /// Param `source` của `whats_new_list_open`.
    enum Source: String {
        case sheet, settings
    }

    let sections: [WhatsNewListSection]
    let resolve: WhatsNewResolver
    let source: Source
    let onRun: (WhatsNewCard, WhatsNewResolvedAction) -> Void

    /// `onAppear` bắn lại khi quay về từ màn khác — chỉ đếm một lần mỗi lần mở danh sách.
    @State private var didLogOpen = false

    var body: some View {
        List {
            ForEach(sections) { section in
                Section {
                    ForEach(section.cards) { card in
                        row(card, resolved: card.resolvedAction(resolve))
                    }
                } header: {
                    header(section)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(DSColor.pageBackground.ignoresSafeArea())
        .navigationTitle("What's new")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar(.visible, for: .navigationBar)
        .trackOverlayScreen("whats_new_list")
        .onAppear {
            guard !didLogOpen else { return }
            didLogOpen = true
            Track.log(.whatsNewListOpen(source: source.rawValue))
        }
    }

    private func header(_ section: WhatsNewListSection) -> some View {
        HStack(spacing: 8) {
            Text("Version \(section.title)")
            if section.isNewForYou {
                Text("New for you")
                    .font(.caption2.weight(.semibold))
                    .textCase(nil)
                    .foregroundColor(DSColor.onAccent)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Capsule().fill(DSColor.accent))
            }
        }
    }

    @ViewBuilder
    private func row(_ card: WhatsNewCard, resolved: WhatsNewResolvedAction?) -> some View {
        if let resolved {
            Button { onRun(card, resolved) } label: {
                HStack(alignment: .center, spacing: 12) {
                    rowText(card, cta: card.ctaTitle)
                    Image(systemName: "chevron.right")
                        .font(.footnote.weight(.semibold))
                        .foregroundColor(DSColor.textTertiary)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("whatsNew.row.\(card.id)")
        } else {
            rowText(card, cta: nil)
        }
    }

    private func rowText(_ card: WhatsNewCard, cta: String?) -> some View {
        HStack(alignment: .top, spacing: 12) {
            WhatsNewIcon(systemImage: card.systemImage, size: 36)
            VStack(alignment: .leading, spacing: 4) {
                // Chữ thẻ đã qua `String(localized:)` trong catalog của app.
                Text(card.title)
                    .font(.headline)
                    .foregroundColor(DSColor.textPrimary)
                Text(card.body)
                    .font(.subheadline)
                    .foregroundColor(DSColor.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
                if let cta {
                    Text(cta)
                        .font(.subheadline.weight(.semibold))
                        .foregroundColor(DSColor.accent)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.vertical, 4)
    }
}

extension WhatsNewListView {
    /// Danh sách mở từ Settings (đặt trong `NavigationStack` của Settings): nhóm theo catalog + lần hiện gần nhất của
    /// presenter, nút dòng ghi `whats_new_cta` (surface `settings`, không `from_version`) rồi giao `run` ngay — không
    /// có sheet nào để đợi đóng.
    @MainActor
    static func settings(presenter: WhatsNewPresenter, resolve: @escaping WhatsNewResolver,
                         run: @escaping WhatsNewRunner) -> WhatsNewListView {
        WhatsNewListView(
            sections: WhatsNewListModel.sections(cards: presenter.cards, current: presenter.current,
                                                 lastShownFrom: presenter.lastShownFrom),
            resolve: resolve, source: .settings,
            onRun: { card, action in presenter.runFromSettingsList(card, action) { run($0) } })
    }
}
