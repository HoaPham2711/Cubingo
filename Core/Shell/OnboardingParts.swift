import SwiftUI

/// Một dòng tính năng/hướng dẫn trong tour: icon nhỏ nền accent nhạt + title + subtitle.
/// `title`/`subtitle` là `String` ⇒ call site PHẢI bọc `String(localized:)`.
struct OnboardingFeatureRow: View {
    let systemImage: String
    let title: String
    let subtitle: String
    /// Ô icon 36pt ở cỡ chữ mặc định, lớn theo chữ (icon bên trong co giãn).
    @ScaledMetric(relativeTo: .subheadline) private var iconBox: CGFloat = 36

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(DSColor.accent.opacity(0.14))
                    .frame(width: iconBox, height: iconBox)
                Image(systemName: systemImage)
                    .scaledFont(size: 15, weight: .semibold)
                    .foregroundColor(DSColor.accent)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .scaledFont(size: 15, weight: .semibold)
                    .foregroundColor(DSColor.textPrimary)
                Text(subtitle)
                    .scaledFont(size: 13)
                    .foregroundColor(DSColor.textSecondary)
                    // Không có thì VStack cha bị nén dọc sẽ ép subtitle còn 1 dòng + "…" thay vì xuống dòng.
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
    }
}

/// Khung chung một trang tour: cuộn khi thiếu chỗ thay vì nén chữ thành "…" (cắt ở đâu tuỳ máy, có lúc là chính
/// dòng công khai analytics), cột đọc giữa trên iPad.
///
/// Trang Welcome của app nên có dòng công khai analytics (nếu app thu số liệu) ngay tại đây, cỡ 12pt NGANG HÀNG các
/// dòng chú thích khác — cố ý KHÔNG nhỏ hơn: thông báo minh bạch in nhỏ hơn mọi thứ quanh nó thì tự phủ định mục
/// đích. Tên app (`AppConfig.displayName`) hiển thị bằng `Text(verbatim:)` — tên riêng không dịch.
struct OnboardingPageScaffold<Content: View>: View {
    @ViewBuilder let content: Content

    var body: some View {
        GeometryReader { geo in
            ScrollView {
                VStack(spacing: 0) { content }
                    .padding(.horizontal, 28)
                    // iPad: không kéo giãn cả màn (iPhone: no-op).
                    .readableContentWidth(DSLayout.formWidth)
                    .padding(.top, 8)
                    .padding(.bottom, 16)
                    .frame(minHeight: geo.size.height, alignment: .top)
            }
            .scrollBounceBehavior(.basedOnSize)
        }
    }
}

/// Trang hướng dẫn: minh hoạ + tiêu đề + các dòng hướng dẫn. Minh hoạ bằng SF Symbols/mockup SwiftUI, KHÔNG ảnh —
/// không phải chụp lại khi UI đổi, tự đúng iPhone/iPad. `title` và chữ trong `Row` là `String` ⇒ call site PHẢI
/// bọc `String(localized:)`.
struct OnboardingInfoPage: View {
    struct Row {
        let icon: String
        let title: String
        let subtitle: String
    }

    let title: String
    let illustration: AnyView
    let rows: [Row]

    var body: some View {
        OnboardingPageScaffold {
            illustration
                .frame(height: 180)
                .frame(maxWidth: .infinity)
                .padding(.top, 8)
                .padding(.bottom, 28)
            Text(title)
                .scaledFont(size: 26, weight: .bold)
                .foregroundColor(DSColor.textPrimary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity)
            VStack(alignment: .leading, spacing: 20) {
                ForEach(rows.indices, id: \.self) { i in
                    OnboardingFeatureRow(systemImage: rows[i].icon, title: rows[i].title,
                                         subtitle: rows[i].subtitle)
                }
            }
            .padding(.top, 28)
            .padding(.horizontal, 6)
        }
    }
}

#Preview {
    ZStack {
        Color.black.ignoresSafeArea()
        OnboardingInfoPage(
            title: "Preview",
            illustration: AnyView(Image(systemName: "sparkles").font(.system(size: 64))
                .foregroundColor(DSColor.accent)),
            rows: [OnboardingInfoPage.Row(icon: "star", title: "Row title", subtitle: "Row subtitle")])
    }
}
