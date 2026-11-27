import Foundation
// KHÔNG import Firebase* ở đây: chỉ `AppCheckTokenSource.swift` được phép (lint_firebase_imports.py). Lấy token
// App Check qua facade đó, không gọi thẳng `AppCheck.appCheck()`.

/// Gửi phản hồi về API của app (`POST <baseURL>/api/v1/feedback`). Gốc API là tham số bắt buộc — app đọc nó ở
/// `AppConfig.apiBaseURL` (host theo config: Debug/Internal vào host dev, Release vào host prod) nên không có hằng
/// số host nào phải nhớ đổi trước khi ship. Chỉ được nối vào app khi `[features] web_api = true` (xem
/// `AppHost/Config/Features.generated.yml`).
///
/// Mã lỗi: ngoài 2xx là `.rejected(mã)` (4xx lẫn 5xx), mất mạng/hết giờ là `.offline`. Không ghi nội dung phản hồi
/// hay chẩn đoán ra log ở bản Store: chỉ ghi host, mã trạng thái và có/không token, qua `applog` (`.private`).
final class WebAPIFeedbackTransport: FeedbackTransport {

    static let path = "api/v1/feedback"
    /// Trần thời gian chờ một lần gửi (giây). Mặc định của URLSession là 60 s — quá lâu cho một form đang quay.
    static let requestTimeout: TimeInterval = 20
    static let appCheckHeader = "X-Firebase-AppCheck"

    private let baseURL: URL
    private let session: URLSession
    private let appVersion: String
    private let token: () async -> String?

    init(baseURL: URL, appVersion: String, session: URLSession = .shared,
         token: @escaping () async -> String? = AppCheckTokenSource.currentToken) {
        self.baseURL = baseURL
        self.appVersion = appVersion
        self.session = session
        self.token = token
    }

    static func feedbackURL(baseURL: URL) -> URL {
        baseURL.appendingPathComponent(path)
    }

    func send(_ draft: FeedbackDraft) async throws {
        // Body (kèm validate) dựng TRƯỚC mọi thứ có thể ra mạng — kể cả lấy token.
        let body = try FeedbackRequestEncoder.body(for: draft, appVersion: appVersion, clientTime: Date())

        var req = URLRequest(url: Self.feedbackURL(baseURL: baseURL), timeoutInterval: Self.requestTimeout)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = body

        // App Check là lớp chứng minh "người gửi là app thật" (máy chủ còn giới hạn tần suất theo IP). Không lấy được
        // token thì vẫn gửi, không header — máy chủ quyết định; chặn ở client chỉ làm mất phản hồi thật.
        let appCheckToken = await token()
        if let appCheckToken {
            req.setValue(appCheckToken, forHTTPHeaderField: Self.appCheckHeader)
        }
        applog("[feedback] POST \(req.url?.host ?? "?") appcheck=\(appCheckToken == nil ? "NIL" : "có")")

        let data: Data
        let resp: URLResponse
        do {
            (data, resp) = try await session.data(for: req)
        } catch {
            applog("[feedback] không gửi được: \((error as? URLError)?.code.rawValue ?? 0)")
            throw FeedbackSendError.offline
        }
        guard let http = resp as? HTTPURLResponse else { throw FeedbackSendError.offline }
        guard (200..<300).contains(http.statusCode) else {
            applog("[feedback] bị từ chối \(http.statusCode)")
            #if INTERNAL
            // Body của API nói rõ nguyên nhân (vd `app_check_failed`, `rate_limited`, field nào sai). Chỉ build
            // INTERNAL, qua `applog`; cắt ngắn vì body có thể dài.
            applog("[feedback] body: " + String((String(data: data, encoding: .utf8) ?? "<không đọc được>").prefix(300)))
            #endif
            throw FeedbackSendError.rejected(http.statusCode)
        }
    }
}
