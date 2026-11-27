import SwiftUI
import XCTest
@testable import AppHost

final class DSThemeTests: XCTestCase {

    /// Bảng literal chép từ `DesignTokens.swift` TRƯỚC khi có khe theme — bản chuẩn phải giữ đúng từng giá trị.
    func testBanChuanGiuDungGiaTriCu() {
        let p = DSTheme.standard.palette
        XCTAssertEqual(p.accent, Color(hex: 0x4CD9CE))
        XCTAssertEqual(p.accentDark, Color(hex: 0x2B9C95))
        XCTAssertEqual(p.onAccent, Color(hex: 0x04211F))
        XCTAssertEqual(p.pageBackground, Color(hex: 0x101113))
        XCTAssertEqual(p.cardBackground, Color(hex: 0x1C1C1E))
        XCTAssertEqual(p.sheetBackground, Color(hex: 0x2C2C2E))
        XCTAssertEqual(p.statusGood, Color(hex: 0x48D678))
        XCTAssertEqual(p.statusWarning, Color(hex: 0xFFB340))
        XCTAssertEqual(p.statusWarningAlt, Color(hex: 0xFFD650))
        XCTAssertEqual(p.statusDanger, Color(hex: 0xFF453A))
        XCTAssertEqual(p.statusMissing, Color(hex: 0xFF7846))
        XCTAssertEqual(p.textPrimary, Color.white)
        XCTAssertEqual(p.textSecondary, Color.white.opacity(0.6))
        XCTAssertEqual(p.textTertiary, Color.white.opacity(0.4))
        XCTAssertEqual(p.glassTint, Color.black.opacity(0.5))
        XCTAssertEqual(p.hairlineOnGlass, Color.white.opacity(0.2))
        XCTAssertEqual(p.ringTrack, Color.white.opacity(0.18))
        XCTAssertEqual(p.hairlineOnCard, Color.white.opacity(0.12))
        XCTAssertEqual(p.sheetHandle, Color.white.opacity(0.25))
        XCTAssertEqual(p.chartSeries1, Color(hex: 0x2FA79F))
        XCTAssertEqual(p.chartSeries2, Color(hex: 0x8079E0))
        XCTAssertEqual(p.chartSeries3, Color(hex: 0xB08A3A))
        XCTAssertEqual(DSTheme.standard.colorScheme, .dark)
    }

    func testCaiTruocKhiDocThiDoiToken() {
        let slot = DSThemeSlot()
        let custom = DSTheme.standard.withAccent(hex: 0xFF8A3D)
        XCTAssertTrue(slot.install(custom))
        XCTAssertEqual(slot.current, custom)
        XCTAssertEqual(slot.current.palette.accent, Color(hex: 0xFF8A3D))
        XCTAssertNotEqual(slot.current.palette.accent, DSTheme.standard.palette.accent)
    }

    func testDocTruocRoiCaiBiTuChoi() {
        let slot = DSThemeSlot()
        XCTAssertEqual(slot.current, DSTheme.standard)   // lần đọc đầu khoá khe
        XCTAssertFalse(slot.install(DSTheme.standard.withAccent(hex: 0xFF8A3D)))
        XCTAssertEqual(slot.current, DSTheme.standard)
    }

    func testCaiHaiLanBiTuChoi() {
        let slot = DSThemeSlot()
        let first = DSTheme.standard.withAccent(hex: 0xFF8A3D)
        XCTAssertTrue(slot.install(first))
        XCTAssertFalse(slot.install(DSTheme.standard.withAccent(hex: 0x3366FF)))
        XCTAssertEqual(slot.current, first)
    }

    func testWithAccentSuyRaMauToiVaMauChu() {
        // Accent sáng (vàng) ⇒ chữ tối; accent tối (xanh đậm) ⇒ chữ trắng.
        let bright = DSTheme.standard.withAccent(hex: 0xFFD650).palette
        XCTAssertEqual(bright.onAccent, Color(hex: 0x101113))
        let dark = DSTheme.standard.withAccent(hex: 0x1A3A8C).palette
        XCTAssertEqual(dark.onAccent, Color.white)
        // accentDark = từng kênh × 0,7.
        let c = hexComponents(0xFF8A3D)
        let t = DSTheme.standard.withAccent(hex: 0xFF8A3D).palette
        XCTAssertEqual(t.accent, Color(hex: 0xFF8A3D))
        XCTAssertEqual(t.accentDark, Color(.sRGB, red: c.red * 0.7, green: c.green * 0.7, blue: c.blue * 0.7, opacity: 1))
        // Literal độc lập với công thức: 0xC86432 = (200, 100, 50) × 0,7 = (140, 70, 35) = 0x8C4623 (chia hết).
        XCTAssertEqual(DSTheme.standard.withAccent(hex: 0xC86432).palette.accentDark, Color(hex: 0x8C4623))
        // 0xFF8A3D có độ chói ≈ 0,398 > 0,179 ⇒ chữ tối.
        XCTAssertEqual(t.onAccent, Color(hex: 0x101113))
        // Phần còn lại giữ nguyên.
        XCTAssertEqual(t.pageBackground, DSTheme.standard.palette.pageBackground)
        XCTAssertEqual(DSTheme.standard.withAccent(hex: 0xFF8A3D).colorScheme, .dark)
    }

    /// Ngưỡng độ chói WCAG 0,179 — hai accent xám sát ngưỡng hai phía (luminance của xám = linear(kênh)):
    /// 0x7B7B7B ≈ 0,198 (trên ngưỡng) ⇒ chữ tối; 0x6F6F6F ≈ 0,159 (dưới ngưỡng) ⇒ chữ trắng.
    func testWithAccentNguongDoChoiSatHaiPhia() {
        XCTAssertEqual(DSTheme.standard.withAccent(hex: 0x7B7B7B).palette.onAccent, Color(hex: 0x101113))
        XCTAssertEqual(DSTheme.standard.withAccent(hex: 0x6F6F6F).palette.onAccent, Color.white)
    }

    func testDSColorDocQuaKhe() {
        let p = DSTheme.current.palette
        XCTAssertEqual(DSColor.accent, p.accent)
        XCTAssertEqual(DSColor.accentDark, p.accentDark)
        XCTAssertEqual(DSColor.onAccent, p.onAccent)
        XCTAssertEqual(DSColor.pageBackground, p.pageBackground)
        XCTAssertEqual(DSColor.cardBackground, p.cardBackground)
        XCTAssertEqual(DSColor.sheetBackground, p.sheetBackground)
        XCTAssertEqual(DSColor.statusGood, p.statusGood)
        XCTAssertEqual(DSColor.statusWarning, p.statusWarning)
        XCTAssertEqual(DSColor.statusWarningAlt, p.statusWarningAlt)
        XCTAssertEqual(DSColor.statusDanger, p.statusDanger)
        XCTAssertEqual(DSColor.statusMissing, p.statusMissing)
        XCTAssertEqual(DSColor.textPrimary, p.textPrimary)
        XCTAssertEqual(DSColor.textSecondary, p.textSecondary)
        XCTAssertEqual(DSColor.textTertiary, p.textTertiary)
        XCTAssertEqual(DSColor.glassTint, p.glassTint)
        XCTAssertEqual(DSColor.hairlineOnGlass, p.hairlineOnGlass)
        XCTAssertEqual(DSColor.ringTrack, p.ringTrack)
        XCTAssertEqual(DSColor.hairlineOnCard, p.hairlineOnCard)
        XCTAssertEqual(DSColor.sheetHandle, p.sheetHandle)
        XCTAssertEqual(DSColor.chartSeries1, p.chartSeries1)
        XCTAssertEqual(DSColor.chartSeries2, p.chartSeries2)
        XCTAssertEqual(DSColor.chartSeries3, p.chartSeries3)
    }
}
