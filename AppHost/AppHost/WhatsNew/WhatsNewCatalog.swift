import Foundation

/// Catalog What's New CỦA APP — lõi (`Core/Engage/WhatsNew/`) chỉ giữ luật chọn/hiện thẻ.
///
/// Thêm thẻ cho bản đang làm: dùng case "chưa đóng dấu" của `CardVersion` (chỉ biên dịch ở Debug/Internal);
/// `bump_version.sh` đóng dấu thành `.released("X.Y.Z")` lúc ra bản, và build Release không biên dịch được nếu còn sót
/// thẻ chưa đóng dấu. File này KHÔNG được chứa chữ đó ở đâu khác (kể cả comment): `stamp_whats_new.py --check` đếm
/// chuỗi thô và cổng phát hành coi là chưa đóng dấu.
/// Chữ thẻ đi qua biến `String` ⇒ BẮT BUỘC `String(localized:)`. Thẻ có nút: `action: WhatsNewAction(key: "…")`, đích
/// do resolver/runner của app quyết. "Đã dùng": `usedWhen` (event `Track.log`) và `usedOnDisk` (dấu vết qua
/// `UsageProbe.hasTrace`) — cả hai thuần, không gọi lại `Track`. Hợp đồng chung gác ở `WhatsNewCatalogTests`.
///
/// Thẻ `welcome` chỉ để chạy trọn đường ống (chọn thẻ, sheet, đóng dấu, cổng biên dịch, hợp đồng): không nút, không
/// bao giờ bị coi là "đã dùng". App thật thay bằng thẻ của mình (có nút và luật "đã dùng" thật).
enum WhatsNewCatalog {
    static let cards: [WhatsNewCard] = [
        WhatsNewCard(
            id: "welcome",
            version: .released("0.1.0"),
            priority: 1,
            systemImage: "sparkles",
            title: String(localized: "Welcome"),
            body: String(localized: "Thanks for updating. New features will be introduced here."),
            ctaTitle: String(localized: "Got it"),
            action: nil),
    ]
}
