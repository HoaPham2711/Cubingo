import Foundation

/// Mục cấp cao của app — MỘT nguồn cho tab bar (iPhone) lẫn sidebar (iPad), xem `ShellTab`.
/// Nội dung từng tab dựng ở `AppShellView.content(for:)` (switch vét cạn).
enum AppTab: String, ShellTab {
    case home
    case settings

    var title: String {
        switch self {
        case .home: return String(localized: "Home")
        case .settings: return String(localized: "Settings")
        }
    }

    var systemImage: String {
        switch self {
        case .home: return "house"
        case .settings: return "gearshape"
        }
    }
}

/// Kiểu "mục phụ" của sidebar iPad (hàng chỉ sidebar có, dưới một tab) — tham số `Extra` của `ShellNavigationModel`.
/// Không có mục phụ nào ⇒ `Never`.
typealias AppSidebarExtra = Never
