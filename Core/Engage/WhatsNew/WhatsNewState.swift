import Foundation

/// Trạng thái What's New trong UserDefaults. `defaults` inject được — test dùng suite riêng, không ghi
/// `UserDefaults.standard` của host.
///
/// Bốn key của tính năng:
/// - `whatsNew.lastSeenVersion`, `whatsNew.lastShownFrom` — do struct này quản.
/// - `whatsNew.usedCards`, `whatsNew.diskSeeded` — của `FeatureUsageLedger` (có khoá riêng, ghi từ nhiều queue);
///   ở đây chỉ nêu tên cho đủ bảng key, KHÔNG đọc/ghi — muốn biết thẻ đã dùng thì hỏi ledger.
struct WhatsNewState {
    static let lastSeenKey = "whatsNew.lastSeenVersion"
    static let lastShownFromKey = "whatsNew.lastShownFrom"
    static let usedCardsKey = FeatureUsageLedger.usedCardsKey
    static let diskSeededKey = FeatureUsageLedger.diskSeededKey

    /// Giá trị `lastShownFrom` khi sheet hiện cho khách cũ chưa có `lastSeen` ("Recent updates").
    static let unknownFrom = "unknown"

    let defaults: UserDefaults

    /// Bản cuối cùng khách đã xem xong phần What's New. Chuỗi hỏng ⇒ `nil` (coi như chưa có).
    var lastSeen: AppVersion? {
        defaults.string(forKey: Self.lastSeenKey).flatMap(AppVersion.init)
    }

    /// `from` của lần hiện sheet gần nhất (`"unknown"` khi khách cũ chưa có mốc) — cho nhãn "New for you" của danh
    /// sách.
    var lastShownFrom: String? {
        defaults.string(forKey: Self.lastShownFromKey)
    }

    /// Ghi `lastSeen` — chỉ TIẾN, không bao giờ lùi (khách hạ bản / cài bản cũ hơn thì giữ mốc cao nhất).
    func recordSeen(_ version: AppVersion) {
        if let old = lastSeen, old >= version { return }
        defaults.set(version.description, forKey: Self.lastSeenKey)
    }

    func recordShown(from: AppVersion?) {
        defaults.set(from?.description ?? Self.unknownFrom, forKey: Self.lastShownFromKey)
    }
}
