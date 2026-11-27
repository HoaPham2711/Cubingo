import SwiftUI

/// Thẻ trắng bo 22 pt, gờ dưới màu đào (bản phác); `selected` ⇒ viền cam 3 pt.
struct StyleCard: ViewModifier {
    var selected: Bool = false
    static let cornerRadius: CGFloat = 22

    func body(content: Content) -> some View {
        content
            .background(
                RoundedRectangle(cornerRadius: Self.cornerRadius, style: .continuous).fill(Color.white)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Self.cornerRadius, style: .continuous)
                    .strokeBorder(selected ? DSColor.accent : Color.clear, lineWidth: 3)
            )
            .background(
                RoundedRectangle(cornerRadius: Self.cornerRadius, style: .continuous)
                    .fill(Color(hex: 0xF0C8A8))
                    .offset(y: 4)
            )
            .padding(.bottom, 4)
    }
}

extension View {
    func styleCard(selected: Bool = false) -> some View {
        modifier(StyleCard(selected: selected))
    }
}
