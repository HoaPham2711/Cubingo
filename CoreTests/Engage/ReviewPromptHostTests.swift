import XCTest
@testable import AppHost

/// Phần logic của hộp hỏi trước (`ReviewPromptFlow`) — phần SwiftUI của host không dựng trong unit test.
@MainActor
final class ReviewPromptHostTests: XCTestCase {

    private var defaults: UserDefaults!
    private var sink: RecordingSink!
    private let suite = "ReviewPromptHostTests"

    override func setUp() {
        super.setUp()
        UserDefaults().removePersistentDomain(forName: suite)
        defaults = UserDefaults(suiteName: suite)
        sink = RecordingSink()
        Track.install(sink)
    }

    override func tearDown() {
        Track.reset()
        UserDefaults().removePersistentDomain(forName: suite)
        defaults = nil
        sink = nil
        super.tearDown()
    }

    private func prompter() -> ReviewPrompter {
        ReviewPrompter(defaults: defaults, notificationCenter: NotificationCenter(), isInternalBuild: false)
    }

    private func outcomes() -> [String] {
        sink.events.filter { $0.name == "review_answer" }.compactMap {
            if case .string(let s)? = $0.parameters["outcome"] { return s } else { return nil }
        }
    }

    func testNotNowGhiCauTraLoiVaKhongGoiHeThong() {
        let p = prompter()
        var scheduled = 0
        var requested = 0
        ReviewPromptFlow.answer(.later, prompter: p, after: { _, _ in scheduled += 1 }, requestReview: { requested += 1 })
        XCTAssertEqual(ReviewPromptState.load(from: defaults).lastAnswer, .later)
        XCTAssertEqual(ReviewPromptState.load(from: defaults).consecutiveDeclines, 1)
        XCTAssertEqual(outcomes(), ["later"])
        XCTAssertEqual(scheduled, 0)
        XCTAssertEqual(requested, 0, "Not Now không được chạm hộp hệ thống (không tiêu quota của iOS)")
    }

    /// Hộp hệ thống chỉ được gọi SAU khi alert đã đóng hẳn: trễ 0,5 s, không gọi ngay trong action.
    func testRateGoiHeThongSauDoTre() {
        let p = prompter()
        var delay: TimeInterval?
        var work: (() -> Void)?
        var requested = 0
        ReviewPromptFlow.answer(.rate, prompter: p, after: { d, w in delay = d; work = w },
                                requestReview: { requested += 1 })
        XCTAssertEqual(ReviewPromptState.load(from: defaults).lastAnswer, .rate)
        XCTAssertEqual(outcomes(), ["rate"])
        XCTAssertEqual(delay, 0.5)
        XCTAssertEqual(requested, 0, "chưa tới lúc: alert còn đang đóng")
        XCTAssertFalse(sink.names.contains("review_prompt"))

        work?()
        XCTAssertEqual(requested, 1)
        XCTAssertTrue(sink.names.contains("review_prompt"))
    }

    func testHienHopGhiNguonCuaMoment() {
        ReviewPromptFlow.asked(.outputDone)
        ReviewPromptFlow.asked(.contentClosed(dwellSeconds: 20, reopened: false))
        let sources = sink.events.filter { $0.name == "review_ask" }.compactMap { e -> String? in
            if case .string(let s)? = e.parameters["source"] { return s } else { return nil }
        }
        XCTAssertEqual(sources, ["output", "content"])
    }
}
