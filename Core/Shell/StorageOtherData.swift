import Foundation

/// Dọn đồ tạm các lần chạy trước để lại + đo dung lượng. Hàm tĩnh, inject URL + mốc thời gian để test bằng thư mục
/// tạm. Màn "Storage" theo dữ liệu riêng của app là việc của app; lõi chỉ giữ phần dùng chung này.
enum StorageOtherData {

    /// Nơi chỉ chứa đồ tạm: `tmp/` của app (export, chia sẻ, `NSIRD_*` của NSFileCoordinator…). Thư mục staging
    /// riêng của app (vd chỗ chép file vào trước khi nhập) đi qua `runAtLaunch(extraDirs:)`.
    static var defaultTempDirs: [URL] { [FileManager.default.temporaryDirectory] }

    /// Gốc chứa dữ liệu người dùng: `purge` từ chối thư mục BẰNG hoặc là TỔ TIÊN của một gốc này (truyền nhầm
    /// Documents/Library/home là mỗi lần mở app xoá sạch dữ liệu, âm thầm). Thư mục con thật sự của chúng vẫn được
    /// phép (staging hợp lệ thường nằm dưới Application Support hoặc Caches); `tmp/` là con của home nên được phép.
    /// Danh sách này LUÔN có hiệu lực: `protectedRoots` do nơi gọi truyền chỉ THÊM gốc bảo vệ, không thay thế.
    static var defaultProtectedRoots: [URL] {
        let fm = FileManager.default
        var roots = [URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)]
        for d: FileManager.SearchPathDirectory in [.documentDirectory, .libraryDirectory,
                                                   .applicationSupportDirectory, .cachesDirectory] {
            roots += fm.urls(for: d, in: .userDomainMask)
        }
        if let lib = fm.urls(for: .libraryDirectory, in: .userDomainMask).first {
            roots.append(lib.appendingPathComponent("Preferences", isDirectory: true))
        }
        return roots
    }

    /// Chuẩn hoá để so đường dẫn: bỏ `.`/`..` rồi giải symlink (symlink trỏ tới Documents vẫn là Documents).
    /// `purge` kiểm VÀ liệt kê đúng URL này — đường dẫn được kiểm là đường dẫn bị dọn.
    static func normalized(_ url: URL) -> URL {
        url.standardizedFileURL.resolvingSymlinksInPath()
    }

    /// Thành phần đường dẫn để SO: `normalized` rồi bỏ `/private` ở đầu. `resolvingSymlinksInPath` chỉ bỏ `/private`
    /// khi đường dẫn TỒN TẠI, nên một gốc bảo vệ chưa được tạo trên đĩa (vd Application Support lúc mới cài) và cùng
    /// thư mục đó viết qua `/private/var/…` sẽ lệch nhau nếu không đưa về một dạng.
    static func comparableComponents(_ url: URL) -> [String] {
        let c = normalized(url).pathComponents
        if c.count >= 2, c[0] == "/", c[1] == "private" { return ["/"] + c.dropFirst(2) }
        return c
    }

    /// Hàm quyết định thuần: `dir` được phép dọn khi nó KHÔNG bằng và KHÔNG là tổ tiên của gốc bảo vệ nào — xét
    /// `protectedRoots` HỢP với `defaultProtectedRoots` (truyền `[]` không tắt được chốt chặn).
    static func isAllowedPurgeRoot(_ dir: URL, protectedRoots: [URL]) -> Bool {
        let d = comparableComponents(dir)
        for root in protectedRoots + defaultProtectedRoots {
            let p = comparableComponents(root)
            // `p` bắt đầu bằng `d` ⇔ `d` bằng `p` hoặc là tổ tiên của `p`.
            if p.starts(with: d) { return false }
        }
        return true
    }

    /// Mục cấp 1 mà dọn lúc mở app phải chừa: `tmp/<bundle-id>-Inbox/` là nơi hệ thống đặt file tới qua "Open in" /
    /// "Copy to" — tạo TRƯỚC khi tiến trình chạy (cold launch), nên ctime luôn trước mốc cắt; dọn nó ở nền là xoá
    /// file đúng lúc app đang nhập. Hệ thống tự quản thư mục này.
    static func isLaunchExcluded(_ item: URL) -> Bool {
        item.lastPathComponent.hasSuffix("-Inbox")
    }

    /// Cổng host test, tách thành hàm thuần để kiểm được không cần chờ task nền.
    static func shouldRun(isUnitTestHost: Bool) -> Bool {
        !isUnitTestHost
    }

    /// Gọi MỘT lần lúc mở app, trong `App.init` TRƯỚC mọi thứ ghi vào `tmp/`: mốc cắt là "bây giờ lúc gọi" (đồng
    /// bộ), phần xoá chạy nền — file process này tạo ra sau mốc có ctime sau mốc nên an toàn, còn file tạo TRƯỚC lời
    /// gọi (kể cả của chính lần chạy này) sẽ bị xoá.
    ///
    /// Host unit test ⇒ không làm gì, trả `nil`: test tạo thư mục làm việc ngay trong `tmp/`, dọn ở đây là xoá dưới
    /// chân test.
    @discardableResult
    static func runAtLaunch(extraDirs: [URL] = [],
                            isUnitTestHost: Bool = AppEnvironment.isUnitTestHost) -> Task<Int64, Never>? {
        guard shouldRun(isUnitTestHost: isUnitTestHost) else { return nil }
        let dirs = defaultTempDirs + extraDirs
        let now = Date()
        return Task.detached(priority: .utility) {
            let daDon = launchPurge(dirs: dirs, now: now)
            if daDon > 0 {
                applog("[storage] dọn file tạm lúc mở app: \(ByteCountFormatter.string(fromByteCount: daDon, countStyle: .file))")
            }
            return daDon
        }
    }

    /// Phần dọn của `runAtLaunch` (đồng bộ, test được): mốc cắt = `now`, chừa thư mục Inbox của hệ thống.
    @discardableResult
    static func launchPurge(dirs: [URL], now: Date, protectedRoots: [URL] = defaultProtectedRoots) -> Int64 {
        purge(dirs: dirs, olderThan: 0, now: now, protectedRoots: protectedRoots, excluding: isLaunchExcluded)
    }

    /// Xoá các mục CẤP 1 trong `dirs` có ctime trước `now - olderThan`; trả số byte đã giải phóng.
    ///
    /// Theo **ctime** (`attributeModificationDate`), không theo ngày tạo/sửa: `FileManager.copyItem` giữ nguyên hai
    /// ngày đó của file nguồn (đo trên APFS), nên file vừa chép vào tmp để nhập sẽ trông "cũ" và bị xoá giữa lúc
    /// nhập. Chỉ xét cấp 1 vì thư mục đang dùng có thể chứa file chép từ nguồn cũ; ctime thư mục đổi mỗi khi thêm
    /// mục bên trong. Hệ quả với `olderThan > 0`: thư mục cấp 1 được xét theo ctime của CHÍNH nó (lần cuối thêm/bớt
    /// mục con trực tiếp), không theo tuổi nội dung bên trong.
    ///
    /// `olderThan` âm bị kẹp về 0: âm đẩy mốc cắt vào tương lai ⇒ xoá cả file đang ghi.
    ///
    /// Biên an toàn: `dir` bằng/là tổ tiên của gốc bảo vệ (`isAllowedPurgeRoot`, `protectedRoots` chỉ THÊM vào gốc
    /// mặc định) ⇒ bỏ qua cả thư mục, ghi log; kiểm và liệt kê cùng MỘT URL đã chuẩn hoá. (Hiện `standardizedFileURL`
    /// đã giải `..` theo đường THẬT — `tmp/L/..` với `L` là symlink ra cha của đích, giống hệ thống tệp — nên liệt kê
    /// URL thô cũng cho cùng kết quả; dùng một URL để "đường được kiểm là đường bị dọn" không dựa vào chi tiết đó.) Chỉ
    /// xoá mục NẰM TRONG thư mục được giao, không bao giờ xoá chính thư mục đó; symlink cấp 1 chỉ bị gỡ chính cái link
    /// (`removeItem` không đi theo link); thư mục không tồn tại ⇒ không làm gì; `excluding` trả `true` ⇒ chừa mục đó.
    @discardableResult
    static func purge(dirs: [URL], olderThan age: TimeInterval, now: Date,
                      protectedRoots: [URL] = defaultProtectedRoots,
                      excluding: (URL) -> Bool = { _ in false }) -> Int64 {
        let fm = FileManager.default
        let cutoff = now.addingTimeInterval(-max(age, 0))
        var freed: Int64 = 0
        for raw in dirs {
            let dir = normalized(raw)
            guard isAllowedPurgeRoot(dir, protectedRoots: protectedRoots) else {
                applog("[storage] TỪ CHỐI dọn \(raw.path): bằng hoặc chứa thư mục dữ liệu được bảo vệ")
                continue
            }
            let items = (try? fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil, options: [])) ?? []
            for item in items where !excluding(item) {
                guard let ctime = (try? item.resourceValues(forKeys: [.attributeModificationDateKey]))?.attributeModificationDate,
                      ctime < cutoff else { continue }
                let size = bytes(of: item)
                if (try? fm.removeItem(at: item)) != nil { freed += size }
            }
        }
        return freed
    }

    /// Tổng kích thước LOGIC, gồm cả file ẩn. Nhận URL file lẫn thư mục; không tồn tại ⇒ 0. Symlink tính 0 và
    /// không đi theo (enumerator mặc định cũng không theo symlink bên trong).
    static func bytes(of url: URL) -> Int64 {
        let keys: Set<URLResourceKey> = [.fileSizeKey, .isRegularFileKey, .isSymbolicLinkKey]
        guard let v = try? url.resourceValues(forKeys: keys), v.isSymbolicLink != true else { return 0 }
        if v.isRegularFile == true { return Int64(v.fileSize ?? 0) }
        guard let e = FileManager.default.enumerator(at: url, includingPropertiesForKeys: Array(keys)) else { return 0 }
        var total: Int64 = 0
        for case let f as URL in e {
            guard let fv = try? f.resourceValues(forKeys: keys), fv.isRegularFile == true,
                  fv.isSymbolicLink != true else { continue }
            total += Int64(fv.fileSize ?? 0)
        }
        return total
    }
}
