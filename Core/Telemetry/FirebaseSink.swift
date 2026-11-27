import Foundation
import FirebaseCore
import FirebaseAnalytics
import FirebaseCrashlytics

/// Nơi DUY NHẤT trong `Core/` được import Firebase (chỉ ba module trên).
/// `tools/telemetry/lint_firebase_imports.py` gác điều này ở pre-commit.
final class FirebaseSink: AnalyticsSink {

    /// Tiền tố domain của non-fatal trên Crashlytics (app suy từ bundle id) — nhóm lỗi của mỗi app tách riêng.
    private let crashDomainPrefix: String

    init(crashDomainPrefix: String) {
        self.crashDomainPrefix = crashDomainPrefix
    }

    func log(_ event: AppEvent) {
        Analytics.logEvent(event.name, parameters: FirebaseSink.doi(event.parameters))
        #if INTERNAL
        // Soi ngay khi cắm máy, không phải chờ 4–24h Firebase đổ dữ liệu về.
        print("[telemetry] \(event.name) \(event.parameters)")
        #endif
    }

    func set(_ property: UserProperty) {
        Analytics.setUserProperty(property.value, forName: property.name)
    }

    func diagnostic(_ key: DiagnosticKey, _ value: String) {
        Crashlytics.crashlytics().setCustomValue(value, forKey: key.rawValue)
    }

    func nonFatal(_ error: NonFatal) {
        // Crashlytics gộp nhóm theo `domain` + `code`, mà `code` của NSError phải là số ⇒ băm ổn
        // định (djb2) từ mã chữ, kèm mã chữ trong userInfo cho người đọc.
        var h: UInt32 = 5381
        for b in error.code.utf8 { h = (h &* 33) &+ UInt32(b) }
        Crashlytics.crashlytics().record(error: NSError(
            domain: "\(crashDomainPrefix).\(error.domain.rawValue)", code: Int(h % 1_000_000),
            userInfo: error.detail.isEmpty ? ["code": error.code] : ["code": error.code, "detail": error.detail]))
        #if INTERNAL
        print("[telemetry] non-fatal \(error.domain.rawValue) \(error.code) \(error.detail)")
        #endif
    }

    func breadcrumb(_ crumb: Breadcrumb) {
        Crashlytics.crashlytics().log(crumb.text)
        #if INTERNAL
        print("[telemetry] crumb \(crumb.text)")
        #endif
    }

    /// GA4 không có kiểu bool — gửi 1/0 để còn dùng làm điều kiện lọc trong báo cáo.
    private static func doi(_ params: [String: ParamValue]) -> [String: Any] {
        var out: [String: Any] = [:]
        for (k, v) in params {
            switch v {
            case let .string(s): out[k] = s
            case let .int(i):    out[k] = i
            case let .double(d): out[k] = d
            case let .bool(b):   out[k] = b ? 1 : 0
            }
        }
        return out
    }
}

/// Cấu hình app cấp cho bước khởi động telemetry.
struct TelemetryConfig {
    /// Tiền tố domain non-fatal Crashlytics (vd suy từ bundle id).
    var crashDomainPrefix: String
    /// Công tắc `[features] apple_ads` (`AppConfig.features.appleAds`): tắt ⇒ không bao giờ hỏi AdServices.
    var appleAdsEnabled: Bool
    /// Chạy NGAY TRƯỚC `FirebaseApp.configure()`, chỉ khi thật sự cấu hình. Chỗ cho những thiết lập SDK chỉ có
    /// hiệu lực nếu đặt trước configure — vd provider App Check của khối tuỳ chọn: đặt sau configure thì App
    /// Check đã khởi tạo với provider mặc định và lệnh đó IM LẶNG không có tác dụng (không lỗi, không cảnh báo).
    var preConfigure: (() -> Void)? = nil
}

/// Khởi động telemetry. Gọi đúng một lần, ở `init()` của App, TRƯỚC mọi thứ khác: `first_open`/`session_start`
/// do Firebase tự bắn ngay khi configure, và chúng là mẫu số của toàn bộ retention. Ghi nhận "đã dùng" trên
/// máy (`Track.installUsageObserver`) gắn TRƯỚC hàm này để không lỡ event nào của lần mở.
///
/// Không đủ điều kiện (thiếu plist, Simulator, host test) ⇒ giữ `NoOpSink`, KHÔNG chạm SDK: telemetry im lặng,
/// app chạy bình thường.
enum TelemetryBootstrap {

    private static let lock = NSLock()
    /// Đã gọi `FirebaseApp.configure()` trong tiến trình này. Mọi lối vào SDK sau đó đều hỏi cờ này trước.
    nonisolated(unsafe) private static var configuredConfig: TelemetryConfig?

    /// Hàm quyết định thuần (test được): chỉ cấu hình khi bundle CÓ `GoogleService-Info.plist` (thiếu plist mà
    /// gọi `FirebaseApp.configure()` thì Firebase ném exception — app chết ngay lúc mở), không phải Simulator,
    /// không phải host unit test.
    ///
    /// Simulator giữ `NoOpSink`: review UI và chụp ảnh chạy hàng ngày ở đó — bơm dữ liệu giả vào funnel là tự
    /// làm hỏng chính số liệu mình sắp đọc. Host test: test không bao giờ được gửi gì ra ngoài.
    static func shouldConfigure(hasPlist: Bool, isSimulator: Bool, isUnitTestHost: Bool) -> Bool {
        hasPlist && !isSimulator && !isUnitTestHost
    }

    /// Đúng file `FirebaseApp.configure()` đọc. Bản `Debug` chưa có plist: pha build "Chọn GoogleService-Info
    /// theo config" chỉ cảnh báo và không chép gì ⇒ ở đây `false`.
    static var bundleHasFirebasePlist: Bool {
        Bundle.main.path(forResource: "GoogleService-Info", ofType: "plist") != nil
    }

    /// Gọi MỘT lần, trên main thread, trong lúc app khởi động: trạng thái "đã cấu hình" được nhận TRƯỚC khi
    /// `configure()` trả về, nên một lời gọi song song từ luồng khác có thể thấy "đã cấu hình" khi SDK chưa sẵn sàng.
    static func start(_ config: TelemetryConfig) {
        guard shouldConfigure(hasPlist: bundleHasFirebasePlist, isSimulator: AppEnvironment.isSimulator,
                              isUnitTestHost: AppEnvironment.isUnitTestHost) else { return }
        // `FirebaseApp.configure()` gọi lần thứ hai sẽ RAISE EXCEPTION ⇒ start lần hai là no-op.
        lock.lock()
        guard configuredConfig == nil else { lock.unlock(); return }
        configuredConfig = config
        lock.unlock()

        config.preConfigure?()
        if FirebaseApp.app() == nil { FirebaseApp.configure() }

        // Cam kết máy móc: không SDK quảng cáo, không IDFA. Cùng với `FirebaseAnalyticsCore`
        // ⇒ không cần ATT prompt. Attribution Apple Ads của chính lượt cài này đi qua AdServices
        // (`AppleAdsAttribution`) — cũng không cần ATT, và không đổi dòng consent dưới.
        //
        // Muốn bật opt-in (vd EU) sau này: sửa ĐÚNG dòng `.analyticsStorage` này thành `.denied`
        // cho tới khi user đồng ý.
        Analytics.setConsent([.analyticsStorage: .granted,
                              .adStorage: .denied,
                              .adUserData: .denied,
                              .adPersonalization: .denied])

        let enabled = TelemetryConsent.isEnabled()
        apDungConsent(enabled)
        // Consent tắt ngay từ lúc mở: SDK đã ngừng thu VÀ facade cũng không chuyển tiếp (giữ NoOp) — cùng
        // phòng thủ hai lớp như khi user gạt tắt giữa phiên.
        if enabled { ganSink(config) }
        // Ngay sau khi sink gắn: gán lại nguồn cài đã chốt + hỏi Apple Ads ở nền nếu chưa. Consent tắt thì
        // `resolveIfNeeded` tự bỏ qua, không đếm lần chạy.
        AppleAdsAttribution.startAtLaunch(appleAdsEnabled: config.appleAdsEnabled)
    }

    /// Gọi mỗi khi user gạt "Share usage data" trong Settings (gộp `apDungConsent` + `resume` + `Track.reset()`).
    ///
    /// BẬT lại KHÔNG được đi qua `start()`/`configure()`: `FirebaseApp.configure()` gọi lần thứ hai sẽ
    /// **raise exception** và app chết ngay tại chỗ user vừa bật lại chia sẻ dữ liệu — lỗi tệ nhất có thể, vì
    /// nó phạt đúng người vừa đồng ý giúp mình. Ở đây chỉ bật lại thu thập + gắn lại sink.
    ///
    /// Bootstrap đã quyết KHÔNG cấu hình (thiếu plist / Simulator / host test) ⇒ no-op: SDK chưa configure thì
    /// không được chạm, và sink vốn đã là NoOp.
    static func consentDidChange(_ enabled: Bool) {
        lock.lock(); let config = configuredConfig; lock.unlock()
        guard let config else { return }
        apDungConsent(enabled)
        if enabled {
            ganSink(config)
            // Người tắt chia sẻ dữ liệu từ đầu chưa từng được hỏi nguồn cài — hỏi bù khi bật lại.
            AppleAdsAttribution.startAtLaunch(appleAdsEnabled: config.appleAdsEnabled)
        } else {
            // Phòng thủ hai lớp: SDK đã ngừng thu, và facade cũng thôi chuyển tiếp. Một lớp hỏng thì lớp kia
            // vẫn tôn trọng lựa chọn của user.
            Track.reset()
            FirebaseScreenBridge.handler = { _ in }
        }
    }

    private static func ganSink(_ config: TelemetryConfig) {
        Track.install(FirebaseSink(crashDomainPrefix: config.crashDomainPrefix))
        FirebaseScreenBridge.handler = { name in
            var parameters = FirebaseScreenBridge.customParameters(for: name)
            parameters[AnalyticsParameterScreenName] = name
            Analytics.logEvent(AnalyticsEventScreenView, parameters: parameters)
        }
    }

    /// Bật/tắt thu thập ở tầng SDK. Chỉ gọi khi đã configure.
    private static func apDungConsent(_ enabled: Bool) {
        Analytics.setAnalyticsCollectionEnabled(enabled)
        Crashlytics.crashlytics().setCrashlyticsCollectionEnabled(enabled)
        if !enabled {
            // Ngừng gửi là chưa đủ — xoá luôn app-instance-id cục bộ để lần bật lại là một
            // định danh mới, không nối được với lịch sử cũ.
            Analytics.resetAnalyticsData()
        }
    }
}
