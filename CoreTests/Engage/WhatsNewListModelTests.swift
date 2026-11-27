import XCTest
@testable import AppHost

/// Danh sách đầy đủ What's New: nhóm theo bản, mới trên cùng, `.unreleased` dưới số `current`, nhãn "New for you"
/// khi bản > `lastShownFrom` (`"unknown"`/nil/chuỗi hỏng ⇒ không nhãn).
final class WhatsNewListModelTests: XCTestCase {

    private func v(_ s: String) -> AppVersion { AppVersion(s)! }

    private func card(_ id: String, _ version: CardVersion, priority: Int = 5) -> WhatsNewCard {
        WhatsNewCard(id: id, version: version, priority: priority, systemImage: "star",
                     title: id, body: id, ctaTitle: id, action: WhatsNewAction(key: "go"))
    }

    private lazy var cards: [WhatsNewCard] = [
        card("delta", .released("1.10.0"), priority: 6),
        card("charlie", .released("1.10.0"), priority: 6),
        card("bravo", .released("1.11.0"), priority: 7),
        card("echo", .released("1.13.0"), priority: 4),
        card("alpha", .released("1.14.0"), priority: 8),
        card("dev", .unreleased, priority: 9),
        card("future", .released("1.15.0"), priority: 9),
    ]

    private func sections(lastShownFrom: String?) -> [WhatsNewListSection] {
        WhatsNewListModel.sections(cards: cards, current: v("1.14.0"), lastShownFrom: lastShownFrom)
    }

    func testNhomTheoBanMoiTrenCung() {
        let s = sections(lastShownFrom: nil)
        XCTAssertEqual(s.map(\.title), ["1.14.0", "1.13.0", "1.11.0", "1.10.0"])
        // Trong nhóm: ưu tiên ↓ rồi id ↑ (giống selector).
        XCTAssertEqual(s.last?.cards.map(\.id), ["charlie", "delta"])
    }

    func testUnreleasedNamDuoiSoCurrent() {
        let s = sections(lastShownFrom: nil)
        XCTAssertEqual(s.first?.version, v("1.14.0"))
        XCTAssertEqual(s.first?.cards.map(\.id), ["dev", "alpha"])
    }

    func testTheMoiHonCurrentKhongHien() {
        XCTAssertFalse(sections(lastShownFrom: nil).flatMap(\.cards).contains { $0.id == "future" })
    }

    func testNhanNewForYouChiChoBanLonHonLastShownFrom() {
        let s = sections(lastShownFrom: "1.11.0")
        XCTAssertEqual(s.map(\.isNewForYou), [true, true, false, false])
    }

    func testKhongNhanKhiUnknownHoacChuaTungHien() {
        XCTAssertEqual(sections(lastShownFrom: "unknown").map(\.isNewForYou), [false, false, false, false])
        XCTAssertEqual(sections(lastShownFrom: nil).map(\.isNewForYou), [false, false, false, false])
        XCTAssertEqual(sections(lastShownFrom: "rác").map(\.isNewForYou), [false, false, false, false])
    }

    func testIdNhomOnDinhVaDuyNhat() {
        let ids = sections(lastShownFrom: nil).map(\.id)
        XCTAssertEqual(Set(ids).count, ids.count)
    }
}
