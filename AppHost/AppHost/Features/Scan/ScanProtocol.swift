import Foundation

/// Lời dặn của một bước quét.
enum ScanInstruction: Equatable {
    case start, turnLeft, backToFirst, tiltTopToYou, tiltBottomToYou
}

/// Một bước quét: mặt nó chụp (`nil` = chỉ kiểm tâm đã về mặt đầu).
struct ScanStep: Equatable {
    let instruction: ScanInstruction
    let face: CubeFace?
}

/// Giao thức quét 3×3: F, (xoay trái) R, B, L, quay về mặt đầu, nghiêng mặt trên về phía mình (U), nghiêng ngược lại
/// (D). Với cách cầm này, ảnh mỗi mặt đã đúng thứ tự đọc Kociemba (bảng "Toạ độ khối") — ghép với xoay 0.
enum ScanProtocol {
    static let cube3: [ScanStep] = [
        ScanStep(instruction: .start, face: .f),
        ScanStep(instruction: .turnLeft, face: .r),
        ScanStep(instruction: .turnLeft, face: .b),
        ScanStep(instruction: .turnLeft, face: .l),
        ScanStep(instruction: .backToFirst, face: nil),
        ScanStep(instruction: .tiltTopToYou, face: .u),
        ScanStep(instruction: .tiltBottomToYou, face: .d),
    ]

    /// 54 mẫu theo thứ tự Kociemba (U R F D L B).
    static func assemble(_ grids: [CubeFace: [CubeRGB]]) -> [CubeRGB] {
        CubeFace.allCases.flatMap { grids[$0] ?? [] }
    }
}
