@testable import AppHost
import XCTest

final class AppEnvironmentTests: XCTestCase {
    func testHostUnitTestDuocNhanRa() {
        XCTAssertTrue(AppEnvironment.isUnitTestHost)
    }

    func testDocGiaTriSauLaunchArgument() {
        XCTAssertEqual(AppEnvironment.value(afterArgument: "-uiPreview", in: ["x", "-uiPreview", "home"]), "home")
        XCTAssertNil(AppEnvironment.value(afterArgument: "-uiPreview", in: ["x", "-uiPreview"]))
        XCTAssertNil(AppEnvironment.value(afterArgument: "-uiPreview", in: ["x"]))
        XCTAssertNil(AppEnvironment.value(afterArgument: "-uiPreview", in: ["-uiPreview", "-khac"]))
    }

    func testChayTrenSimulator() {
        XCTAssertTrue(AppEnvironment.isSimulator)   // suite chỉ chạy trên Simulator
    }
}
