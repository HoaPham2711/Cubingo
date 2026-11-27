import SwiftUI

/// Nền gradient kem → hồng nhạt của phong cách A (bản phác `visual-style.html`).
struct StyleBackground: View {
    static let top = Color(hex: 0xFFF4E0)
    static let bottom = Color(hex: 0xFFE1EC)

    var body: some View {
        LinearGradient(colors: [Self.top, Self.bottom], startPoint: .top, endPoint: .bottom)
            .ignoresSafeArea()
    }
}

extension View {
    /// Đặt nền gradient của app sau nội dung.
    func styleBackground() -> some View {
        background(StyleBackground())
    }
}
