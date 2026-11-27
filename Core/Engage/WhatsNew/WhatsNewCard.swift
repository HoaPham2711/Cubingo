import Foundation

/// Bản mà thẻ thuộc về. `.unreleased` = thẻ viết trên nhánh phát triển, chưa biết số bản — lúc chạy tính như
/// `current`; `tools/release/bump_version.sh` thay bằng `.released("X.Y.Z")` lúc release.
///
/// CHỐT CHÍNH chống ship thẻ chưa đóng dấu là TRÌNH BIÊN DỊCH: case `unreleased` chỉ tồn tại dưới
/// `#if INTERNAL || WHATSNEW_ALLOW_UNRELEASED`. Debug + Internal có `INTERNAL`; Release (archive App Store) không có
/// cờ nào ⇒ còn sót một thẻ `.unreleased` ở bất kỳ dạng nào (member ngắn, `CardVersion.unreleased`, hằng, nhánh
/// `#if`…) thì build Release lỗi biên dịch ngay. `WHATSNEW_ALLOW_UNRELEASED` CHỈ do `tools/i18n/verify_catalog.py`
/// truyền qua dòng lệnh khi build Release để đọc `.stringsdata` (case không mang chuỗi nên tập key không đổi) — để
/// `--check`/`--write` chạy được trên nhánh phát triển; project.yml và archive Store KHÔNG bao giờ đặt cờ này.
/// Mọi `switch` trên `CardVersion` phải bọc nhánh `case .unreleased` trong cùng điều kiện như `effective(current:)`
/// (gác bởi `tools/release/test_whats_new_compile_gate.py`). `tools/release/stamp_whats_new.py` chỉ là tiện ích
/// đóng dấu, không phải cổng.
enum CardVersion: Equatable {
    #if INTERNAL || WHATSNEW_ALLOW_UNRELEASED
    case unreleased
    #endif
    case released(AppVersion)

    /// Cho catalog viết `.released("1.13.0")` — dạng `bump_version.sh` đóng dấu. Chuỗi hỏng là lỗi lập trình trong
    /// catalog ⇒ dừng ngay (test hợp đồng catalog của app dựng mọi thẻ nên bắt được trước khi ship).
    static func released(_ version: String) -> CardVersion {
        guard let v = AppVersion(version) else { preconditionFailure("CardVersion: bản hỏng \"\(version)\"") }
        return .released(v)
    }

    /// Bản dùng để so sánh / nhóm: `.unreleased` ⇒ `current`.
    func effective(current: AppVersion) -> AppVersion {
        switch self {
        #if INTERNAL || WHATSNEW_ALLOW_UNRELEASED
        case .unreleased: return current
        #endif
        case .released(let v): return v
        }
    }
}

/// Đích của nút trên thẻ — một KHOÁ do app đặt (vd `WhatsNewAction(key: "open_settings")`); lõi không biết khoá nào
/// nghĩa là gì. App có thể khai `static let` trong extension cho gọn catalog. Khả dụng hay không do `WhatsNewResolver`
/// của app quyết lúc chọn/vẽ thẻ.
struct WhatsNewAction: Hashable {
    let key: String
}

/// Hành động đã gắn đích cụ thể, sẵn để `WhatsNewRunner` của app thực thi. `payload` mang dữ liệu đích (vd id mục
/// cần mở) mà resolver tìm được ở thời điểm resolve.
struct WhatsNewResolvedAction: Equatable {
    let key: String
    var payload: [String: String] = [:]
}

/// App trả đích dùng được cho action, hoặc `nil` ⇒ không có đích lúc này (thẻ bản cũ bị bỏ khỏi sheet; thẻ còn lại
/// hiện không nút — không vẽ nút chết). Gọi trên main, phải nhanh và thuần (chỉ đọc trạng thái app đang có).
typealias WhatsNewResolver = (WhatsNewAction) -> WhatsNewResolvedAction?

/// App thực thi nút thẻ đã bấm (điều hướng, mở màn…). Presenter chỉ giao hành động SAU khi sheet đóng hẳn.
typealias WhatsNewRunner = @MainActor (WhatsNewResolvedAction) -> Void

/// Một thẻ What's New. Có closure nên không Equatable — so theo `id`.
struct WhatsNewCard: Identifiable {
    /// Ổn định, snake_case — đi thẳng vào param telemetry.
    let id: String
    let version: CardVersion
    /// Cao hơn = đứng trước; hoà ⇒ bản mới hơn trước, rồi `id` tăng dần.
    let priority: Int
    let systemImage: String
    /// Người gọi truyền `String(localized:)`.
    let title: String
    /// Người gọi truyền `String(localized:)`, ≤ 90 ký tự.
    let body: String
    /// Nhãn nút hành động trên thẻ. Người gọi truyền `String(localized:)`, ≤ 3 từ. Thẻ không có `action` không vẽ nút.
    let ctaTitle: String
    /// `nil` ⇒ thẻ thông tin, không có nút (và không bị luật "bỏ thẻ không có đích" loại).
    let action: WhatsNewAction?
    /// Event nào chứng tỏ khách đã dùng tính năng. Thuần, chạy trên queue của người gọi `Track.log`.
    let usedWhen: (AppEvent) -> Bool
    /// Seed một lần từ dấu vết có sẵn trên máy. Thuần, chạy ở queue nền (seed của presenter).
    let usedOnDisk: (UsageProbe) -> Bool

    init(id: String, version: CardVersion, priority: Int, systemImage: String, title: String, body: String,
         ctaTitle: String, action: WhatsNewAction?,
         usedWhen: @escaping (AppEvent) -> Bool = { _ in false },
         usedOnDisk: @escaping (UsageProbe) -> Bool = { _ in false }) {
        self.id = id
        self.version = version
        self.priority = priority
        self.systemImage = systemImage
        self.title = title
        self.body = body
        self.ctaTitle = ctaTitle
        self.action = action
        self.usedWhen = usedWhen
        self.usedOnDisk = usedOnDisk
    }
}

extension WhatsNewCard {
    /// Thứ tự hiển thị dùng chung cho sheet (selector) và danh sách: ưu tiên ↓, bản ↓, id ↑.
    static func displayOrder(current: AppVersion) -> (WhatsNewCard, WhatsNewCard) -> Bool {
        { a, b in
            if a.priority != b.priority { return a.priority > b.priority }
            let va = a.version.effective(current: current), vb = b.version.effective(current: current)
            if va != vb { return va > vb }
            return a.id < b.id
        }
    }

    /// Đích của nút thẻ theo resolver của app; thẻ không có action ⇒ `nil` (resolver không bị hỏi).
    func resolvedAction(_ resolve: WhatsNewResolver) -> WhatsNewResolvedAction? {
        action.flatMap(resolve)
    }
}
