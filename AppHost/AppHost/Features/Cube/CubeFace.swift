import Foundation

/// Sáu mặt theo thứ tự chuẩn Kociemba (U R F D L B). Chỉ `import Foundation`: tool `tools/app/kociemba/` biên dịch
/// lại file này bằng `swiftc`.
enum CubeFace: Int, CaseIterable {
    case u, r, f, d, l, b

    var opposite: CubeFace {
        switch self {
        case .u: return .d
        case .d: return .u
        case .r: return .l
        case .l: return .r
        case .f: return .b
        case .b: return .f
        }
    }

    var letter: Character {
        switch self {
        case .u: return "U"
        case .r: return "R"
        case .f: return "F"
        case .d: return "D"
        case .l: return "L"
        case .b: return "B"
        }
    }

    init?(letter: Character) {
        guard let f = CubeFace.allCases.first(where: { $0.letter == letter }) else { return nil }
        self = f
    }
}

/// Nhãn nhóm màu 0…5 — KHÔNG phải màu chuẩn: tên/RGB thật nằm ở `CubePalette` (bảng màu tự nhận diện).
struct CubeColor: Hashable {
    let raw: UInt8

    init(raw: UInt8) { self.raw = raw }
    init(_ face: CubeFace) { raw = UInt8(face.rawValue) }

    static let all: [CubeColor] = (0..<6).map { CubeColor(raw: UInt8($0)) }
}
