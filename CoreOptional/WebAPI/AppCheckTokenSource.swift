import Foundation
import FirebaseAppCheck
import FirebaseCore

/// Facade App Check duy nhất của template — nhốt `FirebaseAppCheck` sau một điểm, cùng lý do `Track` nhốt Firebase
/// Analytics. `tools/telemetry/lint_firebase_imports.py` chỉ cho đúng file này import `FirebaseAppCheck`
/// (+ `FirebaseCore` để hỏi `FirebaseApp.app()`); `WebAPIFeedbackTransport` đi qua đây.
///
/// An toàn khi Firebase CHƯA cấu hình (template không chứa `GoogleService-Info.plist`; Simulator và host unit test
/// không bao giờ gọi `FirebaseApp.configure()` — xem `TelemetryBootstrap.shouldConfigure`): `AppCheck.appCheck()`
/// crash nếu không có app mặc định, nên mọi lối vào SDK đều hỏi `canUseSDK` trước. KHÔNG bao giờ in/ghi token.
enum AppCheckTokenSource {

    /// Hàm quyết định thuần (test được): chỉ chạm SDK trên thiết bị thật, ngoài host test, khi Firebase đã cấu hình.
    static func canUseSDK(isSimulator: Bool, isUnitTestHost: Bool, firebaseConfigured: Bool) -> Bool {
        firebaseConfigured && !isSimulator && !isUnitTestHost
    }

    /// Đặt provider App Check. PHẢI chạy TRƯỚC `FirebaseApp.configure()`: sau đó App Check đã khởi tạo với provider
    /// mặc định và lệnh này IM LẶNG không có tác dụng (không lỗi, không cảnh báo). App nối vào
    /// `TelemetryConfig.preConfigure` — hook đó chỉ chạy ngay trước lần configure thật.
    ///
    /// DeviceCheck chạy trên mọi thiết bị thật (Internal lẫn Release) mà không cần cấu hình thêm. Simulator và host
    /// test: không làm gì (không bao giờ có configure ở đó).
    static func installProvider() {
        guard !AppEnvironment.isSimulator, !AppEnvironment.isUnitTestHost else { return }
        AppCheck.setAppCheckProviderFactory(DeviceCheckProviderFactory())
    }

    /// Token App Check hiện tại, hoặc `nil` khi không dùng được SDK hoặc lấy thất bại. Thất bại KHÔNG chặn gửi:
    /// máy chủ (`POST /api/v1/feedback`) là lớp enforcement thật; chặn ở client chỉ làm mất phản hồi thật khi
    /// DeviceCheck trục trặc. Không ném, không crash.
    static func currentToken() async -> String? {
        guard canUseSDK(isSimulator: AppEnvironment.isSimulator, isUnitTestHost: AppEnvironment.isUnitTestHost,
                        firebaseConfigured: FirebaseApp.app() != nil) else { return nil }
        do {
            return try await AppCheck.appCheck().token(forcingRefresh: false).token
        } catch {
            // KHÔNG dùng `try?`: nuốt lỗi ở đây là mù hoàn toàn khi DeviceCheck trục trặc — triệu chứng duy nhất user
            // thấy sẽ là "Something went wrong" sau khi máy chủ trả 401. `applog` là `.private` ở bản Store.
            applog("[appcheck] lấy token thất bại: \(error.localizedDescription)")
            return nil
        }
    }
}
