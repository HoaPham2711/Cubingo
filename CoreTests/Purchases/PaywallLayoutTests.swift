@testable import AppHost
import XCTest

/// Bố cục paywall theo cỡ chữ: cỡ trợ năng thì chọn gói + CTA + điều khoản phải nằm trong vùng cuộn (ghim thì bị đẩy
/// ra ngoài màn, không với tới được); cỡ thường giữ chân màn ghim như cũ.
final class PaywallLayoutTests: XCTestCase {

    func testCoChuThuongGhimChanMan() {
        XCTAssertTrue(PaywallLayout.pinsFooter(isAccessibilitySize: false))
    }

    func testCoChuTroNangKhongGhimChanMan() {
        XCTAssertFalse(PaywallLayout.pinsFooter(isAccessibilitySize: true))
    }
}
