import SwiftUI
import UIKit

/// Sở hữu CHUNG cờ `UIApplication.isIdleTimerDisabled`.
///
/// Vì sao cần: cờ này là state TOÀN CỤC của app, nhưng thường có nhiều nơi cùng muốn giữ màn sáng (ghi hình, xử lý
/// nền dài, export/render video — qua `.keepScreenAwake(...)`). Mỗi bên tự ghi thì bên nào kết thúc trước sẽ trả màn
/// về tự tắt trong khi bên kia còn đang chạy — user đứng chờ một việc 10 phút thì màn khoá giữa chừng. Ở đây giữ tập
/// chủ sở hữu: còn ai giữ thì màn còn sáng.
///
/// Chỉ gọi trên main thread (yêu cầu của `UIApplication`).
final class IdleTimerCoordinator {

    static let shared = IdleTimerCoordinator()

    /// Đường ghi thật ra hệ thống — test tiêm closure đếm để không đụng `UIApplication`.
    private let apply: (Bool) -> Void
    private var owners: Set<String> = []
    /// Giá trị đã ghi lần cuối; chặn ghi trùng (call site gọi theo `didSet` nên rất dày).
    private var applied = false

    init(apply: @escaping (Bool) -> Void = { UIApplication.shared.isIdleTimerDisabled = $0 }) {
        self.apply = apply
    }

    /// true = còn ít nhất một chủ sở hữu muốn giữ màn sáng.
    var keepAwake: Bool { !owners.isEmpty }

    /// Đăng ký/nhả nhu cầu giữ sáng của một chủ sở hữu. Nhả một chủ chưa từng giữ là no-op.
    func set(_ owner: String, keepAwake: Bool) {
        if keepAwake { owners.insert(owner) } else { owners.remove(owner) }
        let want = self.keepAwake
        guard want != applied else { return }
        applied = want
        apply(want)
        applog("[power] màn hình \(want ? "GIỮ SÁNG" : "trả về tự tắt")"
               + (owners.isEmpty ? "" : " (đang giữ: \(owners.sorted().joined(separator: ", ")))"))
    }
}

extension View {
    /// Giữ màn sáng khi `active`. Mỗi view một chủ sở hữu riêng trong `IdleTimerCoordinator` (tên + UUID) ⇒ hai view
    /// cùng tên không nhả nhầm của nhau; view biến mất (đóng màn giữa chừng) thì tự nhả.
    func keepScreenAwake(_ owner: String, when active: Bool) -> some View {
        modifier(KeepScreenAwake(owner: owner, active: active))
    }
}

private struct KeepScreenAwake: ViewModifier {
    let owner: String
    let active: Bool
    @State private var id = UUID()

    private var key: String { "\(owner)#\(id.uuidString.prefix(4))" }

    func body(content: Content) -> some View {
        content
            .onAppear { IdleTimerCoordinator.shared.set(key, keepAwake: active) }
            .onChange(of: active) { _, a in IdleTimerCoordinator.shared.set(key, keepAwake: a) }
            .onDisappear { IdleTimerCoordinator.shared.set(key, keepAwake: false) }
    }
}
