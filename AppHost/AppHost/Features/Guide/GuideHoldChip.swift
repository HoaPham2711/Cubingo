import SwiftUI

/// Chip "Hold: … on top, … facing you" với hai chấm màu thật của khối.
struct GuideHoldChip: View {
    let top: CubeColor
    let front: CubeColor
    let palette: CubePalette

    var body: some View {
        HStack(spacing: 10) {
            HStack(spacing: 4) {
                dot(top)
                dot(front)
            }
            Text(GuideText.hold(top: palette.name(top), front: palette.name(front)))
                .scaledFont(size: 15, weight: .bold, design: .rounded)
                .foregroundColor(DSColor.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(Capsule().fill(Color.white))
        .overlay(Capsule().strokeBorder(DSColor.accent.opacity(0.5), lineWidth: 1.5))
        .accessibilityElement(children: .combine)
    }

    private func dot(_ c: CubeColor) -> some View {
        let rgb = palette.rgb(c)
        return RoundedRectangle(cornerRadius: 4, style: .continuous)
            .fill(Color(.sRGB, red: rgb.r, green: rgb.g, blue: rgb.b, opacity: 1))
            .overlay(RoundedRectangle(cornerRadius: 4).strokeBorder(Color.black.opacity(0.2)))
            .frame(width: 16, height: 16)
    }
}
