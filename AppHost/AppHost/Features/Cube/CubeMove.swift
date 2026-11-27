import Foundation

/// Một bước: xoay một mặt hoặc cả khối (x/y/z), `turns` ∈ {1, 2, 3} = xuôi, kép, ngược chiều kim đồng hồ (nhìn từ
/// phía mặt đó; x như R, y như U, z như F).
struct CubeMove: Hashable {
    enum Axis: Hashable {
        case face(CubeFace)
        case x, y, z
    }

    let axis: Axis
    let turns: Int

    init(_ axis: Axis, _ turns: Int = 1) {
        precondition((1...3).contains(turns), "turns phải là 1, 2 hoặc 3")
        self.axis = axis
        self.turns = turns
    }

    var inverse: CubeMove { CubeMove(axis, 4 - turns) }

    var isRotation: Bool {
        if case .face = axis { return false }
        return true
    }

    /// Mặt của bước (nil với bước xoay cả khối).
    var face: CubeFace? {
        if case .face(let f) = axis { return f }
        return nil
    }

    var notation: String {
        let base: String
        switch axis {
        case .face(let f): base = String(f.letter)
        case .x: base = "x"
        case .y: base = "y"
        case .z: base = "z"
        }
        switch turns {
        case 2: return base + "2"
        case 3: return base + "'"
        default: return base
        }
    }

    /// Tách theo khoảng trắng; một ký hiệu lạ ⇒ `nil`. Chuỗi rỗng ⇒ `[]`.
    static func parse(_ s: String) -> [CubeMove]? {
        var out: [CubeMove] = []
        for token in s.split(whereSeparator: \.isWhitespace) {
            guard let m = parseOne(Substring(token)) else { return nil }
            out.append(m)
        }
        return out
    }

    private static func parseOne(_ t: Substring) -> CubeMove? {
        guard let first = t.first, t.count <= 2 else { return nil }
        let axis: Axis
        switch first {
        case "x": axis = .x
        case "y": axis = .y
        case "z": axis = .z
        default:
            guard let f = CubeFace(letter: first) else { return nil }
            axis = .face(f)
        }
        switch t.dropFirst() {
        case "": return CubeMove(axis, 1)
        case "2": return CubeMove(axis, 2)
        case "'": return CubeMove(axis, 3)
        default: return nil
        }
    }

    /// Chỉ số trong `faceMoves + rotations` (0…26).
    var tableIndex: Int {
        switch axis {
        case .face(let f): return f.rawValue * 3 + turns - 1
        case .x: return 18 + turns - 1
        case .y: return 21 + turns - 1
        case .z: return 24 + turns - 1
        }
    }

    /// 18 bước mặt theo thứ tự Kociemba: U U2 U' R R2 R' F … B'.
    static let faceMoves: [CubeMove] = CubeFace.allCases.flatMap { f in (1...3).map { CubeMove(.face(f), $0) } }
    /// 9 bước xoay cả khối: x x2 x' y … z'.
    static let rotations: [CubeMove] = [Axis.x, .y, .z].flatMap { a in (1...3).map { CubeMove(a, $0) } }
}
