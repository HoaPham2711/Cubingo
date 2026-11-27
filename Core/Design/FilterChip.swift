import SwiftUI

/// Pill toggle dùng cho filter chip (All / Done / Pending…) và preset picker kiểu HIG mới.
struct FilterChip: View {
    let title: String
    let isActive: Bool
    /// SF Symbol nhỏ sau nhãn — vd badge khoá của tính năng trả phí. Emoji 🔒 lệch tông hẳn với bảng màu
    /// (vàng cam trên nền accent teal) nên đi bằng symbol để ăn theo `foregroundColor`.
    var systemImage: String? = nil
    /// SF Symbol TRƯỚC nhãn — icon loại trên chip lọc.
    var leadingSystemImage: String? = nil
    /// Số đếm mờ sau nhãn (chip lọc kèm số lượng). `nil` = không hiện.
    var count: Int? = nil
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 5) {
                if let leadingSystemImage {
                    Image(systemName: leadingSystemImage).scaledFont(size: 12, weight: .semibold)
                }
                Text(title)
                    .scaledFont(size: 14, weight: isActive ? .semibold : .regular)
                if let count {
                    Text(verbatim: "\(count)")
                        .scaledFont(size: 13, weight: .medium, monospacedDigit: true)
                        .opacity(0.6)
                }
                if let systemImage {
                    Image(systemName: systemImage).scaledFont(size: 11, weight: .semibold)
                }
            }
            .foregroundColor(isActive ? DSColor.onAccent : DSColor.textPrimary.opacity(0.7))
            .padding(.horizontal, 16)
            .padding(.vertical, 7)
        }
        .background(Capsule().fill(isActive ? DSColor.accent : DSColor.cardBackground))
    }
}

#Preview {
    ZStack {
        Color.black.ignoresSafeArea()
        HStack {
            FilterChip(title: "All", isActive: true) {}
            FilterChip(title: "Done", isActive: false) {}
        }
    }
}
