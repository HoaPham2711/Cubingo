import XCTest
@testable import AppHost

final class DesignTokensTests: XCTestCase {

    func testHexComponentsPureWhite() {
        let c = hexComponents(0xFFFFFF)
        XCTAssertEqual(c.red, 1.0, accuracy: 0.001)
        XCTAssertEqual(c.green, 1.0, accuracy: 0.001)
        XCTAssertEqual(c.blue, 1.0, accuracy: 0.001)
    }

    func testHexComponentsPureBlack() {
        let c = hexComponents(0x000000)
        XCTAssertEqual(c.red, 0, accuracy: 0.001)
        XCTAssertEqual(c.green, 0, accuracy: 0.001)
        XCTAssertEqual(c.blue, 0, accuracy: 0.001)
    }

    func testHexComponentsAccentTeal() {
        // #4CD9CE — giá trị mặc định của template cho `DSColor.accent`
        let c = hexComponents(0x4CD9CE)
        XCTAssertEqual(c.red, Double(0x4C) / 255, accuracy: 0.001)
        XCTAssertEqual(c.green, Double(0xD9) / 255, accuracy: 0.001)
        XCTAssertEqual(c.blue, Double(0xCE) / 255, accuracy: 0.001)
    }
}
