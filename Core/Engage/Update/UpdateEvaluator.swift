import Foundation

/// Bản đang có trên App Store (trích từ Lookup API).
struct StoreRelease: Codable, Equatable {
    let version: String
    let minimumOsVersion: String
    let url: URL
    /// "What's New" của bản trên Store (Lookup API `releaseNotes`). Optional + `var` ⇒ JSON đã lưu
    /// bởi bản app cũ (không có field) vẫn decode; theo ngôn ngữ storefront của region máy, có thể
    /// lệch ngôn ngữ UI — là dữ liệu, không localize.
    var releaseNotes: String?
}

/// Chưa có `.required` (force update): khi có
/// nguồn cấu hình, thêm case ở đây và `evaluate` là chỗ duy nhất phải đổi logic.
enum UpdateStatus: Equatable {
    case upToDate
    case available(version: String, url: URL, notes: String?)
}

enum UpdateEvaluator {
    /// Nhắc khi Store có bản MỚI HƠN bản đang cài VÀ máy lên được iOS tối thiểu của bản đó.
    /// Mọi chuỗi version parse không được → `.upToDate` (thà không nhắc còn hơn nhắc sai).
    static func evaluate(installed: String, osVersion: String, release: StoreRelease?) -> UpdateStatus {
        guard let release,
              let store = AppVersion(release.version),
              let current = AppVersion(installed),
              let minOS = AppVersion(release.minimumOsVersion),
              let os = AppVersion(osVersion),
              store > current, minOS <= os
        else { return .upToDate }
        return .available(version: release.version, url: release.url, notes: release.releaseNotes)
    }

    /// Banner Home ẩn sau khi user bấm × cho version đó; hiện lại khi Store có bản mới hơn nữa.
    /// Hàng trong Settings KHÔNG dùng hàm này — nó hiện mọi lúc `.available`.
    static func shouldShowBanner(status: UpdateStatus, dismissedVersion: String?) -> Bool {
        guard case .available(let version, _, _) = status else { return false }
        guard let dismissedVersion, let dismissed = AppVersion(dismissedVersion),
              let available = AppVersion(version)
        else { return true }
        return available > dismissed
    }

    /// Log `update_prompt` "shown" một lần cho mỗi phiên bản được mời trong vòng đời màn chứa banner Home: `onAppear`
    /// bắn lại mỗi lần đổi tab / quay lại — đếm hết là phồng số hiển thị, lệch tỉ lệ mở Store. `update_prompt` chỉ
    /// được log từ banner Home (hàng Update trong Settings không log).
    static func shouldLogUpdateShown(loggedVersion: String?, offeredVersion: String?) -> Bool {
        guard let offeredVersion else { return false }
        return offeredVersion != loggedVersion
    }

    /// Dòng phụ của banner: dòng ĐẦU KHÔNG RỖNG của release notes (bỏ dòng trắng/toàn khoảng trắng
    /// ở đầu, cắt ký tự vô hình hai đầu — `trimInvisible`). `nil` ⇒ banner dùng câu chung "Version … is on the App Store."
    static func bannerHeadline(notes: String?) -> String? {
        // `isNewline` gồm cả CRLF (một Character) và U+2028 — notes dán từ nhiều nguồn.
        notes?.split(whereSeparator: \.isNewline)
            .lazy
            .map(trimInvisible)
            .first { !$0.isEmpty }
    }

    /// Cắt ký tự VÔ HÌNH ở hai đầu dòng, theo Character (cụm grapheme) — không theo scalar: cờ vùng (tag
    /// U+E0020…E007F là Cf), ❤️ (VS16), gia đình (ZWJ) mang scalar vô hình BÊN TRONG cụm, cắt theo scalar là xén đuôi
    /// emoji. Character vô hình = MỌI scalar là khoảng trắng, Default_Ignorable (BOM, U+200B…D, U+2060, U+3164, U+115F,
    /// CGJ, VS lẻ) hoặc Cc/Cf. Notes dán từ Word/Notes hay mang chúng ⇒ dòng chỉ có chúng thành headline trông rỗng.
    private static func trimInvisible(_ line: Substring) -> String {
        var t = line
        while let c = t.first, isInvisible(c) { t.removeFirst() }
        while let c = t.last, isInvisible(c) { t.removeLast() }
        return String(t)
    }

    private static func isInvisible(_ c: Character) -> Bool {
        c.unicodeScalars.allSatisfy { s in
            let p = s.properties
            return p.isWhitespace || p.isDefaultIgnorableCodePoint
                || p.generalCategory == .control || p.generalCategory == .format
        }
    }
}
