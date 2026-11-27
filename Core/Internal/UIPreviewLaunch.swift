import Foundation

/// Cơ chế route `-uiPreview <tên>` (chụp ảnh/xem màn trên Simulator). Lõi chỉ giữ cơ chế đọc launch argument và
/// hợp đồng route; danh sách route, seed dữ liệu mẫu và nơi dựng màn là của APP (mỗi app một `enum AppPreview:
/// String, UIPreviewRoute`).
///
/// CỔNG SIMULATOR: `rawRoute` đọc qua `AppEnvironment.uiPreviewRoute` — chỉ có giá trị ở build Simulator
/// (`#if targetEnvironment(simulator)`); build device LUÔN `nil`, nên route preview (bỏ qua luồng thật/onboarding, seed
/// dữ liệu mẫu) không thể kích hoạt trên máy thật dù ai đó truyền argument. Mọi tham số phụ của route đi qua
/// `flag`/`value` cũng cùng cổng. Dữ liệu mẫu/seed của app phải tự bọc `#if targetEnvironment(simulator)`. Các type ở file này
/// biên dịch ở MỌI config nên KHÔNG nằm trong `debug_symbols.txt` (chỉ type INTERNAL-only mới nằm đó).
enum UIPreviewLaunch {
    /// Giá trị sau `-uiPreview`; `nil` khi không có argument hoặc không phải Simulator.
    static var rawRoute: String? { AppEnvironment.uiPreviewRoute }

    /// Cờ phụ `-<name>` có mặt không. Device luôn `false`. `name` truyền cả dấu `-` (vd. `-uiPreviewTips`).
    static func flag(_ name: String) -> Bool {
        flag(name, in: CommandLine.arguments)
    }

    /// Giá trị tham số phụ ngay sau `name`. Device luôn `nil`.
    static func value(after name: String) -> String? {
        value(after: name, in: CommandLine.arguments)
    }

    // MARK: - Thuần (test được: truyền argv giả; cổng Simulator nằm ở hai hàm trên)

    static func flag(_ name: String, in args: [String]) -> Bool {
        AppEnvironment.isSimulator && args.contains(name)
    }

    static func value(after name: String, in args: [String]) -> String? {
        AppEnvironment.isSimulator ? AppEnvironment.value(afterArgument: name, in: args) : nil
    }
}

/// Hợp đồng của route preview do app khai: `enum AppPreview: String, UIPreviewRoute { case home, onboarding, … }`.
/// App dựng route hiện tại: `UIPreviewLaunch.rawRoute.flatMap(AppPreview.init(rawValue:))`.
protocol UIPreviewRoute: RawRepresentable, CaseIterable where RawValue == String {
    /// Route hiện tour onboarding ⇒ app giữ cờ `WhatsNewHost.hasSeenOnboardingKey = false`, route khác ⇒ `true`.
    var isOnboarding: Bool { get }
}
