import Foundation

/// Một yêu cầu điều hướng tiêu thụ một lần, truyền xuống View như tham số: `pending` để `onChange` nghe,
/// `take()` để lấy-và-xoá. View không nhận kênh nào thì truyền `.none` (tường minh, không mặc định).
///
/// Cách dùng ở model sở hữu kênh (lối ngoài như thẻ What's New, deep-link):
/// - Màn đích giữ `path`/`editMode` riêng ⇒ lối ngoài chỉ đặt yêu cầu ở model; view đích nghe ở CẢ `onChange`
///   LẪN `onAppear` (view có thể được dựng mới sau `select`) rồi `take()`.
/// - Giá trị `UUID` khi yêu cầu không mang dữ liệu ⇒ hai lần bấm liên tiếp vẫn là hai giá trị khác nhau.
/// - `take()` không có yêu cầu thì KHÔNG ghi (`@Published` không bắn thừa mỗi `onAppear`).
struct OneShotRequest<Value: Equatable> {
    let pending: Value?
    let take: () -> Value?

    static var none: OneShotRequest { OneShotRequest(pending: nil, take: { nil }) }
}
