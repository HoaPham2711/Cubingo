import SwiftUI

/// Row 52px cho InsetGroupedList — thay row thô trong `List` native ở các sheet redesign.
struct InsetGroupedRow: View {
    let title: String
    var detail: String? = nil
    var showChevron: Bool = true
    var isLast: Bool = false
    /// Khi có giá trị: hiện Toggle thay vì detail/chevron (dùng cho hàng công tắc bật/tắt trong sheet tuỳ chọn).
    var toggle: Binding<Bool>? = nil

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(title)
                    .font(.system(size: 17))
                    .foregroundColor(DSColor.textPrimary)
                Spacer()
                if let toggle {
                    Toggle("", isOn: toggle)
                        .labelsHidden()
                        .tint(DSColor.accent)
                } else {
                    if let detail {
                        Text(detail)
                            .font(.system(size: 15))
                            .foregroundColor(DSColor.textSecondary)
                    }
                    if showChevron {
                        Image(systemName: "chevron.right")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(DSColor.textTertiary)
                    }
                }
            }
            .padding(.horizontal, 16)
            .frame(height: 52)
            if !isLast {
                Rectangle()
                    .fill(DSColor.hairlineOnCard)
                    .frame(height: 0.5)
                    .padding(.leading, 16)
            }
        }
    }
}

/// Card bo góc 26px bọc quanh danh sách `InsetGroupedRow` — thay `List` native trong sheet.
/// Lưu ý: header thụt lề 20px nhưng card body sát mép — khi đặt trong `BottomSheetChrome`,
/// tự bọc `.padding(.horizontal, 20)` quanh view này để card thẳng hàng với tiêu đề sheet.
struct InsetGroupedList<Content: View>: View {
    var header: String? = nil
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let header {
                Text(header.uppercased())
                    .font(.system(size: 13))
                    .foregroundColor(DSColor.textSecondary)
                    .padding(.horizontal, 20)
            }
            VStack(spacing: 0) {
                content()
            }
            .background(DSColor.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: DSRadius.insetList, style: .continuous))
        }
    }
}

#Preview {
    ZStack {
        DSColor.pageBackground.ignoresSafeArea()
        InsetGroupedList(header: "Options") {
            InsetGroupedRow(title: "Details")
            InsetGroupedRow(title: "Share", isLast: true)
        }
        .padding()
    }
}
