import XCTest
@testable import AppHost

/// Chặn mạng bằng URLProtocol: kiểm request thật `WebAPIFeedbackTransport` dựng ra và cách nó dịch mã HTTP. Không
/// chạm mạng thật, không ngủ. Host thử `dev.example.com` là host mẫu của template, không phải máy chủ có thật.
final class WebAPIFeedbackTransportTests: XCTestCase {

    private final class Stub: URLProtocol {
        static var status = 201
        static var loi: Error?
        static var lastRequest: URLRequest?
        static var lastBody: Data?

        override class func canInit(with request: URLRequest) -> Bool { true }
        override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
        override func startLoading() {
            Stub.lastRequest = request
            // URLSession chuyển httpBody thành stream trước khi tới URLProtocol.
            if let s = request.httpBodyStream {
                s.open()
                var d = Data()
                var buf = [UInt8](repeating: 0, count: 4096)
                while s.hasBytesAvailable {
                    let n = s.read(&buf, maxLength: buf.count)
                    if n <= 0 { break }
                    d.append(buf, count: n)
                }
                s.close()
                Stub.lastBody = d
            } else {
                Stub.lastBody = request.httpBody
            }
            if let loi = Stub.loi {
                client?.urlProtocol(self, didFailWithError: loi)
                return
            }
            let resp = HTTPURLResponse(url: request.url!, statusCode: Stub.status, httpVersion: nil, headerFields: nil)!
            client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: Data("{\"ok\":true}".utf8))
            client?.urlProtocolDidFinishLoading(self)
        }
        override func stopLoading() {}
    }

    private func phienGia() -> URLSession {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [Stub.self]
        return URLSession(configuration: cfg)
    }

    /// `token` luôn truyền tường minh: test không phụ thuộc App Check thật.
    private func dung(base: String = "https://dev.example.com", token: String? = nil) -> WebAPIFeedbackTransport {
        WebAPIFeedbackTransport(baseURL: URL(string: base)!, appVersion: "9.9.9", session: phienGia(), token: { token })
    }
    private let draft = FeedbackDraft(type: .bug, message: "hỏng", email: nil, diagnostics: "d")

    override func setUp() {
        Stub.status = 201
        Stub.loi = nil
        Stub.lastRequest = nil
        Stub.lastBody = nil
    }

    /// Gốc API lấy từ tham số (do app đọc ở `AppConfig.apiBaseURL`), có hay không dấu `/` cuối đều ra một URL.
    func testURLTheoBaseURL() {
        XCTAssertEqual(WebAPIFeedbackTransport.path, "api/v1/feedback")
        for base in ["https://dev.example.com", "https://dev.example.com/"] {
            XCTAssertEqual(WebAPIFeedbackTransport.feedbackURL(baseURL: URL(string: base)!).absoluteString,
                           "https://dev.example.com/api/v1/feedback", base)
        }
    }

    func testGuiPOSTJSONToiDungDuongDanVaHetGio() async throws {
        for ok in [200, 201, 204] {
            Stub.status = ok
            try await dung().send(draft)
        }
        let req = try XCTUnwrap(Stub.lastRequest)
        XCTAssertEqual(req.httpMethod, "POST")
        XCTAssertEqual(req.url?.absoluteString, "https://dev.example.com/api/v1/feedback")
        XCTAssertEqual(req.value(forHTTPHeaderField: "Content-Type"), "application/json")
        // Có trần thời gian chờ riêng (không dựa mặc định 60 s của URLSession): form không treo vô hạn khi mạng chập chờn.
        XCTAssertEqual(req.timeoutInterval, WebAPIFeedbackTransport.requestTimeout)
        XCTAssertLessThanOrEqual(WebAPIFeedbackTransport.requestTimeout, 30)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: try XCTUnwrap(Stub.lastBody)) as? [String: Any])
        XCTAssertEqual(json["appVersion"] as? String, "9.9.9")
        XCTAssertEqual(json["message"] as? String, "hỏng")
    }

    /// Mọi mã ngoài 2xx là `.rejected(mã)` — 4xx (client sai/bị chặn) lẫn 5xx (máy chủ lỗi); phân biệt ý nghĩa là việc
    /// của lớp hiển thị. Mã 2xx là thành công. Mất mạng là `.offline` (test riêng), không lẫn với mã HTTP.
    func testMaLoiServerThanhRejected() async {
        for ma in [400, 401, 403, 404, 422, 429, 500, 502, 503] {
            Stub.status = ma
            do {
                try await dung().send(draft)
                XCTFail("mã \(ma) phải ném")
            } catch {
                XCTAssertEqual(error as? FeedbackSendError, .rejected(ma))
            }
        }
    }

    func testMatMangVaHetGioThanhOffline() async {
        for loi in [URLError(.notConnectedToInternet), URLError(.timedOut), URLError(.cannotFindHost)] {
            Stub.loi = loi
            do {
                try await dung().send(draft)
                XCTFail("\(loi.code) phải ném")
            } catch {
                XCTAssertEqual(error as? FeedbackSendError, .offline, "\(loi.code)")
            }
        }
    }

    func testDraftSaiKhongRaMang() async {
        do {
            try await dung().send(FeedbackDraft(type: .bug, message: " ", email: nil, diagnostics: "d"))
            XCTFail("phải ném")
        } catch {
            XCTAssertEqual(error as? FeedbackValidationError, .messageEmpty)
        }
        XCTAssertNil(Stub.lastRequest)
    }

    /// App Check là lớp chứng minh "người gửi là app thật". Có token ⇒ gửi kèm header; KHÔNG có token (Firebase chưa
    /// cấu hình, Simulator, DeviceCheck trục trặc) ⇒ VẪN gửi, không header — máy chủ quyết định (chặn ở client chỉ làm
    /// mất phản hồi thật).
    func testHeaderAppCheckChiGuiKhiCoToken() async throws {
        try await dung(token: "token-thu").send(draft)
        XCTAssertEqual(Stub.lastRequest?.value(forHTTPHeaderField: "X-Firebase-AppCheck"), "token-thu")

        Stub.lastRequest = nil
        try await dung(token: nil).send(draft)
        let req = try XCTUnwrap(Stub.lastRequest, "không có token vẫn phải gửi")
        XCTAssertNil(req.value(forHTTPHeaderField: "X-Firebase-AppCheck"))
    }
}
