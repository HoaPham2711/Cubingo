import Foundation

/// Kết quả kiểm tra khối ở màn review.
enum ScanReviewOutcome: Equatable {
    case ok(CubeFacelets)
    /// Đi từ quét, đếm màu đúng mà còn lỗi, và đúng MỘT cách xoay lại mặt U/D làm khối hợp lệ ⇒ tự sửa, không hỏi.
    case autoFixed(CubeFacelets)
    case issue(CubeIssue)
    case incomplete(missing: Int)
    case ambiguousCenters
}

/// Trạng thái màn kiểm tra màu / nhập tay (spec 5.4).
@MainActor
final class ScanReviewModel: ObservableObject {
    @Published private(set) var facelets: [CubeColor?]
    @Published private(set) var palette: CubePalette
    @Published private(set) var issue: CubeIssue?
    @Published private(set) var suspects: Set<Int> = []
    let isManual: Bool
    /// Mốc cân trắng của lần quét (nhập tay ⇒ `nil`).
    let whiteReference: CubeRGB?
    private var confidence: [Double]?
    /// Hai tâm quá giống nhau — chặn cho tới khi người dùng chạm sửa một ô của hai mặt đó.
    private var pendingAmbiguous: (CubeFace, CubeFace)?

    static let defaultManualCenters: [CubeFace: CubeColorName] = [
        .u: .white, .r: .red, .f: .green, .d: .yellow, .l: .orange, .b: .blue,
    ]

    init(scan: ScanResult) {
        facelets = scan.facelets.stickers.map { Optional($0) }
        palette = scan.palette
        confidence = scan.confidence
        isManual = false
        whiteReference = scan.whiteReference
        if let (a, b) = scan.ambiguousCenters {
            pendingAmbiguous = (CubeFace(rawValue: Int(a.raw))!, CubeFace(rawValue: Int(b.raw))!)
        }
    }

    /// Nhập tay: tâm tô sẵn theo `centers`, 48 ô còn trống.
    init(manualCenters: [CubeFace: CubeColorName]) {
        var f = [CubeColor?](repeating: nil, count: 54)
        var colors: [CubeColor: CubeRGB] = [:]
        for face in CubeFace.allCases {
            f[face.rawValue * 9 + 4] = CubeColor(face)
            colors[CubeColor(face)] = (manualCenters[face] ?? .white).standardRGB
        }
        facelets = f
        palette = CubePalette(colors: colors)
        isManual = true
        whiteReference = nil
    }

    static func isCenter(_ i: Int) -> Bool { i % 9 == 4 }

    /// Đặt màu một ô (tâm không đổi được ở đây — `setCenter`).
    func set(_ index: Int, to c: CubeColor) {
        guard !Self.isCenter(index) else { return }
        facelets[index] = c
        confidence?[index] = 100
        if let (a, b) = pendingAmbiguous, [a.rawValue, b.rawValue].contains(index / 9) { pendingAmbiguous = nil }
        suspects.remove(index)
    }

    /// Nhập tay: đổi màu tâm sang tên khác (không đen, không trùng tâm khác).
    func setCenter(_ face: CubeFace, to name: CubeColorName) {
        guard isManual, name != .black else { return }
        let others = CubeFace.allCases.filter { $0 != face }.map { palette.colorName(CubeColor($0)) }
        guard !others.contains(name) else { return }
        var colors = palette.colors
        colors[CubeColor(face)] = name.standardRGB
        palette = CubePalette(colors: colors)
    }

    /// Tên các màu còn chọn được cho tâm của `face` (nhập tay).
    func centerChoices(for face: CubeFace) -> [CubeColorName] {
        let others = CubeFace.allCases.filter { $0 != face }.map { palette.colorName(CubeColor($0)) }
        return CubeColorName.allCases.filter { $0 != .black && !others.contains($0) }
    }

    @discardableResult
    func validate() -> ScanReviewOutcome {
        let missing = facelets.filter { $0 == nil }.count
        if missing > 0 {
            issue = nil
            suspects = []
            return .incomplete(missing: missing)
        }
        if pendingAmbiguous != nil {
            issue = nil
            suspects = []
            return .ambiguousCenters
        }
        let f = CubeFacelets(n: 3, stickers: facelets.map { $0! })
        guard let found = CubeValidation.firstIssue(f, confidence: confidence) else {
            issue = nil
            suspects = []
            return .ok(f)
        }
        if !isManual, !Self.isColorCount(found), let fixed = CubeValidation.repairScanOrientation(f) {
            facelets = fixed.stickers.map { Optional($0) }
            issue = nil
            suspects = []
            return .autoFixed(fixed)
        }
        issue = found
        switch found {
        case let .colorCount(_, _, _, _, s): suspects = Set(s)
        case let .impossiblePiece(stickers): suspects = Set(stickers)
        case .twistedCorner, .flippedEdge, .swappedPieces: suspects = []
        }
        return .issue(found)
    }

    private static func isColorCount(_ i: CubeIssue) -> Bool {
        if case .colorCount = i { return true }
        return false
    }
}

/// Chữ thông báo của màn kiểm tra (chép đúng spec 5.4).
enum ScanReviewText {
    static func message(_ o: ScanReviewOutcome, palette: CubePalette) -> String {
        switch o {
        case .ok, .autoFixed:
            return String(localized: "Looks right — let's go!")
        case .incomplete(let missing):
            return String(localized: "\(missing) squares left to fill.")
        case .ambiguousCenters:
            return String(localized: "Two centers look the same color. Tap the squares to fix them.")
        case .issue(let i):
            switch i {
            case let .colorCount(over, under, overCount, underCount, _):
                let overName = palette.name(over), underName = palette.name(under)
                return String(localized:
                    "You have \(overCount) \(overName) and \(underCount) \(underName). One square is probably wrong.")
            case .impossiblePiece:
                return String(localized: "These squares can't be on the same piece. Check their colors.")
            case .twistedCorner:
                return String(localized:
                    "One corner is twisted — this happens when a cube was taken apart and put back. Twist that corner to fix it.")
            case .flippedEdge:
                return String(localized:
                    "One edge is flipped — this happens when a cube was taken apart and put back. Flip that edge to fix it.")
            case .swappedPieces:
                return String(localized: "Two pieces are swapped — this happens when a cube was taken apart and put back.")
            }
        }
    }
}
