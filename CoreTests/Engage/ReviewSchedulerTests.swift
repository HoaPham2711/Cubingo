import XCTest
@testable import AppHost

/// Bộ canh "màn yên" của lời mời đánh giá. Đồng hồ và nhịp tick được bơm vào nên test không chờ Timer thật.
@MainActor
final class ReviewSchedulerTests: XCTestCase {

    private var defaults: UserDefaults!
    private var center: NotificationCenter!
    private var sink: RecordingSink!
    private let suite = "ReviewSchedulerTests"
    private var now = Date(timeIntervalSince1970: 1_000_000_000)

    override func setUp() {
        super.setUp()
        UserDefaults().removePersistentDomain(forName: suite)
        defaults = UserDefaults(suiteName: suite)
        center = NotificationCenter()
        sink = RecordingSink()
        Track.install(sink)
    }

    override func tearDown() {
        Track.reset()
        UserDefaults().removePersistentDomain(forName: suite)
        defaults = nil
        center = nil
        sink = nil
        super.tearDown()
    }

    /// `isInternalBuild: false` BẮT BUỘC (config `Debug` CŨNG có cờ `INTERNAL`) — xem `ReviewPrompterTests`.
    private func prompter(isInternal: Bool = false) -> ReviewPrompter {
        ReviewPrompter(defaults: defaults, notificationCenter: center, clock: { [unowned self] in now },
                       isInternalBuild: isInternal)
    }

    /// Thay `Timer`: giữ closure tick, test tự gõ nhịp. `cancel` làm nhịp ngừng chạy như `Timer.invalidate`.
    private final class ManualDriver {
        private(set) var interval: TimeInterval?
        private(set) var scheduledCount = 0
        private(set) var running = false
        private var handler: (@MainActor () -> Void)?

        func schedule(_ interval: TimeInterval, _ tick: @escaping @MainActor () -> Void) -> () -> Void {
            self.interval = interval
            scheduledCount += 1
            running = true
            handler = tick
            return { [self] in running = false; handler = nil }
        }

        @MainActor func tick() { handler?() }
    }

    /// `isQuiet` trả lần lượt các giá trị đã cho, hết thì giữ giá trị cuối.
    private final class QuietScript {
        private var values: [Bool]
        private(set) var calls = 0
        init(_ values: [Bool]) { self.values = values }
        func next() -> Bool {
            calls += 1
            return values.count > 1 ? values.removeFirst() : (values.first ?? false)
        }
    }

    private final class Counter { var n = 0 }

    private func make(_ p: ReviewPrompter, quiet: QuietScript, driver: ManualDriver,
                      presented: Counter) -> ReviewScheduler {
        ReviewScheduler(prompter: p, isQuiet: { quiet.next() }, present: { presented.n += 1 },
                        now: { [unowned self] in now }, schedule: driver.schedule)
    }

    private var skipReasons: [String] {
        sink.events.filter { $0.name == "review_skip" }.compactMap {
            if case .string(let s)? = $0.parameters["reason"] { return s } else { return nil }
        }
    }

    // MARK: - Chờ yên

    func testChoToiKhiYenMoiHoi() {
        let p = prompter()
        let quiet = QuietScript([false, false, true])
        let driver = ManualDriver()
        let presented = Counter()
        let s = make(p, quiet: quiet, driver: driver, presented: presented)

        s.arm(.outputDone)
        XCTAssertEqual(driver.interval, 0.5, "nhịp poll giữ như nguồn")
        driver.tick(); driver.tick()
        XCTAssertEqual(presented.n, 0, "chưa yên thì không được hỏi")
        XCTAssertNil(p.pendingAsk)

        driver.tick()
        XCTAssertEqual(presented.n, 1)
        XCTAssertEqual(p.pendingAsk, .outputDone)
        XCTAssertEqual(ReviewPromptState.load(from: defaults).askDates, [now], "decide đã ghi sổ lần hỏi")
        XCTAssertFalse(driver.running, "hỏi xong phải dừng nhịp")

        driver.tick()
        XCTAssertEqual(presented.n, 1, "đúng một lần")
    }

    // MARK: - Hết hạn

    func testHetHanThiKhongHoi() {
        let p = prompter()
        let quiet = QuietScript([false])
        let driver = ManualDriver()
        let presented = Counter()
        let s = make(p, quiet: quiet, driver: driver, presented: presented)

        s.arm(.outputDone)
        now = now.addingTimeInterval(ReviewScheduler.timeout)
        driver.tick()
        XCTAssertTrue(driver.running, "đúng 10 phút chưa hết hạn (so sánh `>`)")
        XCTAssertTrue(skipReasons.isEmpty)

        now = now.addingTimeInterval(1)
        driver.tick()
        XCTAssertFalse(driver.running, "quá hạn phải dừng nhịp")
        XCTAssertEqual(skipReasons, ["no_quiet_moment"])
        XCTAssertEqual(presented.n, 0)
        XCTAssertNil(p.pendingAsk)

        // Màn hình yên sau đó cũng không được hỏi: lượt đã bị bỏ.
        driver.tick()
        XCTAssertEqual(presented.n, 0)
        XCTAssertEqual(ReviewPromptState.load(from: defaults).askDates, [])
    }

    func testTimeoutMacDinhLa10PhutVaNhip05Giay() {
        XCTAssertEqual(ReviewScheduler.timeout, 600)
        XCTAssertEqual(ReviewScheduler.pollInterval, 0.5)
    }

    // MARK: - Quyết định

    func testQuyetDinhSkipThiKhongPresent() {
        let p = prompter()
        let driver = ManualDriver()
        let presented = Counter()
        let s = make(p, quiet: QuietScript([true]), driver: driver, presented: presented)

        s.arm(.contentClosed(dwellSeconds: 1, reopened: true))
        driver.tick()
        XCTAssertEqual(presented.n, 0)
        XCTAssertNil(p.pendingAsk)
        XCTAssertEqual(skipReasons, ["dwell_too_short"], "lý do skip phải được ghi lại")
        XCTAssertFalse(driver.running)
    }

    /// Build nội bộ: im lặng, không làm bẩn số liệu bằng `review_skip`.
    func testBuildInternalSkipKhongGhiSkipEvent() {
        let p = prompter(isInternal: true)
        let driver = ManualDriver()
        let presented = Counter()
        let s = make(p, quiet: QuietScript([true]), driver: driver, presented: presented)

        s.arm(.outputDone)
        driver.tick()
        XCTAssertEqual(presented.n, 0)
        XCTAssertTrue(skipReasons.isEmpty)
    }

    // MARK: - Gài chồng

    /// Hai moment chờ chồng nhau thì `outputDone` thắng, và chỉ có MỘT nhịp.
    func testGaiChongThiGopVaChiMotNhip() {
        let p = prompter()
        let driver = ManualDriver()
        let presented = Counter()
        let s = make(p, quiet: QuietScript([false, true]), driver: driver, presented: presented)

        s.arm(.contentClosed(dwellSeconds: 1, reopened: false))   // một mình thì bị skip dwell
        s.arm(.outputDone)
        XCTAssertEqual(driver.scheduledCount, 1)
        driver.tick(); driver.tick()
        XCTAssertEqual(p.pendingAsk, .outputDone)
        XCTAssertEqual(presented.n, 1)
    }

    /// Gài lại thì đồng hồ hết hạn tính từ lần gài MỚI nhất.
    func testGaiLaiThiTinhHanTuLanGaiMoi() {
        let p = prompter()
        let driver = ManualDriver()
        let s = make(p, quiet: QuietScript([false]), driver: driver, presented: Counter())

        s.arm(.outputDone)
        now = now.addingTimeInterval(ReviewScheduler.timeout - 10)
        s.arm(.outputDone)
        now = now.addingTimeInterval(ReviewScheduler.timeout - 10)
        driver.tick()
        XCTAssertTrue(driver.running, "mới gài lại 590 s trước, chưa hết hạn")
    }

    func testBypassPolicyHoiThangKhongQuaLuat() {
        let p = prompter()
        let driver = ManualDriver()
        let presented = Counter()
        let s = make(p, quiet: QuietScript([true]), driver: driver, presented: presented)

        s.arm(.contentClosed(dwellSeconds: 1, reopened: false), bypassPolicy: true)
        driver.tick()
        XCTAssertEqual(p.pendingAsk, .contentClosed(dwellSeconds: 1, reopened: false))
        XCTAssertEqual(presented.n, 1)
        XCTAssertEqual(ReviewPromptState.load(from: defaults).askDates, [], "bypass không ghi sổ")
    }

    /// Dừng xong gài lại phải chạy lại được (trạng thái được dọn sạch).
    func testGaiLaiSauKhiDungThiChayLai() {
        let p = prompter()
        let driver = ManualDriver()
        let presented = Counter()
        let s = make(p, quiet: QuietScript([true]), driver: driver, presented: presented)

        s.arm(.contentClosed(dwellSeconds: 1, reopened: false))
        driver.tick()
        XCTAssertFalse(driver.running)
        s.arm(.outputDone)
        XCTAssertEqual(driver.scheduledCount, 2)
        driver.tick()
        XCTAssertEqual(presented.n, 1)
    }
}
