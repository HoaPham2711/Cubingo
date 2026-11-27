import Foundation

/// Cấu hình của app đọc lúc chạy từ Info.plist. Nguồn: `app.config.toml` → `appconfig.py render` →
/// `Identity.xcconfig` → khoá Info trong `AppHost/project.yml`. Công tắc tính năng đọc ở đây, không `#if`.
///
/// Khoá vắng hoặc rỗng ⇒ `nil` / `[]` / `false` — không bao giờ crash (host test, preview, plist thiếu khoá).
struct AppConfig: Equatable {
    struct Features: Equatable {
        var paywall: Bool
        var appleAds: Bool
        var webAPI: Bool
    }

    var displayName: String
    var bundleID: String
    var version: String
    var build: String
    var appStoreID: String?
    var webHost: String?
    var supportEmail: String?
    var productIDs: [String]
    var features: Features

    init(info: [String: Any]) {
        func text(_ key: String) -> String? {
            guard let s = info[key] as? String, !s.isEmpty else { return nil }
            return s
        }
        func flag(_ key: String) -> Bool {
            if let b = info[key] as? Bool { return b }
            guard let s = info[key] as? String else { return false }
            return ["YES", "TRUE", "1"].contains(s.uppercased())
        }
        displayName = text("CFBundleDisplayName") ?? text("CFBundleName") ?? ""
        bundleID = text("CFBundleIdentifier") ?? ""
        version = text("CFBundleShortVersionString") ?? ""
        build = text("CFBundleVersion") ?? ""
        appStoreID = text("AppStoreID")
        webHost = text("WebHost")
        supportEmail = text("SupportEmail")
        productIDs = (text("ProductIDs") ?? "").split(whereSeparator: \.isWhitespace).map(String.init)
        features = Features(paywall: flag("FeaturePaywall"), appleAds: flag("FeatureAppleAds"),
                            webAPI: flag("FeatureWebAPI"))
    }

    static let current = AppConfig(info: Bundle.main.infoDictionary ?? [:])

    /// `https://<webHost>/<path>`; `nil` khi app không có web.
    private func webURL(_ path: String) -> URL? {
        guard let webHost else { return nil }
        return URL(string: "https://\(webHost)/\(path)")
    }

    var siteURL: URL? { webURL("") }
    var privacyURL: URL? { webURL("privacy/") }
    var termsURL: URL? { webURL("terms/") }
    var supportURL: URL? { webURL("support/") }
    /// Gốc API — cùng host với site.
    var apiBaseURL: URL? { webURL("") }
}
