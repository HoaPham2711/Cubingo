import Foundation

/// Khối người dùng chọn ở màn đầu. Đợt A chỉ có 3×3; các khối khác hiện mờ "SOON".
enum FlowPuzzle: String, CaseIterable {
    case cube3, cube2, pyramid, cube4

    var isAvailable: Bool { self == .cube3 }

    var title: String {
        switch self {
        case .cube3: return String(localized: "3×3")
        case .cube2: return String(localized: "2×2")
        case .pyramid: return String(localized: "Pyramid")
        case .cube4: return String(localized: "4×4")
        }
    }

    var subtitle: String {
        switch self {
        case .cube3: return String(localized: "The classic")
        case .cube2: return String(localized: "Pocket cube")
        case .pyramid: return String(localized: "Four sides")
        case .cube4: return String(localized: "Big cube")
        }
    }

    /// Số ô trên một cạnh của biểu tượng lưới.
    var gridSize: Int {
        switch self {
        case .cube3, .pyramid: return 3
        case .cube2: return 2
        case .cube4: return 4
        }
    }
}

/// Chế độ chỉ bước — Task 14 chuyển về `Features/Guide/`.
enum GuideMode: Hashable { case teach, quick }

/// Các màn của luồng một chiều, đẩy trên `NavigationStack` gốc (màn chọn khối).
enum FlowRoute: Hashable {
    case scan
    case review(manual: Bool)
    case mode
    case guide(GuideMode)
    case done
}
