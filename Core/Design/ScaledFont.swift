import SwiftUI

/// Chọn text style mà một cỡ chữ cố định "đi theo" khi Dynamic Type đổi — để `scaledFont(size:)` co giãn cùng nhịp
/// với chữ hệ thống quanh nó. Quy tắc: text style LỚN NHẤT có cỡ mặc định (ở cỡ `large`) ≤ `size`; nhỏ hơn mọi style
/// ⇒ `.caption2`. Ví dụ 14 ⇒ `.footnote` (13), 17 ⇒ `.body`, 28 ⇒ `.title`, 52 ⇒ `.largeTitle`.
enum ScaledFontStyle {
    /// Cỡ mặc định (pt, Dynamic Type `large`) của từng text style iOS, từ lớn tới nhỏ. `.headline` cùng 17 với
    /// `.body` nên không cần riêng — cùng đường cong co giãn.
    static let defaultSizes: [(style: Font.TextStyle, size: CGFloat)] = [
        (.largeTitle, 34), (.title, 28), (.title2, 22), (.title3, 20), (.body, 17),
        (.callout, 16), (.subheadline, 15), (.footnote, 13), (.caption, 12), (.caption2, 11),
    ]

    static func textStyle(forPointSize size: CGFloat) -> Font.TextStyle {
        defaultSizes.first { $0.size <= size }?.style ?? .caption2
    }
}

/// `.font(.system(size:weight:design:))` nhưng CO GIÃN theo Dynamic Type (`@ScaledMetric`). Ở cỡ chữ mặc định cho ra
/// đúng cỡ đã viết ⇒ giao diện không đổi; ở cỡ trợ năng lớn lên cùng chữ hệ thống. Dùng thay `.system(size:)` cho
/// mọi chữ (và icon đi cùng chữ) — `.system(size:)` trần KHÔNG co giãn.
private struct ScaledSystemFont: ViewModifier {
    @ScaledMetric private var size: CGFloat
    private let weight: Font.Weight
    private let design: Font.Design
    private let monospacedDigit: Bool

    init(size: CGFloat, weight: Font.Weight, design: Font.Design, monospacedDigit: Bool,
         relativeTo style: Font.TextStyle) {
        _size = ScaledMetric(wrappedValue: size, relativeTo: style)
        self.weight = weight
        self.design = design
        self.monospacedDigit = monospacedDigit
    }

    func body(content: Content) -> some View {
        let font = Font.system(size: size, weight: weight, design: design)
        return content.font(monospacedDigit ? font.monospacedDigit() : font)
    }
}

extension View {
    /// Font hệ thống cỡ `size` co giãn theo Dynamic Type. `relativeTo` mặc định suy từ cỡ
    /// (`ScaledFontStyle.textStyle(forPointSize:)`).
    func scaledFont(size: CGFloat, weight: Font.Weight = .regular, design: Font.Design = .default,
                    monospacedDigit: Bool = false, relativeTo style: Font.TextStyle? = nil) -> some View {
        modifier(ScaledSystemFont(size: size, weight: weight, design: design, monospacedDigit: monospacedDigit,
                                  relativeTo: style ?? ScaledFontStyle.textStyle(forPointSize: size)))
    }
}
