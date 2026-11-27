import SwiftUI

/// Nút "dày" kiểu app học tập: mặt nút màu nhấn, gờ dưới tối hơn 4 pt; nhấn thì mặt nút lún xuống gờ.
struct StyleThickButton: ButtonStyle {
    enum Kind { case primary, secondary }

    var kind: Kind = .primary
    static let edgeHeight: CGFloat = 4

    func makeBody(configuration: Configuration) -> some View {
        let pressed = configuration.isPressed
        let face = kind == .primary ? DSColor.accent : Color.white
        let edge = kind == .primary ? Color(hex: 0xC45A00) : Color(hex: 0xF0C8A8)
        let text = kind == .primary ? Color.white : DSColor.textPrimary
        return configuration.label
            .scaledFont(size: 18, weight: .bold, design: .rounded)
            .foregroundColor(text)
            .frame(maxWidth: .infinity, minHeight: 52)
            .padding(.horizontal, 16)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous).fill(face)
            )
            .offset(y: pressed ? Self.edgeHeight : 0)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous).fill(edge)
                    .offset(y: Self.edgeHeight)
            )
            .padding(.bottom, Self.edgeHeight)
            .animation(.easeOut(duration: 0.08), value: pressed)
    }
}
