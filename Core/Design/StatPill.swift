import SwiftUI

/// Một mục trong StatPill: text đã format sẵn + màu tuỳ chỉnh (vd accent cho số liệu nổi bật).
struct StatPillItem: Identifiable {
    let id = UUID()
    let text: String
    var color: Color = DSColor.textPrimary.opacity(0.85)
}

/// Capsule "liquid glass" hiển thị nhiều chỉ số cách nhau bằng separator dọc.
struct StatPill: View {
    let items: [StatPillItem]

    var body: some View {
        HStack(spacing: 14) {
            ForEach(Array(items.enumerated()), id: \.element.id) { index, item in
                if index > 0 {
                    Rectangle()
                        .fill(DSColor.hairlineOnGlass)
                        .frame(width: 1, height: 12)
                }
                Text(item.text)
                    .scaledFont(size: 13, weight: .semibold, monospacedDigit: true)
                    .foregroundColor(item.color)
                    // Cỡ chữ trợ năng: co nhẹ thay vì cắt "…" khi ba chỉ số không vừa một hàng.
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
            }
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 9)
        .background(
            ZStack {
                Capsule().fill(.ultraThinMaterial)
                Capsule().fill(DSColor.glassTint)
            }
        )
    }
}

#Preview {
    ZStack {
        Color.black.ignoresSafeArea()
        StatPill(items: [
            StatPillItem(text: "24.3k items", color: DSColor.accent),
            StatPillItem(text: "18.2 m²"),
            StatPillItem(text: "00:42"),
        ])
    }
}
