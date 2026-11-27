import XCTest
@testable import AppHost

/// Ledger "đã dùng tính năng" của What's New. Thẻ dựng tay, UserDefaults suite riêng — không đụng catalog của app,
/// không ghi `UserDefaults.standard` của host.
final class FeatureUsageLedgerTests: XCTestCase {

    private var suiteName = ""
    private var defaults: UserDefaults!

    override func setUp() {
        super.setUp()
        suiteName = "FeatureUsageLedgerTests.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)!
    }

    override func tearDown() {
        // `Track.reset()` KHÔNG gỡ observer (cố ý) ⇒ phải gỡ riêng, không thì ledger của test này nghe event của
        // test sau.
        Track.removeUsageObserver()
        Track.reset()
        defaults.removePersistentDomain(forName: suiteName)
        defaults = nil
        super.tearDown()
    }

    // MARK: - Dựng dữ liệu

    /// Thẻ A: dùng khi xem paywall; seed khi probe có dấu vết `trace_a`.
    private let cardA = WhatsNewCard(
        id: "card_a", version: .unreleased, priority: 5, systemImage: "star", title: "A", body: "A", ctaTitle: "A",
        action: WhatsNewAction(key: "go_a"),
        usedWhen: { $0.isNamed(ShellEventName.paywallView) },
        usedOnDisk: { $0.hasTrace("trace_a") })

    /// Thẻ B: dùng khi gửi phản hồi; seed khi probe có dấu vết `trace_b`.
    private let cardB = WhatsNewCard(
        id: "card_b", version: .unreleased, priority: 5, systemImage: "star", title: "B", body: "B", ctaTitle: "B",
        action: WhatsNewAction(key: "go_b"),
        usedWhen: { $0.isNamed(ShellEventName.feedbackSent) },
        usedOnDisk: { $0.hasTrace("trace_b") })

    private func ledger() -> FeatureUsageLedger {
        FeatureUsageLedger(cards: [cardA, cardB], defaults: defaults)
    }

    /// Probe với các dấu vết cho trước (đúng = có dấu vết).
    private func probe(_ traces: String...) -> ClosureUsageProbe {
        ClosureUsageProbe(Dictionary(uniqueKeysWithValues: traces.map { ($0, { true }) }))
    }

    /// Observer ghi lại số event sink đã nhận TẠI LÚC observer được gọi — để kiểm thứ tự "observer trước sink".
    private final class OrderProbe: UsageObserver {
        let sink: RecordingSink
        var sinkCountsAtNote: [Int] = []
        init(sink: RecordingSink) { self.sink = sink }
        func note(_ event: AppEvent) { sinkCountsAtNote.append(sink.events.count) }
    }

    // MARK: - note qua Track.log

    func test_trackLog_matchingEvent_recordsCard_evenWithNoOpSink() {
        let l = ledger()
        Track.install(NoOpSink())
        Track.installUsageObserver(l)

        Track.log(.paywallView(source: "settings"))

        XCTAssertEqual(l.usedCards, ["card_a"])
        // Ghi vào defaults inject: instance mới trên cùng suite đọc lại được.
        XCTAssertEqual(ledger().usedCards, ["card_a"])
    }

    func test_trackLog_nonMatchingEvent_recordsNothing() {
        let l = ledger()
        Track.installUsageObserver(l)

        Track.log(.updatePrompt(action: "shown"))

        XCTAssertEqual(l.usedCards, [])
        XCTAssertNil(defaults.object(forKey: FeatureUsageLedger.usedCardsKey))
    }

    func test_note_isIdempotent_andAccumulates() {
        let l = ledger()
        l.note(.paywallView(source: "settings"))
        l.note(.paywallView(source: "root"))
        l.note(.feedbackSent(kind: "bug"))

        XCTAssertEqual(l.usedCards, ["card_a", "card_b"])
        XCTAssertEqual(defaults.stringArray(forKey: FeatureUsageLedger.usedCardsKey), ["card_a", "card_b"])
    }

    func test_trackLog_observerRunsBeforeSink_andSinkGetsEventOnce() {
        let sink = RecordingSink()
        let probe = OrderProbe(sink: sink)
        Track.install(sink)
        Track.installUsageObserver(probe)

        Track.log(.paywallView(source: "settings"))

        XCTAssertEqual(probe.sinkCountsAtNote, [0], "observer phải chạy TRƯỚC sink")
        XCTAssertEqual(sink.names, ["paywall_view"], "sink nhận đúng một lần")
    }

    /// Ledger thật gắn làm observer: sink chỉ nhận đúng event đã log — ledger KHÔNG được gọi lại telemetry (vòng lặp
    /// observer → log, hoặc event/thuộc tính/crash log phát sinh mà người gọi không hề bắn).
    func test_ledger_doesNotCallBackIntoTelemetry() {
        let sink = RecordingSink()
        Track.install(sink)
        let l = ledger()
        Track.installUsageObserver(l)

        Track.log(.paywallView(source: "settings"))
        l.seedFromDiskIfNeeded(probe: probe("trace_b"))

        XCTAssertEqual(l.usedCards, ["card_a", "card_b"])
        XCTAssertEqual(sink.names, ["paywall_view"])
        XCTAssertEqual(sink.properties, [])
        XCTAssertTrue(sink.diagnostics.isEmpty)
        XCTAssertEqual(sink.nonFatals.count, 0)
        XCTAssertEqual(sink.breadcrumbs.count, 0)
    }

    func test_removeUsageObserver_stopsRecording() {
        let l = ledger()
        Track.installUsageObserver(l)
        Track.removeUsageObserver()

        Track.log(.paywallView(source: "settings"))

        XCTAssertEqual(l.usedCards, [])
    }

    /// Tắt "Share usage data" (`Track.reset()`) KHÔNG được tắt ghi nhận "đã dùng" trên máy.
    func test_trackReset_keepsUsageObserver() {
        let l = ledger()
        Track.installUsageObserver(l)
        Track.reset()

        Track.log(.paywallView(source: "settings"))

        XCTAssertEqual(l.usedCards, ["card_a"])
    }

    // MARK: - Seed từ đĩa

    func test_seed_probeTrueForA_recordsOnlyA() {
        let l = ledger()
        l.seedFromDiskIfNeeded(probe: probe("trace_a"))

        XCTAssertEqual(l.usedCards, ["card_a"])
        XCTAssertTrue(defaults.bool(forKey: FeatureUsageLedger.diskSeededKey))
    }

    func test_seed_runsOnlyOnce() {
        let l = ledger()
        l.seedFromDiskIfNeeded(probe: probe("trace_a"))
        l.seedFromDiskIfNeeded(probe: probe("trace_a", "trace_b"))
        // Instance mới (lần mở app sau) cũng không seed lại.
        ledger().seedFromDiskIfNeeded(probe: probe("trace_b"))

        XCTAssertEqual(ledger().usedCards, ["card_a"])
    }

    func test_seed_withNoTraces_stillMarksSeeded() {
        let l = ledger()
        l.seedFromDiskIfNeeded(probe: probe())
        l.seedFromDiskIfNeeded(probe: probe("trace_b"))

        XCTAssertEqual(l.usedCards, [])
        XCTAssertTrue(defaults.bool(forKey: FeatureUsageLedger.diskSeededKey))
    }

    func test_seed_keepsCardsAlreadyNoted() {
        let l = ledger()
        l.note(.feedbackSent(kind: "feature"))
        l.seedFromDiskIfNeeded(probe: probe("trace_a"))

        XCTAssertEqual(l.usedCards, ["card_a", "card_b"])
    }

    // MARK: - Không bẩn host

    func test_ledger_doesNotTouchStandardDefaults() {
        let std = UserDefaults.standard
        let beforeUsed = std.object(forKey: FeatureUsageLedger.usedCardsKey)
        let beforeSeeded = std.object(forKey: FeatureUsageLedger.diskSeededKey)

        let l = ledger()
        Track.installUsageObserver(l)
        Track.log(.paywallView(source: "settings"))
        l.seedFromDiskIfNeeded(probe: probe("trace_b"))

        XCTAssertEqual(l.usedCards, ["card_a", "card_b"])
        XCTAssertNil(beforeUsed)
        XCTAssertNil(beforeSeeded)
        XCTAssertNil(std.object(forKey: FeatureUsageLedger.usedCardsKey))
        XCTAssertNil(std.object(forKey: FeatureUsageLedger.diskSeededKey))
    }

    /// N thẻ id riêng, mỗi event khớp ĐÚNG một thẻ ⇒ mỗi lượt là một read-modify-write khác nhau trên defaults.
    /// Thiếu khoá ⇒ hai luồng đọc cùng tập cũ, luồng ghi sau đè mất id của luồng kia ⇒ count < N.
    func test_note_fromManyQueues_distinctCards_noLostUpdate() {
        let n = 400
        let many: [WhatsNewCard] = (0..<n).map { i in
            WhatsNewCard(id: "c\(i)", version: .unreleased, priority: 5, systemImage: "star", title: "x", body: "x",
                         ctaTitle: "x", action: WhatsNewAction(key: "go"),
                         usedWhen: { $0.isNamed(ShellEventName.tourReplay) && $0.string("source") == "s\(i)" })
        }
        for round in 0..<2 {
            let name = suiteName + ".concurrent\(round)"
            let d = UserDefaults(suiteName: name)!
            defer { d.removePersistentDomain(forName: name) }
            let l = FeatureUsageLedger(cards: many, defaults: d)
            DispatchQueue.concurrentPerform(iterations: n) { i in
                l.note(.tourReplay(source: "s\(i)"))
            }
            XCTAssertEqual(l.usedCards.count, n, "vòng \(round): mất id khi ghi song song")
        }
    }

    // MARK: - ClosureUsageProbe (dấu vết do app cấp, chỉ đọc)

    func test_closureProbe_unknownKey_isFalse() {
        XCTAssertFalse(ClosureUsageProbe([:]).hasTrace("anything"))
        XCTAssertFalse(ClosureUsageProbe(["trace_a": { true }]).hasTrace("trace_b"))
    }

    /// Mỗi khoá đọc đúng closure của nó — không lẫn nguồn.
    func test_closureProbe_eachKeyReadsItsOwnClosure() {
        let p = ClosureUsageProbe(["yes": { true }, "no": { false }])
        XCTAssertTrue(p.hasTrace("yes"))
        XCTAssertFalse(p.hasTrace("no"))
    }

    /// Closure chạy LÚC HỎI (không chụp giá trị lúc dựng): app dựng probe sớm, seed chạy sau — phải thấy dấu vết
    /// có lúc seed. Khoá không ai hỏi thì closure không bao giờ chạy (không IO thừa).
    func test_closureProbe_evaluatesLazily_onlyAskedKeys() {
        var exists = false
        var askedOther = 0
        let p = ClosureUsageProbe(["file": { exists }, "other": { askedOther += 1; return true }])
        XCTAssertFalse(p.hasTrace("file"))
        exists = true
        XCTAssertTrue(p.hasTrace("file"))
        XCTAssertEqual(askedOther, 0)
    }
}
