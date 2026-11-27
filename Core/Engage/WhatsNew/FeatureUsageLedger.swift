import Foundation

/// Ghi nhận "khách đã dùng tính năng của thẻ nào" — CHỈ trên máy.
///
/// - `Track.log` gọi `note(_:)` TRƯỚC sink, kể cả sink NoOp (khách tắt "Share usage data" vẫn được ghi nhận — dữ liệu
///   không rời máy). App gắn ledger vào `Track` TRƯỚC khi khởi động telemetry để không lỡ event nào của lần mở.
/// - `seedFromDiskIfNeeded(probe:)` chạy MỘT lần trong đời cài app (cờ `whatsNew.diskSeeded`).
/// - Idempotent: id chỉ được thêm, không bao giờ gỡ.
///
/// Thread-safe: telemetry log từ nhiều queue. Cố ý KHÔNG gọi lại telemetry từ đây (vòng lặp observer → log).
final class FeatureUsageLedger: UsageObserver {

    static let usedCardsKey = "whatsNew.usedCards"
    static let diskSeededKey = "whatsNew.diskSeeded"

    private let cards: [WhatsNewCard]
    private let defaults: UserDefaults
    private let lock = NSLock()

    init(cards: [WhatsNewCard], defaults: UserDefaults) {
        self.cards = cards
        self.defaults = defaults
    }

    /// Id thẻ đã coi là "đã dùng".
    var usedCards: Set<String> {
        lock.lock(); defer { lock.unlock() }
        return storedUsed()
    }

    func note(_ event: AppEvent) {
        let hit = cards.filter { $0.usedWhen(event) }.map(\.id)
        guard !hit.isEmpty else { return }
        lock.lock(); defer { lock.unlock() }
        add(hit)
    }

    /// Seed từ dấu vết có sẵn trên máy — chỉ lần đầu. Thẻ không có dấu vết ⇒ không seed được (chấp nhận).
    func seedFromDiskIfNeeded(probe: UsageProbe) {
        lock.lock(); defer { lock.unlock() }
        guard !defaults.bool(forKey: Self.diskSeededKey) else { return }
        add(cards.filter { $0.usedOnDisk(probe) }.map(\.id))
        defaults.set(true, forKey: Self.diskSeededKey)
    }

    // MARK: - Gọi khi đang giữ `lock`

    private func storedUsed() -> Set<String> {
        Set(defaults.stringArray(forKey: Self.usedCardsKey) ?? [])
    }

    private func add(_ ids: [String]) {
        let old = storedUsed()
        let new = old.union(ids)
        guard new != old else { return }
        // Sắp xếp để file defaults tất định (dễ đọc khi gỡ lỗi).
        defaults.set(new.sorted(), forKey: Self.usedCardsKey)
    }
}
