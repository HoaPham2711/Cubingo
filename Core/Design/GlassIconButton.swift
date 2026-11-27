import SwiftUI

/// Nút icon tròn 44px kiểu "liquid glass" — thay `Toggle(.button)`/`Button(.bordered)` nổi trên nội dung nền ảnh/video.
struct GlassIconButton: View {
    let systemImage: String
    var isActive: Bool = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            ZStack {
                Circle().fill(.ultraThinMaterial)
                Circle().fill(isActive ? DSColor.accent.opacity(0.9) : DSColor.glassTint)
                Image(systemName: systemImage)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(isActive ? DSColor.onAccent : DSColor.textPrimary.opacity(0.85))
            }
            .frame(width: 44, height: 44)
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    ZStack {
        Color.black.ignoresSafeArea()
        HStack(spacing: 12) {
            GlassIconButton(systemImage: "star", isActive: true) {}
            GlassIconButton(systemImage: "xmark") {}
        }
    }
}
