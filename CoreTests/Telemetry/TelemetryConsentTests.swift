@testable import AppHost
import XCTest

/// Cổng cho mặc định opt-out. Bẫy chính: `UserDefaults.bool(forKey:)` trả `false` khi key CHƯA
/// TỪNG được ghi — nếu đọc thẳng nó thì mọi user mới sẽ mặc định TẮT, ngược hẳn quyết định
/// opt-out, và không có triệu chứng nào ngoài "dashboard trống".
final class TelemetryConsentTests: XCTestCase {

    private var defaults: UserDefaults!
    private let suite = "TelemetryConsentTests"

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

    func testMacDinhBatKhiChuaTungGhi() {
        XCTAssertTrue(TelemetryConsent.isEnabled(in: defaults),
                      "user mới phải mặc định BẬT (opt-out)")
    }

    func testTatThiGiuTat() {
        TelemetryConsent.set(false, in: defaults)
        XCTAssertFalse(TelemetryConsent.isEnabled(in: defaults))
    }

    /// Cổng chống lệch: `@AppStorage(TelemetryConsent.defaultsKey) private var shareUsageData = true`
    /// trong `SettingsView` và `TelemetryConsent.isEnabled` phải cùng KEY và cùng MẶC ĐỊNH.
    /// Lệch = UI nói một đằng, hệ thống làm một nẻo, và không có triệu chứng nào nhìn thấy được.
    func testKeyDungTenVaMacDinhKhopUI() {
        XCTAssertEqual(TelemetryConsent.defaultsKey, "telemetry.shareUsageData")
        XCTAssertTrue(TelemetryConsent.isEnabled(in: defaults))
    }

    func testBatLaiDuocSauKhiTat() {
        TelemetryConsent.set(false, in: defaults)
        TelemetryConsent.set(true, in: defaults)
        XCTAssertTrue(TelemetryConsent.isEnabled(in: defaults))
    }
}
