import Foundation

enum FeedbackSendError: Error, Equatable {
    case offline
    /// Máy chủ từ chối — mã HTTP kèm theo. Ý nghĩa từng mã là của API cụ thể, không phải của lõi.
    case rejected(Int)
}

/// Cửa duy nhất ra mạng cho phản hồi. Có protocol để `FeedbackView` test được mà không chạm
/// URLSession — cùng lý do `StoreClient` tồn tại ở khối mua hàng.
///
/// Lõi KHÔNG có transport thật và cố ý không có transport "mở Mail": mở Mail không xác nhận được
/// là thư đã gửi, nên form sẽ báo "Thanks!" sai. App không có transport thì không dựng form mà dùng
/// `SupportContact`/`SupportMailOpener`.
protocol FeedbackTransport {
    func send(_ draft: FeedbackDraft) async throws
}
