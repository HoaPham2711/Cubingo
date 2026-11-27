import Foundation

/// Body của `POST /api/v1/feedback` — JSON phẳng đúng sáu field, khớp schema của máy chủ nhận phản hồi. Tách khỏi
/// phần mạng để hình dạng test được bằng dữ liệu tĩnh. Đổi tên/kiểu field hay trần độ dài (`FeedbackDraft.max*`)
/// là đổi hợp đồng với máy chủ: sửa schema phía máy chủ cùng lúc.
enum FeedbackRequestEncoder {

    static func body(for draft: FeedbackDraft, appVersion: String, clientTime: Date) throws -> Data {
        // Validate TRƯỚC khi ra mạng: để máy chủ bắt lỗi này là tốn một vòng round-trip và trả về 422 chung chung,
        // không nói được cho user họ sai chỗ nào. Trần đo bằng byte UTF-8 (cùng `FeedbackDraft.validate()`).
        try draft.validate()

        let fields: [String: Any] = [
            "type": draft.type.rawValue,
            "message": draft.message,
            // nil thành chuỗi rỗng: hình dạng body không dao động theo input.
            "email": draft.email ?? "",
            "diagnostics": draft.diagnostics,
            "appVersion": cat(appVersion, toUTF8Bytes: FeedbackDraft.maxAppVersionLength),
            // Máy chủ đòi số nguyên mili-giây.
            "clientTime": Int64((clientTime.timeIntervalSince1970 * 1000).rounded(.down)),
        ]
        return try JSONSerialization.data(withJSONObject: fields)
    }

    /// Cắt theo ranh giới ký tự (không bao giờ xé đôi một ký tự nhiều byte) sao cho ≤ `toUTF8Bytes` byte —
    /// chặt hơn hoặc bằng đếm ký tự của máy chủ. Chuỗi rỗng giữ nguyên (máy chủ đòi ≥ 1: lỗi đó thuộc nơi cấp version).
    static func cat(_ s: String, toUTF8Bytes limit: Int) -> String {
        var out = ""
        var bytes = 0
        for ch in s {
            let n = String(ch).utf8.count
            if bytes + n > limit { break }
            out.append(ch)
            bytes += n
        }
        return out
    }
}
