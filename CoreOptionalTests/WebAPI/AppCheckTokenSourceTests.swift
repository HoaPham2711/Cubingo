import XCTest
@testable import AppHost

/// `AppCheckTokenSource` không được chạm SDK khi Firebase chưa cấu hình (`AppCheck.appCheck()` crash nếu không có
/// app mặc định) — template không chứa `GoogleService-Info.plist`, Simulator và host unit test không bao giờ configure.
final class AppCheckTokenSourceTests: XCTestCase {

    func testChiHoiSDKKhiThietBiThatDaCauHinhFirebase() {
        typealias S = AppCheckTokenSource
        XCTAssertTrue(S.canUseSDK(isSimulator: false, isUnitTestHost: false, firebaseConfigured: true))
        XCTAssertFalse(S.canUseSDK(isSimulator: true, isUnitTestHost: false, firebaseConfigured: true))
        XCTAssertFalse(S.canUseSDK(isSimulator: false, isUnitTestHost: true, firebaseConfigured: true))
        XCTAssertFalse(S.canUseSDK(isSimulator: false, isUnitTestHost: false, firebaseConfigured: false))
    }

    /// Ở host test: không crash, không token, không ném.
    func testTokenNilVaCaiProviderAnToanKhiKhongCoFirebase() async {
        AppCheckTokenSource.installProvider()
        let token = await AppCheckTokenSource.currentToken()
        XCTAssertNil(token)
    }
}
