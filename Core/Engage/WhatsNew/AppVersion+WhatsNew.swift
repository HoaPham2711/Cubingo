import Foundation

// Phần bổ sung cho `AppVersion` (Core/Engage/Update/AppVersion.swift) mà What's New cần. Tên file khác
// `AppVersion.swift` vì hai file trùng tên trong cùng target thì Xcode báo "filename used twice".
//
// KHÔNG cho `AppVersion` conform `ExpressibleByStringLiteral`: khi đó `AppVersion("abc")` với literal bị Swift
// hiểu là ép literal (SE-0213) ⇒ đi vào `init(stringLiteral:)` thay vì `init?` ⇒ mất nhánh trả nil. Catalog viết
// `.released("1.13.0")` qua `CardVersion.released(_: String)` (WhatsNewCard.swift).

extension AppVersion: CustomStringConvertible {
    /// Giữ đúng số thành phần đã viết (`1.14` ⇒ "1.14") — dùng cho tiêu đề nhóm và param telemetry.
    var description: String { components.map(String.init).joined(separator: ".") }
}
