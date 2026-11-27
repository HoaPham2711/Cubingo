import XCTest
@testable import AppHost

final class AppStoreLookupClientTests: XCTestCase {
    /// Id và tên là dữ liệu giả — test không được phụ thuộc cấu hình thật của app.
    private let okJSON = Data("""
    {"resultCount":1,"results":[{"version":"1.4.0","minimumOsVersion":"17.0",
     "trackViewUrl":"https://apps.apple.com/us/app/sample-app/id1234567890?uo=4","trackName":"Sample App"}]}
    """.utf8)
    private let emptyJSON = Data(#"{"resultCount":0,"results":[]}"#.utf8)

    func testParseBinhThuong() throws {
        let r = try XCTUnwrap(AppStoreLookupClient.parse(okJSON))
        XCTAssertEqual(r.version, "1.4.0")
        XCTAssertEqual(r.minimumOsVersion, "17.0")
        XCTAssertEqual(r.url.host, "apps.apple.com")
    }

    func testParseCoReleaseNotes() throws {
        let json = Data(#"""
        {"resultCount":1,"results":[{"version":"1.5.0","minimumOsVersion":"17.0",
         "trackViewUrl":"https://apps.apple.com/app/id1234567890","releaseNotes":"New themes\nBug fixes"}]}
        """#.utf8)
        let r = try XCTUnwrap(AppStoreLookupClient.parse(json))
        XCTAssertEqual(r.version, "1.5.0")
        XCTAssertEqual(r.releaseNotes, "New themes\nBug fixes")
    }

    func testParseKhongCoReleaseNotesThiNil() throws {
        let r = try XCTUnwrap(AppStoreLookupClient.parse(okJSON))
        XCTAssertNil(r.releaseNotes, "thiếu releaseNotes không được làm hỏng parse")
    }

    func testResultCountKhongTraVeNil() throws {
        XCTAssertNil(try AppStoreLookupClient.parse(emptyJSON))
    }

    func testThieuFieldHoacJSONHongThiThrow() {
        XCTAssertThrowsError(try AppStoreLookupClient.parse(Data(#"{"resultCount":1,"results":[{"version":"1.0"}]}"#.utf8)))
        XCTAssertThrowsError(try AppStoreLookupClient.parse(Data("<html>".utf8)))
    }

    func testURLCoVaKhongCoCountry() {
        let a = AppStoreLookupClient.url(appID: "1234567890", country: "vn").absoluteString
        XCTAssertEqual(a, "https://itunes.apple.com/lookup?id=1234567890&country=vn")
        let b = AppStoreLookupClient.url(appID: "1234567890", country: nil).absoluteString
        XCTAssertEqual(b, "https://itunes.apple.com/lookup?id=1234567890")
    }

    func testRongOCountryThiGoiLaiKhongCountry() async throws {
        let calls = CallLog()
        let empty = emptyJSON, ok = okJSON
        let client = AppStoreLookupClient(appID: "1", country: "vn") { url in
            await calls.append(url)
            return url.query?.contains("country=") == true ? empty : ok
        }
        let r = try await client.fetchLatest()
        XCTAssertEqual(r?.version, "1.4.0")
        let urls = await calls.urls
        XCTAssertEqual(urls.count, 2, "rỗng ở country thì phải hỏi lại đúng một lần không country")
        guard urls.count == 2 else { return }
        XCTAssertFalse(urls[1].query?.contains("country=") ?? true)
    }

    func testCoKetQuaOCountryThiKhongGoiLai() async throws {
        let calls = CallLog()
        let ok = okJSON
        let client = AppStoreLookupClient(appID: "1", country: "vn") { url in
            await calls.append(url); return ok
        }
        _ = try await client.fetchLatest()
        let n = await calls.urls.count
        XCTAssertEqual(n, 1)
    }

    func testKhongCountryChiGoiMotLan() async throws {
        let calls = CallLog()
        let empty = emptyJSON
        let client = AppStoreLookupClient(appID: "1", country: nil) { url in
            await calls.append(url); return empty
        }
        let r = try await client.fetchLatest()
        XCTAssertNil(r)
        let n = await calls.urls.count
        XCTAssertEqual(n, 1)
    }
}

private actor CallLog {
    var urls: [URL] = []
    func append(_ u: URL) { urls.append(u) }
}
