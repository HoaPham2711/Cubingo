import Foundation

/// Link vào app (Universal Link) đã tách: các đoạn đường dẫn (đã giải percent-encoding, bỏ đoạn rỗng) + query.
/// `https://<host>/` ⇒ `path == []` (gốc). Query trùng khoá ⇒ giá trị CUỐI thắng; khoá không có giá trị ⇒ `""`.
struct AppLink: Equatable {
    let path: [String]
    let query: [String: String]
}

/// Bộ định tuyến link thuần: URL ngoài ⇒ `AppLink` (hoặc bỏ), rồi giao cho app qua `WhatsNewPresenter`.
/// App gắn `.onOpenURL` + `.onContinueUserActivity(NSUserActivityTypeBrowsingWeb)` ở cấp App và gọi `route`; ánh xạ
/// `AppLink` ⇒ màn là việc của app. Chỉ nhận `https` đúng host web đang chạy (`AppConfig.webHost`: bản Debug/Internal =
/// host dev, Release = host prod) — host lạ/`http`/scheme khác ⇒ bỏ, không mở màn nào.
enum AppLinkRouter {
    /// URL `https` với host == `expectedHost` (không phân biệt hoa thường; so nguyên văn — host có dấu chấm cuối hay
    /// dạng Unicode khác dạng punycode của cấu hình ⇒ khác) ⇒ `AppLink`; có cổng/user/mật khẩu, khác host (hoặc app
    /// không có host) ⇒ `nil`. Query theo `URLComponents`: `+` giữ nguyên là `+`. Không bao giờ crash.
    static func parse(_ url: URL, expectedHost: String?) -> AppLink? {
        guard let expectedHost, !expectedHost.isEmpty,
              let comps = URLComponents(url: url, resolvingAgainstBaseURL: false),
              comps.scheme?.lowercased() == "https",
              // `encodedHost`: dạng ASCII/punycode như cấu hình (`host` giải IDN ra Unicode ⇒ không bao giờ khớp).
              let host = comps.encodedHost, host.caseInsensitiveCompare(expectedHost) == .orderedSame,
              // Universal Link thật không bao giờ có cổng hay user/mật khẩu — có ⇒ URL dựng tay, bỏ.
              comps.port == nil, comps.user == nil, comps.password == nil
        else { return nil }
        // Tách trên đường dẫn CÒN mã hoá rồi mới giải từng đoạn: `%2F` trong một đoạn không được thành dấu phân cách.
        let path = comps.percentEncodedPath.split(separator: "/", omittingEmptySubsequences: true)
            .map { String($0).removingPercentEncoding ?? String($0) }
        var query: [String: String] = [:]
        for item in comps.queryItems ?? [] {
            query[item.name] = item.value ?? ""
        }
        return AppLink(path: path, query: query)
    }

    /// Nhận URL ngoài: parse; hợp lệ ⇒ báo presenter (`noteAppLinkOpened`: What's New không hiện đè trong lượt dùng
    /// này) rồi giao `apply`. Sheet What's New đang trên màn ⇒ presenter giữ link tới khi sheet
    /// đóng (nhiều link liền nhau ⇒ link MỚI NHẤT thắng); không ⇒ `apply` ngay. Trả `false` khi URL bị bỏ.
    @MainActor @discardableResult
    static func route(_ url: URL, expectedHost: String?, whatsNew: WhatsNewPresenter,
                      apply: @escaping (AppLink) -> Void) -> Bool {
        guard let link = parse(url, expectedHost: expectedHost) else { return false }
        whatsNew.noteAppLinkOpened()
        if !whatsNew.routeIncomingLink({ apply(link) }) { apply(link) }
        return true
    }
}
