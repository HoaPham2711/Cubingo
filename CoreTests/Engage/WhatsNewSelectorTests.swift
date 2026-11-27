import XCTest
@testable import AppHost

/// Luật chọn thẻ cho sheet What's New + phần resolve (đích của nút thẻ do app quyết qua `WhatsNewResolver`).
/// Thẻ dựng tay, resolver giả — không đụng catalog của app.
final class WhatsNewSelectorTests: XCTestCase {

    // MARK: - Dựng dữ liệu

    private func v(_ s: String) -> AppVersion { AppVersion(s)! }

    /// Đích luôn dùng được với resolver mặc định của test.
    private let always = WhatsNewAction(key: "always")
    /// Đích resolver mặc định trả `nil` (app chưa có dữ liệu cho nó).
    private let needsData = WhatsNewAction(key: "needs_data")

    private func card(_ id: String, _ version: CardVersion, priority: Int = 5,
                      action: WhatsNewAction? = WhatsNewAction(key: "always")) -> WhatsNewCard {
        WhatsNewCard(id: id, version: version, priority: priority, systemImage: "star",
                     title: id, body: id, ctaTitle: id, action: action)
    }

    /// Resolver giả: chỉ khoá `always` resolve được.
    private func defaultResolve(_ a: WhatsNewAction) -> WhatsNewResolvedAction? {
        a.key == "always" ? WhatsNewResolvedAction(key: a.key) : nil
    }

    private func select(lastSeen: String?, current: String, existing: Bool = true,
                        _ cards: [WhatsNewCard], used: Set<String> = [],
                        resolve: WhatsNewResolver? = nil) -> WhatsNewSelector.Outcome {
        WhatsNewSelector.select(lastSeen: lastSeen.map(v), current: v(current), isExistingUser: existing,
                                cards: cards, usedCards: used, resolve: resolve ?? defaultResolve)
    }

    /// `.show` ⇒ (id thẻ, moreCount, from); `.none` ⇒ fail.
    private func shown(_ o: WhatsNewSelector.Outcome,
                       file: StaticString = #filePath, line: UInt = #line) -> ([String], Int, AppVersion?)? {
        guard case let .show(cards, more, from) = o else {
            XCTFail("mong .show, được \(o)", file: file, line: line); return nil
        }
        return (cards.map(\.id), more, from)
    }

    private func markSeen(_ o: WhatsNewSelector.Outcome,
                          file: StaticString = #filePath, line: UInt = #line) -> Bool? {
        guard case let .none(m) = o else { XCTFail("mong .none, được \(o)", file: file, line: line); return nil }
        return m
    }

    // MARK: - Luật 1, 2: cài mới / cùng bản / hạ bản

    func testCaiMoiKhongHienVaGhiSeen() {
        let o = select(lastSeen: nil, current: "1.14.0", existing: false, [card("a", .released("1.14.0"))])
        XCTAssertEqual(markSeen(o), true)
    }

    func testCungBanKhongHienKhongGhi() {
        let o = select(lastSeen: "1.14.0", current: "1.14.0", [card("a", .released("1.14.0"))])
        XCTAssertEqual(markSeen(o), false)
    }

    func testHaBanKhongGhiLui() {
        let o = select(lastSeen: "1.15.0", current: "1.14.0", [card("a", .released("1.14.0"))])
        XCTAssertEqual(markSeen(o), false)
    }

    // MARK: - Luật 3: khoảng (lastSeen, current]

    func testChiCoBanSuaLoiTrongKhoang() {
        let o = select(lastSeen: "1.14.0", current: "1.14.1",
                       [card("a", .released("1.14.0")), card("b", .released("1.13.0"))])
        XCTAssertEqual(markSeen(o), true)
    }

    /// Ca biên dưới: thẻ ĐÚNG bản lastSeen đã thấy rồi ⇒ loại; bản kế ⇒ có.
    func testBienDuoiLastSeenLoaiTheCungBan() {
        let o = select(lastSeen: "1.12.0", current: "1.14.0",
                       [card("old", .released("1.12.0"), priority: 9), card("mid", .released("1.13.0"), priority: 1)])
        XCTAssertEqual(shown(o)?.0, ["mid"])
    }

    func testBienTrenTheMoiHonCurrentBiLoai() {
        let o = select(lastSeen: "1.12.0", current: "1.14.0",
                       [card("future", .released("1.15.0"), priority: 9), card("now", .released("1.14.0"))])
        XCTAssertEqual(shown(o)?.0, ["now"])
    }

    func testSoTheoSoKhongTheoChuoi() {
        let o = select(lastSeen: "1.9.0", current: "1.10.0",
                       [card("ten", .released("1.10.0")), card("nine", .released("1.9.0"))])
        XCTAssertEqual(shown(o)?.0, ["ten"])
    }

    func testNhayNhieuBanLay3TheoUuTienVaDemPhanCon() {
        let cards = [
            card("p4", .released("1.10.0"), priority: 4),
            card("p9", .released("1.12.0"), priority: 9),
            card("p7", .released("1.11.0"), priority: 7),
            card("p2", .released("1.13.0"), priority: 2),
            card("p8", .released("1.14.0"), priority: 8),
        ]
        guard let (ids, more, from) = shown(select(lastSeen: "1.6.0", current: "1.14.0", cards)) else { return }
        // Thẻ bản mới nhất trong khoảng (1.14.0) đứng đầu dù ưu tiên thấp hơn; còn lại theo ưu tiên.
        XCTAssertEqual(ids, ["p8", "p9", "p7"])
        XCTAssertEqual(more, 2)
        XCTAssertEqual(from, v("1.6.0"))
    }

    // MARK: - Luật 4: đã dùng / không có đích

    func testTheDaDungBiBoTheKeLenThay() {
        let cards = [
            card("a", .released("1.13.0"), priority: 9),
            card("b", .released("1.13.0"), priority: 8),
            card("c", .released("1.13.0"), priority: 7),
            card("d", .released("1.13.0"), priority: 6),
        ]
        guard let (ids, more, _) = shown(select(lastSeen: "1.12.0", current: "1.14.0", cards, used: ["a"]))
        else { return }
        XCTAssertEqual(ids, ["b", "c", "d"])
        XCTAssertEqual(more, 0)
    }

    func testHetTheViDaDungThiGhiSeen() {
        let o = select(lastSeen: "1.12.0", current: "1.14.0", [card("a", .released("1.13.0"))], used: ["a"])
        XCTAssertEqual(markSeen(o), true)
    }

    func testResolveNilBiBoHetThiNoneMarkSeen() {
        // Hai thẻ bản CŨ (1.13.0) trỏ vào đích resolver trả nil; thẻ bản mới nhất trong khoảng là "help"/"new"
        // (1.14.0) ⇒ luật "bỏ thẻ không có đích" áp cho hai thẻ cũ.
        let cards = [card("x", .released("1.13.0"), priority: 9, action: needsData),
                     card("y", .released("1.13.0"), priority: 8, action: WhatsNewAction(key: "also_missing"))]
        let withHelp = cards + [card("help", .released("1.14.0"), priority: 1, action: always)]
        XCTAssertEqual(shown(select(lastSeen: "1.12.0", current: "1.14.0", withHelp))?.0, ["help"])

        // Còn thẻ cũ không đích + thẻ mới nhất đã dùng ⇒ không còn gì ⇒ ghi seen.
        let usedNewest = cards + [card("new", .released("1.14.0"), action: needsData)]
        XCTAssertEqual(markSeen(select(lastSeen: "1.12.0", current: "1.14.0", usedNewest, used: ["new"])), true)
    }

    // MARK: - Thẻ bản mới nhất trong khoảng: luôn hiện dù không có đích

    /// Thẻ chính của bản mới mà đích chưa dùng được (app chưa có dữ liệu cho nó) ⇒ vẫn lên sheet (không nút) và
    /// đứng đầu dù ưu tiên thấp hơn thẻ cũ.
    func testTheBanMoiNhatKhongDichVanHienVaDungDau() {
        let cards = [card("headline", .released("1.15.0"), priority: 1, action: needsData),
                     card("help", .released("1.14.0"), priority: 9, action: always),
                     card("stale", .released("1.14.0"), priority: 8, action: needsData)]
        // Có lastSeen: chỉ thẻ 1.15.0 trong khoảng.
        XCTAssertEqual(shown(select(lastSeen: "1.14.2", current: "1.15.0", cards))?.0, ["headline"])
        // Khách cũ chưa có lastSeen: thẻ mới nhất đứng đầu, thẻ cũ không đích (stale) vẫn bị bỏ.
        XCTAssertEqual(shown(select(lastSeen: nil, current: "1.15.0", cards))?.0, ["headline", "help"])
    }

    /// Bản sửa lỗi không có thẻ riêng: khách nhảy thẳng 1.14.2 → 1.15.1 ⇒ thẻ 1.15.0 là bản mới nhất trong khoảng.
    func testBanMoiNhatTinhTheoKhoangKhongTheoCurrent() {
        let cards = [card("headline", .released("1.15.0"), action: needsData)]
        XCTAssertEqual(shown(select(lastSeen: "1.14.2", current: "1.15.1", cards))?.0, ["headline"])
    }

    /// Luật "đã dùng" vẫn áp cho thẻ bản mới nhất: khách đã dùng tính năng thì không cần giới thiệu.
    func testTheBanMoiNhatDaDungVanBiBo() {
        let cards = [card("headline", .released("1.15.0"), action: needsData),
                     card("help", .released("1.14.0"), action: always)]
        XCTAssertEqual(shown(select(lastSeen: nil, current: "1.15.0", cards, used: ["headline"]))?.0, ["help"])
    }

    // MARK: - Khách cũ chưa có lastSeen, hoà ưu tiên, .unreleased

    func testKhachCuChuaCoLastSeenThayToanCatalog() {
        let cards = [card("a", .released("1.10.0"), priority: 1), card("b", .released("1.14.0"), priority: 2),
                     card("future", .released("1.15.0"), priority: 9)]
        guard let (ids, more, from) = shown(select(lastSeen: nil, current: "1.14.0", existing: true, cards))
        else { return }
        XCTAssertEqual(ids, ["b", "a"])
        XCTAssertEqual(more, 0)
        XCTAssertNil(from)
    }

    func testHoaUuTienBanMoiTruocRoiId() {
        let cards = [card("z_old", .released("1.11.0")), card("b_new", .released("1.13.0")),
                     card("a_new", .released("1.13.0"))]
        XCTAssertEqual(shown(select(lastSeen: "1.10.0", current: "1.14.0", cards))?.0, ["a_new", "b_new", "z_old"])
    }

    func testUnreleasedTinhNhuCurrent() {
        let cards = [card("dev", .unreleased, priority: 1), card("old", .released("1.13.0"), priority: 9)]
        // lastSeen 1.13.0 < current ⇒ thẻ .unreleased có, thẻ 1.13.0 đã thấy.
        XCTAssertEqual(shown(select(lastSeen: "1.13.0", current: "1.14.0", cards))?.0, ["dev"])
        // Đã xem ở chính bản này ⇒ .unreleased không hiện lại.
        XCTAssertEqual(markSeen(select(lastSeen: "1.14.0", current: "1.14.0", cards)), false)
        // Hoà ưu tiên: .unreleased (= current) đứng trước bản cũ hơn.
        let tie = [card("a_old", .released("1.13.0")), card("z_dev", .unreleased)]
        XCTAssertEqual(shown(select(lastSeen: "1.12.0", current: "1.14.0", tie))?.0, ["z_dev", "a_old"])
    }

    func testCardVersionEffective() {
        XCTAssertEqual(CardVersion.unreleased.effective(current: v("1.14.0")), v("1.14.0"))
        XCTAssertEqual(CardVersion.released("1.12.0").effective(current: v("1.14.0")), v("1.12.0"))
        XCTAssertEqual(CardVersion.released("1.12.0"), .released(v("1.12.0")))
    }

    func testClosureMacDinhTraFalse() {
        let c = card("a", .unreleased)
        XCTAssertFalse(c.usedWhen(.paywallView(source: "settings")))
        XCTAssertFalse(c.usedOnDisk(ClosureUsageProbe(["anything": { true }])))
    }

    // MARK: - resolve: đích do app quyết qua `WhatsNewResolver`

    /// Selector hỏi resolver bằng ĐÚNG action của thẻ (khoá), và chỉ cho thẻ bản cũ cần kiểm đích.
    func testResolverNhanDungActionCuaThe() {
        var asked: [String] = []
        let spy: WhatsNewResolver = { a in asked.append(a.key); return WhatsNewResolvedAction(key: a.key) }
        let cards = [card("old", .released("1.13.0"), action: WhatsNewAction(key: "old_target")),
                     card("new", .released("1.14.0"), action: WhatsNewAction(key: "new_target"))]
        XCTAssertEqual(shown(select(lastSeen: "1.12.0", current: "1.14.0", cards, resolve: spy))?.0, ["new", "old"])
        XCTAssertTrue(asked.contains("old_target"))
        XCTAssertFalse(asked.contains { $0 != "old_target" && $0 != "new_target" })
    }

    /// Cùng một thẻ bản cũ: resolver có đích ⇒ giữ; resolver nil ⇒ bỏ. Kết quả do resolver quyết, không do khoá.
    func testCungTheBanCuGiuHayBoTheoResolver() {
        let cards = [card("old", .released("1.13.0"), priority: 9, action: WhatsNewAction(key: "target")),
                     card("new", .released("1.14.0"), priority: 1)]
        let yes: WhatsNewResolver = { WhatsNewResolvedAction(key: $0.key) }
        let no: WhatsNewResolver = { _ in nil }
        XCTAssertEqual(shown(select(lastSeen: "1.12.0", current: "1.14.0", cards, resolve: yes))?.0, ["new", "old"])
        XCTAssertEqual(shown(select(lastSeen: "1.12.0", current: "1.14.0", cards, resolve: no))?.0, ["new"])
    }

    /// Thẻ thông tin (không có action) không có đích để thiếu ⇒ không bị luật "bỏ thẻ không đích" loại, và resolver
    /// không bị hỏi cho nó.
    func testTheKhongCoActionKhongBiBoVaKhongHoiResolver() {
        var asked = 0
        let spy: WhatsNewResolver = { _ in asked += 1; return nil }
        let cards = [card("info", .released("1.13.0"), priority: 9, action: nil),
                     card("new", .released("1.14.0"), priority: 1, action: nil)]
        XCTAssertEqual(shown(select(lastSeen: "1.12.0", current: "1.14.0", cards, resolve: spy))?.0, ["new", "info"])
        XCTAssertEqual(asked, 0)
    }

    /// `resolvedAction(_:)` của thẻ trả đúng kết quả resolver (kể cả payload) — sheet/danh sách vẽ nút từ đây.
    func testResolvedActionMangPayloadCuaResolver() {
        let resolve: WhatsNewResolver = { WhatsNewResolvedAction(key: $0.key, payload: ["item": "42"]) }
        let c = card("a", .released("1.13.0"), action: WhatsNewAction(key: "open_item"))
        XCTAssertEqual(c.resolvedAction(resolve), WhatsNewResolvedAction(key: "open_item", payload: ["item": "42"]))
        XCTAssertNil(card("b", .released("1.13.0"), action: nil).resolvedAction(resolve))
        XCTAssertNil(c.resolvedAction { _ in nil })
    }
}
