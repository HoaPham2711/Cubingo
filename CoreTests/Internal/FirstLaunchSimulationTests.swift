#if INTERNAL
import XCTest
@testable import AppHost

/// Toggle debug "Giả lập lần đầu mở app" — chỉ build INTERNAL. Dùng suite UserDefaults tạm (không đụng `.standard`).
/// `extraKeys`/`onReset` là static dùng chung ⇒ mỗi test trả về nguyên trạng trong tearDown.
final class FirstLaunchSimulationTests: XCTestCase {
    private var suite = ""
    private var d: UserDefaults!
    private var savedExtraKeys: [String] = []
    private var savedOnReset: ((UserDefaults) -> Void)!
    private var resetCalls = 0

    override func setUp() {
        suite = "FirstLaunchSimulationTests.\(UUID().uuidString)"
        d = UserDefaults(suiteName: suite)!
        savedExtraKeys = FirstLaunchSimulation.extraKeys
        savedOnReset = FirstLaunchSimulation.onReset
        resetCalls = 0
        FirstLaunchSimulation.extraKeys = ["test.extraFirstRun"]
        FirstLaunchSimulation.onReset = { [unowned self] _ in resetCalls += 1 }
        // Trạng thái "đã dùng app": qua tour, có khoá "chỉ lần đầu" của app, có tuỳ chọn không liên quan.
        d.set(true, forKey: WhatsNewHost.hasSeenOnboardingKey)
        d.set("đã xem", forKey: "test.extraFirstRun")
        d.set("list", forKey: "test.unrelatedOption")
    }

    override func tearDown() {
        FirstLaunchSimulation.extraKeys = savedExtraKeys
        FirstLaunchSimulation.onReset = savedOnReset
        d.removePersistentDomain(forName: suite)
        d = nil
    }

    func testTatThiKhongXoaGi() {
        FirstLaunchSimulation.applyAtLaunch(defaults: d)
        XCTAssertTrue(d.bool(forKey: WhatsNewHost.hasSeenOnboardingKey))
        XCTAssertEqual(d.string(forKey: "test.extraFirstRun"), "đã xem")
        XCTAssertEqual(resetCalls, 0, "tắt ⇒ không xin xoá TipKit")
    }

    func testBatThiMoiLanMoAppNhuLanDau() {
        d.set(true, forKey: FirstLaunchSimulation.enabledKey)
        FirstLaunchSimulation.applyAtLaunch(defaults: d)
        XCTAssertFalse(d.bool(forKey: WhatsNewHost.hasSeenOnboardingKey), "tour phải hiện lại")
        XCTAssertNil(d.object(forKey: "test.extraFirstRun"), "khoá app đăng ký (extraKeys) phải bị quên")
        XCTAssertEqual(resetCalls, 1, "TipKit xoá datastore trước configure")
        XCTAssertTrue(d.bool(forKey: FirstLaunchSimulation.enabledKey), "toggle vẫn bật cho lần sau")
    }

    /// Chỉ quên khoá đã đăng ký — KHÔNG xoá cả domain.
    func testKhongDungKhoaKhac() {
        d.set(true, forKey: FirstLaunchSimulation.enabledKey)
        FirstLaunchSimulation.applyAtLaunch(defaults: d)
        XCTAssertEqual(d.string(forKey: "test.unrelatedOption"), "list")
    }

    /// Bật toggle ⇒ áp dụng ngay (không đợi mở lại app); tắt ⇒ chỉ hạ cờ, không xoá thêm gì.
    func testBatToggleApDungNgay() {
        FirstLaunchSimulation.setEnabled(true, defaults: d)
        XCTAssertTrue(FirstLaunchSimulation.enabled(in: d))
        XCTAssertFalse(d.bool(forKey: WhatsNewHost.hasSeenOnboardingKey))
        XCTAssertNil(d.object(forKey: "test.extraFirstRun"))
        XCTAssertEqual(resetCalls, 1)
        d.set("lai", forKey: "test.extraFirstRun")
        FirstLaunchSimulation.setEnabled(false, defaults: d)
        XCTAssertFalse(FirstLaunchSimulation.enabled(in: d))
        XCTAssertEqual(d.string(forKey: "test.extraFirstRun"), "lai")
        XCTAssertEqual(resetCalls, 1)
    }

    /// Mặc định `onReset` là yêu cầu xoá TipKit thật (cờ chờ trong defaults), khoá onboarding lấy từ hằng của lõi.
    func testMacDinhDungHangCuaLoi() {
        FirstLaunchSimulation.onReset = savedOnReset
        XCTAssertTrue(FirstLaunchSimulation.firstRunKeys.contains(WhatsNewHost.hasSeenOnboardingKey))
        d.set(true, forKey: FirstLaunchSimulation.enabledKey)
        FirstLaunchSimulation.applyAtLaunch(defaults: d)
        XCTAssertTrue(d.bool(forKey: AppTips.resetPendingKey))
    }
}
#endif
