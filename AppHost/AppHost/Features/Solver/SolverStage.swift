import Foundation

/// Bảy chặng của Teach me (3×3), theo thứ tự.
enum SolverStageKind: Int, CaseIterable {
    case cross = 1, corners, middle, topCross, topFace, topCorners, topEdges
}

/// Lý do của một nhóm bước (hiện dưới câu hướng dẫn). Màu `edge` là màu BÊN của cạnh (không phải màu nền).
enum SolverReason: Equatable {
    case hold(top: CubeColor, front: CubeColor)
    case makeDaisy(edge: CubeColor)
    case dropToCross(edge: CubeColor)
    case liftCorner
    case placeCorner(CubeColor, CubeColor)
    case insertEdge(CubeColor, CubeColor, toRight: Bool)
    case popEdge
    case makeTopCross
    case orientTopCorners
    case placeTopCorners
    case placeTopEdges
    case alignTop
}

/// Một bước chỉ cho người dùng. `reason` chỉ ở bước đầu một nhóm; mọi bước xoay cả khối mang `.hold` của hướng cầm
/// SAU bước đó. `algorithm` đánh dấu mọi bước thuộc một công thức có tên.
struct SolverStep: Equatable {
    let move: CubeMove
    let reason: SolverReason?
    let algorithm: SolverAlgorithm?
}

struct SolverStage: Equatable {
    let kind: SolverStageKind
    let steps: [SolverStep]
    let start: CubeFacelets

    var end: CubeFacelets { start.applying(steps.map(\.move)) }
}

/// Dựng các bước của một chặng trên trạng thái đang đi (dùng chung cho mọi chặng của Teach me).
struct SolverStageBuilder {
    let kind: SolverStageKind
    let start: CubeFacelets
    private(set) var state: CubeFacelets
    private(set) var steps: [SolverStep] = []

    init(kind: SolverStageKind, start: CubeFacelets) {
        self.kind = kind
        self.start = start
        state = start
    }

    var stage: SolverStage { SolverStage(kind: kind, steps: steps, start: start) }

    /// Một nhóm bước: `reason` gắn vào bước mặt đầu tiên; bước xoay cả khối luôn mang `.hold` của hướng sau nó.
    mutating func group(_ moves: [CubeMove], reason: SolverReason?, algorithm: SolverAlgorithm? = nil) {
        var pending = reason
        for m in moves {
            state = state.applying(m)
            if m.isRotation {
                let h = SolverHold.hold(of: state)
                steps.append(SolverStep(move: m, reason: .hold(top: h.top, front: h.front), algorithm: nil))
            } else {
                steps.append(SolverStep(move: m, reason: pending, algorithm: algorithm))
                pending = nil
            }
        }
    }

    /// Nhóm "bước chuẩn bị (U…) + công thức": lý do ở bước đầu của cả nhóm.
    mutating func algorithm(_ a: SolverAlgorithm, setup: [CubeMove] = [], reason: SolverReason?) {
        group(setup, reason: reason)
        group(a.moves, reason: setup.isEmpty ? reason : nil, algorithm: a)
    }

    /// Xoay cả khối để `top` lên trên (giữ mặt trước nếu được).
    mutating func hold(top: CubeColor) {
        group(SolverHold.rotations(from: state, top: top, preferFront: state.center(.f)), reason: nil)
    }

    /// Số nấc k (thứ tự ưu tiên 0, 1, 3, 2) sao cho áp `axis`^k thì `predicate` đúng.
    func firstTurns(_ axis: CubeMove.Axis, _ predicate: (CubeFacelets) -> Bool) -> Int? {
        for k in [0, 1, 3, 2] {
            let g = k == 0 ? state : state.applying(CubeMove(axis, k))
            if predicate(g) { return k }
        }
        return nil
    }

    static func turns(_ axis: CubeMove.Axis, _ k: Int) -> [CubeMove] {
        k % 4 == 0 ? [] : [CubeMove(axis, k % 4)]
    }
}

/// Tra cứu miếng trên facelet theo vị trí chuẩn Kociemba (dùng chung cho các chặng).
enum SolverPieces {
    static let corners = CubeCubies.cornerFacelet
    static let edges = CubeCubies.edgeFacelet

    /// Màu đối diện `c` (theo tâm).
    static func opposite(of c: CubeColor, in f: CubeFacelets) -> CubeColor {
        let face = CubeFace.allCases.first { f.center($0) == c }!
        return f.center(face.opposite)
    }

    static func colors(_ f: CubeFacelets, _ idx: [Int]) -> [CubeColor] { idx.map { f.stickers[$0] } }

    /// Vị trí góc (0…7) mang đúng bộ màu.
    static func cornerPosition(_ f: CubeFacelets, colors want: Set<CubeColor>) -> Int? {
        corners.indices.first { Set(colors(f, corners[$0])) == want }
    }

    /// Vị trí cạnh (0…11) mang đúng bộ màu.
    static func edgePosition(_ f: CubeFacelets, colors want: Set<CubeColor>) -> Int? {
        edges.indices.first { Set(colors(f, edges[$0])) == want }
    }

    /// Mặt của một chỉ số facelet.
    static func face(ofSticker i: Int) -> CubeFace { CubeFace(rawValue: i / 9)! }
}
