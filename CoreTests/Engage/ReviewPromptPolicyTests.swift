import XCTest
@testable import AppHost

/// Cảnh giác chi phối file này: một policy luôn trả `.skip` sẽ làm phần lớn test xanh
/// (memory `test-green-does-not-mean-test-guards`). Nên mỗi luật có một test khẳng định `.ask`
/// ở đúng biên, và các test `.skip` khẳng định ĐÍCH DANH lý do.
final class ReviewPromptPolicyTests: XCTestCase {

    private let moc = Date(timeIntervalSince1970: 1_000_000_000)
    private typealias P = ReviewTuning
    private let tuning = ReviewTuning()

    private func ngayTruoc(_ d: Double) -> Date { moc.addingTimeInterval(-d * 86400) }

    private func quyet(_ moment: ReviewMoment = .outputDone,
                       state: ReviewPromptState = ReviewPromptState(),
                       friction: SessionFriction = SessionFriction(),
                       isInternal: Bool = false) -> ReviewDecision {
        ReviewPromptPolicy.decide(moment: moment, state: state, friction: friction, isInternalBuild: isInternal,
                                  tuning: tuning, now: moc)
    }

    private func dong(_ giay: Int, reopened: Bool = false) -> ReviewMoment {
        .contentClosed(dwellSeconds: giay, reopened: reopened)
    }

    // MARK: - Nhánh CHO PHÉP

    /// User mới tinh, output đầu tiên xong: hỏi luôn — bắt chờ ≥ 2 ngày thì gần như không ai tới lượt.
    func testOutputLanDauThiHoiNgay() {
        XCTAssertEqual(quyet(), .ask)
    }

    func testDongNoiDungSauHanhDongGiaTriThiHoi() {
        XCTAssertEqual(quyet(dong(tuning.minDwellSeconds), friction: SessionFriction(hadValueAction: true)), .ask)
    }

    func testDongNoiDungMucMoLaiThiHoi() {
        XCTAssertEqual(quyet(dong(tuning.minDwellSeconds, reopened: true)), .ask)
    }

    // MARK: - "Kết quả tốt"

    func testDwellNganThiThoi() {
        XCTAssertEqual(quyet(dong(tuning.minDwellSeconds - 1, reopened: true)), .skip(.dwellTooShort))
    }

    /// Xem lần đầu, không làm gì với mục đó ⇒ chưa có bằng chứng nó có ích.
    func testDongNoiDungKhongTinHieuGiaTriThiThoi() {
        XCTAssertEqual(quyet(dong(120)), .skip(.noValueSignal))
    }

    /// Mục hoàn tất đầu tiên có thể chỉ là thử — chưa đủ.
    func testMotMucHoanTatChuaTinhGiaTri() {
        let f = SessionFriction(completedCount: tuning.completionsForValueSignal - 1)
        XCTAssertEqual(quyet(dong(tuning.minDwellSeconds), friction: f), .skip(.noValueSignal))
    }

    /// Làm tiếp sau khi xem kết quả đầu (ca thực tế: user hoàn tất 3 mục trong một phiên mà bị chặn) ⇒ hỏi.
    func testHaiMucHoanTatTrongPhienThiHoi() {
        let f = SessionFriction(completedCount: tuning.completionsForValueSignal)
        XCTAssertEqual(quyet(dong(tuning.minDwellSeconds), friction: f), .ask)
    }

    /// Hoàn tất nhiều mục vẫn không vượt dwell — lướt qua màn nội dung thì không hỏi.
    func testNhieuMucHoanTatVanCanDwell() {
        let f = SessionFriction(completedCount: 5)
        XCTAssertEqual(quyet(dong(tuning.minDwellSeconds - 1), friction: f), .skip(.dwellTooShort))
    }

    // MARK: - Bực mình

    /// Không xin sao ngay sau khi vừa làm hỏng việc của họ.
    func testTacVuLoiTrongPhienThiThoi() {
        XCTAssertEqual(quyet(friction: SessionFriction(taskFailed: true)), .skip(.sessionFriction))
    }

    func testRestoreLoiTrongPhienThiThoi() {
        XCTAssertEqual(quyet(friction: SessionFriction(restoreFailed: true)), .skip(.sessionFriction))
    }

    func testBucMinhGanDayThiThoi() {
        let f = SessionFriction(lastNegativeAt: moc.addingTimeInterval(-Double(tuning.recentFrictionMinutes) * 60 + 1))
        XCTAssertEqual(quyet(friction: f), .skip(.recentFriction))
    }

    /// Chỉ chặn 5 phút, không chặn cả phiên (chặn cả phiên thì user free gặp paywall là mất cả lần mở app).
    func testBucMinhQuaNamPhutThiHoi() {
        let f = SessionFriction(lastNegativeAt: moc.addingTimeInterval(-Double(tuning.recentFrictionMinutes) * 60))
        XCTAssertEqual(quyet(friction: f), .ask)
    }

    func testVuaGuiFeedbackThiThoi() {
        XCTAssertEqual(quyet(state: ReviewPromptState(lastFeedbackSentDate: ngayTruoc(3))), .skip(.recentFeedback))
    }

    func testFeedbackDungBienThiHoi() {
        XCTAssertEqual(quyet(state: ReviewPromptState(lastFeedbackSentDate: ngayTruoc(Double(tuning.feedbackCooldownDays)))),
                       .ask)
    }

    // MARK: - Nhịp hỏi

    func testSauRateChuaDu90NgayThiThoi() {
        let s = ReviewPromptState(askDates: [ngayTruoc(Double(tuning.daysAfterRate) - 1)], lastAnswer: .rate)
        XCTAssertEqual(quyet(state: s), .skip(.askedRecently))
    }

    func testSauRateDu90NgayThiHoi() {
        let s = ReviewPromptState(askDates: [ngayTruoc(Double(tuning.daysAfterRate))], lastAnswer: .rate)
        XCTAssertEqual(quyet(state: s), .ask)
    }

    func testSauNotNowChuaDu30NgayThiThoi() {
        let s = ReviewPromptState(askDates: [ngayTruoc(Double(tuning.daysAfterLater) - 1)], lastAnswer: .later,
                                  consecutiveDeclines: 1)
        XCTAssertEqual(quyet(state: s), .skip(.askedRecently))
    }

    func testSauNotNowDu30NgayThiHoi() {
        let s = ReviewPromptState(askDates: [ngayTruoc(Double(tuning.daysAfterLater))], lastAnswer: .later,
                                  consecutiveDeclines: 1)
        XCTAssertEqual(quyet(state: s), .ask)
    }

    /// Hộp hiện mà app bị tắt trước khi trả lời ⇒ coi như Not Now (30 ngày), không treo 90 ngày.
    func testChuaTraLoiThiCoiNhuNotNow() {
        let s = ReviewPromptState(askDates: [ngayTruoc(Double(tuning.daysAfterLater))], lastAnswer: nil)
        XCTAssertEqual(quyet(state: s), .ask)
    }

    func testHaiLanNotNowLienTiepThiDung180Ngay() {
        let s = ReviewPromptState(askDates: [ngayTruoc(Double(tuning.declinePauseDays) - 1)], lastAnswer: .later,
                                  consecutiveDeclines: tuning.declinesBeforePause)
        XCTAssertEqual(quyet(state: s), .skip(.declinedTwice))
    }

    func testHaiLanNotNowQua180NgayThiHoi() {
        let s = ReviewPromptState(askDates: [ngayTruoc(Double(tuning.declinePauseDays))], lastAnswer: .later,
                                  consecutiveDeclines: tuning.declinesBeforePause)
        XCTAssertEqual(quyet(state: s), .ask)
    }

    func testDuBaLanTrongNamThiThoi() {
        let s = ReviewPromptState(askDates: [ngayTruoc(300), ngayTruoc(200), ngayTruoc(100)], lastAnswer: .rate)
        XCTAssertEqual(quyet(state: s), .skip(.yearlyCap))
    }

    /// Trần là 365 ngày CUỘN, không phải trọn đời.
    func testLanHoiQuaMotNamKhongTinhVaoTran() {
        let s = ReviewPromptState(askDates: [ngayTruoc(500), ngayTruoc(200), ngayTruoc(100)], lastAnswer: .rate)
        XCTAssertEqual(quyet(state: s), .ask)
    }

    func testBuildInternalKhongBaoGioTuHoi() {
        XCTAssertEqual(quyet(isInternal: true), .skip(.internalBuild))
    }

    // MARK: - Gộp moment

    func testOutputThangDongNoiDungKhiGop() {
        XCTAssertEqual(ReviewMoment.outputDone.merged(with: dong(3)), .outputDone)
        XCTAssertEqual(dong(3).merged(with: .outputDone), .outputDone)
        XCTAssertEqual(dong(3).merged(with: dong(40, reopened: true)), dong(40, reopened: true))
    }

    func testHangSoMacDinhDungNhuSpec() {
        let t = ReviewTuning()
        XCTAssertEqual(t.minDwellSeconds, 15)
        XCTAssertEqual(t.recentFrictionMinutes, 5)
        XCTAssertEqual(t.feedbackCooldownDays, 7)
        XCTAssertEqual(t.maxAsksPerYear, 3)
        XCTAssertEqual(t.daysAfterRate, 90)
        XCTAssertEqual(t.daysAfterLater, 30)
        XCTAssertEqual(t.declinesBeforePause, 2)
        XCTAssertEqual(t.declinePauseDays, 180)
        XCTAssertEqual(t.completionsForValueSignal, 2)
    }
}
