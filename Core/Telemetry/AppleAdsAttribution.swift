import Foundation

/// Kết quả một lần hỏi API attribution của Apple.
enum AttributionFetchOutcome: Equatable {
    /// 200 + thân đọc được.
    case resolved(AttributionResult)
    /// 404 — Apple chưa có dữ liệu (gọi quá sớm sau khi lấy token), thử lại sau 5 s.
    case notReady
    /// `"token"` | `"network"` | `"parse"` | `"http_<status>"`.
    case failed(code: String)
}

/// Lấy token AdServices rồi hỏi Apple. Bản thật: `LiveAttributionClient` (chỗ duy nhất dùng AdServices).
protocol AttributionClient: Sendable {
    func fetch() async -> AttributionFetchOutcome
}

/// Chốt nguồn cài của lượt cài này: `apple_ads` / `organic` / `unknown`, gán thành thuộc tính GA4.
///
/// Logic thuần — mạng, đồng hồ, sleep, consent đều tiêm vào. Là `actor` vì có hai lối gọi có thể
/// chồng nhau: lúc khởi động và lúc user bật lại "Share usage data" (`TelemetryBootstrap.consentDidChange`).
actor AppleAdsAttribution {

    static let retryDelay: TimeInterval = 5
    /// Số lần gọi tối đa mỗi lần chạy khi Apple trả 404 (khuyến nghị của Apple).
    static let maxCallsPerRun = 3
    /// Chốt `unknown` sau chừng này lần chạy CÓ gọi mạng…
    static let giveUpRuns = 5
    /// …hoặc sau chừng này thời gian kể từ lần thử đầu.
    static let giveUpAge: TimeInterval = 7 * 24 * 3600

    static let resultKey = "attribution.result"
    static let runsKey = "attribution.runs"
    static let firstTryKey = "attribution.firstTry"
    static let callsKey = "attribution.calls"

    private let client: AttributionClient
    private let defaults: UserDefaults
    private let now: @Sendable () -> Date
    private let sleep: @Sendable (TimeInterval) async -> Void
    private let consent: @Sendable () -> Bool
    private var inFlight = false

    init(client: AttributionClient, defaults: UserDefaults,
         now: @escaping @Sendable () -> Date,
         sleep: @escaping @Sendable (TimeInterval) async -> Void,
         consent: @escaping @Sendable () -> Bool) {
        self.client = client
        self.defaults = defaults
        self.now = now
        self.sleep = sleep
        self.consent = consent
    }

    func resolveIfNeeded() async {
        // Actor cho phép chen ngang ở mỗi `await` ⇒ cờ này mới là thứ chặn hai luồng mạng song song.
        guard !inFlight else { return }
        inFlight = true
        defer { inFlight = false }

        guard defaults.data(forKey: Self.resultKey) == nil else { return }
        // Consent tắt: không gọi và KHÔNG đếm lần chạy — người bật lại sau vẫn được thử đủ.
        guard consent() else { return }

        let runs = defaults.integer(forKey: Self.runsKey) + 1
        defaults.set(runs, forKey: Self.runsKey)
        let firstTry = (defaults.object(forKey: Self.firstTryKey) as? Date) ?? now()
        defaults.set(firstTry, forKey: Self.firstTryKey)

        vong: for lan in 1...Self.maxCallsPerRun {
            guard consent() else { return }
            let calls = defaults.integer(forKey: Self.callsKey) + 1
            defaults.set(calls, forKey: Self.callsKey)
            switch await client.fetch() {
            case let .resolved(r):
                chot(r)
                return
            case .notReady:
                if lan < Self.maxCallsPerRun { await sleep(Self.retryDelay) }
            case let .failed(code):
                // Lỗi khác 404 thì thử lại ngay cũng vô ích — để lần mở app sau.
                Track.nonFatal(.attribution, code: code)
                break vong
            }
        }

        if runs >= Self.giveUpRuns || now().timeIntervalSince(firstTry) >= Self.giveUpAge {
            chot(AttributionResult(source: .unknown, campaign: nil, adGroup: nil, keyword: nil,
                                   country: nil, conversion: nil, attempts: 0))
        }
    }

    /// Gán lại thuộc tính từ kết quả đã lưu, không gọi mạng, không bắn event. No-op nếu chưa chốt.
    nonisolated static func applyStoredProperties(defaults: UserDefaults) {
        guard let data = defaults.data(forKey: resultKey),
              let r = try? JSONDecoder().decode(AttributionResult.self, from: data) else { return }
        ganThuocTinh(r)
    }

    // MARK: - Riêng

    private func chot(_ ketQua: AttributionResult) {
        var r = ketQua
        r.attempts = defaults.integer(forKey: Self.callsKey)
        if let data = try? JSONEncoder().encode(r) { defaults.set(data, forKey: Self.resultKey) }
        Self.ganThuocTinh(r)
        Track.log(.attributionResolved(r))
    }

    private static func ganThuocTinh(_ r: AttributionResult) {
        Track.set(.acqSource(r.source.rawValue))
        guard r.source == .appleAds else { return }
        if let c = r.campaign { Track.set(.asaCampaign(c)) }
        if let k = r.keyword { Track.set(.asaKeyword(k)) }
    }
}
