import Foundation

/// Ngôn ngữ hiển thị của app, ĐỘC LẬP với ngôn ngữ hệ thống. `code == nil` = theo locale máy.
///
/// Danh sách ngôn ngữ lấy từ `Bundle.main.localizations` (các thư mục `.lproj` thật sự có trong app) — thêm bản dịch
/// vào String Catalog là Picker tự có thêm dòng, KHÔNG phải sửa file này (nên `Core/` giống hệt ở mọi app).
struct AppLanguage: Hashable, Identifiable {
    /// Mã ngôn ngữ (`"en"`, `"vi"`, `"zh-Hans"`…); `nil` = theo hệ thống.
    let code: String?

    var id: String { code ?? "system" }

    static let system = AppLanguage(code: nil)

    static let defaultsKey = "appLanguageOverride"

    /// `.system` + mỗi mã bản địa hoá một lần (bỏ `Base`), sắp theo tên hiển thị.
    static func available(localizations: [String] = Bundle.main.localizations) -> [AppLanguage] {
        var seen = Set<String>()
        let real = localizations
            .filter { $0 != "Base" && seen.insert($0).inserted }
            .map { AppLanguage(code: $0) }
            .sorted { $0.title.localizedCaseInsensitiveCompare($1.title) == .orderedAscending }
        return [.system] + real
    }

    /// Settings chỉ hiện Picker khi có ÍT NHẤT hai ngôn ngữ thật — với một ngôn ngữ (tiếng Anh nguồn) lựa chọn vô nghĩa.
    static func isPickerVisible(localizations: [String] = Bundle.main.localizations) -> Bool {
        available(localizations: localizations).count > 2
    }

    /// `.system`: chuỗi localize; còn lại: tên tự gọi của ngôn ngữ (vd "Tiếng Việt"), không có thì chính mã.
    var title: String {
        guard let code else { return String(localized: "System") }
        let locale = Locale(identifier: code)
        return locale.localizedString(forIdentifier: code) ?? code
    }

    /// Đọc lựa chọn đã lưu — key chưa từng ghi, giá trị rác, hoặc mã bundle không còn đều coi là `.system`.
    static func load(from d: UserDefaults = .standard,
                     localizations: [String] = Bundle.main.localizations) -> AppLanguage {
        guard let stored = d.string(forKey: defaultsKey),
              let match = available(localizations: localizations).first(where: { $0.code == stored })
        else { return .system }
        return match
    }

    /// Ghi lựa chọn + set/xoá override `AppleLanguages` — có hiệu lực từ lần khởi động SAU (không đổi ngôn ngữ ngay
    /// trong phiên đang chạy), UI gọi nơi này phải báo user khởi động lại app.
    func apply(to d: UserDefaults = .standard) {
        d.set(code ?? "system", forKey: Self.defaultsKey)
        if let code {
            d.set([code], forKey: "AppleLanguages")
        } else {
            d.removeObject(forKey: "AppleLanguages")
        }
    }
}
