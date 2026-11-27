import Foundation

/// Nguồn "bản mới nhất trên App Store". Protocol để `UpdateChecker` test được bằng stub.
protocol AppStoreLookup: Sendable {
    /// `nil` = Store không có thông tin về app (chưa lên Store / không bán ở vùng này).
    func fetchLatest() async throws -> StoreRelease?
}

/// Gọi iTunes Lookup API — không backend, không SDK.
///
/// `country` = region thiết bị; có thể lệch storefront của Apple ID nhưng version hầu như giống
/// nhau giữa các storefront. App không bán ở vùng đó thì API trả `resultCount: 0` → hỏi lại một
/// lần không `country` (storefront US mặc định).
struct AppStoreLookupClient: AppStoreLookup {
    typealias Fetch = @Sendable (URL) async throws -> Data

    let appID: String
    let country: String?
    let fetch: Fetch

    /// `appID` bắt buộc, KHÔNG có mặc định: id là của từng app (`AppConfig.appStoreID`), lõi không giữ hằng nào.
    /// App chưa có id thì đừng dựng client này — `UpdateChecker.makeDefault(appID:)` lo ca đó.
    init(appID: String,
         country: String? = Locale.current.region?.identifier.lowercased(),
         fetch: @escaping Fetch = AppStoreLookupClient.liveFetch) {
        self.appID = appID
        self.country = country
        self.fetch = fetch
    }

    /// Có `country` mà rỗng → hỏi lại một lần không `country`. Không có `country` → nhánh
    /// `if let` bỏ qua, chỉ gọi đúng MỘT lần.
    func fetchLatest() async throws -> StoreRelease? {
        if let country, let r = try Self.parse(await fetch(Self.url(appID: appID, country: country))) {
            return r
        }
        return try Self.parse(await fetch(Self.url(appID: appID, country: nil)))
    }

    static func url(appID: String, country: String?) -> URL {
        var c = URLComponents(string: "https://itunes.apple.com/lookup")!
        c.queryItems = [URLQueryItem(name: "id", value: appID)]
            + (country.map { [URLQueryItem(name: "country", value: $0)] } ?? [])
        return c.url!
    }

    static func parse(_ data: Data) throws -> StoreRelease? {
        let resp = try JSONDecoder().decode(Response.self, from: data)
        guard let e = resp.results.first else { return nil }
        return StoreRelease(version: e.version, minimumOsVersion: e.minimumOsVersion, url: e.trackViewUrl,
                            releaseNotes: e.releaseNotes)
    }

    /// Không cache HTTP: `UpdateChecker` đã tự throttle 24h, cache URLSession chồng lên chỉ làm
    /// bản mới hiện trễ thêm.
    static let liveFetch: Fetch = { url in
        let req = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 10)
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard (resp as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
        return data
    }

    private struct Response: Decodable {
        let results: [Entry]
    }

    private struct Entry: Decodable {
        let version: String
        let minimumOsVersion: String
        let trackViewUrl: URL
        /// Không phải app nào/bản nào cũng có ⇒ Optional, thiếu không làm hỏng parse.
        let releaseNotes: String?
    }
}
