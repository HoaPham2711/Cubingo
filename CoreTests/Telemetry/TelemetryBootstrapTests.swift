@testable import AppHost
import XCTest

/// Khởi động telemetry: chỉ cấu hình Firebase khi có plist, không Simulator, không host test — gọi
/// `FirebaseApp.configure()` thiếu plist là Firebase ném exception, app chết ngay lúc mở.
final class TelemetryBootstrapTests: XCTestCase {

    override func tearDown() {
        Track.reset()
        super.tearDown()
    }

    func testThieuPlistKhongCauHinh() {
        XCTAssertFalse(TelemetryBootstrap.shouldConfigure(hasPlist: false, isSimulator: false, isUnitTestHost: false))
    }

    func testSimulatorKhongCauHinh() {
        XCTAssertFalse(TelemetryBootstrap.shouldConfigure(hasPlist: true, isSimulator: true, isUnitTestHost: false))
    }

    func testHostTestKhongCauHinh() {
        XCTAssertFalse(TelemetryBootstrap.shouldConfigure(hasPlist: true, isSimulator: false, isUnitTestHost: true))
    }

    func testDuDieuKienThiCauHinh() {
        XCTAssertTrue(TelemetryBootstrap.shouldConfigure(hasPlist: true, isSimulator: false, isUnitTestHost: false))
    }

    func testStartTrongHostTestGiuNoOp() {
        TelemetryBootstrap.start(.init(crashDomainPrefix: "t", appleAdsEnabled: true))
        XCTAssertTrue(Track.isUsingNoOpSink)
    }

    /// Bootstrap đã quyết KHÔNG cấu hình (host test / Simulator / thiếu plist) ⇒ bật lại consent không được gắn
    /// sink Firebase hay chạm SDK chưa cấu hình; tắt consent cũng không làm gì.
    func testConsentDidChangeKhiChuaCauHinhLaNoOp() {
        TelemetryBootstrap.start(.init(crashDomainPrefix: "t", appleAdsEnabled: true))
        TelemetryBootstrap.consentDidChange(true)
        XCTAssertTrue(Track.isUsingNoOpSink)
        TelemetryBootstrap.consentDidChange(false)
        TelemetryBootstrap.consentDidChange(true)
        XCTAssertTrue(Track.isUsingNoOpSink)
    }
}
