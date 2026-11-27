import SwiftUI

/// Token bố cục cho màn rộng (iPad).
///
/// Mọi quyết định "màn rộng" đi theo size class / bề rộng THẬT, không theo `userInterfaceIdiom`:
/// iPad chạy cửa sổ hẹp (Split View 1/3, Stage Manager thu nhỏ) là compact và phải trông như iPhone.
enum DSLayout {
    /// Bề rộng tối đa cho nội dung đọc/cuộn dọc (danh sách, Paywall, Onboarding…). Trên iPhone luôn
    /// lớn hơn màn ⇒ không có tác dụng.
    static let readableWidth: CGFloat = 700
    /// Bề rộng tối đa cho panel/form nổi (panel đáy, thanh chọn nổi…).
    static let formWidth: CGFloat = 560
}

extension View {
    /// Giới hạn bề rộng nội dung thành một cột ĐẶT GIỮA khung đầy. Khung ngoài vẫn
    /// `maxWidth: .infinity` nên nền/cuộn vẫn tràn màn — chỉ nội dung bị giới hạn. Màn hẹp hơn
    /// `maxWidth` ⇒ no-op. `alignment` = căn nội dung BÊN TRONG cột (VD `.leading` cho VStack
    /// canh trái có thể co hẹp hơn cột), cột thì luôn ở giữa.
    func readableContentWidth(_ maxWidth: CGFloat = DSLayout.readableWidth,
                              alignment: Alignment = .center) -> some View {
        frame(maxWidth: maxWidth, alignment: alignment)
            .frame(maxWidth: .infinity)
    }
}
