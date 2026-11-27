import Foundation

/// Một nhóm trong màn "What's new" đầy đủ — một bản.
struct WhatsNewListSection: Identifiable {
    /// Bản của nhóm; thẻ `.unreleased` nằm trong nhóm `current`.
    let version: AppVersion
    /// Đã sắp: ưu tiên ↓ rồi id ↑ (cùng luật với sheet).
    let cards: [WhatsNewCard]
    /// Bản mới hơn lần hiện sheet gần nhất (`whatsNew.lastShownFrom`).
    let isNewForYou: Bool

    var title: String { version.description }
    var id: String { title }
}

/// Nhóm thẻ theo bản cho `WhatsNewListView` — hàm thuần. Danh sách đầy đủ nên KHÔNG lọc thẻ đã dùng; dòng nào
/// mở được hành động do view hỏi resolver của app.
enum WhatsNewListModel {
    /// Giá trị `lastShownFrom` khi sheet hiện cho khách cũ chưa có mốc (không biết bản cũ).
    static let unknownFrom = "unknown"

    static func sections(cards: [WhatsNewCard], current: AppVersion,
                         lastShownFrom: String?) -> [WhatsNewListSection] {
        // nil / "unknown" / chuỗi hỏng ⇒ không nhóm nào có nhãn.
        let shownFrom = lastShownFrom.flatMap { $0 == unknownFrom ? nil : AppVersion($0) }
        let visible = cards.filter { $0.version.effective(current: current) <= current }

        // AppVersion không Hashable (== có đệm 0) ⇒ gom bằng mảng, giữ thứ tự xác định.
        var groups: [(version: AppVersion, cards: [WhatsNewCard])] = []
        for card in visible {
            let v = card.version.effective(current: current)
            if let i = groups.firstIndex(where: { $0.version == v }) {
                groups[i].cards.append(card)
            } else {
                groups.append((v, [card]))
            }
        }
        let order = WhatsNewCard.displayOrder(current: current)
        return groups
            .sorted { $0.version > $1.version }
            .map { g in
                WhatsNewListSection(version: g.version, cards: g.cards.sorted(by: order),
                                    isNewForYou: shownFrom.map { g.version > $0 } ?? false)
            }
    }
}
