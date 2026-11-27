import Foundation
@testable import AppHost

/// Transport giả cho test UI. Ghi lại cái được gửi và cho phép ép lỗi — hai thứ `FeedbackView`
/// cần để test được ba nhánh trạng thái mà không chạm mạng.
final class FakeFeedbackTransport: FeedbackTransport {
    private(set) var sent: [FeedbackDraft] = []
    var errorToThrow: Error?

    func send(_ draft: FeedbackDraft) async throws {
        if let errorToThrow { throw errorToThrow }
        sent.append(draft)
    }
}
