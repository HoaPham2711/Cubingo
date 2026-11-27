import SwiftUI

/// Bo góc riêng lẻ (vd chỉ 2 góc trên) — `clipShape`/`cornerRadius` mặc định của SwiftUI bo đều 4 góc.
struct RoundedCorner: Shape {
    var radius: CGFloat = .infinity
    var corners: UIRectCorner = .allCorners

    func path(in rect: CGRect) -> Path {
        let path = UIBezierPath(
            roundedRect: rect,
            byRoundingCorners: corners,
            cornerRadii: CGSize(width: radius, height: radius)
        )
        return Path(path.cgPath)
    }
}

/// Handle kéo + tiêu đề lớn cho bottom sheet — top-radius 28px theo design system.
struct BottomSheetChrome<Content: View>: View {
    let title: String
    var subtitle: String? = nil
    /// Cử chỉ ẩn trên TIÊU ĐỀ (nhấn giữ 1,5s). Dùng cho lối vào công cụ nội bộ mà không bày ra
    /// cho người dùng thường — cùng khuôn với `internalLongPressSheet` của lõi. nil = không có.
    var onTitleLongPress: (() -> Void)? = nil
    /// Nút đóng ✕ ở mép phải hàng tiêu đề. nil = không có (sheet chỉ đóng bằng vuốt xuống).
    /// Đặt ở CHROME chứ không để caller tự vẽ trong nội dung: nút đóng phải đứng yên khi phần
    /// nội dung cuộn, và phải thẳng hàng tiêu đề — khi sheet tự đặt ✕ vào đầu ScrollView thì nó
    /// vừa lệch xuống một dòng vừa cuộn mất.
    var onClose: (() -> Void)? = nil
    /// Nội dung sheet — KHÔNG tự thêm padding ngang; caller tự bọc `.padding(.horizontal, 20)`
    /// nếu cần thẳng hàng với tiêu đề (xem `#Preview` bên dưới).
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Capsule()
                .fill(DSColor.sheetHandle)
                .frame(width: 38, height: 5)
                .frame(maxWidth: .infinity)
                .padding(.top, 10)
            HStack(alignment: .firstTextBaseline) {
                Text(title)
                    .font(.system(size: 21, weight: .bold))
                    .foregroundColor(DSColor.textPrimary)
                    // Chỉ nhận cử chỉ trên VÙNG CHỮ tiêu đề, không phải cả hàng — nhấn giữ nhầm
                    // ở khoảng trống bên phải (nơi có subtitle phụ) sẽ khó hiểu.
                    .contentShape(Rectangle())
                    .onLongPressGesture(minimumDuration: 1.5) { onTitleLongPress?() }
                Spacer()
                if let subtitle {
                    Text(subtitle)
                        .font(.system(size: 14))
                        .foregroundColor(DSColor.textSecondary)
                }
                if let onClose {
                    Button(action: onClose) {
                        Image(systemName: "xmark")
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundColor(DSColor.textSecondary)
                            // Vùng chạm 44×44 theo HIG; glyph 15px tự nó quá nhỏ để bấm trúng.
                            .frame(width: 44, height: 44)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    // Glyph chỉ cao ~15px trong khung 44px → căn baseline đẩy nó lệch hẳn xuống.
                    .alignmentGuide(.firstTextBaseline) { $0[VerticalAlignment.center] + 5 }
                    // Bù nửa phần khung thừa để glyph vẫn cách mép 20px như tiêu đề bên trái.
                    .padding(.trailing, -12)
                }
            }
            .padding(.horizontal, 20)
            content()
        }
        .padding(.bottom, 20)
        .background(DSColor.sheetBackground)
        .clipShape(RoundedCorner(radius: DSRadius.sheetTop, corners: [.topLeft, .topRight]))
    }
}

#Preview {
    ZStack(alignment: .bottom) {
        DSColor.pageBackground.ignoresSafeArea()
        BottomSheetChrome(title: "Export options", subtitle: "Subtitle") {
            // `verbatim:` — chuỗi mẫu của #Preview KHÔNG được vào String Catalog
            // (Xcode vẫn extract #Preview). Xem tools/i18n/lint_localizable.py rule R5.
            Text(verbatim: "Sheet content")
                .foregroundColor(.white)
                .padding(.horizontal, 20)
        }
    }
}
