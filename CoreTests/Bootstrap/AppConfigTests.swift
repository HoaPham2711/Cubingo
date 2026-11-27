@testable import AppHost
import XCTest

/// Test dựng `AppConfig(info:)` từ dictionary tự viết — không phụ thuộc giá trị cấu hình thật của template
/// (`new_app_check.sh` và `feature_matrix_check.sh` của template đều chạy lại `run_tests.py --full` dưới định danh khác / tổ hợp
/// tắt hết tính năng). Ngoại lệ duy nhất:
/// `testConfigThatCuaTemplateDocDuoc` chỉ kiểm Info.plist thật ĐỌC ĐƯỢC.
final class AppConfigTests: XCTestCase {
    func testDocDuKhoa() {
        let c = AppConfig(info: ["CFBundleDisplayName": "Bé's Notes 2", "WebHost": "example.com",
            "ProductIDs": "a b c", "FeaturePaywall": "YES", "FeatureAppleAds": "NO", "FeatureWebAPI": "NO"])
        XCTAssertEqual(c.displayName, "Bé's Notes 2")
        XCTAssertEqual(c.productIDs, ["a", "b", "c"])
        XCTAssertEqual(c.features, .init(paywall: true, appleAds: false, webAPI: false))
        XCTAssertEqual(c.privacyURL?.absoluteString, "https://example.com/privacy/")
        XCTAssertEqual(c.termsURL?.absoluteString, "https://example.com/terms/")
    }

    func testThieuKhoaKhongCrash() {
        let c = AppConfig(info: [:])
        XCTAssertNil(c.webHost); XCTAssertNil(c.privacyURL); XCTAssertEqual(c.productIDs, [])
        XCTAssertEqual(c.features, .init(paywall: false, appleAds: false, webAPI: false))
    }

    func testHostRongLaNil() { XCTAssertNil(AppConfig(info: ["WebHost": ""]).webHost) }

    func testConfigThatCuaTemplateDocDuoc() {            // Info.plist thật của host
        XCTAssertFalse(AppConfig.current.displayName.isEmpty)
        XCTAssertEqual(AppConfig.current.bundleID, Bundle.main.bundleIdentifier)
    }

    func testDuongDanWebVaApi() {
        let c = AppConfig(info: ["WebHost": "dev.example.com"])
        XCTAssertEqual(c.siteURL?.absoluteString, "https://dev.example.com/")
        XCTAssertEqual(c.supportURL?.absoluteString, "https://dev.example.com/support/")
        XCTAssertEqual(c.apiBaseURL?.absoluteString, "https://dev.example.com/")
    }

    func testGiaTriRongLaNilVaIdCachNhieuDauCach() {
        let c = AppConfig(info: ["AppStoreID": "", "SupportEmail": "", "ProductIDs": "  x   y "])
        XCTAssertNil(c.appStoreID)
        XCTAssertNil(c.supportEmail)
        XCTAssertEqual(c.productIDs, ["x", "y"])
    }

    func testDocPhienBanVaCoKieuBool() {
        let c = AppConfig(info: ["CFBundleIdentifier": "a.b", "CFBundleShortVersionString": "1.2.3",
                                 "CFBundleVersion": "7", "AppStoreID": "123", "SupportEmail": "s@x.io",
                                 "FeatureWebAPI": true, "FeaturePaywall": "NO"])
        XCTAssertEqual(c.bundleID, "a.b")
        XCTAssertEqual(c.version, "1.2.3")
        XCTAssertEqual(c.build, "7")
        XCTAssertEqual(c.appStoreID, "123")
        XCTAssertEqual(c.supportEmail, "s@x.io")
        XCTAssertEqual(c.features, .init(paywall: false, appleAds: false, webAPI: true))
    }
}
