@testable import AppHost
import XCTest

/// Thuộc tính người dùng gom một chỗ — thiếu chúng thì mọi báo cáo mất khả năng cắt lát. Lõi chỉ lo cơ chế;
/// danh sách thuộc tính là của app (`UserPropertySync.appProperties`).
final class UserPropertySyncTests: XCTestCase {

    private var sink: RecordingSink!
    private var defaults: UserDefaults!
    private let suite = "UserPropertySyncTests"

    override func setUp() {
        super.setUp()
        UserDefaults().removePersistentDomain(forName: suite)
        defaults = UserDefaults(suiteName: suite)
        sink = RecordingSink()
        Track.install(sink)
    }

    override func tearDown() {
        UserPropertySync.appProperties = { _ in [] }
        Track.reset()
        UserDefaults().removePersistentDomain(forName: suite)
        sink = nil
        defaults = nil
        super.tearDown()
    }

    /// `refresh` gửi đúng những gì app đăng ký, đọc từ ĐÚNG `defaults` được truyền vào.
    func testRefreshGuiThuocTinhAppDangKy() {
        defaults.set("dark", forKey: "demo.theme")
        UserPropertySync.appProperties = { d in
            [UserProperty(name: "theme", value: d.string(forKey: "demo.theme") ?? "none"),
             UserProperty(name: "has_tried_x", value: d.bool(forKey: "demo.tried") ? "true" : "false")]
        }
        UserPropertySync.refresh(defaults: defaults)
        XCTAssertEqual(sink.properties, [UserProperty(name: "theme", value: "dark"),
                                         UserProperty(name: "has_tried_x", value: "false")])
    }

    func testRefreshMacDinhKhongGuiGi() {
        UserPropertySync.refresh(defaults: defaults)
        XCTAssertEqual(sink.properties, [], "app chưa đăng ký ⇒ lõi không tự bịa thuộc tính nào")
    }

    /// Cờ một chiều: cờ trên máy chỉ ghi MỘT lần (không bao giờ về false), nhưng thuộc tính được GỬI ở MỌI lần
    /// gọi — như `markExported`/`markShared` của nguồn: lượt gửi đầu có thể rơi (sink chưa gắn, consent tắt) mà
    /// lượt sau vẫn bù được.
    func testMarkFlagGhiCoMotLanNhungLuonGui() {
        let p = UserProperty(name: "has_tried_x", value: "true")
        let ghi = WriteCountingDefaults(suiteName: suite + ".count")!
        ghi.removePersistentDomain(forName: suite + ".count")
        defer { ghi.removePersistentDomain(forName: suite + ".count") }
        UserPropertySync.markFlag("demo.tried", p, defaults: ghi)
        UserPropertySync.markFlag("demo.tried", p, defaults: ghi)
        UserPropertySync.markFlag("demo.tried", p, defaults: ghi)
        XCTAssertEqual(sink.properties, [p, p, p], "thuộc tính gửi ở mọi lần gọi")
        XCTAssertEqual(ghi.writes["demo.tried"], 1, "cờ chỉ ghi một lần")
        XCTAssertTrue(ghi.bool(forKey: "demo.tried"))
    }

    /// `is_pro` cố ý KHÔNG đi qua đây: quyền Pro có MỘT nguồn sự thật (entitlements) và nó tự gán mỗi lần đổi.
    /// Hai nơi cùng gán là mở đường cho hai nơi nói hai chuyện khác nhau — kể cả khi app lỡ đăng ký nó.
    func testIsProKhongDoSyncGan() {
        UserPropertySync.appProperties = { _ in [.isPro(true), UserProperty(name: "theme", value: "dark")] }
        UserPropertySync.refresh(defaults: defaults)
        XCTAssertFalse(sink.properties.contains { $0.name == UserProperty.isPro(true).name })
        XCTAssertEqual(sink.properties.map(\.name), ["theme"])
    }
}

/// Đếm số lần GHI theo khoá — để phân biệt "cờ ghi một lần" với "ghi lại cùng giá trị mỗi lần".
/// Chỉ đè `set(_: Any?)`: `set(_: Bool)` của Foundation đi qua nó (đè cả hai thì mỗi lần ghi bị đếm hai lần).
private final class WriteCountingDefaults: UserDefaults {
    private(set) var writes: [String: Int] = [:]

    override func set(_ value: Any?, forKey defaultName: String) {
        writes[defaultName, default: 0] += 1
        super.set(value, forKey: defaultName)
    }
}
