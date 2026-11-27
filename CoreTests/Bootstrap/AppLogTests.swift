@testable import AppHost
import XCTest

final class AppLogTests: XCTestCase {
    func testGhiRaFileKhiInternal() throws {
        // Test chạy ở Debug (có cờ INTERNAL) ⇒ file log phải có và chứa dòng vừa ghi.
        let token = "abc-\(UUID().uuidString)"
        applog(token)
        let url = try XCTUnwrap(AppLog.fileURL)
        let text = try String(contentsOf: url, encoding: .utf8)
        XCTAssertTrue(text.contains(token))
    }

    func testXoayVongKhiVuotTran() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("AppLogTests-\(UUID().uuidString)")
        addTeardownBlock { try? FileManager.default.removeItem(at: dir) }
        let log = AppLogFile(url: dir.appendingPathComponent("app.log"), maxBytes: 120)
        log.append("dong-1-" + String(repeating: "a", count: 50))
        log.append("dong-2-" + String(repeating: "b", count: 50))   // vượt trần ⇒ xoay vòng
        log.append("dong-3")
        let current = try String(contentsOf: XCTUnwrap(log.url), encoding: .utf8)
        let rotated = try String(contentsOf: XCTUnwrap(log.rotatedURL), encoding: .utf8)
        XCTAssertFalse(current.contains("dong-1"))
        XCTAssertTrue(current.contains("dong-2") && current.contains("dong-3"))
        XCTAssertTrue(rotated.contains("dong-1"))
        XCTAssertFalse(rotated.contains("dong-2"))
        XCTAssertLessThanOrEqual(try XCTUnwrap(current.data(using: .utf8)).count, 120)
    }
}
