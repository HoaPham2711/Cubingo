import XCTest
@testable import AppHost

/// Dấu INTERNAL: chỉ ở build INTERNAL và KHÔNG ở route `-uiPreview` — ảnh review/ảnh store chụp qua route phải sạch.
final class InternalBadgeTests: XCTestCase {
    func testAnKhiChayRoutePreview() {
        XCTAssertFalse(InternalBuild.showsBadge(isInternal: true, uiPreviewRoute: "home"))
        XCTAssertFalse(InternalBuild.showsBadge(isInternal: true, uiPreviewRoute: "paywall"))
    }

    func testHienKhiChayThuongOBuildInternal() {
        XCTAssertTrue(InternalBuild.showsBadge(isInternal: true, uiPreviewRoute: nil))
    }

    func testKhongBaoGioHienNgoaiBuildInternal() {
        XCTAssertFalse(InternalBuild.showsBadge(isInternal: false, uiPreviewRoute: nil))
        XCTAssertFalse(InternalBuild.showsBadge(isInternal: false, uiPreviewRoute: "home"))
    }
}
