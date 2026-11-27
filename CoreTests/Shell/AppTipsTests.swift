import XCTest
@testable import AppHost

/// Khung TipKit của lõi — phần test được không cần dựng UI, không đụng datastore TipKit.
final class AppTipsTests: XCTestCase {

    /// `Tips.resetDatastore()` chỉ gọi được TRƯỚC `configure` ⇒ "Show tips again" đặt cờ, lần mở sau mới xoá.
    func testYeuCauResetDatCo() {
        let suite = "AppTipsTests.\(UUID().uuidString)"
        let d = UserDefaults(suiteName: suite)!
        defer { d.removePersistentDomain(forName: suite) }
        XCTAssertFalse(d.bool(forKey: AppTips.resetPendingKey))
        AppTips.requestReset(defaults: d)
        XCTAssertTrue(d.bool(forKey: AppTips.resetPendingKey))
    }
}
