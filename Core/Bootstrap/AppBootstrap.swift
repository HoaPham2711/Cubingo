import Foundation

/// Chuỗi khởi động dùng chung. App gọi MỘT lần trong `App.init()`:
///
///     AppBootstrap.run(AppBootstrap.standardSteps(config: config, usageLedger: ledger, tmpDirs: []))
///
/// Thứ tự chuẩn và lý do từng vị trí (đổi chỗ là hỏng một bất biến):
/// 1. `takeIncident` — đọc + xoá dấu "đang làm việc" của lần chạy trước, TRƯỚC mọi thứ có thể `begin` dấu mới.
/// 2. `purgeTmp` — `StorageOtherData.runAtLaunch` lấy mốc cắt NGAY lúc gọi và xoá (ở nền) mọi mục cấp 1 của `tmp/`
///    tạo trước mốc ⇒ phải đứng trước mọi bước có thể ghi tmp (Firebase configure có thể ghi), nếu không file của
///    chính lần chạy này bị xoá. Có route `-uiPreview` thì bước này BỊ BỎ (`skipInUIPreview`) — vì vậy seed preview
///    của app (`AppHostApp.init` → `AppPreviewSeed.prepare()`) chạy TRƯỚC `run` mà file của nó không bị dọn. Ai thêm
///    seed ghi tmp phải biết: an toàn chỉ nhờ purgeTmp không chạy ở route preview; bỏ cờ đó thì seed phải dời sau.
/// 3. `usageObserver` (chỉ khi app có What's New) — ghi nhận "đã dùng" gắn TRƯỚC sink để không lỡ event nào.
/// 4. `telemetry` — sớm nhất có thể sau ba bước trên: `first_open`/`session_start` bắn ngay lúc configure (mẫu số
///    retention). Tự khởi động attribution Apple Ads (không có bước riêng — gọi hai lần là thừa).
/// 5. `firstLaunchSim` — "giả lập lần đầu mở app" (chỉ INTERNAL) xin TipKit xoá datastore: chỉ hợp lệ TRƯỚC configure.
/// 6. `tips` — `AppTips.configure()`.
///
/// `Entitlements.start()` KHÔNG phải bước khởi động: gọi ở `.task` của scene (không trong `init`), bỏ qua khi
/// `skipsStoreKit`. Kiểm tra cập nhật (mạng) cũng ở `.task`, bỏ qua khi `skipsNetwork`.
enum AppBootstrap {

    /// Dấu của lần chạy trước chết giữa chừng (crash/hết RAM) — `nil` nếu không có hoặc chạy trong host test. Gán
    /// đúng một lần ở bước `takeIncident`; app đọc để hiện lối "báo sự cố" nếu muốn.
    private(set) static var launchIncident: ActiveWorkMarker?

    /// Chạy `steps` tuần tự đúng thứ tự khai báo, bỏ bước theo môi trường. Trả tên các bước ĐÃ chạy, đúng thứ tự.
    @discardableResult
    static func run(_ steps: [LaunchStep], isUnitTestHost: Bool = AppEnvironment.isUnitTestHost,
                    uiPreviewRoute: String? = AppEnvironment.uiPreviewRoute) -> [String] {
        var ran: [String] = []
        for step in steps {
            if isUnitTestHost && step.skipInUnitTestHost { continue }
            if uiPreviewRoute != nil && step.skipInUIPreview { continue }
            step.run()
            ran.append(step.name)
        }
        return ran
    }

    /// Không đụng StoreKit thật: host unit test (action Test không gắn file `.storekit` ⇒ sandbox thật bật hộp thoại
    /// "Sign in to Apple Account" treo cả suite), và route `-uiPreview` không cần sản phẩm (`simctl launch` không gắn
    /// `.storekit` ⇒ cùng hộp thoại che màn cần chụp). Route trong `routesNeedingStore` (VD paywall) thì giữ.
    static func skipsStoreKit(isUnitTestHost: Bool = AppEnvironment.isUnitTestHost,
                              uiPreviewRoute: String? = AppEnvironment.uiPreviewRoute,
                              routesNeedingStore: Set<String>) -> Bool {
        if isUnitTestHost { return true }
        if let route = uiPreviewRoute, !routesNeedingStore.contains(route) { return true }
        return false
    }

    /// Không gọi mạng lúc mở/lên lại app (kiểm tra cập nhật…): host unit test không bao giờ ra mạng; ảnh chụp route
    /// preview không được phụ thuộc mạng.
    static func skipsNetwork(isUnitTestHost: Bool = AppEnvironment.isUnitTestHost,
                             uiPreviewRoute: String? = AppEnvironment.uiPreviewRoute) -> Bool {
        isUnitTestHost || uiPreviewRoute != nil
    }

    /// Các bước chuẩn theo đúng thứ tự ở comment của `AppBootstrap`. `usageLedger == nil` ⇒ không có `usageObserver`.
    /// `tmpDirs` = thư mục tạm riêng của app cần dọn thêm lúc mở. `telemetryPreConfigure` chạy ngay trước
    /// `FirebaseApp.configure()` (VD provider App Check của khối tuỳ chọn — app nối, lõi không biết khối đó).
    static func standardSteps(config: AppConfig, usageLedger: FeatureUsageLedger?, tmpDirs: [URL],
                              telemetryPreConfigure: (() -> Void)? = nil) -> [LaunchStep] {
        var steps: [LaunchStep] = [
            LaunchStep(name: "takeIncident") {
                launchIncident = ActiveWorkMarkerStore.shared.takeIncident()
            },
            // Route preview: không dọn tmp thật của sim (ảnh không được phụ thuộc lần dùng trước).
            LaunchStep(name: "purgeTmp", skipInUIPreview: true) {
                StorageOtherData.runAtLaunch(extraDirs: tmpDirs)
            },
        ]
        if let usageLedger {
            steps.append(LaunchStep(name: "usageObserver") { Track.installUsageObserver(usageLedger) })
        }
        let telemetry = TelemetryConfig(crashDomainPrefix: config.bundleID.isEmpty ? "app" : config.bundleID,
                                        appleAdsEnabled: config.features.appleAds,
                                        preConfigure: telemetryPreConfigure)
        steps += [
            // Tự no-op trong host test / Simulator / thiếu plist ⇒ không cần bỏ ở host.
            LaunchStep(name: "telemetry", skipInUnitTestHost: false) { TelemetryBootstrap.start(telemetry) },
            // Preview: không giả lập lần đầu (nó xoá cờ onboarding route vừa ép) và không ghi datastore TipKit.
            LaunchStep(name: "firstLaunchSim", skipInUIPreview: true) { InternalLaunch.beforeTipsConfigure() },
            LaunchStep(name: "tips", skipInUIPreview: true) { AppTips.configure() },
        ]
        return steps
    }
}
