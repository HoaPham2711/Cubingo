import XCTest
@testable import AppHost

/// Logic thuần của màn Settings: hàng/nhóm nào hiện theo cấu hình, ánh xạ kết quả Khôi phục → alert, link.
/// Cấu hình dựng tường minh bằng `AppConfig(info:)` — không phụ thuộc giá trị thật trong `app.config.toml`.
final class SettingsModelTests: XCTestCase {

    private struct FakeTransport: FeedbackTransport {
        func send(_ draft: FeedbackDraft) async throws {}
    }

    private func config(_ info: [String: Any]) -> AppConfig { AppConfig(info: info) }

    // MARK: - shows*

    func testAccountHienKhiBatPaywall() {
        XCTAssertTrue(SettingsModel.showsAccount(config: config(["FeaturePaywall": "YES", "ProductIDs": "p.a"])))
    }

    /// App miễn phí hoàn toàn không thấy gì về Pro.
    func testAccountAnKhiTatPaywall() {
        XCTAssertFalse(SettingsModel.showsAccount(config: config(["FeaturePaywall": "NO", "ProductIDs": "p.a"])))
        XCTAssertFalse(SettingsModel.showsAccount(config: config([:])))
    }

    func testFormPhanHoiHienKhiCoTransport() {
        XCTAssertTrue(SettingsModel.showsFeedbackForm(transport: FakeTransport()))
    }

    /// Không có web API ⇒ không có form (mở Mail không xác nhận được là đã gửi), chỉ còn "Contact us".
    func testFormPhanHoiAnKhiKhongCoTransport() {
        XCTAssertFalse(SettingsModel.showsFeedbackForm(transport: nil))
    }

    func testRateHienKhiCoAppStoreID() {
        XCTAssertTrue(SettingsModel.showsRateRow(config: config(["AppStoreID": "123456"])))
    }

    func testRateAnKhiAppStoreIDRong() {
        XCTAssertFalse(SettingsModel.showsRateRow(config: config([:])))
        XCTAssertFalse(SettingsModel.showsRateRow(config: config(["AppStoreID": ""])))
        XCTAssertFalse(SettingsModel.showsRateRow(config: config(["AppStoreID": "   "])))
    }

    func testContactHienKhiCoEmail() {
        XCTAssertTrue(SettingsModel.showsContactRow(config: config(["SupportEmail": "help@example.com"])))
    }

    func testContactAnKhiEmailRong() {
        XCTAssertFalse(SettingsModel.showsContactRow(config: config([:])))
        XCTAssertFalse(SettingsModel.showsContactRow(config: config(["SupportEmail": "  "])))
    }

    // MARK: - Đánh giá + cập nhật

    func testLinkDanhGiaDungDangApple() {
        XCTAssertEqual(SettingsModel.reviewURL(config: config(["AppStoreID": " 123456 "]))?.absoluteString,
                       "https://apps.apple.com/app/id123456?action=write-review")
        XCTAssertNil(SettingsModel.reviewURL(config: config([:])))
    }

    /// Hàng "Update to …" chỉ khi có App Store id VÀ checker báo có bản mới.
    func testHangCapNhatTheoTrangThaiVaAppStoreID() {
        let url = URL(string: "https://apps.apple.com/app/id1")!
        let co = UpdateStatus.available(version: "2.0", url: url, notes: nil)
        XCTAssertEqual(SettingsModel.updateVersion(config: config(["AppStoreID": "1"]), status: co), "2.0")
        XCTAssertNil(SettingsModel.updateVersion(config: config(["AppStoreID": "1"]), status: .upToDate))
        XCTAssertNil(SettingsModel.updateVersion(config: config([:]), status: co))
    }

    // MARK: - Khôi phục

    /// Ba nhánh không được gộp: nói với người ĐÃ trả tiền rằng họ chưa từng mua (vì mạng lỗi) là sai sự thật.
    func testBaNhanhKhoiPhuc() {
        XCTAssertNil(SettingsModel.restoreAlert(for: .restored), "khôi phục được ⇒ không alert, hàng trạng thái tự đổi")
        let none = SettingsModel.restoreAlert(for: .noPurchasesFound)
        let failed = SettingsModel.restoreAlert(for: .failed)
        XCTAssertNotNil(none)
        XCTAssertNotNil(failed)
        XCTAssertNotEqual(none, failed)
        XCTAssertNotEqual(none?.title, failed?.title)
    }

    /// `RestoreAlert.make` là nguồn DUY NHẤT: Settings và paywall trả đúng nó (không còn ánh xạ riêng trôi lệch).
    func testRestoreAlertBaNhanh() {
        XCTAssertNil(RestoreAlert.make(.restored))
        let none = RestoreAlert.make(.noPurchasesFound)
        let failed = RestoreAlert.make(.failed)
        XCTAssertNotNil(none)
        XCTAssertNotNil(failed)
        XCTAssertNotEqual(none?.title, failed?.title)
        XCTAssertNotEqual(none?.message, failed?.message)
        for outcome in [Entitlements.RestoreOutcome.restored, .noPurchasesFound, .failed] {
            XCTAssertEqual(SettingsModel.restoreAlert(for: outcome), RestoreAlert.make(outcome), "\(outcome)")
            XCTAssertEqual(PaywallView.restoreAlert(for: outcome), RestoreAlert.make(outcome), "\(outcome)")
        }
    }

    /// Chỉ lỗi mạng/App Store là "bực mình do app" — chưa từng mua là kết quả hợp lệ.
    func testChiLoiKhoiPhucMoiChanHoiDanhGia() {
        XCTAssertTrue(SettingsModel.countsAsReviewFriction(.failed))
        XCTAssertFalse(SettingsModel.countsAsReviewFriction(.noPurchasesFound))
        XCTAssertFalse(SettingsModel.countsAsReviewFriction(.restored))
    }

    // MARK: - Đồng ý số liệu, link, phiên bản

    /// Mặc định của toggle "Share usage data" PHẢI khớp `TelemetryConsent` trên máy chưa từng ghi — lệch là UI
    /// hiện BẬT trong khi hệ thống đang TẮT (hoặc ngược lại).
    func testMacDinhChiaSeSoLieuKhopTelemetryConsent() {
        let suite = "SettingsModelTests.\(UUID().uuidString)"
        let d = UserDefaults(suiteName: suite)!
        defer { d.removePersistentDomain(forName: suite) }
        XCTAssertEqual(SettingsModel.shareUsageDataDefault, TelemetryConsent.isEnabled(in: d))
    }

    func testHangLinkAnKhiKhongCoHost() {
        XCTAssertTrue(SettingsModel.linkRows(AppLinks(config: config([:]))).isEmpty)
        let rows = SettingsModel.linkRows(AppLinks(config: config(["WebHost": "example.com"])))
        XCTAssertEqual(rows.map(\.url.absoluteString),
                       ["https://example.com/privacy/", "https://example.com/terms/", "https://example.com/"])
        XCTAssertEqual(Set(rows.map(\.id)).count, rows.count)
    }

    func testChuoiPhienBan() {
        XCTAssertEqual(SettingsModel.versionText(config: config(["CFBundleShortVersionString": "1.2.3",
                                                                 "CFBundleVersion": "45"])), "1.2.3 (45)")
    }
}
