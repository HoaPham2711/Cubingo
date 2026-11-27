import Foundation

/// Phần paywall do APP cấp: tiêu đề mặc định, bảng so sánh Free / Pro, link điều khoản, gói chọn sẵn.
/// Lõi (`PaywallView` + `PaywallCopy`) chỉ lo khung, gói, nút mua và copy giá/dùng thử — những thứ mang nghĩa vụ
/// Guideline 3.1.2 nên phải giống nhau ở mọi app.
///
/// Mọi chuỗi ở đây là `String` đi tới `Text(...)` qua biến ⇒ app PHẢI bọc `String(localized: "...")` tại chỗ viết
/// literal, nếu không Xcode không extract được vào String Catalog. Không viết cứng tên app trong chuỗi
/// (dùng `AppConfig.displayName`).
///
/// Bảng so sánh là LỜI HỨA bán hàng: con số trong ô nên lấy từ chính luật app thi hành (hằng số của
/// `FreeUseLedger`, quota…) thay vì gõ lại, để sửa luật mà quên bảng không thể xảy ra âm thầm.
struct PaywallContent {
    struct Row {
        let title: String
        let free: Cell
        let pro: Cell
    }

    enum Cell: Equatable {
        case yes, no
        /// Đã localize tại nguồn (app).
        case text(String)
    }

    struct Section {
        /// `nil` = nhóm không có tiêu đề (bảng một nhóm).
        let title: String?
        let rows: [Row]
    }

    /// Tiêu đề khi call site không truyền `headline` ngữ cảnh (vd "Upgrade to Pro").
    var defaultHeadline: String
    /// MỘT nhóm, ít dòng là tốt nhất: paywall phải đọc xong trong một màn. Rỗng ⇒ không vẽ bảng.
    var sections: [Section]
    /// Từ `AppConfig.termsURL/privacyURL`, dựng từ host web đã cấu hình của app (`[web]` trong app.config.toml).
    /// Paywall bán subscription PHẢI hiện cả hai link (App Store Guideline 3.1.2). Thiếu host ⇒ hai URL là `nil`
    /// và link biến mất khỏi paywall — vì vậy cổng release (thêm ở task cuối của Plan 2) bắt buộc có host khi
    /// paywall bật.
    var termsURL: URL?
    var privacyURL: URL?
    /// Loại gói được chọn sẵn khi mở paywall. Không có trong danh sách tải về ⇒ gói đầu tiên
    /// (`PaywallView.initialSelection`).
    var preselectedKind: ProProduct.Kind = .year
}
