import XCTest
@testable import AppHost

/// Cổng Simulator của route `-uiPreview`: argv giả đi qua phần thuần; kết quả chỉ có ở Simulator (test chạy ở đó),
/// device luôn nil/false (nhánh `#else` của `AppEnvironment` — xác nhận bằng đọc code, test không chạy trên device).
final class UIPreviewLaunchTests: XCTestCase {
    private enum Sample: String, UIPreviewRoute {
        case home, onboarding
        var isOnboarding: Bool { self == .onboarding }
    }

    func testFlagVaGiaTriDocTuArgv() throws {
        try XCTSkipUnless(AppEnvironment.isSimulator, "chỉ Simulator mới đọc route")
        let args = ["app", "-uiPreview", "home", "-uiPreviewTips", "-uiPreviewDepth", "3"]
        XCTAssertTrue(UIPreviewLaunch.flag("-uiPreviewTips", in: args))
        XCTAssertFalse(UIPreviewLaunch.flag("-khacHan", in: args))
        XCTAssertEqual(UIPreviewLaunch.value(after: "-uiPreviewDepth", in: args), "3")
        XCTAssertNil(UIPreviewLaunch.value(after: "-uiPreviewTips", in: args), "sau cờ là cờ khác ⇒ không có giá trị")
    }

    func testRouteCuaAppDungHopDong() {
        XCTAssertEqual(Sample(rawValue: "onboarding")?.isOnboarding, true)
        XCTAssertEqual(Sample.allCases.filter(\.isOnboarding).count, 1)
        XCTAssertNil(Sample(rawValue: "khong-co"))
    }
}
