import SwiftUI

/// `screen_view` KHÔNG tự động ở SwiftUI — Firebase chỉ tự bắt cho `UIViewController`. App thuần
/// SwiftUI nên mọi màn phải tự khai báo.
///
/// Cố ý dùng tên màn TĨNH truyền vào từ call site, không suy từ kiểu View: tên suy tự động sẽ
/// đổi theo mỗi lần refactor và làm gãy báo cáo lịch sử.
extension View {
    /// Màn nền (tab, màn gốc): chỉ báo lúc xuất hiện.
    func trackScreen(_ name: String) -> some View {
        onAppear { ScreenTracker.shared.enter(name) }
    }

    /// Màn PHỦ LÊN màn khác (cover/sheet/push): báo lúc xuất hiện VÀ trả lại tên màn bên dưới lúc
    /// đóng. Thiếu vế sau thì đóng paywall xong GA4 vẫn tính thời gian cho `paywall` — màn bên
    /// dưới không `onAppear` lại khi một sheet đóng.
    func trackOverlayScreen(_ name: String) -> some View {
        onAppear { ScreenTracker.shared.push(name) }
            .onDisappear { ScreenTracker.shared.pop(name) }
    }
}

/// Chống bắn trùng: SwiftUI gọi `onAppear` lại khi view quay lại từ cover/sheet, và với
/// `TabView` thì mọi tab đã ghé qua đều có thể `onAppear` lần nữa. Chỉ bắn khi tên màn THAY ĐỔI.
final class ScreenTracker {
    static let shared = ScreenTracker()

    private(set) var current: String?
    /// Các màn phủ đang mở, trên cùng ở cuối. `base` là màn nền bên dưới tất cả.
    private var overlays: [String] = []
    private var base: String?

    /// `internal` để test dựng được instance riêng, không đụng singleton.
    init() {}

    /// Màn nền. Khi đang có màn phủ thì CHỈ ghi nhớ (không bắn): `TabView`/`NavigationStack` bên
    /// dưới một cover vẫn có thể `onAppear`, bắn lúc đó là gán nhầm thời gian của màn phủ.
    func enter(_ name: String) {
        base = name
        guard overlays.isEmpty else { return }
        report(name)
    }

    func push(_ name: String) {
        if overlays.last != name { overlays.append(name) }
        report(name)
    }

    func pop(_ name: String) {
        // Gỡ lần xuất hiện TRÊN CÙNG của tên này — `onDisappear` không bảo đảm thứ tự LIFO khi
        // hai cover đóng cùng lúc.
        guard let i = overlays.lastIndex(of: name) else { return }
        overlays.remove(at: i)
        if let top = overlays.last ?? base { report(top) }
    }

    /// Đổi màn phủ trên cùng tại chỗ (vd gạt chế độ ngay trên một màn phủ) — không bắn tên màn nền xen giữa.
    func swap(_ old: String, _ new: String) {
        if let i = overlays.lastIndex(of: old) { overlays.remove(at: i) }
        push(new)
    }

    private func report(_ name: String) {
        guard name != current else { return }
        current = name
        FirebaseScreenBridge.log(name)
    }
}

/// Cầu nối tách riêng để `ScreenTracker` test được mà không cần Firebase (file này không import SDK nào).
/// `screen_view` là event dành riêng của GA4 (có param chuẩn `screen_name`) nên nó không nằm trong `AppEvent`.
enum FirebaseScreenBridge {
    /// Được sink Firebase thay bằng cài đặt thật lúc chạy trên device.
    nonisolated(unsafe) static var handler: (String) -> Void = { _ in }
    static func log(_ name: String) { handler(name) }

    /// SDK Firebase làm rơi `firebase_screen` trên iOS 27 trong khi param tự đặt vẫn về đủ — báo cáo bù tên
    /// màn đọc param này, đổi tên nó là gãy báo cáo đó.
    static func customParameters(for name: String) -> [String: Any] { ["screen_label": name] }
}
