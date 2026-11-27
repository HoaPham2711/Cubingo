import SwiftUI

/// Theme của app — file CỦA APP (không đồng bộ từ template). Đổi màu nhấn:
/// `static let theme: DSTheme = .standard.withAccent(hex: 0xRRGGBB)`. `AppHostApp.init` tiêm giá trị này một lần.
enum AppTheme {
    static let theme: DSTheme = .standard
}
