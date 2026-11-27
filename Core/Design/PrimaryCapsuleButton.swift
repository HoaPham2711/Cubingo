import SwiftUI

/// CTA full-width (cao tối thiểu 52pt, chữ co giãn theo Dynamic Type) kiểu capsule teal — dùng cho hành động chính trong sheet
/// (vd "Continue", "Export & Share").
struct PrimaryCapsuleButton: View {
    let title: String
    var systemImage: String? = nil
    var isDisabled: Bool = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if let systemImage {
                    Image(systemName: systemImage)
                }
                Text(title)
                    .scaledFont(size: 17, weight: .semibold)
                    .multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity)
            // Cao 52 ở cỡ chữ mặc định; cỡ trợ năng ⇒ cao theo chữ thay vì cắt nhãn.
            .padding(.vertical, 8)
            .frame(minHeight: 52)
        }
        .background(Capsule().fill(DSColor.accent.opacity(isDisabled ? 0.4 : 1)))
        .foregroundColor(DSColor.onAccent)
        .disabled(isDisabled)
    }
}

#Preview {
    ZStack {
        Color.black.ignoresSafeArea()
        PrimaryCapsuleButton(title: "Export & Share", systemImage: "square.and.arrow.up") {}
            .padding()
    }
}
