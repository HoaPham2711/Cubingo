import XCTest
@testable import AppHost

/// Cái bẫy quen thuộc: `UserDefaults.integer(forKey:)` trả 0 và
/// `object(forKey:)` trả nil khi key CHƯA TỪNG ghi — mặc định phải là "chưa hỏi lần nào".
final class ReviewPromptStateTests: XCTestCase {

    private var defaults: UserDefaults!
    private let suite = "ReviewPromptStateTests"
    private let moc = Date(timeIntervalSince1970: 1_000_000_000)

    override func setUp() {
        super.setUp()
        UserDefaults().removePersistentDomain(forName: suite)
        defaults = UserDefaults(suiteName: suite)
    }

    override func tearDown() {
        UserDefaults().removePersistentDomain(forName: suite)
        defaults = nil
        super.tearDown()
    }

    func testMacDinhKhiChuaTungGhi() {
        let s = ReviewPromptState.load(from: defaults)
        XCTAssertEqual(s.askDates, [])
        XCTAssertNil(s.lastAnswer)
        XCTAssertNil(s.lastAskedDate)
        XCTAssertEqual(s.consecutiveDeclines, 0)
        XCTAssertNil(s.lastFeedbackSentDate)
        XCTAssertEqual(s.openedItemIDs, [])
    }

    func testGhiRoiDocLaiKhopTungTruong() {
        var s = ReviewPromptState.load(from: defaults)
        s.askDates = [moc.addingTimeInterval(-100 * 86400), moc.addingTimeInterval(-3 * 86400)]
        s.lastAnswer = .later
        s.consecutiveDeclines = 2
        s.lastFeedbackSentDate = moc.addingTimeInterval(-86400)
        s.openedItemIDs = ["A", "B"]
        s.save(to: defaults, now: moc)

        XCTAssertEqual(ReviewPromptState.load(from: defaults), s)
    }

    /// Trần "3 lần / 365 ngày cuộn": lần hỏi quá một năm phải rơi khỏi sổ, không thì trần cũng
    /// thành trọn đời.
    func testLanHoiQuaMotNamBiCatKhiGhi() {
        var s = ReviewPromptState()
        s.askDates = [moc.addingTimeInterval(-400 * 86400), moc.addingTimeInterval(-10 * 86400)]
        s.save(to: defaults, now: moc)
        XCTAssertEqual(ReviewPromptState.load(from: defaults).askDates, [moc.addingTimeInterval(-10 * 86400)])
    }

    func testIdMucDaMoCoTran() {
        var s = ReviewPromptState()
        s.openedItemIDs = (0..<(ReviewPromptState.maxRememberedItems + 5)).map { "I\($0)" }
        s.save(to: defaults, now: moc)
        let ids = ReviewPromptState.load(from: defaults).openedItemIDs
        XCTAssertEqual(ids.count, ReviewPromptState.maxRememberedItems)
        XCTAssertEqual(ids.last, "I\(ReviewPromptState.maxRememberedItems + 4)", "giữ cái MỚI nhất")
    }

    /// Sổ chỉ có một phiên bản: key lạ cùng tiền tố (vd. của một bản trước) KHÔNG được đọc thành lần hỏi.
    func testKeyLaCungTienToKhongDuocDocThanhLanHoi() {
        defaults.set(moc.addingTimeInterval(-20 * 86400), forKey: "review.lastAskedDate")
        defaults.set(1, forKey: "review.askCount")
        let s = ReviewPromptState.load(from: defaults)
        XCTAssertEqual(s.askDates, [])
        XCTAssertNil(s.lastAnswer)
    }

    /// Mọi lần hỏi đều quá một năm ⇒ sau khi cắt, sổ ghi ra là rỗng và đọc lại cũng rỗng (không hồi sinh).
    func testSoRongSauKhiCatVanLaRong() {
        var s = ReviewPromptState()
        s.askDates = [moc.addingTimeInterval(-400 * 86400)]
        s.save(to: defaults, now: moc)
        XCTAssertEqual(ReviewPromptState.load(from: defaults).askDates, [])
        XCTAssertNotNil(defaults.object(forKey: "review.askDates"), "mảng rỗng vẫn được ghi, không bị coi là chưa ghi")
    }

    func testKeyCoTienToRiengKhongDungChamKhac() {
        defaults.set("giu-nguyen", forKey: "other.system.key")
        ReviewPromptState(askDates: [moc]).save(to: defaults, now: moc)
        let keys = defaults.dictionaryRepresentation().keys.filter { $0.hasPrefix("review.") }
        XCTAssertFalse(keys.isEmpty)
        XCTAssertEqual(defaults.string(forKey: "other.system.key"), "giu-nguyen",
                       "không được đụng vào key của hệ thống khác")
    }
}
