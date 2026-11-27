import SwiftUI

/// Theme của app — file CỦA APP (không đồng bộ từ template). `AppHostApp.init` tiêm giá trị này một lần.
///
/// Cubingo (spec mục 7, phong cách A): giao diện CHỈ sáng, nhấn cam #FF7A00, xanh lá "xong", nền kem.
enum AppTheme {
    static let theme: DSTheme = DSTheme(palette: light, colorScheme: .light).withAccent(hex: 0xFF7A00)

    /// Palette sáng khai đủ mọi trường; `accent`/`accentDark`/`onAccent` do `withAccent` đặt lại.
    private static let light = DSTheme.Palette(
        accent: Color(hex: 0xFF7A00),
        accentDark: Color(hex: 0xB35500),
        onAccent: Color(hex: 0x101113),
        pageBackground: Color(hex: 0xFFF6EE),
        cardBackground: Color(hex: 0xFFFFFF),
        sheetBackground: Color(hex: 0xFFFFFF),
        statusGood: Color(hex: 0x2DBE60),
        statusWarning: Color(hex: 0xE08A00),
        statusWarningAlt: Color(hex: 0xC9A100),
        statusDanger: Color(hex: 0xE0362C),
        statusMissing: Color(hex: 0xE5603A),
        textPrimary: Color(hex: 0x2B1D14),
        textSecondary: Color(hex: 0x2B1D14, opacity: 0.6),
        textTertiary: Color(hex: 0x2B1D14, opacity: 0.4),
        glassTint: Color.white.opacity(0.7),
        hairlineOnGlass: Color.black.opacity(0.1),
        ringTrack: Color.black.opacity(0.08),
        hairlineOnCard: Color.black.opacity(0.08),
        sheetHandle: Color.black.opacity(0.15),
        chartSeries1: DSTheme.standard.palette.chartSeries1,
        chartSeries2: DSTheme.standard.palette.chartSeries2,
        chartSeries3: DSTheme.standard.palette.chartSeries3)
}
