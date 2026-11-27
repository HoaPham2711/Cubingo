import SwiftUI

/// Banner "có bản mới" đầu màn Home. Đóng được (×).
struct UpdateBanner: View {
    let version: String
    /// Release notes của bản trên Store (`nil` khi Lookup không trả).
    let notes: String?
    let onUpdate: () -> Void
    let onDismiss: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "arrow.down.app.fill")
                .scaledFont(size: 26)
                .foregroundColor(DSColor.accent)
            VStack(alignment: .leading, spacing: 2) {
                Text("Update available")
                    .scaledFont(size: 15, weight: .semibold)
                    .foregroundColor(DSColor.textPrimary)
                subtitle
                    .scaledFont(size: 13)
                    .foregroundColor(DSColor.textSecondary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 8)
            Button("Update", action: onUpdate)
                .scaledFont(size: 14, weight: .semibold)
                .foregroundColor(DSColor.onAccent)
                .padding(.horizontal, 14)
                .padding(.vertical, 7)
                .background(Capsule().fill(DSColor.accent))
                .buttonStyle(.plain)
            Button(action: onDismiss) {
                Image(systemName: "xmark")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(DSColor.textTertiary)
                    .frame(width: 28, height: 28)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Dismiss")
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 16).fill(DSColor.cardBackground))
    }

    /// Dòng đầu của release notes thay câu chung.
    /// Notes là dữ liệu từ Store (ngôn ngữ theo region máy) ⇒ `verbatim`, không đi qua catalog.
    @ViewBuilder
    private var subtitle: some View {
        if let headline = UpdateEvaluator.bannerHeadline(notes: notes) {
            Text(verbatim: headline)
        } else {
            Text("Version \(version) is on the App Store.")
        }
    }
}
