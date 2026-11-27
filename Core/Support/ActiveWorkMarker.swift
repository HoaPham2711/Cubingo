import Foundation

/// Dấu trên đĩa: "đang làm một việc dài". Còn nguyên ở lần mở sau ⇒ lần chạy trước chết giữa
/// chừng (crash hoặc bị kill vì hết RAM). `kind` là chuỗi tuỳ app (vd. `"import"`), `workID` khoá
/// một việc cụ thể.
struct ActiveWorkMarker: Codable, Equatable {
    var workID: String
    var kind: String
    var startedAt: Date
    /// App đang ở nền lúc dấu được ghi/cập nhật. iOS kill app nền là chuyện bình thường,
    /// không phải sự cố của app ⇒ dấu còn `true` lúc khởi động lại KHÔNG tính là sự cố.
    var backgrounded: Bool
}

/// Mỗi `kind` một file riêng trong thư mục dấu (hai việc khác loại có thể chạy chồng nhau). Store
/// duyệt FILE trên đĩa chứ không dựa danh sách kind khai trước. Gọi được từ mọi thread: lock + ghi atomic.
final class ActiveWorkMarkerStore {
    /// Host unit test dùng thư mục tạm — nếu không, test để lại dấu thật trên simulator và lần
    /// `-uiPreview` sau hiện banner sự cố giả.
    static let shared: ActiveWorkMarkerStore = {
        if AppEnvironment.isUnitTestHost {
            let tmp = FileManager.default.temporaryDirectory
                .appendingPathComponent("active-work-unit-test", isDirectory: true)
            return ActiveWorkMarkerStore(directory: tmp)
        }
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return ActiveWorkMarkerStore(directory: base.appendingPathComponent("active-work", isDirectory: true))
    }()

    private let directory: URL
    private let lock = NSLock()
    /// Trạng thái nền trong bộ nhớ; dấu mới do `begin` kế thừa (việc hàng loạt chạy tiếp ở nền và
    /// bắt đầu việc kế tiếp ngay ở đó).
    private var isBackgrounded = false

    init(directory: URL) {
        self.directory = directory
    }

    /// Tên file cho một `kind`. `kind` là chuỗi tuỳ ý nên PHẢI làm sạch trước khi thành tên file:
    /// `/` hay `..` không được dẫn ra ngoài thư mục dấu. Chỉ chữ THƯỜNG/số ASCII và `-` giữ nguyên; mọi byte
    /// khác (kể cả chữ HOA) thành `%XX` — APFS mặc định của iOS không phân biệt hoa/thường nên
    /// `Import` và `import` phải ra hai tên khác nhau kể cả khi so không phân biệt hoa/thường. Phép biến đổi này đơn ánh (hai kind khác nhau không bao giờ trùng file —
    /// thay thế mất thông tin kiểu "mọi ký tự lạ thành `_`" sẽ để `a/b` ghi đè `a_b`) và không bao
    /// giờ sinh `.`, `/` hay tên rỗng/ẩn.
    static func fileName(forKind kind: String) -> String {
        guard !kind.isEmpty else { return "%.json" }
        var out = ""
        for b in kind.utf8 {
            let giuNguyen = (b >= 0x30 && b <= 0x39) || (b >= 0x61 && b <= 0x7A) || b == 0x2D
            out += giuNguyen ? String(UnicodeScalar(b)) : String(format: "%%%02X", b)
        }
        return out + ".json"
    }

    private func url(forKind kind: String) -> URL {
        directory.appendingPathComponent(Self.fileName(forKind: kind))
    }

    // Các hàm dưới đây CHỈ được gọi khi đang giữ `lock`.

    /// Mọi file `.json` trong thư mục dấu, theo thứ tự tên (tất định).
    private func markerFiles() -> [URL] {
        let files = (try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? []
        return files.filter { $0.pathExtension == "json" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    private func read(_ file: URL) -> ActiveWorkMarker? {
        guard let data = try? Data(contentsOf: file) else { return nil }
        let dec = JSONDecoder()
        dec.dateDecodingStrategy = .iso8601
        // Tên file phải khớp kind trong nội dung; lệch/hỏng ⇒ bỏ.
        guard let m = try? dec.decode(ActiveWorkMarker.self, from: data),
              Self.fileName(forKind: m.kind) == file.lastPathComponent else {
            // File hỏng: bỏ, không bao giờ crash.
            try? FileManager.default.removeItem(at: file)
            return nil
        }
        return m
    }

    private func write(_ m: ActiveWorkMarker) {
        let enc = JSONEncoder()
        enc.dateEncodingStrategy = .iso8601
        guard let data = try? enc.encode(m) else { return }
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try? data.write(to: url(forKind: m.kind), options: .atomic)
    }

    func begin(kind: String, workID: String) {
        lock.lock(); defer { lock.unlock() }
        write(ActiveWorkMarker(workID: workID, kind: kind, startedAt: Date(),
                               backgrounded: isBackgrounded))
    }

    /// Chỉ xoá khi dấu đúng của `workID` này — dấu của việc khác còn nguyên.
    func clear(kind: String, workID: String) {
        lock.lock(); defer { lock.unlock() }
        let file = url(forKind: kind)
        guard let m = read(file), m.kind == kind, m.workID == workID else { return }
        try? FileManager.default.removeItem(at: file)
    }

    /// Ghi nhận app xuống nền/lên lại, cập nhật cả các dấu đang có trên đĩa (mọi kind).
    func setBackgrounded(_ value: Bool) {
        lock.lock(); defer { lock.unlock() }
        isBackgrounded = value
        for file in markerFiles() {
            guard var m = read(file), m.backgrounded != value else { continue }
            m.backgrounded = value
            write(m)
        }
    }

    /// Gọi MỘT lần lúc khởi động, trước khi việc nào bắt đầu. Đọc rồi xoá mọi dấu; trả dấu mới
    /// nhất trong số các dấu không phải do nền. Không có ⇒ `nil`.
    func takeIncident() -> ActiveWorkMarker? {
        lock.lock(); defer { lock.unlock() }
        var found: [ActiveWorkMarker] = []
        for file in markerFiles() {
            if let m = read(file) { found.append(m) }
            try? FileManager.default.removeItem(at: file)
        }
        return found.filter { !$0.backgrounded }.max { $0.startedAt < $1.startedAt }
    }
}
