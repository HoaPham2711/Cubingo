import XCTest
@testable import AppHost

/// Attribution Apple Ads (AdServices): parse payload, retry 404, consent, chạy chồng, gán lại thuộc tính đã lưu,
/// cổng `apple_ads` của `startAtLaunch`.
final class AppleAdsAttributionTests: XCTestCase {

    // MARK: - Parse payload

    private func data(_ s: String) -> Data { Data(s.utf8) }

    func testParseQuangCao() throws {
        let r = try XCTUnwrap(AttributionPayload.parse(data("""
        {"attribution":true,"orgId":1,"campaignId":542370539,"adGroupId":542317095,"keywordId":87675432,\
        "countryOrRegion":"US","conversionType":"Download","clickDate":"2026-11-20T08:00Z"}
        """)))
        XCTAssertEqual(r.source, .appleAds)
        XCTAssertEqual(r.campaign, "542370539")
        XCTAssertEqual(r.adGroup, "542317095")
        XCTAssertEqual(r.keyword, "87675432")
        XCTAssertEqual(r.country, "US")
        XCTAssertEqual(r.conversion, "Download")
    }

    func testParseTuNhien() throws {
        let r = try XCTUnwrap(AttributionPayload.parse(data(#"{"attribution":false}"#)))
        XCTAssertEqual(r, AttributionResult(source: .organic, campaign: nil, adGroup: nil, keyword: nil,
                                            country: nil, conversion: nil, attempts: 0))
    }

    func testParseSearchMatchKhongKeyword() throws {
        let r = try XCTUnwrap(AttributionPayload.parse(data(
            #"{"attribution":true,"campaignId":5,"adGroupId":6,"countryOrRegion":"US","conversionType":"Download"}"#)))
        XCTAssertEqual(r.source, .appleAds)
        XCTAssertEqual(r.campaign, "5")
        XCTAssertNil(r.keyword)
    }

    func testParseHongTraNil() {
        for s in ["not json", "[]", "{}", #"{"attribution":"yes"}"#] {
            XCTAssertNil(AttributionPayload.parse(data(s)), s)
        }
    }

    // MARK: - Actor AppleAdsAttribution

    private var sink: RecordingSink!
    private var defaults: UserDefaults!
    private var suiteName: String!

    override func setUp() {
        super.setUp()
        sink = RecordingSink()
        Track.install(sink)
        suiteName = "attr-\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)
    }

    override func tearDown() {
        Track.reset()
        UserDefaults().removePersistentDomain(forName: suiteName)
        super.tearDown()
    }

    private let t0 = Date(timeIntervalSince1970: 1_800_000_000)

    private func ads(campaign: String = "1", keyword: String? = "9") -> AttributionResult {
        AttributionResult(source: .appleAds, campaign: campaign, adGroup: "2", keyword: keyword,
                          country: "US", conversion: "Download", attempts: 0)
    }
    private let organic = AttributionResult(source: .organic, campaign: nil, adGroup: nil, keyword: nil,
                                            country: nil, conversion: nil, attempts: 0)

    private func make(_ client: FakeClient, now: Date? = nil, consent: ConsentBox = ConsentBox(true),
                      sleeps: SleepLog = SleepLog()) -> AppleAdsAttribution {
        let at = now ?? t0
        return AppleAdsAttribution(client: client, defaults: defaults, now: { at },
                                   sleep: { await sleeps.add($0) }, consent: { consent.value })
    }

    /// Event `attribution_resolved` đã bắn, đọc ngược từ param (AppEvent là struct, không `if case` được).
    private struct Resolved: Equatable {
        let source: AttributionResult.Source?
        let attempts: Int?
    }

    private var resolvedEvents: [Resolved] {
        sink.events.filter { $0.isNamed(ShellEventName.attributionResolved) }.map { e in
            var attempts: Int?
            if case .int(let n) = e.parameters["attempts"] { attempts = n }
            return Resolved(source: e.string("acq_source").flatMap(AttributionResult.Source.init(rawValue:)),
                            attempts: attempts)
        }
    }

    func testQuangCaoChotVaGanThuocTinh() async {
        let c = FakeClient([.resolved(ads())])
        let a = make(c)
        await a.resolveIfNeeded()
        XCTAssertTrue(sink.properties.contains(.acqSource("apple_ads")))
        XCTAssertTrue(sink.properties.contains(.asaCampaign("1")))
        XCTAssertTrue(sink.properties.contains(.asaKeyword("9")))
        XCTAssertEqual(resolvedEvents.map(\.attempts), [1])
        await a.resolveIfNeeded()
        let calls = await c.calls
        XCTAssertEqual(calls, 1)
        XCTAssertEqual(resolvedEvents.count, 1)
    }

    func testTuNhien() async {
        await make(FakeClient([.resolved(organic)])).resolveIfNeeded()
        XCTAssertEqual(sink.properties, [.acqSource("organic")])
    }

    func testSearchMatchKhongCoKeyword() async {
        await make(FakeClient([.resolved(ads(keyword: nil))])).resolveIfNeeded()
        XCTAssertTrue(sink.properties.contains(.asaCampaign("1")))
        XCTAssertFalse(sink.properties.contains { $0.name == UserProperty.asaKeyword("").name })
    }

    func test404BaLanRoiThoi() async {
        let c = FakeClient([.notReady, .notReady, .notReady])
        let sleeps = SleepLog()
        await make(c, sleeps: sleeps).resolveIfNeeded()
        let calls = await c.calls
        let slept = await sleeps.values
        XCTAssertEqual(calls, 3)
        XCTAssertEqual(slept, [5, 5])
        XCTAssertTrue(sink.events.isEmpty)
        XCTAssertTrue(sink.nonFatals.isEmpty)
        XCTAssertNil(defaults.data(forKey: AppleAdsAttribution.resultKey))
    }

    func test404RoiThanhCong() async {
        await make(FakeClient([.notReady, .resolved(organic)])).resolveIfNeeded()
        XCTAssertEqual(resolvedEvents.map(\.attempts), [2])
    }

    func testLoiMangGhiNonFatalVaChuaChot() async {
        let c = FakeClient([.failed(code: "network")])
        await make(c).resolveIfNeeded()
        let calls = await c.calls
        XCTAssertEqual(calls, 1)
        XCTAssertEqual(sink.nonFatals, [NonFatal(domain: .attribution, code: "network")])
        XCTAssertTrue(sink.events.isEmpty)
    }

    func testTraVeHongKhongChotOrganic() async {
        await make(FakeClient([.failed(code: "parse")])).resolveIfNeeded()
        XCTAssertNil(defaults.data(forKey: AppleAdsAttribution.resultKey))
        XCTAssertTrue(sink.properties.isEmpty)
    }

    func testChotUnknownSauNamLanChay() async {
        let c = FakeClient(repeating: .failed(code: "network"))
        for _ in 0..<4 { await make(c).resolveIfNeeded() }
        XCTAssertTrue(resolvedEvents.isEmpty)
        await make(c).resolveIfNeeded()
        XCTAssertEqual(resolvedEvents.map(\.source), [.unknown])
        XCTAssertEqual(resolvedEvents.first?.attempts, 5)
        XCTAssertTrue(sink.properties.contains(.acqSource("unknown")))
        await make(c).resolveIfNeeded()
        let calls = await c.calls
        XCTAssertEqual(calls, 5)
    }

    func testChotUnknownSauBayNgay() async {
        let c = FakeClient(repeating: .failed(code: "network"))
        await make(c, now: t0).resolveIfNeeded()
        XCTAssertTrue(resolvedEvents.isEmpty)
        await make(c, now: t0.addingTimeInterval(7 * 24 * 3600)).resolveIfNeeded()
        XCTAssertEqual(resolvedEvents.map(\.source), [.unknown])
    }

    func testConsentTatKhongGoiKhongDem() async {
        let c = FakeClient([.resolved(organic)])
        await make(c, consent: ConsentBox(false)).resolveIfNeeded()
        let calls = await c.calls
        XCTAssertEqual(calls, 0)
        XCTAssertNil(defaults.object(forKey: AppleAdsAttribution.runsKey))
    }

    func testConsentTatKhongDemLanChay() async {
        let c = FakeClient(repeating: .failed(code: "network"))
        for _ in 0..<4 { await make(c, consent: ConsentBox(false)).resolveIfNeeded() }
        await make(c).resolveIfNeeded()
        XCTAssertEqual(defaults.integer(forKey: AppleAdsAttribution.runsKey), 1)
        XCTAssertTrue(resolvedEvents.isEmpty)
    }

    func testTatConsentGiuaChungThiDung() async {
        let consent = ConsentBox(true)
        let c = FakeClient([.notReady, .resolved(organic)], afterCall: { consent.value = false })
        await make(c, consent: consent).resolveIfNeeded()
        let calls = await c.calls
        XCTAssertEqual(calls, 1)
        XCTAssertTrue(sink.events.isEmpty)
        XCTAssertTrue(sink.properties.isEmpty)
    }

    func testGoiChongNhauChiMotLuong() async {
        let c = FakeClient([.resolved(organic)], gated: true)
        let a = make(c)
        async let first: Void = a.resolveIfNeeded()
        await c.waitUntilCalled()
        async let second: Void = a.resolveIfNeeded()
        await second
        await c.open()
        await first
        let calls = await c.calls
        XCTAssertEqual(calls, 1)
        XCTAssertEqual(resolvedEvents.count, 1)
    }

    func testApplyStoredProperties() async {
        await make(FakeClient([.resolved(ads())])).resolveIfNeeded()
        let moi = RecordingSink()
        Track.install(moi)
        AppleAdsAttribution.applyStoredProperties(defaults: defaults)
        XCTAssertEqual(Set(moi.properties.map(\.name)), ["acq_source", "asa_campaign", "asa_keyword"])
        XCTAssertTrue(moi.events.isEmpty)
    }

    /// Công tắc `[features] apple_ads` tắt ⇒ không hỏi Apple, kể cả khi không phải host test / Simulator.
    /// Vế đối chứng (công tắc bật ⇒ đúng 1 lần gọi) chứng minh đường tiêm thật sự tới được client giả — nếu
    /// không có nó, "0 lần" có thể chỉ là do cổng host test chặn trước.
    func testTatCoAppleAdsThiKhongHoi() async {
        let tat = FakeClient([.resolved(organic)])
        let t1 = AppleAdsAttribution.startAtLaunch(appleAdsEnabled: false, isUnitTestHost: false, isSimulator: false,
                                                   defaults: defaults, attribution: make(tat))
        XCTAssertNil(t1)
        await t1?.value
        let callsTat = await tat.calls
        XCTAssertEqual(callsTat, 0)

        let bat = FakeClient([.resolved(organic)])
        let t2 = AppleAdsAttribution.startAtLaunch(appleAdsEnabled: true, isUnitTestHost: false, isSimulator: false,
                                                   defaults: defaults, attribution: make(bat))
        await t2?.value
        let callsBat = await bat.calls
        XCTAssertEqual(callsBat, 1, "đối chứng: công tắc bật thì client giả phải được hỏi")
    }

    /// Overload nhận `AttributionResult` (dạng nguồn gọi) phải ra ĐÚNG event của factory tách tham số: cùng khoá,
    /// cùng cách mã hoá; field nil ⇒ vắng khoá.
    func testAttributionResolvedTuKetQuaKhopFactoryTachThamSo() {
        var r = ads()
        r.attempts = 3
        XCTAssertEqual(AppEvent.attributionResolved(r),
                       .attributionResolved(source: "apple_ads", attempts: 3, campaign: "1", adGroup: "2",
                                            keyword: "9", country: "US", conversion: "Download"))
        var o = organic
        o.attempts = 1
        XCTAssertEqual(AppEvent.attributionResolved(o).parameters,
                       ["acq_source": .string("organic"), "attempts": .int(1)])
    }

    /// Đối chứng chung: cả ba điều kiện cho phép ⇒ client giả PHẢI được hỏi đúng 1 lần (đường tiêm còn sống).
    private func assertDoiChungDuocHoi(file: StaticString = #filePath, line: UInt = #line) async {
        let c = FakeClient([.resolved(organic)])
        let t = AppleAdsAttribution.startAtLaunch(appleAdsEnabled: true, isUnitTestHost: false, isSimulator: false,
                                                  defaults: defaults, attribution: make(c))
        XCTAssertNotNil(t, "đối chứng: đủ điều kiện thì phải chạy", file: file, line: line)
        await t?.value
        let calls = await c.calls
        XCTAssertEqual(calls, 1, "đối chứng: đủ điều kiện thì client giả phải được hỏi", file: file, line: line)
    }

    /// Host unit test: công tắc bật vẫn KHÔNG hỏi Apple — chạy test không được gọi mạng thật.
    func testHostTestThiKhongHoi() async {
        let c = FakeClient([.resolved(organic)])
        let t = AppleAdsAttribution.startAtLaunch(appleAdsEnabled: true, isUnitTestHost: true, isSimulator: false,
                                                  defaults: defaults, attribution: make(c))
        XCTAssertNil(t)
        await t?.value
        let calls = await c.calls
        XCTAssertEqual(calls, 0)
        await assertDoiChungDuocHoi()
    }

    /// Simulator: công tắc bật vẫn KHÔNG hỏi Apple — review UI/chụp ảnh không được bơm số liệu giả.
    func testSimulatorThiKhongHoi() async {
        let c = FakeClient([.resolved(organic)])
        let t = AppleAdsAttribution.startAtLaunch(appleAdsEnabled: true, isUnitTestHost: false, isSimulator: true,
                                                  defaults: defaults, attribution: make(c))
        XCTAssertNil(t)
        await t?.value
        let calls = await c.calls
        XCTAssertEqual(calls, 0)
        await assertDoiChungDuocHoi()
    }

    // MARK: - LiveAttributionClient (không chạm mạng)

    func testLiveOutcomeMap() {
        XCTAssertEqual(LiveAttributionClient.outcome(status: 200, body: data(#"{"attribution":false}"#)),
                       .resolved(organic))
        XCTAssertEqual(LiveAttributionClient.outcome(status: 200, body: data("x")), .failed(code: "parse"))
        XCTAssertEqual(LiveAttributionClient.outcome(status: 404, body: Data()), .notReady)
        XCTAssertEqual(LiveAttributionClient.outcome(status: 400, body: Data()), .failed(code: "http_400"))
    }

    func testLiveTokenLoi() async {
        let c = LiveAttributionClient(token: { throw CocoaError(.featureUnsupported) })
        let r = await c.fetch()
        XCTAssertEqual(r, .failed(code: "token"))
    }
}

// MARK: - Test doubles

final class ConsentBox: @unchecked Sendable {
    private let lock = NSLock()
    private var _value: Bool
    init(_ v: Bool) { _value = v }
    var value: Bool {
        get { lock.lock(); defer { lock.unlock() }; return _value }
        set { lock.lock(); _value = newValue; lock.unlock() }
    }
}

actor SleepLog {
    private(set) var values: [TimeInterval] = []
    func add(_ v: TimeInterval) { values.append(v) }
}

/// Trả lần lượt `script`; hết thì lặp `repeating` (nếu có). `gated`: lần gọi đầu treo tới khi `open()`.
actor FakeClient: AttributionClient {
    private var script: [AttributionFetchOutcome]
    private let repeating: AttributionFetchOutcome?
    private let afterCall: (@Sendable () -> Void)?
    private(set) var calls = 0
    private var gate: CheckedContinuation<Void, Never>?
    private var gated: Bool
    private var calledWaiters: [CheckedContinuation<Void, Never>] = []

    init(_ script: [AttributionFetchOutcome] = [], repeating: AttributionFetchOutcome? = nil,
         gated: Bool = false, afterCall: (@Sendable () -> Void)? = nil) {
        self.script = script; self.repeating = repeating; self.gated = gated; self.afterCall = afterCall
    }

    func fetch() async -> AttributionFetchOutcome {
        calls += 1
        calledWaiters.forEach { $0.resume() }; calledWaiters.removeAll()
        if gated {
            gated = false
            await withCheckedContinuation { gate = $0 }
        }
        afterCall?()
        if !script.isEmpty { return script.removeFirst() }
        return repeating ?? .failed(code: "script_het")
    }

    func waitUntilCalled() async {
        if calls > 0 { return }
        await withCheckedContinuation { calledWaiters.append($0) }
    }

    func open() { gate?.resume(); gate = nil }
}
