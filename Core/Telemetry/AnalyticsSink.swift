import Foundation

/// Đích đến của event. Firebase là MỘT cài đặt của protocol này, không phải là protocol này.
protocol AnalyticsSink: AnyObject {
    func log(_ event: AppEvent)
    func set(_ property: UserProperty)
    /// Ngữ cảnh gắn vào crash report (Crashlytics custom key). KHÔNG phải analytics.
    func diagnostic(_ key: DiagnosticKey, _ value: String)
    /// Lỗi không làm chết app nhưng đáng xem cùng chỗ với crash.
    func nonFatal(_ error: NonFatal)
    /// Dòng log gắn vào crash report kế tiếp (tab Logs của Crashlytics, có mốc ms). KHÔNG phải analytics.
    func breadcrumb(_ crumb: Breadcrumb)
}

/// Mốc vòng đời ghi vào log crash để đọc trình tự NGAY trước crash — event GA4 chỉ có tới phút, không nói
/// được thứ gì còn sống lúc đó. Chỉ chữ cố định + chỉ số do app đặt — không chuỗi tự do (cùng lý do `NonFatal`
/// chỉ mang mã ngắn). App thêm mốc của nó bằng `static func` trong extension, không dựng chuỗi tại call site.
struct Breadcrumb: Equatable {
    let text: String
}

/// Khoá ngữ cảnh crash. App thêm khoá của nó bằng `static let` trong extension — cùng lý do `AppEvent` gom tên
/// về danh mục: không có string literal rải rác.
struct DiagnosticKey: RawRepresentable, Hashable {
    let rawValue: String

    /// Giai đoạn app đang ở (vd `idle`, hoặc giai đoạn do app đặt).
    static let stage = DiagnosticKey(rawValue: "stage")
}

/// Lỗi không-chết gửi lên Crashlytics. CHỈ mang mã ngắn cố định: `localizedDescription` có thể
/// chứa đường dẫn file (tên do user đặt) nên không bao giờ đi qua đây.
struct NonFatal: Equatable {
    /// Nhóm lỗi. App thêm nhóm của nó bằng `static let` trong extension.
    struct Domain: RawRepresentable, Hashable {
        let rawValue: String

        static let attribution = Domain(rawValue: "attribution")
    }

    let domain: Domain
    /// Mã ngắn: tên pha xử lý, mã lỗi SDK… Dùng làm khoá gộp nhóm trên Console.
    let code: String
    /// Nguyên nhân chi tiết (mã lỗi SDK), chỉ để đọc — KHÔNG tham gia gộp nhóm.
    var detail: String = ""
}

/// Mặc định của `Track`. Nuốt hết — test, Simulator, và bản chưa cấu hình Firebase đều rơi vào đây.
final class NoOpSink: AnalyticsSink {
    func log(_ event: AppEvent) {}
    func set(_ property: UserProperty) {}
    func diagnostic(_ key: DiagnosticKey, _ value: String) {}
    func nonFatal(_ error: NonFatal) {}
    func breadcrumb(_ crumb: Breadcrumb) {}
}

/// Sink cho test: ghi lại để assert "màn này bắn đúng event gì".
final class RecordingSink: AnalyticsSink {
    private(set) var events: [AppEvent] = []
    private(set) var properties: [UserProperty] = []
    private(set) var diagnostics: [DiagnosticKey: String] = [:]
    private(set) var nonFatals: [NonFatal] = []
    private(set) var breadcrumbs: [Breadcrumb] = []

    func log(_ event: AppEvent) { events.append(event) }
    func set(_ property: UserProperty) { properties.append(property) }
    func diagnostic(_ key: DiagnosticKey, _ value: String) { diagnostics[key] = value }
    func nonFatal(_ error: NonFatal) { nonFatals.append(error) }
    func breadcrumb(_ crumb: Breadcrumb) { breadcrumbs.append(crumb) }

    /// Tiện cho assert: danh sách tên event theo đúng thứ tự bắn.
    var names: [String] { events.map(\.name) }

    func clear() {
        events.removeAll(); properties.removeAll(); diagnostics.removeAll(); nonFatals.removeAll()
        breadcrumbs.removeAll()
    }
}
