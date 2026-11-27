import XCTest
@testable import AppHost

@MainActor
final class UpdateCheckerTests: XCTestCase {
    private let url = URL(string: "https://apps.apple.com/app/id1234567890")!

    private func freshDefaults() throws -> UserDefaults {
        let name = "update-check-\(UUID().uuidString)"
        let d = try XCTUnwrap(UserDefaults(suiteName: name))
        addTeardownBlock { d.removePersistentDomain(forName: name) }
        return d
    }

    private func make(_ lookup: StubLookup, _ d: UserDefaults, installed: String = "1.0",
                      clock: Clock) -> UpdateChecker {
        UpdateChecker(lookup: lookup, defaults: d, installedVersion: installed, osVersion: "17.5",
                      now: { clock.now })
    }

    func testCheckLanDauGoiLookupVaCapNhatStatus() async throws {
        let lookup = StubLookup(.success(StoreRelease(version: "1.1", minimumOsVersion: "17.0", url: url)))
        let c = make(lookup, try freshDefaults(), clock: Clock())
        await c.checkIfNeeded()
        XCTAssertEqual(c.status, .available(version: "1.1", url: url, notes: nil))
        XCTAssertEqual(lookup.calls, 1)
    }

    func testTrong24hKhongGoiLaiSau24hGoiLai() async throws {
        let lookup = StubLookup(.success(StoreRelease(version: "1.1", minimumOsVersion: "17.0", url: url)))
        let clock = Clock()
        let c = make(lookup, try freshDefaults(), clock: clock)
        await c.checkIfNeeded()
        clock.now += UpdateChecker.checkInterval - 1
        await c.checkIfNeeded()
        XCTAssertEqual(lookup.calls, 1, "chưa đủ 24h thì không được gọi mạng")
        clock.now += 2
        await c.checkIfNeeded()
        XCTAssertEqual(lookup.calls, 2, "quá 24h phải gọi lại")
    }

    func testDongHoLuiVeTruocThiVanGoiLai() async throws {
        let lookup = StubLookup(.success(nil))
        let clock = Clock()
        let c = make(lookup, try freshDefaults(), clock: clock)
        await c.checkIfNeeded()
        clock.now -= 3600
        await c.checkIfNeeded()
        XCTAssertEqual(lookup.calls, 2, "lastCheck ở tương lai (đổi giờ máy) không được chặn check mãi")
    }

    func testLoiMangGiuStatusCuVaKhongGhiLastCheck() async throws {
        let d = try freshDefaults()
        let lookup = StubLookup(.success(StoreRelease(version: "1.1", minimumOsVersion: "17.0", url: url)))
        let clock = Clock()
        let c = make(lookup, d, clock: clock)
        await c.checkIfNeeded()
        clock.now += UpdateChecker.checkInterval + 1
        lookup.result = .failure(URLError(.notConnectedToInternet))
        await c.checkIfNeeded()
        XCTAssertEqual(c.status, .available(version: "1.1", url: url, notes: nil), "lỗi mạng không được xoá banner")
        await c.checkIfNeeded()
        XCTAssertEqual(lookup.calls, 3, "lỗi không ghi lastCheck → lần sau thử lại ngay")
    }

    func testStatusDaLuuDuocEvaluateLaiTheoVersionDangCai() async throws {
        let d = try freshDefaults()
        let clock = Clock()
        let lookup = StubLookup(.success(StoreRelease(version: "1.1", minimumOsVersion: "17.0", url: url)))
        await make(lookup, d, installed: "1.0", clock: clock).checkIfNeeded()

        // Mở lại app, KHÔNG gọi mạng: bản 1.0 vẫn thấy banner ngay, bản đã cập nhật lên 1.1 thì không.
        XCTAssertEqual(make(lookup, d, installed: "1.0", clock: clock).status, .available(version: "1.1", url: url, notes: nil))
        XCTAssertEqual(make(lookup, d, installed: "1.1", clock: clock).status, .upToDate)
    }

    func testDismissAnBannerVaNhoQuaLanMoApp() async throws {
        let d = try freshDefaults()
        let clock = Clock()
        let lookup = StubLookup(.success(StoreRelease(version: "1.1", minimumOsVersion: "17.0", url: url)))
        let c = make(lookup, d, clock: clock)
        await c.checkIfNeeded()
        XCTAssertTrue(c.showsHomeBanner)
        c.dismissBanner()
        XCTAssertFalse(c.showsHomeBanner)
        XCTAssertFalse(make(lookup, d, clock: clock).showsHomeBanner, "dismiss phải sống qua lần mở app")

        lookup.result = .success(StoreRelease(version: "1.2", minimumOsVersion: "17.0", url: url))
        clock.now += UpdateChecker.checkInterval + 1
        await c.checkIfNeeded()
        XCTAssertTrue(c.showsHomeBanner, "bản mới hơn bản đã dismiss phải hiện lại")
    }

    // MARK: - Release notes

    func testStoreReleaseDaLuuBoiBanCuKhongCoNotesVanDecode() throws {
        // Đúng dạng JSON bản app cũ (chưa có `releaseNotes`) ghi vào `updateCheck.lastRelease`.
        let legacy = try JSONEncoder().encode(LegacyStoreRelease(version: "1.1", minimumOsVersion: "17.0", url: url))
        let decoded = try JSONDecoder().decode(StoreRelease.self, from: legacy)
        XCTAssertEqual(decoded, StoreRelease(version: "1.1", minimumOsVersion: "17.0", url: url))
        XCTAssertNil(decoded.releaseNotes)

        let d = try freshDefaults()
        d.set(legacy, forKey: UpdateChecker.Key.lastRelease)
        XCTAssertEqual(make(StubLookup(.success(nil)), d, installed: "1.0", clock: Clock()).status,
                       .available(version: "1.1", url: url, notes: nil),
                       "bản lưu cũ không có notes vẫn phải cho banner hiện ngay khi mở app")
    }

    func testNotesDuocLuuVaSongQuaLanMoApp() async throws {
        let d = try freshDefaults()
        let clock = Clock()
        let lookup = StubLookup(.success(StoreRelease(version: "1.1", minimumOsVersion: "17.0", url: url,
                                                      releaseNotes: "New themes\nFixes")))
        let c = make(lookup, d, clock: clock)
        await c.checkIfNeeded()
        XCTAssertEqual(c.status, .available(version: "1.1", url: url, notes: "New themes\nFixes"))
        XCTAssertEqual(make(lookup, d, clock: clock).status,
                       .available(version: "1.1", url: url, notes: "New themes\nFixes"))
    }

    // MARK: - appID từ cấu hình

    /// App không có App Store id (chưa tạo bản ghi trên Store) ⇒ KHÔNG được gọi mạng và không công bố gì.
    /// Id rỗng/toàn khoảng trắng cũng thế — cấu hình sinh ra chuỗi rỗng khi khoá để trống. Vế đối chứng:
    /// có id thì cùng đường đó phải gọi `fetch`, để test này không xanh chỉ vì `fetch` hỏng.
    func testAppIDRongKhongGoiMang() async throws {
        for appID in [nil, "", "   "] as [String?] {
            let d = try freshDefaults()
            let calls = FetchCounter()
            let c = UpdateChecker.makeDefault(appID: appID, defaults: d, fetch: calls.fetch)
            await c.checkIfNeeded()
            XCTAssertEqual(calls.count, 0, "appID \(String(describing: appID)) không được gọi mạng")
            XCTAssertEqual(c.status, .upToDate)
            XCTAssertNil(d.object(forKey: UpdateChecker.Key.lastCheck), "không ghi lastCheck khi không kiểm")
        }

        let d = try freshDefaults()
        let calls = FetchCounter()
        let c = UpdateChecker.makeDefault(appID: "1234567890", defaults: d, fetch: calls.fetch)
        await c.checkIfNeeded()
        XCTAssertGreaterThanOrEqual(calls.count, 1, "có appID thì phải gọi Lookup")
        XCTAssertNotNil(d.object(forKey: UpdateChecker.Key.lastCheck))
    }
}

/// Hình dạng `StoreRelease` trước khi có `releaseNotes` — mô phỏng dữ liệu đã lưu trên máy khách.
private struct LegacyStoreRelease: Codable {
    let version: String
    let minimumOsVersion: String
    let url: URL
}

private final class Clock: @unchecked Sendable {
    var now = Date(timeIntervalSince1970: 1_800_000_000)
}

private final class StubLookup: AppStoreLookup, @unchecked Sendable {
    var result: Result<StoreRelease?, Error>
    private(set) var calls = 0
    init(_ r: Result<StoreRelease?, Error>) { result = r }
    func fetchLatest() async throws -> StoreRelease? {
        calls += 1
        return try result.get()
    }
}

/// Đếm số lần `fetch` được gọi; trả JSON hợp lệ để đường có id chạy hết.
private final class FetchCounter: @unchecked Sendable {
    private let lock = NSLock()
    private var n = 0
    var count: Int { lock.lock(); defer { lock.unlock() }; return n }
    var fetch: AppStoreLookupClient.Fetch {
        { [self] _ in
            lock.lock(); n += 1; lock.unlock()
            return Data("""
            {"resultCount":1,"results":[{"version":"999.0","minimumOsVersion":"1.0",
             "trackViewUrl":"https://apps.apple.com/app/id1234567890"}]}
            """.utf8)
        }
    }
}
