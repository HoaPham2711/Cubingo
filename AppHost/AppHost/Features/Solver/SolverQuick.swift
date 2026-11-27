import Foundation

enum SolverQuickError: Error, Equatable {
    /// Hết giờ mà chưa có lời giải nào.
    case timedOut
}

/// "Just solve it": lời giải ngắn bằng thuật toán hai pha. Dựng MỘT lần ở `AppHostApp`; bảng nạp lười ở lần gọi đầu
/// (closure — test truyền closure ném lỗi để giả lỗi nạp).
final class SolverQuick: @unchecked Sendable {
    private let loadTables: @Sendable () throws -> SolverKociembaTables
    private let lock = NSLock()
    private var cached: SolverKociembaTables?

    init(tables: @escaping @Sendable () throws -> SolverKociembaTables) {
        loadTables = tables
    }

    /// Chạy ngoài main actor. Huỷ task ⇒ `CancellationError`; hết giờ ⇒ lời giải tốt nhất đã có (≤ 30 bước), chưa có
    /// ⇒ `SolverQuickError.timedOut`. Khối đã giải ⇒ `[]`. Chỉ trả bước mặt.
    func solve(_ c: CubeCubies, maxLength: Int = 22, timeout: Duration = .seconds(1)) async throws -> [CubeMove] {
        try Task.checkCancellation()
        let tables = try self.tables()
        let deadline = ContinuousClock.now + timeout
        let search = SolverKociembaSearch(tables: tables, start: c, maxLength: maxLength, deadline: deadline,
                                          isCancelled: { Task.isCancelled })
        let found: [Int]?
        do {
            found = try search.run()
        } catch SolverKociembaSearch.Stop.cancelled {
            throw CancellationError()
        }
        guard let found else { throw SolverQuickError.timedOut }
        return found.map { CubeMove.faceMoves[$0] }
    }

    private func tables() throws -> SolverKociembaTables {
        lock.lock()
        defer { lock.unlock() }
        if let cached { return cached }
        let t = try loadTables()
        cached = t
        return t
    }
}
