#if DEBUG
@testable import AppHost
import XCTest

/// `screen_view` gắn tay vì SwiftUI không được Firebase tự bắt. Rủi ro chính không phải thiếu
/// event mà là THỪA: `onAppear` chạy lại mỗi lần view quay về từ cover/sheet.
final class ScreenTrackingTests: XCTestCase {

    override func tearDown() { FirebaseScreenBridge.handler = { _ in }; super.tearDown() }

    /// SDK làm rơi `firebase_screen` trên iOS 27 ⇒ tên màn phải đi kèm một param tự đặt
    /// (đổi tên param là gãy báo cáo bù tên màn đang đọc nó).
    func testThamSoTuDatMangTenMan() {
        XCTAssertEqual(FirebaseScreenBridge.customParameters(for: "paywall") as? [String: String],
                       ["screen_label": "paywall"])
    }

    func testVaoCungManNhieuLanChiBanMotLan() {
        var banRa: [String] = []
        FirebaseScreenBridge.handler = { banRa.append($0) }
        let t = ScreenTracker()
        t.enter("home"); t.enter("home"); t.enter("home")
        XCTAssertEqual(banRa, ["home"],
                       "onAppear chạy lại khi quay về từ cover — bắn trùng làm phồng screen_view")
    }

    func testDoiManThiBanTiep() {
        var banRa: [String] = []
        FirebaseScreenBridge.handler = { banRa.append($0) }
        let t = ScreenTracker()
        t.enter("home"); t.enter("library"); t.enter("home")
        XCTAssertEqual(banRa, ["home", "library", "home"],
                       "quay lại màn cũ SAU khi đã sang màn khác là một lượt xem mới")
    }

    // MARK: - Màn phủ

    /// Màn bên dưới KHÔNG `onAppear` lại khi cover đóng — không trả tên thì GA4 tính thời gian
    /// ở Home cho `paywall`.
    func testDongManPhuThiTraLaiManBenDuoi() {
        var banRa: [String] = []
        FirebaseScreenBridge.handler = { banRa.append($0) }
        let t = ScreenTracker()
        t.enter("home"); t.push("detail"); t.push("paywall"); t.pop("paywall"); t.pop("detail")
        XCTAssertEqual(banRa, ["home", "detail", "paywall", "detail", "home"])
    }

    /// Tab bên dưới một cover vẫn có thể `onAppear` — bắn lúc đó là gán nhầm thời gian của cover.
    func testManNenXuatHienDuoiManPhuThiIMLANG() {
        var banRa: [String] = []
        FirebaseScreenBridge.handler = { banRa.append($0) }
        let t = ScreenTracker()
        t.enter("home"); t.push("detail"); t.enter("library"); t.pop("detail")
        XCTAssertEqual(banRa, ["home", "detail", "library"],
                       "màn nền đổi ngầm chỉ được báo khi cover đóng")
    }

    func testOnAppearLapLaiCuaManPhuKhongChongNganXep() {
        var banRa: [String] = []
        FirebaseScreenBridge.handler = { banRa.append($0) }
        let t = ScreenTracker()
        t.enter("home"); t.push("editor"); t.push("editor"); t.pop("editor")
        XCTAssertEqual(banRa, ["home", "editor", "home"],
                       "push trùng mà chồng hai tầng thì một lần pop không về được màn nền")
    }

    /// Hai cover đóng cùng lúc: `onDisappear` không bảo đảm LIFO.
    func testPopSaiThuTuVanVeDung() {
        var banRa: [String] = []
        FirebaseScreenBridge.handler = { banRa.append($0) }
        let t = ScreenTracker()
        t.enter("home"); t.push("detail"); t.push("settings"); t.pop("detail"); t.pop("settings")
        XCTAssertEqual(banRa, ["home", "detail", "settings", "home"])
    }

    func testDoiCheDoManPhuKhongBanManNenXenGiua() {
        var banRa: [String] = []
        FirebaseScreenBridge.handler = { banRa.append($0) }
        let t = ScreenTracker()
        t.enter("home"); t.push("editor_draw"); t.swap("editor_draw", "editor_text"); t.pop("editor_text")
        XCTAssertEqual(banRa, ["home", "editor_draw", "editor_text", "home"])
    }
}
#endif
