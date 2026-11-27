import Foundation

/// Kiểm tra App Store có bản mới hơn không.
///
/// Do app sở hữu ở cấp gốc, truyền TƯỜNG MINH xuống view (không `@EnvironmentObject`, cùng lý do với
/// `Entitlements`). Gọi `checkIfNeeded()` mỗi lần app vào `.active`; tự throttle 24h.
@MainActor
final class UpdateChecker: ObservableObject {
    static let checkInterval: TimeInterval = 86_400

    enum Key {
        static let lastCheck = "updateCheck.lastCheck"
        static let lastRelease = "updateCheck.lastRelease"
        static let dismissedVersion = "updateCheck.dismissedVersion"
    }

    @Published private(set) var status: UpdateStatus = .upToDate
    @Published private var dismissedVersion: String?

    /// `nil` = app không có App Store id ⇒ không có gì để tra, `checkIfNeeded()` không làm gì.
    private let lookup: AppStoreLookup?
    private let defaults: UserDefaults
    private let installedVersion: String
    private let osVersion: String
    private let now: () -> Date
    private var inFlight = false

    init(lookup: AppStoreLookup?,
         defaults: UserDefaults = .standard,
         installedVersion: String = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "",
         osVersion: String = UpdateChecker.currentOSVersion,
         now: @escaping () -> Date = Date.init) {
        self.lookup = lookup
        self.defaults = defaults
        self.installedVersion = installedVersion
        self.osVersion = osVersion
        self.now = now
        dismissedVersion = defaults.string(forKey: Key.dismissedVersion)
        // Kết quả lần trước → banner hiện ngay khi mở app, không đợi mạng. Evaluate LẠI theo
        // version đang cài: user đã cập nhật thì bản lưu cũ tự thành `.upToDate`.
        let saved = defaults.data(forKey: Key.lastRelease)
            .flatMap { try? JSONDecoder().decode(StoreRelease.self, from: $0) }
        status = UpdateEvaluator.evaluate(installed: installedVersion, osVersion: osVersion, release: saved)
    }

    var showsHomeBanner: Bool {
        UpdateEvaluator.shouldShowBanner(status: status, dismissedVersion: dismissedVersion)
    }

    func checkIfNeeded() async {
        guard let lookup else { return }
        guard !inFlight else { return }
        if let last = defaults.object(forKey: Key.lastCheck) as? Date {
            let elapsed = now().timeIntervalSince(last)
            // elapsed < 0 = đồng hồ máy bị lùi; không được để nó chặn check mãi.
            if elapsed >= 0, elapsed < Self.checkInterval { return }
        }
        inFlight = true
        defer { inFlight = false }
        do {
            let release = try await lookup.fetchLatest()
            defaults.set(now(), forKey: Key.lastCheck)
            if let release, let data = try? JSONEncoder().encode(release) {
                defaults.set(data, forKey: Key.lastRelease)
            } else {
                defaults.removeObject(forKey: Key.lastRelease)
            }
            status = UpdateEvaluator.evaluate(installed: installedVersion, osVersion: osVersion, release: release)
        } catch {
            // Im lặng, giữ status cũ, KHÔNG ghi lastCheck → lần active sau thử lại.
        }
    }

    /// × trên banner Home. Chỉ ẩn cho version đang hiện; bản mới hơn sẽ hiện lại.
    func dismissBanner() {
        guard case .available(let version, _, _) = status else { return }
        dismissedVersion = version
        defaults.set(version, forKey: Key.dismissedVersion)
    }

    nonisolated static var currentOSVersion: String {
        let v = ProcessInfo.processInfo.operatingSystemVersion
        return "\(v.majorVersion).\(v.minorVersion).\(v.patchVersion)"
    }

    /// `appID` lấy từ `AppConfig.appStoreID`. Nil/rỗng/toàn khoảng trắng ⇒ checker KHÔNG có nguồn tra:
    /// không gọi mạng, không ghi gì, `status` luôn `.upToDate` (app chưa lên Store thì Lookup chỉ trả rỗng,
    /// gọi chỉ tốn mạng). `fetch`/`defaults` bơm được cho test; mặc định là mạng thật và `UserDefaults.standard`.
    static func makeDefault(appID: String?,
                            defaults: UserDefaults = .standard,
                            fetch: @escaping AppStoreLookupClient.Fetch = AppStoreLookupClient.liveFetch) -> UpdateChecker {
        guard let appID, !appID.trimmingCharacters(in: .whitespaces).isEmpty else {
            return UpdateChecker(lookup: nil, defaults: defaults)
        }
        return UpdateChecker(lookup: AppStoreLookupClient(appID: appID, fetch: fetch), defaults: defaults)
    }
}
