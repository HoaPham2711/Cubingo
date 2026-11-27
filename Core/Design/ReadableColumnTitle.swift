import SwiftUI

/// Chỗ đặt tiêu đề lớn của một màn GỐC có cột đọc (`.readableContentWidth`).
///
/// iPad (regular): tiêu đề lớn của thanh điều hướng luôn sát lề trái khung chi tiết, lệch khỏi cột đọc ở giữa ⇒ thanh
/// dùng tiêu đề inline bị thay bằng principal rỗng, và màn tự vẽ tiêu đề lớn làm phần tử đầu tiên TRONG cột
/// (`ReadableColumnTitle`). iPhone (compact, hoặc chưa biết size class): giữ tiêu đề lớn hệ thống, không vẽ gì thêm.
enum ReadableColumnTitlePlacement: Equatable {
    case navigationBar
    case inColumn

    init(sizeClass: UserInterfaceSizeClass?) {
        self = sizeClass == .regular ? .inColumn : .navigationBar
    }

    var titleDisplayMode: NavigationBarItem.TitleDisplayMode {
        self == .inColumn ? .inline : .large
    }

    /// Lề trên của vùng cuộn: ở `.inColumn` tiêu đề tự vẽ đã nằm đầu nội dung ⇒ bỏ đệm trên (`nil` = mặc định).
    var topScrollMargin: CGFloat? {
        self == .inColumn ? 0 : nil
    }
}

/// Tiêu đề lớn tự vẽ trong cột — chỉ hiện ở `.inColumn` (iPad), là header của màn (VoiceOver) vì thanh điều hướng
/// không hiện tiêu đề ở gốc. Đặt làm hàng đầu của `List` hoặc phần tử đầu của `VStack` trong `ScrollView`; các modifier
/// `listRow…` không có tác dụng ngoài `List`. Đi cặp với `.readableColumnNavigationTitle(_:)` trên CÙNG màn, cùng `title`.
struct ReadableColumnTitle: View {
    private let title: Text
    @Environment(\.horizontalSizeClass) private var sizeClass

    init(_ title: Text) {
        self.title = title
    }

    var body: some View {
        if ReadableColumnTitlePlacement(sizeClass: sizeClass) == .inColumn {
            title
                .font(.largeTitle.bold())
                .foregroundColor(DSColor.textPrimary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityAddTraits(.isHeader)
                .listRowBackground(Color.clear)
                .listRowSeparator(.hidden)
                .listRowInsets(EdgeInsets(top: 8, leading: 0, bottom: 0, trailing: 0))
        }
    }
}

private struct ReadableColumnNavigationTitle: ViewModifier {
    let title: Text
    @Environment(\.horizontalSizeClass) private var sizeClass

    func body(content: Content) -> some View {
        let placement = ReadableColumnTitlePlacement(sizeClass: sizeClass)
        content
            .contentMargins(.top, placement.topScrollMargin, for: .scrollContent)
            // `navigationTitle` luôn giữ: màn con có nhãn Back đúng tên màn gốc.
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(placement.titleDisplayMode)
            .toolbar {
                // iPad: principal rỗng thay tiêu đề thanh ⇒ chỉ còn tiêu đề lớn trong cột. Không ẩn cả thanh (màn
                // con và nút toolbar cần nó).
                if placement == .inColumn {
                    ToolbarItem(placement: .principal) {
                        Color.clear.frame(width: 1, height: 1).accessibilityHidden(true)
                    }
                }
            }
    }
}

extension View {
    /// Tiêu đề của màn gốc có cột đọc — áp lên nội dung GỐC của `NavigationStack` (không lên màn con), đi cặp với
    /// `ReadableColumnTitle(title)` đặt đầu nội dung. Thay cho `.navigationTitle` + `.navigationBarTitleDisplayMode`.
    func readableColumnNavigationTitle(_ title: Text) -> some View {
        modifier(ReadableColumnNavigationTitle(title: title))
    }
}
