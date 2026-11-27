import Foundation

/// Giá trị param gửi kèm event. Kiểu đóng thay vì `Any` để test cấu trúc soi được và để
/// sink không phải đoán kiểu lúc chạy.
enum ParamValue: Equatable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
}

/// Danh mục TÊN event: một `enum` có `rawValue` là tên GA4. Lõi có `ShellEventName`; mỗi app khai danh mục
/// riêng của nó (cùng protocol) + static factory trong `extension AppEvent` — không sửa gì trong `Core/`.
/// `TelemetryTaxonomy.violations` duyệt `allCases` của danh mục để ép "mỗi tên có mẫu".
protocol EventNameCatalog: RawRepresentable, CaseIterable where RawValue == String {}

/// Một event analytics: tên + param. Call site không bao giờ dựng tay — luôn qua static factory
/// (`Track.log(.paywallView(source: "settings"))`), nên không có string literal tên event rải rác.
///
/// Vì sao không gọi thẳng `logEvent("...")` tại call site: GA4 không cho sửa hồi tố. Một cái tên gõ sai hay
/// một param PII lọt vào là hỏng vĩnh viễn dữ liệu của khoảng thời gian đó. Gom tên về danh mục + factory thì
/// đổi tên là đổi một dòng, và cổng `TelemetryTaxonomy` gác được cả tập.
///
/// Trước kia là `enum` với `switch` vét cạn (trình biên dịch ép mỗi event khai param + mẫu). Đổi sang struct để
/// app thêm event của nó; phần "ép" chuyển sang `TelemetryTaxonomy.violations` + test cấu trúc.
///
/// Event KHÔNG mang trạng thái của NGƯỜI DÙNG (vd `is_pro`): GA4 cắt lát theo user property sẵn có, nhân đôi
/// nó vào event chỉ tổ phải luồn nguồn quyền qua những tầng view không sở hữu nó.
struct AppEvent: Equatable {
    let name: String
    let parameters: [String: ParamValue]

    init<N: RawRepresentable>(_ name: N, _ parameters: [String: ParamValue] = [:]) where N.RawValue == String {
        self.name = name.rawValue
        self.parameters = parameters
    }

    /// Thay cho `if case .tenEvent = event` của bản enum.
    func isNamed<N: RawRepresentable>(_ name: N) -> Bool where N.RawValue == String {
        self.name == name.rawValue
    }

    /// Giá trị chuỗi của một param; `nil` khi vắng hoặc không phải chuỗi.
    func string(_ key: String) -> String? {
        if case .string(let s) = parameters[key] { return s }
        return nil
    }

    /// Cắt chuỗi về trần 100 ký tự của GA4. Lý do lỗi có thể đến từ `error.localizedDescription` nên dài bao
    /// nhiêu là không đoán trước được — factory cắt tại đây thay vì tin call site. Factory của app dùng chung.
    static func cat(_ s: String) -> String {
        s.count <= 100 ? s : String(s.prefix(100))
    }
}

/// Thuộc tính người dùng — cắt lát mọi báo cáo. GA4 tối đa 25 thuộc tính tuỳ biến. Lõi có 6 (dưới đây); app
/// thêm của nó bằng `UserProperty(name:value:)` hoặc static riêng trong extension.
/// GA4 không có kiểu bool ⇒ cờ gửi dạng chuỗi `"true"`/`"false"`.
struct UserProperty: Equatable {
    let name: String
    let value: String

    static func isPro(_ v: Bool) -> UserProperty { UserProperty(name: "is_pro", value: v ? "true" : "false") }
    /// `"production"` | `"sandbox"` | `"xcode"` — lọc doanh thu TestFlight/sandbox khỏi báo cáo.
    static func storeEnv(_ v: String) -> UserProperty { UserProperty(name: "store_env", value: v) }
    /// Máy nội bộ (từng chạy TestFlight / bản Release cài từ Xcode). Chỉ có giá trị `"true"`; máy khách KHÔNG
    /// mang thuộc tính này.
    static var internalDevice: UserProperty { UserProperty(name: "internal_device", value: "true") }
    /// Nguồn cài: `"apple_ads"` | `"organic"` | `"unknown"`.
    static func acqSource(_ v: String) -> UserProperty { UserProperty(name: "acq_source", value: v) }
    /// campaignId Apple Ads — chỉ khi `acq_source = apple_ads`.
    static func asaCampaign(_ v: String) -> UserProperty { UserProperty(name: "asa_campaign", value: v) }
    /// keywordId Apple Ads — chỉ khi có (Search Match thì không).
    static func asaKeyword(_ v: String) -> UserProperty { UserProperty(name: "asa_keyword", value: v) }
}
