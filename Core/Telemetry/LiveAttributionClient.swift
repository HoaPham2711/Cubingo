import Foundation
import AdServices

/// Chỗ DUY NHẤT import AdServices. Lấy token attribution của lượt cài này rồi hỏi Apple.
/// Không IDFA, không ATT — AdServices được Apple thiết kế để không cần đồng ý theo dõi.
struct LiveAttributionClient: AttributionClient {
    static let endpoint = URL(string: "https://api-adservices.apple.com/api/v1/")!

    private let session: URLSession
    private let token: @Sendable () throws -> String

    init(session: URLSession = .shared,
         token: @escaping @Sendable () throws -> String = { try AAAttribution.attributionToken() }) {
        self.session = session
        self.token = token
    }

    func fetch() async -> AttributionFetchOutcome {
        let t: String
        do { t = try token() } catch { return .failed(code: "token") }
        var req = URLRequest(url: Self.endpoint, timeoutInterval: 10)
        req.httpMethod = "POST"
        req.setValue("text/plain", forHTTPHeaderField: "Content-Type")
        req.httpBody = Data(t.utf8)
        do {
            let (body, resp) = try await session.data(for: req)
            let status = (resp as? HTTPURLResponse)?.statusCode ?? 0
            #if INTERNAL
            print("[attribution] \(status) \(String(decoding: body, as: UTF8.self))")
            #endif
            return Self.outcome(status: status, body: body)
        } catch {
            return .failed(code: "network")
        }
    }

    /// Thuần, test được: map (status, body) → kết quả.
    static func outcome(status: Int, body: Data) -> AttributionFetchOutcome {
        switch status {
        case 200:
            guard let r = AttributionPayload.parse(body) else { return .failed(code: "parse") }
            return .resolved(r)
        case 404:
            return .notReady
        default:
            return .failed(code: "http_\(status)")
        }
    }
}

extension AppleAdsAttribution {
    /// Một instance cho cả app — `inFlight` chỉ chặn được chạy chồng khi mọi lối gọi đi qua cùng actor.
    static let shared = AppleAdsAttribution(
        client: LiveAttributionClient(), defaults: .standard,
        now: { Date() },
        sleep: { try? await Task.sleep(nanoseconds: UInt64($0 * 1_000_000_000)) },
        consent: { TelemetryConsent.isEnabled() })

    /// Gọi SAU khi sink vừa gắn (`TelemetryBootstrap.start`, và khi bật lại consent): gán lại thuộc tính đã
    /// lưu, rồi hỏi Apple ở nền nếu chưa chốt. No-op khi công tắc `[features] apple_ads` tắt, trong host unit
    /// test (không gọi mạng khi chạy test) và trên Simulator.
    static func startAtLaunch(appleAdsEnabled: Bool) {
        startAtLaunch(appleAdsEnabled: appleAdsEnabled, isUnitTestHost: AppEnvironment.isUnitTestHost,
                      isSimulator: AppEnvironment.isSimulator, defaults: .standard, attribution: shared)
    }

    /// Bản tiêm được (test). Trả `Task` đang hỏi Apple, hoặc `nil` khi không làm gì.
    @discardableResult
    static func startAtLaunch(appleAdsEnabled: Bool, isUnitTestHost: Bool, isSimulator: Bool,
                              defaults: UserDefaults, attribution: AppleAdsAttribution) -> Task<Void, Never>? {
        guard appleAdsEnabled, !isUnitTestHost, !isSimulator else { return nil }
        applyStoredProperties(defaults: defaults)
        return Task(priority: .utility) { await attribution.resolveIfNeeded() }
    }
}
