import SwiftUI

/// Chuỗi chỉ hiện ở build INTERNAL: không localize (= `Text(verbatim:)`), để catalog không phụ
/// thuộc config build. Hàm có mặt ở mọi config để call site không phải tự viết `#if`.
func dtext(_ s: String) -> Text { Text(verbatim: s) }

/// Cổng build: `true` chỉ khi biên dịch với cờ `INTERNAL` (Debug, Internal).
enum InternalBuild {
    static var isEnabled: Bool {
        #if INTERNAL
        true
        #else
        false
        #endif
    }

    /// Có vẽ dấu INTERNAL không: chỉ build INTERNAL VÀ không chạy route `-uiPreview` (ảnh review/ảnh store phải
    /// sạch). Hàm thuần để test; `internalBadge()` gọi với giá trị thật.
    static func showsBadge(isInternal: Bool = isEnabled, uiPreviewRoute: String? = AppEnvironment.uiPreviewRoute) -> Bool {
        isInternal && uiPreviewRoute == nil
    }
}

#if INTERNAL
/// Cử chỉ ẩn + sheet: nhấn giữ `minimumDuration` giây trên view thì present `sheet`. 1,5 s đủ dài để không ai mở
/// nhầm khi cuộn, đủ ngắn để người biết đường dùng được hằng ngày.
///
/// BẪY: modifier này chỉ tồn tại ở INTERNAL, nên view gắn nó (và nội dung `sheet`) cũng phải biến mất ở Release mà
/// call site KHÔNG viết `#if`. Quy tắc: wrapper CỤ THỂ (nhận dependency của app, dựng sheet debug của app) nằm Ở APP,
/// bọc `#if INTERNAL … modifier(InternalLongPressSheet { … }) … #else self #endif` — y mẫu `internalBadge()` bên
/// dưới. Nếu call site truyền thẳng closure sheet cho một hàm của lõi thì closure (và type debug trong nó) vẫn phải
/// biên dịch ở Release ⇒ symbol lọt binary. Lõi chỉ có `internalLongPressSheet(...)` generic cho trường hợp nội dung
/// sheet tồn tại ở MỌI config.
struct InternalLongPressSheet<S: View>: ViewModifier {
    let minimumDuration: Double
    let sheet: () -> S
    @State private var isPresented = false

    init(minimumDuration: Double = 1.5, @ViewBuilder sheet: @escaping () -> S) {
        self.minimumDuration = minimumDuration
        self.sheet = sheet
    }

    func body(content: Content) -> some View {
        content
            .contentShape(Rectangle())
            .onLongPressGesture(minimumDuration: minimumDuration) { isPresented = true }
            .sheet(isPresented: $isPresented) { sheet() }
    }
}

/// Dấu nhận biết build INTERNAL. Chỉ tồn tại dưới `INTERNAL`: cổng release tìm tên này trong
/// binary Release và KHÔNG được thấy.
struct InternalDebugMarkerView: View {
    var body: some View {
        dtext("INTERNAL")
            .font(.caption2.bold())
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(.orange, in: Capsule())
            .foregroundStyle(.white)
    }
}
#endif

extension View {
    /// Phủ dấu INTERNAL sát mép TRÊN, trong safe area (không đè tab bar hay nút chính ở đáy), không chặn chạm;
    /// ẩn khi chạy route `-uiPreview` (`InternalBuild.showsBadge`); no-op ở `Release`.
    @ViewBuilder
    func internalBadge() -> some View {
        #if INTERNAL
        if InternalBuild.showsBadge() {
            overlay(alignment: .top) {
                InternalDebugMarkerView().padding(.top, 2).allowsHitTesting(false)
            }
        } else {
            self
        }
        #else
        self
        #endif
    }
}

extension View {
    /// Gắn cử chỉ nhấn giữ mở `sheet` ở INTERNAL; `self` nguyên vẹn ở `Release` — call site không viết `#if`.
    /// CHỈ dùng khi nội dung `sheet` biên dịch được ở Release (vd. view của lõi có mặt mọi config). Sheet debug thật
    /// (type bọc `#if INTERNAL`) ⇒ viết wrapper cụ thể ở app, xem `InternalLongPressSheet`.
    @ViewBuilder
    func internalLongPressSheet<S: View>(minimumDuration: Double = 1.5,
                                         @ViewBuilder sheet: @escaping () -> S) -> some View {
        #if INTERNAL
        modifier(InternalLongPressSheet(minimumDuration: minimumDuration, sheet: sheet))
        #else
        self
        #endif
    }
}

/// Móc nội bộ lúc khởi động app — call site (chuỗi khởi động của vỏ app) gọi KHÔNG điều kiện, không chứa `#if`.
/// Bản App Store (`Release`): hai hàm có thân rỗng.
enum InternalLaunch {
    /// Phải gọi TRƯỚC `AppTips.configure()`: "Giả lập lần đầu mở app" xin TipKit xoá datastore, việc chỉ làm được
    /// trước `Tips.configure`. Gọi ngoài host unit test như `AppTips.configure` (toggle mặc định tắt nên là no-op
    /// trừ khi dev bật tay).
    static func beforeTipsConfigure() {
        #if INTERNAL
        FirstLaunchSimulation.applyAtLaunch()
        #endif
    }

    /// Sau khi scene dựng xong. Thân rỗng ở Release; ở INTERNAL chạy `afterLaunchHook` do app đăng ký (vd. probe
    /// nội bộ theo launch argument — công cụ riêng của app, lõi không biết).
    static func afterLaunch() {
        #if INTERNAL
        afterLaunchHook?()
        #endif
    }

    #if INTERNAL
    /// App đặt MỘT lần lúc mở app, trên main thread, trước `beforeTipsConfigure()`/`afterLaunch()`. Chỉ có ở INTERNAL nên đặt nó cũng phải nằm trong `#if INTERNAL`
    /// ở app, hoặc dùng wrapper của app.
    static var afterLaunchHook: (() -> Void)?
    #endif
}
