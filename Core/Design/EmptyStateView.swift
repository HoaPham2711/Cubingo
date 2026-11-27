import SwiftUI

/// Trạng thái "không có gì ở đây" / "không đi tiếp được": icon mảnh + tiêu đề + một câu giải
/// thích + (tuỳ chọn) một CTA.
///
/// Gom về một chỗ vì bản chép tay ở từng màn sẽ lệch nhau (mỗi nơi một cỡ icon/spacing, có nơi chỉ
/// là một dòng `Text` trần). Màn danh sách rỗng là màn đầu tiên một người dùng mới (và reviewer của
/// Apple) nhìn thấy.
///
/// `title`/`message` là `String` nên **call site phải tự bọc `String(localized:)`** — literal đi
/// qua tham số `String` thì Xcode không extract được (quy ước chuỗi UI của dự án).
struct EmptyStateView: View {
    let systemImage: String
    let title: String
    let message: String
    var actionTitle: String? = nil
    var actionIcon: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: systemImage)
                .font(.system(size: 52, weight: .thin))
                .foregroundColor(DSColor.textTertiary)
            Text(title)
                .scaledFont(size: 17, weight: .semibold)
                .foregroundColor(DSColor.textPrimary)
                .multilineTextAlignment(.center)
            Text(message)
                .scaledFont(size: 14)
                .foregroundColor(DSColor.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            if let actionTitle, let action {
                PrimaryCapsuleButton(title: actionTitle, systemImage: actionIcon, action: action)
                    .padding(.top, 4)
                    .padding(.horizontal, 32)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 28)
        // Gộp thành MỘT phần tử: VoiceOver đọc liền "tiêu đề, mô tả" thay vì bắt user vuốt qua
        // icon trang trí rồi hai mẩu chữ rời.
        .accessibilityElement(children: .combine)
    }
}

#Preview {
    ZStack {
        Color.black.ignoresSafeArea()
        VStack(spacing: 40) {
            EmptyStateView(systemImage: "tray",
                           title: "Nothing here yet",
                           message: "Items you add will show up in this list.",
                           actionTitle: "Add an item",
                           actionIcon: "plus") {}
            EmptyStateView(systemImage: "mappin.slash",
                           title: "No results",
                           message: "Try a different filter.")
        }
    }
}
