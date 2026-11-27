import Foundation

/// Chọn thẻ cho sheet What's New — hàm thuần.
enum WhatsNewSelector {
    static let maxCards = 3

    enum Outcome {
        /// Không hiện sheet. `markSeen` ⇒ người gọi ghi `lastSeen = current` ngay.
        case none(markSeen: Bool)
        /// `from == nil` ⇒ khách cũ chưa có `lastSeen` ("Recent updates").
        case show(cards: [WhatsNewCard], moreCount: Int, from: AppVersion?)
    }

    static func select(lastSeen: AppVersion?, current: AppVersion, isExistingUser: Bool,
                       cards: [WhatsNewCard], usedCards: Set<String>, resolve: WhatsNewResolver) -> Outcome {
        // 1. Cài mới — đã có onboarding giới thiệu app.
        if lastSeen == nil && !isExistingUser { return .none(markSeen: true) }
        // 2. Cùng bản / hạ bản — không ghi lùi.
        if let ls = lastSeen, ls >= current { return .none(markSeen: false) }

        // 3. Thẻ trong khoảng (lastSeen, current]; chưa có lastSeen ⇒ mọi thẻ ≤ current.
        let inRange = cards.filter { card in
            let v = card.version.effective(current: current)
            guard let ls = lastSeen else { return v <= current }
            return ls < v && v <= current
        }
        // 4. Bỏ tính năng đã dùng — mọi thẻ. Bỏ thẻ có action mà không có đích dùng được — CHỈ thẻ của bản cũ: thẻ
        //    của bản mới nhất trong khoảng là tin chính của lần cập nhật này, chưa có đích (app chưa có dữ liệu cho
        //    nó) thì vẫn hiện, không nút. "Mới nhất trong khoảng" chứ không phải "== current": bản sửa lỗi không có
        //    thẻ riêng vẫn giới thiệu bản minor. Thẻ thông tin (không action) không có đích để thiếu ⇒ giữ.
        let newest = inRange.map { $0.version.effective(current: current) }.max()
        func isHeadline(_ card: WhatsNewCard) -> Bool { card.version.effective(current: current) == newest }
        let eligible = inRange
            .filter { !usedCards.contains($0.id) }
            .filter { isHeadline($0) || $0.action == nil || $0.resolvedAction(resolve) != nil }

        // 5. Thẻ bản mới nhất đứng đầu dù ưu tiên thấp hơn; trong mỗi nhóm theo `displayOrder`.
        guard !eligible.isEmpty else { return .none(markSeen: true) }
        let order = WhatsNewCard.displayOrder(current: current)
        let sorted = eligible.sorted { a, b in
            let ha = isHeadline(a), hb = isHeadline(b)
            return ha != hb ? ha : order(a, b)
        }
        return .show(cards: Array(sorted.prefix(maxCards)),
                     moreCount: max(0, sorted.count - maxCards),
                     from: lastSeen)
    }
}
