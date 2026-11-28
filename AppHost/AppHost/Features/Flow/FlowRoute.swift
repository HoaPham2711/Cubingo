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

/// Các màn của luồng một chiều, đẩy trên `NavigationStack` gốc (màn chọn khối).
enum FlowRoute: Hashable {
    case scan
    case review(manual: Bool)
    case mode
    case guide(GuideMode)
    case done
    /// Quét kiểm tra một mặt sau một chặng của Teach me.
    case check

    /// Màn có `RealityView`. Bất biến: mỗi chồng điều hướng chỉ có một màn như vậy (`RealityView` thứ hai bị che làm
    /// màn trên cùng không vẽ).
    var hasRealityView: Bool {
        switch self {
        case .scan, .guide: return true
        default: return false
        }
    }
}
