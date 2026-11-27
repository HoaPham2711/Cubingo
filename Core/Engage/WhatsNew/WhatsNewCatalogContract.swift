import UIKit

/// Hợp đồng mọi catalog What's New phải giữ — app gọi từ test catalog của mình (`AppHostTests/WhatsNewCatalogTests`)
/// với bản trần = bản của chính app. Trả danh sách vi phạm (rỗng = đạt), mỗi dòng nêu id thẻ.
///
/// - id duy nhất, snake_case (đi thẳng vào param telemetry);
/// - tiêu đề 1…30 ký tự, thân 1…90 ký tự, không '!'; thẻ có action thì nhãn nút 1…3 từ;
/// - SF Symbol tồn tại (tên sai ⇒ ô icon trống, không lỗi biên dịch nào bắt);
/// - thẻ đã đóng dấu viết đủ X.Y.Z và không lớn hơn bản app (thẻ của bản tương lai không bao giờ hiện). Thẻ chưa đóng
///   dấu là trạng thái bình thường trên nhánh phát triển ⇒ không kiểm bản (build Store không biên dịch được nếu còn).
enum WhatsNewCatalogContract {
    static let maxTitleLength = 30
    static let maxBodyLength = 90
    static let maxCtaWords = 3

    private static let snakeCase = try! NSRegularExpression(pattern: "^[a-z][a-z0-9]*(_[a-z0-9]+)*$")

    static func violations(_ cards: [WhatsNewCard], bundleVersion: AppVersion) -> [String] {
        var out: [String] = []
        var seen: Set<String> = []
        for c in cards {
            if !seen.insert(c.id).inserted { out.append("\(c.id): id trùng") }
            if snakeCase.firstMatch(in: c.id, range: NSRange(c.id.startIndex..., in: c.id)) == nil {
                out.append("'\(c.id)': id không phải snake_case")
            }
            if c.title.isEmpty || c.title.count > maxTitleLength {
                out.append("\(c.id): tiêu đề phải 1…\(maxTitleLength) ký tự (đang \(c.title.count))")
            }
            if c.body.isEmpty || c.body.count > maxBodyLength {
                out.append("\(c.id): thân phải 1…\(maxBodyLength) ký tự (đang \(c.body.count))")
            }
            if c.action != nil {
                let words = c.ctaTitle.split(separator: " ").count
                if words == 0 || words > maxCtaWords {
                    out.append("\(c.id): nhãn nút phải 1…\(maxCtaWords) từ (đang \(words))")
                }
            }
            if (c.title + c.body + c.ctaTitle).contains("!") { out.append("\(c.id): không dùng '!'") }
            if UIImage(systemName: c.systemImage) == nil {
                out.append("\(c.id): SF Symbol '\(c.systemImage)' không tồn tại")
            }
            if case .released(let v) = c.version {
                if v.components.count != 3 { out.append("\(c.id): viết đủ X.Y.Z, đang là \(v)") }
                if v > bundleVersion { out.append("\(c.id): bản \(v) > bản app \(bundleVersion)") }
            }
        }
        return out
    }
}
