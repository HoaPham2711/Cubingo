import Foundation

/// Kết quả attribution Apple Ads của CHÍNH lượt cài này (AdServices, không IDFA, không ATT).
/// Lưu trong `UserDefaults` sau khi chốt, gán thành thuộc tính GA4 `acq_source` / `asa_*`.
struct AttributionResult: Codable, Equatable {
    enum Source: String, Codable {
        case appleAds = "apple_ads"
        case organic
        /// Thử đủ lâu mà Apple vẫn không trả lời được — chốt để thôi gọi mạng.
        case unknown
    }

    var source: Source
    /// campaignId / adGroupId / keywordId của Apple Ads, dạng chuỗi số. Không phải PII.
    var campaign: String?
    var adGroup: String?
    /// Vắng khi lượt chạm đến từ Search Match (không có từ khoá).
    var keyword: String?
    var country: String?
    /// `Download` | `Redownload`.
    var conversion: String?
    /// Tổng số lần gọi API tới lúc chốt.
    var attempts: Int
}

/// Đọc thân phản hồi của `POST https://api-adservices.apple.com/api/v1/`.
enum AttributionPayload {
    /// `nil` khi thân không phải JSON object hoặc thiếu/không phải Bool `attribution` — caller coi
    /// là lỗi `parse`, KHÔNG được chốt thành `organic`. `attempts` = 0, caller điền.
    static func parse(_ data: Data) -> AttributionResult? {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let flag = obj["attribution"] as? NSNumber,
              CFGetTypeID(flag) == CFBooleanGetTypeID()
        else { return nil }
        guard flag.boolValue else {
            return AttributionResult(source: .organic, campaign: nil, adGroup: nil, keyword: nil,
                                     country: nil, conversion: nil, attempts: 0)
        }
        func chuoi(_ key: String) -> String? {
            switch obj[key] {
            case let n as NSNumber: return n.stringValue
            case let s as String where !s.isEmpty: return s
            default: return nil
            }
        }
        return AttributionResult(source: .appleAds, campaign: chuoi("campaignId"), adGroup: chuoi("adGroupId"),
                                 keyword: chuoi("keywordId"), country: chuoi("countryOrRegion"),
                                 conversion: chuoi("conversionType"), attempts: 0)
    }
}

extension AppEvent {
    /// Dạng gọi của nguồn (`Track.log(.attributionResolved(r))`) — chuyển tiếp sang factory tách tham số để khoá
    /// param và cách mã hoá chỉ nằm MỘT chỗ.
    static func attributionResolved(_ r: AttributionResult) -> AppEvent {
        .attributionResolved(source: r.source.rawValue, attempts: r.attempts, campaign: r.campaign,
                             adGroup: r.adGroup, keyword: r.keyword, country: r.country, conversion: r.conversion)
    }
}
