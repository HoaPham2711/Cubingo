import Foundation

/// Tốc độ hoạt ảnh xoay lớp của khối 3D (Settings + nút chuyển ở màn chỉ bước).
enum PrefsSpeed: String, CaseIterable {
    case slow, medium, fast

    /// Thời lượng một bước xoay 90° (bước kép ×1,5 — `Cube3DView`).
    var quarterTurnSeconds: Double {
        switch self {
        case .slow: return 1.4
        case .medium: return 0.9
        case .fast: return 0.5
        }
    }

    /// Dừng trước khi quay (khối đứng yên, mũi tên hiện) để mắt kịp bắt lớp sắp quay.
    var leadInSeconds: Double { quarterTurnSeconds * 0.5 }

    var label: String {
        switch self {
        case .slow: return String(localized: "Slow")
        case .medium: return String(localized: "Medium")
        case .fast: return String(localized: "Fast")
        }
    }
}

/// Cài đặt của app — dựng MỘT lần ở `AppHostApp`, truyền qua `FlowDependencies`. Ghi ngay mỗi lần đổi.
@MainActor
final class PrefsStore: ObservableObject {
    static let speedKey = "prefs.speed"
    static let hapticsKey = "prefs.haptics"
    static let notationKey = "prefs.notation"

    private let defaults: UserDefaults

    @Published var speed: PrefsSpeed { didSet { defaults.set(speed.rawValue, forKey: Self.speedKey) } }
    @Published var haptics: Bool { didSet { defaults.set(haptics, forKey: Self.hapticsKey) } }
    @Published var showNotation: Bool { didSet { defaults.set(showNotation, forKey: Self.notationKey) } }

    init(defaults: UserDefaults) {
        self.defaults = defaults
        speed = defaults.string(forKey: Self.speedKey).flatMap(PrefsSpeed.init(rawValue:)) ?? .medium
        haptics = defaults.object(forKey: Self.hapticsKey) as? Bool ?? true
        showNotation = defaults.object(forKey: Self.notationKey) as? Bool ?? true
    }
}
