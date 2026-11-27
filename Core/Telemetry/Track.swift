import Foundation

/// Điểm vào duy nhất của call site. Cố tình là `enum` tĩnh: telemetry phải gọi được từ mọi nơi
/// (kể cả sâu trong queue nền) mà không phải luồn một dependency qua 10 tầng.
///
/// Mặc định là `NoOpSink`. Chỉ bước khởi động của app mới gắn sink thật, và chỉ trên device.
/// Hệ quả cố ý: test không cần biết gì về telemetry vẫn tự động an toàn — không mạng, không
/// Firebase. An toàn là trạng thái mặc định, không phải thứ mỗi test phải nhớ bật.
enum Track {

    /// `Track` bị gọi từ nhiều queue (việc nền, UI chạy main) nên biến tĩnh phải có khoá.
    private static let lock = NSLock()
    nonisolated(unsafe) private static var sink: AnalyticsSink = NoOpSink()
    /// Ghi nhận "đã dùng tính năng" trên máy (What's New, `FeatureUsageLedger`). Tách khỏi `sink`: KHÔNG phụ
    /// thuộc "Share usage data" — tắt chia sẻ không được tắt ghi nhận trên máy.
    nonisolated(unsafe) private static var usageObserver: UsageObserver = NoOpUsageObserver()

    static func install(_ newSink: AnalyticsSink) {
        lock.lock(); defer { lock.unlock() }
        sink = newSink
    }

    /// Gỡ SINK về NoOp — dùng khi user tắt "Share usage data", và trong `tearDown` của test.
    /// Cố ý KHÔNG gỡ `usageObserver`: tắt chia sẻ không được tắt ghi nhận trên máy. Test gỡ observer
    /// bằng `removeUsageObserver()`.
    static func reset() {
        install(NoOpSink())
    }

    /// Sink hiện tại có phải NoOp không — cho test và cổng khởi động kiểm "chưa gắn sink thật".
    static var isUsingNoOpSink: Bool {
        lock.lock(); defer { lock.unlock() }
        return sink is NoOpSink
    }

    static func installUsageObserver(_ observer: UsageObserver) {
        lock.lock(); defer { lock.unlock() }
        usageObserver = observer
    }

    /// Về no-op — cho `tearDown` của test.
    static func removeUsageObserver() {
        installUsageObserver(NoOpUsageObserver())
    }

    static func log(_ event: AppEvent) {
        lock.lock(); let s = sink; let o = usageObserver; lock.unlock()
        // Observer TRƯỚC sink: sink thật có thể chậm/throw ở tầng dưới, ghi nhận trên máy không được phụ thuộc nó.
        o.note(event)
        s.log(event)
    }

    static func set(_ property: UserProperty) {
        lock.lock(); let s = sink; lock.unlock()
        s.set(property)
    }

    /// Ngữ cảnh cho crash report — xem `DiagnosticKey`.
    static func diagnostic(_ key: DiagnosticKey, _ value: String) {
        lock.lock(); let s = sink; lock.unlock()
        s.diagnostic(key, value)
    }

    static func nonFatal(_ domain: NonFatal.Domain, code: String, detail: String = "") {
        lock.lock(); let s = sink; lock.unlock()
        s.nonFatal(NonFatal(domain: domain, code: code, detail: detail))
    }

    /// Mốc vòng đời cho log crash — xem `Breadcrumb`.
    static func breadcrumb(_ crumb: Breadcrumb) {
        lock.lock(); let s = sink; lock.unlock()
        s.breadcrumb(crumb)
    }
}

/// Nghe mọi event của `Track.log` (gọi ngoài khoá, trên queue của người gọi) — cài đặt phải tự thread-safe
/// và KHÔNG được gọi lại `Track` (vòng lặp).
protocol UsageObserver: AnyObject {
    func note(_ event: AppEvent)
}

/// Mặc định của `Track` khi chưa gắn ledger: host unit test (app không gắn) và khoảng trước `init()` của App.
/// Simulator ngoài host test VẪN gắn ledger thật (khác `sink` — sink thật chỉ có trên device).
final class NoOpUsageObserver: UsageObserver {
    func note(_ event: AppEvent) {}
}
