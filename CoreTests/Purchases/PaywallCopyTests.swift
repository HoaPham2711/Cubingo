@testable import AppHost
import XCTest

/// Copy của paywall là nghĩa vụ pháp lý, không phải trang trí: nói "free trial" với người không
/// còn đủ điều kiện, HOẶC với gói KHÔNG có introductory offer, là quảng cáo sai giá
/// (Guideline 3.1.2) và đẻ ra khiếu nại hoàn tiền. Có trial hay không là thuộc tính của từng
/// sản phẩm (`ProProduct.freeTrialDays`, đọc từ StoreKit) — không suy theo chu kỳ tháng/năm.
/// Gói trọn đời (mua đứt) không bao giờ được nói tới dùng thử, "free", gia hạn hay huỷ.
/// Id/giá ở đây là giá trị mẫu, không phụ thuộc cấu hình thật của app.
final class PaywallCopyTests: XCTestCase {

    private func sub(_ kind: ProProduct.Kind, _ price: String, trial: Int?) -> ProProduct {
        ProProduct(id: "test.\(kind)", displayPrice: price, kind: kind, freeTrialDays: trial)
    }

    func testDuDieuKienVaGoiCoTrialThiChaoDungThu() {
        let cta = PaywallCopy.cta(for: sub(.year, "$30", trial: 7), eligibleForTrial: true)
        XCTAssertTrue(cta.lowercased().contains("trial"))
        XCTAssertTrue(cta.contains("7"))
    }

    func testDaDungTrialThiKhongChaoDungThuNua() {
        let cta = PaywallCopy.cta(for: sub(.year, "$30", trial: 7), eligibleForTrial: false)
        XCTAssertFalse(cta.lowercased().contains("trial"))
    }

    func testGoiKhongCoOfferThiKhongChaoDungThuDuDuDieuKien() {
        let p = sub(.month, "123.000 ₫", trial: nil)
        let cta = PaywallCopy.cta(for: p, eligibleForTrial: true)
        XCTAssertFalse(cta.lowercased().contains("trial"),
                       "gói không có introductory offer — hứa trial là sai giá")
        let terms = PaywallCopy.terms(for: p, eligibleForTrial: true)
        XCTAssertFalse(terms.lowercased().contains("free for"))
        XCTAssertTrue(terms.contains("123.000 ₫/month"))
    }

    /// Số ngày trên nút phải là số ngày CỦA OFFER, không phải hằng số 7 viết cứng.
    func testSoNgayLayTuOffer() {
        XCTAssertTrue(PaywallCopy.cta(for: sub(.year, "$30", trial: 14), eligibleForTrial: true).contains("14"))
        let terms = PaywallCopy.terms(for: sub(.year, "$11.99", trial: 3), eligibleForTrial: true)
        XCTAssertTrue(terms.contains("3 days"))
        XCTAssertFalse(terms.contains("7"))
    }

    func testDieuKhoanTrialGoiNamNeuGiaVaChuKyNam() {
        let terms = PaywallCopy.terms(for: sub(.year, "456.000 ₫", trial: 7), eligibleForTrial: true)
        XCTAssertTrue(terms.contains("456.000 ₫/year"))
        XCTAssertTrue(terms.lowercased().contains("free for 7 days"))
        XCTAssertTrue(terms.lowercased().contains("cancel"))
    }

    /// Gói tháng có trial: điều khoản phải nói giá THÁNG sau trial, không được mượn chu kỳ năm.
    func testDieuKhoanTrialGoiThangNeuGiaVaChuKyThang() {
        let terms = PaywallCopy.terms(for: sub(.month, "123.000 ₫", trial: 7), eligibleForTrial: true)
        XCTAssertTrue(terms.contains("123.000 ₫/month"))
        XCTAssertTrue(terms.lowercased().contains("free for 7 days"))
        XCTAssertFalse(terms.contains("/year"))
    }

    func testDieuKhoanNeuTuDongGiaHanKhiKhongTrial() {
        let terms = PaywallCopy.terms(for: sub(.year, "456.000 ₫", trial: 7), eligibleForTrial: false)
        XCTAssertTrue(terms.contains("456.000 ₫/year"))
        XCTAssertTrue(terms.lowercased().contains("auto-renew"))
        XCTAssertFalse(terms.lowercased().contains("free for"))
    }

    // MARK: - Gói trọn đời (hành vi mới so với nguồn)

    /// Mua đứt: điều khoản nêu giá là mua MỘT LẦN; không "auto-renews", không trial — kể cả khi group còn đủ
    /// điều kiện dùng thử (cờ đó là của subscription group, không áp cho gói trọn đời).
    func testGoiTronDoiKhongNoiTuGiaHan() {
        let p = ProProduct(id: "x", displayPrice: "$9", kind: .lifetime, freeTrialDays: nil)
        let t = PaywallCopy.terms(for: p, eligibleForTrial: true)
        XCTAssertFalse(t.localizedCaseInsensitiveContains("renew"))
        XCTAssertFalse(t.localizedCaseInsensitiveContains("trial"))
        XCTAssertFalse(t.localizedCaseInsensitiveContains("free"))
        XCTAssertFalse(t.localizedCaseInsensitiveContains("cancel"))
        XCTAssertTrue(t.contains("$9"))
        XCTAssertTrue(t.localizedCaseInsensitiveContains("one-time"))
    }

    /// Dù dữ liệu lỗi gắn `freeTrialDays` cho gói trọn đời, copy vẫn không được hứa dùng thử.
    func testCTAGoiTronDoiKhongNhacDungThu() {
        for trial in [nil, 7] as [Int?] {
            let p = ProProduct(id: "x", displayPrice: "$9", kind: .lifetime, freeTrialDays: trial)
            for eligible in [true, false] {
                let cta = PaywallCopy.cta(for: p, eligibleForTrial: eligible)
                XCTAssertFalse(cta.localizedCaseInsensitiveContains("trial"), cta)
                XCTAssertFalse(cta.localizedCaseInsensitiveContains("free"), cta)
                XCTAssertFalse(cta.localizedCaseInsensitiveContains("subscribe"), cta)
                XCTAssertTrue(cta.contains("$9"), "CTA mua đứt phải nêu giá: \(cta)")
                // Nút mua (thứ user bấm) phải nói bằng chữ đây là trả MỘT LẦN — "Buy for $9" thì không phân biệt
                // được với subscription. Ghim chữ thật sự mang nghĩa đó: "once" trong CTA.
                XCTAssertTrue(cta.localizedCaseInsensitiveContains("once"), "CTA mua đứt phải nói trả một lần: \(cta)")
                let terms = PaywallCopy.terms(for: p, eligibleForTrial: eligible)
                XCTAssertFalse(terms.localizedCaseInsensitiveContains("trial"), terms)
                XCTAssertFalse(terms.localizedCaseInsensitiveContains("renew"), terms)
                // Dòng điều khoản hiện ngay dưới nút cũng phải nói mua một lần (hai chuỗi hiện cùng nhau).
                XCTAssertTrue(terms.localizedCaseInsensitiveContains("one-time"), terms)
            }
        }
    }

    /// Nhãn và giá của hàng gói theo đúng loại gói.
    func testNhanVaGiaHangGoiTheoLoai() {
        XCTAssertEqual(PaywallCopy.planTitle(.month), "Monthly")
        XCTAssertEqual(PaywallCopy.planTitle(.year), "Yearly")
        XCTAssertEqual(PaywallCopy.planTitle(.lifetime), "Lifetime")
        XCTAssertEqual(PaywallCopy.planPrice(sub(.month, "$5", trial: nil)), "$5 / month")
        XCTAssertEqual(PaywallCopy.planPrice(sub(.year, "$30", trial: 7)), "$30 / year")
        let lifetime = PaywallCopy.planPrice(sub(.lifetime, "$80", trial: nil))
        XCTAssertTrue(lifetime.contains("$80"))
        XCTAssertFalse(lifetime.contains("/"), "gói trọn đời không có chu kỳ: \(lifetime)")
    }

    // MARK: - Gói chọn sẵn

    private let monthly = ProProduct(id: "test.m", displayPrice: "$5", kind: .month, freeTrialDays: 7)
    private let yearly = ProProduct(id: "test.y", displayPrice: "$30", kind: .year, freeTrialDays: 7)
    private let lifetime = ProProduct(id: "test.l", displayPrice: "$80", kind: .lifetime)

    /// Gói chọn sẵn PHẢI là id có thật trong danh sách đã tải — nếu không radio "chưa chọn" mà CTA tính tiền
    /// một id chưa từng hiện giá. Ưu tiên loại cấu hình, không có thì phần tử đầu, rỗng ⇒ nil.
    func testGoiChonSanPhaiCoThatTrongDanhSach() {
        let shapes: [[ProProduct]] = [[monthly, yearly, lifetime], [lifetime], [monthly], [yearly, monthly]]
        for products in shapes {
            for kind in [ProProduct.Kind.month, .year, .lifetime] {
                let id = PaywallView.initialSelection(products: products, preselected: kind)
                XCTAssertNotNil(id)
                XCTAssertTrue(products.contains { $0.id == id }, "\(String(describing: id)) không có trong danh sách")
            }
        }
        XCTAssertEqual(PaywallView.initialSelection(products: [monthly, yearly, lifetime], preselected: .year), yearly.id)
        XCTAssertEqual(PaywallView.initialSelection(products: [monthly, yearly, lifetime], preselected: .lifetime),
                       lifetime.id)
        XCTAssertEqual(PaywallView.initialSelection(products: [lifetime, monthly], preselected: .year), lifetime.id,
                       "không có loại chọn sẵn ⇒ phần tử đầu")
        XCTAssertNil(PaywallView.initialSelection(products: [], preselected: .year))
    }

    /// Danh sách đổi (tải lại): lựa chọn còn trong danh sách thì GIỮ; biến mất thì ghim lại vào id có thật.
    func testDanhSachDoiThiGhimLaiGoiChon() {
        XCTAssertEqual(PaywallView.pinnedSelection(current: monthly.id, products: [monthly, yearly],
                                                   preselected: .year), monthly.id)
        XCTAssertEqual(PaywallView.pinnedSelection(current: yearly.id, products: [monthly, lifetime],
                                                   preselected: .year), monthly.id)
        XCTAssertEqual(PaywallView.pinnedSelection(current: nil, products: [lifetime], preselected: .year), lifetime.id)
        XCTAssertNil(PaywallView.pinnedSelection(current: yearly.id, products: [], preselected: .year))
    }
}
