import XCTest

/// Chụp các màn của app theo route `-uiPreview <tên>` ở MỘT hướng cho review UI — không phải test hành vi.
///
/// Tham số qua biến môi trường (xcodebuild chuyển `TEST_RUNNER_X` thành `X`):
/// - `UISHOTS`: danh sách route cách nhau bằng dấu phẩy (mặc định `home`) — tên là `rawValue` của `AppPreview`
///   (`ui_shots.py all` tự mở rộng thành mọi `case` của enum đó). Route nào cũng chụp được với thời gian chờ mặc định;
///   hai tập dưới chỉ là tinh chỉnh (chờ lâu hơn / thêm ảnh cuộn), không bắt buộc khai cho route mới.
/// - `UISHOTS_ORIENT`: `landscape` | `portrait` (mặc định `landscape`).
/// - `UISHOTS_DIR`: thư mục trên máy host để ghi PNG (runner chạy trong sim nhưng thấy FS host).
/// Mỗi route một lần mở app riêng ⇒ ảnh `<route>-land.png` / `<route>-port.png`.
final class UIShotsTests: XCTestCase {
    /// Route có sheet/cover hiện sau khi mở (What's New chờ app active + ~0,6 s; paywall tải sản phẩm) cần chờ lâu hơn.
    private static let slowRoutes: Set<String> = ["whatsNew", "paywall", "feedback"]
    /// Route có thêm ảnh sau khi cuộn — số lần vuốt lên. Ở cỡ chữ trợ năng phần dưới (gói + nút mua của paywall) nằm
    /// ngoài màn đầu; ở cỡ mặc định ảnh cuộn giống ảnh chính.
    private static let scrollRoutes: [String: Int] = ["settings": 1, "paywall": 3, "onboarding": 1]

    func testChupMan() throws {
        let env = ProcessInfo.processInfo.environment
        let landscape = (env["UISHOTS_ORIENT"] ?? "landscape") == "landscape"
        let dir = URL(fileURLWithPath: env["UISHOTS_DIR"] ?? NSTemporaryDirectory())
        let routes = (env["UISHOTS"] ?? "home").split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)

        XCUIDevice.shared.orientation = landscape ? .landscapeLeft : .portrait
        for route in routes {
            let app = XCUIApplication()
            app.launchArguments = ["-uiPreview", route]
            app.launch()
            Thread.sleep(forTimeInterval: Self.slowRoutes.contains(route) ? 4 : 2.5)
            // App chỉ hỗ trợ dọc trên iPhone (project.yml) ⇒ xoay máy sang ngang KHÔNG xoay app; ảnh chụp vẫn dọc và
            // ui_shots.py xoay nó thành ảnh nằm nghiêng mà vẫn báo xanh. Bắt ngay ở đây thay vì ghi ảnh sai.
            let frame = app.windows.firstMatch.frame
            if landscape && frame.width <= frame.height {
                XCTFail("App không xoay ngang (cửa sổ \(Int(frame.width))x\(Int(frame.height))) — máy này chỉ hỗ trợ dọc? Dùng --orient portrait hoặc sim iPad.")
                app.terminate()
                return
            }
            let png = XCUIScreen.main.screenshot().pngRepresentation
            try png.write(to: dir.appendingPathComponent("\(route)-\(landscape ? "land" : "port").png"))
            // Màn dài (Settings): thêm một ảnh sau khi cuộn xuống đáy — `<route>-scrolled-<hướng>.png`.
            if let swipes = Self.scrollRoutes[route] {
                for _ in 0..<swipes { app.swipeUp() }
                Thread.sleep(forTimeInterval: 1)
                let more = XCUIScreen.main.screenshot().pngRepresentation
                try more.write(to: dir.appendingPathComponent("\(route)-scrolled-\(landscape ? "land" : "port").png"))
            }
            app.terminate()
        }
    }
}
