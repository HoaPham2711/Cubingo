@testable import AppHost
import XCTest

final class ScanCameraAuthTests: XCTestCase {
    func testTrangThaiQuyen() {
        XCTAssertEqual(ScanPermissionModel.screen(for: .denied), .denied)
        XCTAssertEqual(ScanPermissionModel.screen(for: .notDetermined), .explain)
        XCTAssertEqual(ScanPermissionModel.screen(for: .authorized), .camera)
        let fake = ScanCameraAuth(status: { .denied }, request: { false })
        XCTAssertEqual(ScanPermissionModel.screen(for: fake.status()), .denied)
    }
}
