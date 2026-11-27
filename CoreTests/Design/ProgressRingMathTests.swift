import XCTest
@testable import AppHost

final class ProgressRingMathTests: XCTestCase {

    func testZeroPercent() {
        XCTAssertEqual(ProgressRingMath.degrees(forPercent: 0), 0)
    }

    func testHalfway() {
        XCTAssertEqual(ProgressRingMath.degrees(forPercent: 50), 180)
    }

    func testFullProgress() {
        XCTAssertEqual(ProgressRingMath.degrees(forPercent: 100), 360)
    }

    func testClampsBelowZero() {
        XCTAssertEqual(ProgressRingMath.degrees(forPercent: -10), 0)
    }

    func testClampsAboveHundred() {
        XCTAssertEqual(ProgressRingMath.degrees(forPercent: 150), 360)
    }
}
