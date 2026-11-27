import XCTest
@testable import AppHost

@MainActor
final class ReviewPrompterTests: XCTestCase {

    private var defaults: UserDefaults!
    private var center: NotificationCenter!
    private let suite = "ReviewPrompterTests"
    private var now = Date(timeIntervalSince1970: 1_000_000_000)

    override func setUp() {
        super.setUp()
        UserDefaults().removePersistentDomain(forName: suite)
        defaults = UserDefaults(suiteName: suite)
        center = NotificationCenter()
    }

    override func tearDown() {
        UserDefaults().removePersistentDomain(forName: suite)
        defaults = nil
        center = nil
        super.tearDown()
    }

    /// `isInternalBuild: false` BẮT BUỘC: test build ở config `Debug`, mà `Debug` CŨNG có cờ
    /// `INTERNAL` — để mặc định thì mọi test khẳng định `.ask` đỏ oan.
    private func moi(isInternal: Bool = false) -> ReviewPrompter {
        ReviewPrompter(defaults: defaults, notificationCenter: center, clock: { [unowned self] in now },
                       isInternalBuild: isInternal)
    }

    /// Notification đăng ký `queue: .main` — chạy một vòng runloop cho handler kịp chạy.
    private func xa() { RunLoop.main.run(until: Date().addingTimeInterval(0.01)) }

    /// Cổng chống hỏi hai lần: `decide` phải tự ghi lần hỏi.
    func testHoiXongThiGhiLaiVaKhongHoiNua() {
        let p = moi()
        XCTAssertEqual(p.decide(.outputDone), .ask)
        XCTAssertEqual(p.decide(.outputDone), .skip(.askedRecently))
        XCTAssertEqual(ReviewPromptState.load(from: defaults).askDates, [now])
    }

    func testRateRoiNotNowCapNhatDemTuChoi() {
        let p = moi()
        p.noteAnswer(.later)
        p.noteAnswer(.later)
        XCTAssertEqual(ReviewPromptState.load(from: defaults).consecutiveDeclines, 2)
        p.noteAnswer(.rate)
        let s = ReviewPromptState.load(from: defaults)
        XCTAssertEqual(s.consecutiveDeclines, 0)
        XCTAssertEqual(s.lastAnswer, .rate)
    }

    /// Lần hỏi mới xoá câu trả lời cũ — không để "Rate" của năm ngoái quyết khoảng chờ lần này.
    func testHoiMoiThiXoaCauTraLoiCu() {
        let p = moi()
        p.noteAnswer(.rate)
        XCTAssertEqual(p.decide(.outputDone), .ask)
        XCTAssertNil(ReviewPromptState.load(from: defaults).lastAnswer)
    }

    func testMoLaiMuc() {
        let p = moi()
        XCTAssertFalse(p.noteItemOpened(id: "A"))
        XCTAssertFalse(p.noteItemOpened(id: "B"))
        XCTAssertTrue(p.noteItemOpened(id: "A"))
    }

    func testTinHieuGiaTriQuaNotificationMoKhoaDongNoiDung() {
        let p = moi()
        XCTAssertEqual(p.decide(.contentClosed(dwellSeconds: 30, reopened: false)), .skip(.noValueSignal))
        ReviewSignals.noteValueAction(center: center)
        xa()
        XCTAssertEqual(p.decide(.contentClosed(dwellSeconds: 30, reopened: false)), .ask)
    }

    /// Đếm mục hoàn tất qua notification: 1 mục chưa đủ, 2 mục mở khoá; phiên mới đếm lại từ 0.
    func testDemMucHoanTatQuaNotification() {
        let p = moi()
        let dongNoiDung = ReviewMoment.contentClosed(dwellSeconds: 30, reopened: false)
        ReviewSignals.noteItemCompleted(center: center)
        xa()
        XCTAssertEqual(p.decide(dongNoiDung), .skip(.noValueSignal))
        p.noteAppBecameActive()
        ReviewSignals.noteItemCompleted(center: center)
        xa()
        XCTAssertEqual(p.decide(dongNoiDung), .skip(.noValueSignal), "phiên mới phải đếm lại từ 0")
        ReviewSignals.noteItemCompleted(center: center)
        xa()
        XCTAssertEqual(p.decide(dongNoiDung), .ask)
    }

    func testHanhDongTieuCucChanNamPhut() {
        let p = moi()
        ReviewSignals.noteNegativeAction(center: center)
        xa()
        XCTAssertEqual(p.decide(.outputDone), .skip(.recentFriction))
        now = now.addingTimeInterval(5 * 60)
        XCTAssertEqual(p.decide(.outputDone), .ask)
    }

    func testDongPaywallChanNamPhut() {
        let p = moi()
        p.notePaywallDismissed()
        XCTAssertEqual(p.decide(.outputDone), .skip(.recentFriction))
    }

    /// Bực mình + tín hiệu giá trị là của một phiên: app active lại thì xoá.
    func testPhienMoiThiXoaTrangThaiPhien() {
        let p = moi()
        p.noteTaskFailed()
        XCTAssertEqual(p.decide(.outputDone), .skip(.sessionFriction))
        p.noteAppBecameActive()
        XCTAssertEqual(p.decide(.outputDone), .ask)
    }

    func testGuiPhanHoiThiChanHoiTrong7Ngay() {
        let p = moi()
        p.noteFeedbackSent()
        XCTAssertEqual(p.decide(.outputDone), .skip(.recentFeedback))
    }

    func testBuildInternalThiKhongBaoGioHoiVaKhongGhiSo() {
        let p = moi(isInternal: true)
        XCTAssertEqual(p.decide(.outputDone), .skip(.internalBuild))
        XCTAssertEqual(ReviewPromptState.load(from: defaults).askDates, [])
    }

    #if INTERNAL
    // MARK: - Pipeline A/B

    /// Công tắc "Chạy luật như user App Store" phải gỡ được luật build nội bộ — không thì nút
    /// thử trên Internal chẳng bao giờ thấy luật thật chạy.
    func testGiaLapUserStoreThiBuildInternalCungHoi() {
        let p = moi(isInternal: true)
        XCTAssertEqual(p.decide(.outputDone), .skip(.internalBuild))
        defaults.set(true, forKey: ReviewPrompter.simulateStoreUserKey)
        XCTAssertEqual(p.decide(.outputDone), .ask)
    }

    /// Reset = user mới: xoá sổ (kể cả key lạ cùng tiền tố `review.`) và trạng thái phiên, nhưng GIỮ công
    /// tắc giả lập.
    func testResetNhuUserMoi() {
        let p = moi(isInternal: true)
        defaults.set(true, forKey: ReviewPrompter.simulateStoreUserKey)
        XCTAssertEqual(p.decide(.outputDone), .ask)
        p.noteAnswer(.later)
        p.noteFeedbackSent()
        _ = p.noteItemOpened(id: "A")
        defaults.set(now, forKey: "review.keyLaConSot")
        p.noteTaskFailed()

        p.debugResetAsNewUser()

        XCTAssertEqual(ReviewPromptState.load(from: defaults), ReviewPromptState())
        XCTAssertEqual(p.debugSnapshot.friction, SessionFriction())
        XCTAssertNil(p.debugLastDecision)
        XCTAssertTrue(defaults.bool(forKey: ReviewPrompter.simulateStoreUserKey))
        XCTAssertEqual(p.decide(.outputDone), .ask)
    }
    #endif
}
