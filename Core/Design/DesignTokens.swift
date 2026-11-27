import SwiftUI

/// Bảng màu + bán kính góc dùng chung. Token màu đọc qua theme đã tiêm lúc khởi động (`DSTheme.current`).
///
/// Giá trị thật nằm ở `DSTheme.standard` (`Core/Design/DSTheme.swift`); app đổi màu bằng cách khai theme ở
/// `AppHost/AppHost/AppTheme.swift`, không sửa file này.
enum DSColor {
    static var accent: Color { DSTheme.current.palette.accent }
    static var accentDark: Color { DSTheme.current.palette.accentDark }
    /// Text đặt trên nền accent — cố ý không dùng trắng, tương phản tốt hơn trên nền teal.
    static var onAccent: Color { DSTheme.current.palette.onAccent }
    static var pageBackground: Color { DSTheme.current.palette.pageBackground }
    static var cardBackground: Color { DSTheme.current.palette.cardBackground }
    static var sheetBackground: Color { DSTheme.current.palette.sheetBackground }
    static var statusGood: Color { DSTheme.current.palette.statusGood }
    static var statusWarning: Color { DSTheme.current.palette.statusWarning }
    static var statusWarningAlt: Color { DSTheme.current.palette.statusWarningAlt }
    static var statusDanger: Color { DSTheme.current.palette.statusDanger }
    static var statusMissing: Color { DSTheme.current.palette.statusMissing }
    static var textPrimary: Color { DSTheme.current.palette.textPrimary }
    static var textSecondary: Color { DSTheme.current.palette.textSecondary }
    static var textTertiary: Color { DSTheme.current.palette.textTertiary }
    /// Nền tint "liquid glass" — nút/pill nổi trên nội dung nền (ảnh/video) ở trạng thái mặc định/inactive.
    static var glassTint: Color { DSTheme.current.palette.glassTint }
    /// Separator dọc trong StatPill — tương phản cao hơn vì nằm trên nền ảnh/video/gradient tối.
    static var hairlineOnGlass: Color { DSTheme.current.palette.hairlineOnGlass }
    /// Track nền của ProgressRing (phần vòng tròn chưa đạt %).
    static var ringTrack: Color { DSTheme.current.palette.ringTrack }
    /// Separator ngang giữa các row trong InsetGroupedList — tương phản thấp hơn vì nằm trên card nền đặc.
    static var hairlineOnCard: Color { DSTheme.current.palette.hairlineOnCard }
    /// Handle kéo của BottomSheetChrome.
    static var sheetHandle: Color { DSTheme.current.palette.sheetHandle }

    // MARK: Biểu đồ nhiều nhóm (chartSeries1...3)
    //
    // ⚠️ BA HEX CỦA `DSTheme.standard` LÀ OUTPUT CỦA VALIDATOR, KHÔNG PHẢI CHỌN BẰNG MẮT. Chúng qua cả 6 check
    // của skill `dataviz` trên nền `cardBackground` (#1C1C1E): dải sáng L 0.48–0.67 của dark mode,
    // sàn chroma, tách CVD (worst ΔE 13.5 deutan), sàn thị lực thường (19.4), tương phản ≥ 3:1.
    // Đổi tay là phá check phân biệt mù màu — đổi thì PHẢI kiểm lại đủ 6 check trên bằng validator của skill
    // `dataviz` (công cụ ngoài, không nằm trong repo này), trên đúng nền `cardBackground`.
    //
    // Màu gắn với NHÓM, không gắn với thứ hạng: đổi tập dữ liệu đang xem không được sơn lại phần biểu đồ.
    /// Nhóm 1 của biểu đồ.
    static var chartSeries1: Color { DSTheme.current.palette.chartSeries1 }
    /// Nhóm 2 của biểu đồ.
    static var chartSeries2: Color { DSTheme.current.palette.chartSeries2 }
    /// Nhóm 3 (thường là phần còn lại). Hổ phách TỐI — cố ý khác
    /// `statusWarning` (#FFB340) vì màu trạng thái là màu dành riêng, không dùng làm màu nhóm.
    static var chartSeries3: Color { DSTheme.current.palette.chartSeries3 }
}

enum DSRadius {
    static let pill: CGFloat = 24
    static let card: CGFloat = 19
    static let sheetTop: CGFloat = 28
    static let insetList: CGFloat = 26
}

/// Chuyển hex 0xRRGGBB thành 3 thành phần 0...1 — tách riêng khỏi `Color.init` để test được thuần logic.
func hexComponents(_ hex: UInt32) -> (red: Double, green: Double, blue: Double) {
    (
        red: Double((hex >> 16) & 0xFF) / 255,
        green: Double((hex >> 8) & 0xFF) / 255,
        blue: Double(hex & 0xFF) / 255
    )
}

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        let c = hexComponents(hex)
        self.init(.sRGB, red: c.red, green: c.green, blue: c.blue, opacity: opacity)
    }
}
