import Foundation

/// Số lượt dùng thử miễn phí đã dùng của MỘT tính năng ("N lần free trước khi phải mua"). Đọc lại store mỗi
/// lần — không cache, để mọi instance/màn luôn thấy cùng một số.
/// Dùng trên main thread (đọc-rồi-ghi không nguyên tử). Bên gọi kiểm `FreeUseGate.canStart` TRƯỚC `consume()`:
/// `consume()` không tự chặn khi đã hết lượt.
final class FreeUseLedger {
    let limit: Int
    private let store: SecureCounterStore

    init(limit: Int, store: SecureCounterStore) {
        self.limit = limit
        self.store = store
    }

    /// Bộ đếm trong Keychain (sống qua gỡ app cài lại), service `<bundle id>.<feature>`, account `used`.
    static func keychain(limit: Int, feature: String) -> FreeUseLedger {
        FreeUseLedger(limit: limit,
                      store: KeychainCounterStore(service: KeychainCounterStore.appService(feature), account: "used"))
    }

    /// Lỗi đọc thật (không phải "chưa có mục") ⇒ coi như 0 lượt đã dùng để không chặn oan user — nhưng phải để
    /// lại dấu vết: 0 nghĩa là user được thêm lượt free, và đây là chỗ duy nhất biết vì sao.
    var used: Int {
        do {
            return try store.read()
        } catch {
            applog("[freeUse] đọc bộ đếm lỗi: \(error) — coi như 0 lượt đã dùng")
            return 0
        }
    }

    var remaining: Int { max(0, limit - used) }

    /// Trừ một lượt. Gọi SAU khi việc dùng thử đã được ghi nhận thành công (không trừ cho lượt chưa bắt đầu).
    /// Đọc lỗi ⇒ ném, KHÔNG ghi `0 + 1`: ghi đè như thế là reset bộ đếm thật về 1.
    func consume() throws { try store.write(try store.read() + 1) }

    /// Trả lại một lượt — CHỈ cho việc thất bại mà user không nhận được gì từ lượt đó (không có kẽ lách lấy
    /// thêm lượt). Không xuống dưới 0.
    func refund() throws {
        let u = try store.read()
        guard u > 0 else { return }
        try store.write(u - 1)
    }

    #if INTERNAL
    /// Chỉ cho bảng debug (thử paywall hết lượt mà không phải dùng hết N lượt). Bản App Store không có hàm này.
    // debug-symbol: required
    func debugSetUsed(_ n: Int) throws { try store.write(max(0, n)) }
    #endif
}

/// Cổng trước khi bắt đầu một lượt dùng tính năng có hạn mức free. Hàm THUẦN để test được mà không cần Keychain.
enum FreeUseGate {
    static func canStart(isPro: Bool, remaining: Int) -> Bool {
        isPro || remaining > 0
    }
}
