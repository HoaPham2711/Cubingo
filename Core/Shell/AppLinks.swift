import Foundation

/// URL công khai của sản phẩm, gom một chỗ — dựng từ host web đã cấu hình (`[web]` trong `app.config.toml`, qua
/// `AppConfig`). App không có web ⇒ mọi link `nil`, UI ẩn hàng tương ứng.
///
/// **Bất biến: hai đường dẫn `/privacy/` và `/terms/` KHÔNG được đổi** (định nghĩa ở `AppConfig`). Chúng được nướng
/// cứng vào binary của mọi bản đã phát hành — bản ship hôm nay sẽ vĩnh viễn trỏ tới đúng URL này, kể cả nhiều năm
/// sau khi web đã redesign. Website phải giữ đường dẫn sống (redirect nếu cần), không bao giờ để 404. Với đăng ký tự
/// động gia hạn, link chết ở paywall là vi phạm App Review Guideline 3.1.2.
///
/// Dấu "/" cuối là CỐ Ý: host tĩnh kiểu auto-trailing-slash trả 307 cho dạng không có "/" rồi mới tới đích; dùng
/// thẳng dạng canonical để bỏ một vòng khứ hồi mạng.
struct AppLinks: Equatable {
    let site: URL?
    let privacy: URL?
    let terms: URL?
    let support: URL?

    init(config: AppConfig) {
        site = config.siteURL
        privacy = config.privacyURL
        terms = config.termsURL
        support = config.supportURL
    }
}
