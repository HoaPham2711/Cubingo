import SwiftUI

/// Theme của app: bảng màu + chế độ giao diện. App khai MỘT giá trị ở `AppHost/AppHost/AppTheme.swift` và tiêm ở
/// dòng đầu `App.init` (`DSTheme.install(AppTheme.theme)`); mọi token `DSColor` đọc qua khe này.
/// `Core/` vì vậy giống hệt nhau ở mọi app — chỉ `AppTheme.swift` khác.
struct DSTheme: Equatable {
    /// Một trường cho MỖI token của `DSColor`, cùng tên.
    struct Palette: Equatable {
        var accent: Color
        var accentDark: Color
        /// Text đặt trên nền accent.
        var onAccent: Color
        var pageBackground: Color
        var cardBackground: Color
        var sheetBackground: Color
        var statusGood: Color
        var statusWarning: Color
        var statusWarningAlt: Color
        var statusDanger: Color
        var statusMissing: Color
        var textPrimary: Color
        var textSecondary: Color
        var textTertiary: Color
        var glassTint: Color
        var hairlineOnGlass: Color
        var ringTrack: Color
        var hairlineOnCard: Color
        var sheetHandle: Color
        var chartSeries1: Color
        var chartSeries2: Color
        var chartSeries3: Color
    }

    var palette: Palette
    var colorScheme: ColorScheme

    /// Bản chuẩn của template: giao diện tối, accent teal — đúng các giá trị `DSColor` có trước khi có khe theme.
    static let standard = DSTheme(
        palette: Palette(
            accent: Color(hex: 0x4CD9CE),
            accentDark: Color(hex: 0x2B9C95),
            onAccent: Color(hex: 0x04211F),
            pageBackground: Color(hex: 0x101113),
            cardBackground: Color(hex: 0x1C1C1E),
            sheetBackground: Color(hex: 0x2C2C2E),
            statusGood: Color(hex: 0x48D678),
            statusWarning: Color(hex: 0xFFB340),
            statusWarningAlt: Color(hex: 0xFFD650),
            statusDanger: Color(hex: 0xFF453A),
            statusMissing: Color(hex: 0xFF7846),
            textPrimary: Color.white,
            textSecondary: Color.white.opacity(0.6),
            textTertiary: Color.white.opacity(0.4),
            glassTint: Color.black.opacity(0.5),
            hairlineOnGlass: Color.white.opacity(0.2),
            ringTrack: Color.white.opacity(0.18),
            hairlineOnCard: Color.white.opacity(0.12),
            sheetHandle: Color.white.opacity(0.25),
            // BA MÀU BIỂU ĐỒ LÀ OUTPUT CỦA VALIDATOR (skill `dataviz`) trên nền `cardBackground` #1C1C1E:
            // đổi tay là phá check phân biệt mù màu. Màu gắn với NHÓM, không gắn với thứ hạng.
            chartSeries1: Color(hex: 0x2FA79F),
            chartSeries2: Color(hex: 0x8079E0),
            // Hổ phách TỐI — cố ý khác `statusWarning` vì màu trạng thái là màu dành riêng.
            chartSeries3: Color(hex: 0xB08A3A)
        ),
        colorScheme: .dark
    )

    /// Đổi màu nhấn, giữ mọi thứ khác: `accentDark` = từng kênh × 0,7; `onAccent` tối (#101113) khi độ chói tương đối
    /// (WCAG) của accent > 0,179 (ngưỡng mà chữ tối và chữ trắng tương phản ngang nhau), ngược lại trắng.
    func withAccent(hex: UInt32) -> DSTheme {
        let c = hexComponents(hex)
        func linear(_ v: Double) -> Double { v <= 0.03928 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4) }
        let luminance = 0.2126 * linear(c.red) + 0.7152 * linear(c.green) + 0.0722 * linear(c.blue)
        var theme = self
        theme.palette.accent = Color(hex: hex)
        theme.palette.accentDark = Color(.sRGB, red: c.red * 0.7, green: c.green * 0.7, blue: c.blue * 0.7, opacity: 1)
        theme.palette.onAccent = luminance > 0.179 ? Color(hex: 0x101113) : Color.white
        return theme
    }

    /// Theme đang hiệu lực (đọc từ khe toàn cục). Lần đọc đầu KHOÁ khe: cài sau đó bị từ chối.
    static var current: DSTheme { globalSlot.current }

    /// Gọi MỘT lần, trước lần đọc token đầu tiên (dòng đầu `App.init`). Cài muộn/cài lần hai là lỗi lập trình:
    /// `assert` ở DEBUG (dừng ngay), bỏ qua ở bản phát hành.
    static func install(_ theme: DSTheme) {
        let accepted = globalSlot.install(theme)
        assert(accepted, "DSTheme.install gọi sau khi khe đã khoá hoặc đã cài — phải là dòng đầu App.init")
    }

    private static let globalSlot = DSThemeSlot()
}

/// Khe chứa theme — tách khỏi `DSTheme` để test không đụng trạng thái toàn cục.
final class DSThemeSlot {
    private let lock = NSLock()
    private var theme: DSTheme?
    private var installed = false

    init() {}

    /// Theme đang có; chưa cài ⇒ `.standard`. Lần đọc đầu khoá khe ở giá trị này.
    var current: DSTheme {
        lock.lock(); defer { lock.unlock() }
        if let theme { return theme }
        theme = .standard
        return .standard
    }

    /// `false` khi khe đã khoá (đã có người đọc) hoặc đã cài một lần.
    @discardableResult
    func install(_ theme: DSTheme) -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard self.theme == nil, !installed else { return false }
        self.theme = theme
        installed = true
        return true
    }
}
