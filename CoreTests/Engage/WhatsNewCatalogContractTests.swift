import XCTest
@testable import AppHost

/// Hợp đồng mọi catalog What's New phải giữ (`WhatsNewCatalogContract`). Catalog dựng tay; bản bundle truyền vào
/// tường minh — không đọc cấu hình thật của template.
final class WhatsNewCatalogContractTests: XCTestCase {

    private let bundle = AppVersion("2.0.0")!

    private func card(_ id: String = "good_card", version: CardVersion = .released("1.0.0"),
                      systemImage: String = "star", title: String = "Title", body: String = "Body text.",
                      cta: String = "Try it", action: WhatsNewAction? = WhatsNewAction(key: "go")) -> WhatsNewCard {
        WhatsNewCard(id: id, version: version, priority: 1, systemImage: systemImage, title: title, body: body,
                     ctaTitle: cta, action: action)
    }

    private func violations(_ cards: [WhatsNewCard]) -> [String] {
        WhatsNewCatalogContract.violations(cards, bundleVersion: bundle)
    }

    func testCatalogHopLeKhongViPham() {
        XCTAssertEqual(violations([card("a"), card("b_two", version: .released("2.0.0")),
                                   card("c3", cta: "", action: nil)]), [])
        XCTAssertEqual(violations([]), [])
    }

    func testIdTrungHoacKhongSnakeCase() {
        XCTAssertEqual(violations([card("dup"), card("dup")]).count, 1)
        for bad in ["Camel", "with-dash", "trailing_", "_lead", "two__under", "9start", ""] {
            XCTAssertEqual(violations([card(bad)]).count, 1, "id '\(bad)' phải bị bắt")
        }
    }

    func testChuRongHoacQuaDai() {
        XCTAssertEqual(violations([card(title: "")]).count, 1)
        XCTAssertEqual(violations([card(title: String(repeating: "a", count: 31))]).count, 1)
        XCTAssertEqual(violations([card(title: String(repeating: "a", count: 30))]), [])
        XCTAssertEqual(violations([card(body: "")]).count, 1)
        XCTAssertEqual(violations([card(body: String(repeating: "b", count: 91))]).count, 1)
        XCTAssertEqual(violations([card(body: String(repeating: "b", count: 90))]), [])
        XCTAssertEqual(violations([card(title: "Wow!")]).count, 1, "không dùng '!'")
    }

    /// Nhãn nút chỉ bắt buộc (và chỉ bị giới hạn ≤ 3 từ) khi thẻ có action — thẻ thông tin không vẽ nút.
    func testNhanNutTheoAction() {
        XCTAssertEqual(violations([card(cta: "")]).count, 1)
        XCTAssertEqual(violations([card(cta: "One two three four")]).count, 1)
        XCTAssertEqual(violations([card(cta: "One two three")]), [])
        XCTAssertEqual(violations([card(cta: "", action: nil)]), [])
    }

    func testSFSymbolKhongTonTai() {
        XCTAssertEqual(violations([card(systemImage: "no.such.symbol.anywhere")]).count, 1)
        XCTAssertEqual(violations([card(systemImage: "sparkles")]), [])
    }

    func testBanReleasedVuotBundleHoacKhongDuXYZ() {
        XCTAssertEqual(violations([card(version: .released("2.0.1"))]).count, 1)
        XCTAssertEqual(violations([card(version: .released("1.5"))]).count, 1, "viết đủ X.Y.Z")
        XCTAssertEqual(violations([card(version: .released("2.0.0"))]), [])
    }

    /// Thẻ chưa đóng dấu là trạng thái bình thường trên nhánh phát triển (build Store không biên dịch được nếu còn)
    /// ⇒ hợp đồng không kiểm bản của nó.
    func testTheChuaDongDauKhongBiKiemBan() {
        XCTAssertEqual(violations([card(version: .unreleased)]), [])
    }

    /// Mỗi vi phạm nêu tên thẻ để người sửa catalog tìm được ngay.
    func testViPhamNeuIdThe() {
        let v = violations([card("named_card", title: "")])
        XCTAssertEqual(v.count, 1)
        XCTAssertTrue(v.first?.contains("named_card") ?? false, "\(v)")
    }
}
