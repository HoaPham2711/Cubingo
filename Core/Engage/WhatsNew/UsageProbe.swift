import Foundation

/// Dấu vết có sẵn trên máy để seed "đã dùng" MỘT lần — cho lần hiện sheet đầu tiên lọc được tính năng khách đã dùng
/// trước khi ledger kịp nghe event nào. Khoá do app đặt (thẻ hỏi `probe.hasTrace("…")` trong `usedOnDisk`).
///
/// Mọi câu hỏi CHỈ ĐỌC: không tạo file/thư mục, không dựng đối tượng có tác dụng phụ lúc khởi tạo (một store tự tạo
/// thư mục/bản ghi khi init sẽ "hồi sinh" dữ liệu khách đã xoá). Probe chạy ở queue nền (seed của presenter) ⇒ câu
/// trả lời phải an toàn khi đọc ngoài main.
protocol UsageProbe {
    func hasTrace(_ key: String) -> Bool
}

/// Probe dựng từ bảng closure của app, vd `ClosureUsageProbe(["settings_file": { FileManager.default.fileExists(…) }])`.
/// Closure chạy LÚC HỎI (không chụp giá trị lúc dựng); khoá không có trong bảng ⇒ không có dấu vết.
struct ClosureUsageProbe: UsageProbe {
    private let traces: [String: () -> Bool]

    init(_ traces: [String: () -> Bool]) {
        self.traces = traces
    }

    func hasTrace(_ key: String) -> Bool {
        traces[key]?() ?? false
    }
}
