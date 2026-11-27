import Foundation
import os

private let appLogger = Logger(subsystem: Bundle.main.bundleIdentifier ?? "app", category: "app")

/// Ghi một dòng log. Mọi config: `os.Logger` (xem bằng Console.app). Build INTERNAL: ghi thêm vào file
/// `AppLog.fileURL` để xem ngay trong app; bản Store (`Release`) không có file, không có đường lấy log.
///
/// Mức riêng tư: bản Store (không cờ `INTERNAL`) ghi nội dung với `.private` — log hợp nhất lấy được khỏi máy qua
/// sysdiagnose, mà nội dung có thể dính người dùng (tên file, mã sản phẩm, mô tả lỗi). Build INTERNAL giữ `.public`
/// để đọc được khi gỡ lỗi. Hai lời gọi tách theo `#if` vì `privacy:` phải là hằng lúc biên dịch (không truyền biến
/// được). Mức riêng tư không quan sát được từ unit test nên không có test riêng cho nó.
func applog(_ message: @autoclosure () -> String) {
    let text = message()
    #if INTERNAL
    appLogger.log("\(text, privacy: .public)")
    AppLogFile.shared.append(text)
    #else
    appLogger.log("\(text, privacy: .private)")
    #endif
}

enum AppLog {
    /// File log hiện tại (build INTERNAL); `nil` ở `Release`.
    static var fileURL: URL? {
        #if INTERNAL
        AppLogFile.shared.url
        #else
        nil
        #endif
    }
}

#if INTERNAL
/// File log của build INTERNAL: `Caches/Logs/app.log`, giới hạn `maxBytes` (mặc định 1 MB). Dòng mới làm file
/// vượt trần ⇒ file hiện tại đổi thành `app.log.1` (đè bản cũ) rồi ghi file mới — tổng tối đa ~2 MB. Ghi đồng
/// bộ dưới khoá: dòng log có trên đĩa ngay khi `applog` trả về (app crash ngay sau vẫn còn).
final class AppLogFile {
    static let shared = AppLogFile(url: defaultURL(), maxBytes: 1_000_000)

    let url: URL?
    let maxBytes: Int
    private let lock = NSLock()
    private let clock = ISO8601DateFormatter()

    init(url: URL?, maxBytes: Int) {
        self.url = url
        self.maxBytes = maxBytes
        clock.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    }

    static func defaultURL() -> URL? {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first?
            .appendingPathComponent("Logs", isDirectory: true)
            .appendingPathComponent("app.log")
    }

    /// Bản trước khi xoay vòng (`app.log.1`).
    var rotatedURL: URL? { url?.appendingPathExtension("1") }

    func append(_ message: String) {
        guard let url else { return }
        lock.lock()
        defer { lock.unlock() }
        let data = Data("\(clock.string(from: Date())) \(message)\n".utf8)
        let fm = FileManager.default
        try? fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let size = ((try? fm.attributesOfItem(atPath: url.path))?[.size] as? NSNumber)?.intValue ?? 0
        if size > 0, size + data.count > maxBytes, let old = rotatedURL {
            try? fm.removeItem(at: old)
            try? fm.moveItem(at: url, to: old)
        }
        if let handle = try? FileHandle(forWritingTo: url) {
            defer { try? handle.close() }
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: data)
        } else {
            try? data.write(to: url)
        }
    }
}
#endif
