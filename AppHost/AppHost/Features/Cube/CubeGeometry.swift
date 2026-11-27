import Foundation

/// Hình học ô của khối N×N (N = 2, 3): vị trí + pháp tuyến của mỗi ô theo toạ độ nhân đôi (chỉ số i ↦ 2i − (N−1)),
/// x sang phải (R), y lên (U), z về phía người nhìn (F). Bảng đặt ô: plan "Toạ độ khối".
///
/// `permutation(m)`: `new[i] = old[perm[i]]` — tính sẵn cho 27 bước khi dựng, cache theo N.
struct CubeGeometry {
    let n: Int
    /// Vị trí (toạ độ nhân đôi) của ô thứ i theo thứ tự Kociemba.
    let positions: [SIMD3<Int>]
    /// Pháp tuyến đơn vị của ô thứ i (mặt chứa ô).
    let normals: [SIMD3<Int>]
    /// Hoán vị theo `CubeMove.tableIndex` (0…26) — mảng thay vì dictionary: `applying` chạy rất nhiều lần ở -O0.
    private let perms: [[Int]]

    private static let two = CubeGeometry(n: 2)
    private static let three = CubeGeometry(n: 3)

    static func of(n: Int) -> CubeGeometry {
        switch n {
        case 2: return two
        case 3: return three
        default: preconditionFailure("chỉ hỗ trợ 2×2 và 3×3")
        }
    }

    func permutation(_ m: CubeMove) -> [Int] { perms[m.tableIndex] }

    /// Toạ độ nhân đôi của chỉ số hàng/cột i.
    static func doubled(_ i: Int, n: Int) -> Int { 2 * i - (n - 1) }

    /// Vị trí + pháp tuyến của ô (mặt, hàng, cột).
    static func sticker(_ face: CubeFace, _ r: Int, _ c: Int, n: Int) -> (position: SIMD3<Int>, normal: SIMD3<Int>) {
        let d = n - 1, rr = doubled(r, n: n), cc = doubled(c, n: n)
        switch face {
        case .u: return (SIMD3(cc, d, rr), SIMD3(0, 1, 0))
        case .r: return (SIMD3(d, -rr, -cc), SIMD3(1, 0, 0))
        case .f: return (SIMD3(cc, -rr, d), SIMD3(0, 0, 1))
        case .d: return (SIMD3(cc, -d, -rr), SIMD3(0, -1, 0))
        case .l: return (SIMD3(-d, -rr, cc), SIMD3(-1, 0, 0))
        case .b: return (SIMD3(-cc, -rr, -d), SIMD3(0, 0, -1))
        }
    }

    /// Trục (0 = x, 1 = y, 2 = z), chiều quay một nấc (−1 = −90°, +1 = +90° theo quy tắc bàn tay phải) và lớp
    /// (dấu toạ độ trên trục: +1, −1; 0 = mọi lớp) của bước.
    static func axisSpec(_ axis: CubeMove.Axis) -> (axis: Int, sign: Int, layer: Int) {
        switch axis {
        case .face(.r): return (0, -1, 1)
        case .face(.l): return (0, 1, -1)
        case .face(.u): return (1, -1, 1)
        case .face(.d): return (1, 1, -1)
        case .face(.f): return (2, -1, 1)
        case .face(.b): return (2, 1, -1)
        case .x: return (0, -1, 0)
        case .y: return (1, -1, 0)
        case .z: return (2, -1, 0)
        }
    }

    /// Quay một vector 90° quanh trục `axis` theo chiều `sign`.
    static func rotate(_ v: SIMD3<Int>, axis: Int, sign: Int) -> SIMD3<Int> {
        switch (axis, sign) {
        case (0, 1): return SIMD3(v.x, -v.z, v.y)
        case (0, _): return SIMD3(v.x, v.z, -v.y)
        case (1, 1): return SIMD3(v.z, v.y, -v.x)
        case (1, _): return SIMD3(-v.z, v.y, v.x)
        case (2, 1): return SIMD3(-v.y, v.x, v.z)
        default: return SIMD3(v.y, -v.x, v.z)
        }
    }

    /// Ô có nằm trong lớp mà bước quay không.
    static func inLayer(_ p: SIMD3<Int>, axis: Int, layer: Int) -> Bool {
        layer == 0 || p[axis] * layer > 0
    }

    private init(n: Int) {
        precondition(n == 2 || n == 3, "chỉ hỗ trợ 2×2 và 3×3")
        self.n = n
        var pos: [SIMD3<Int>] = [], nor: [SIMD3<Int>] = []
        for face in CubeFace.allCases {
            for r in 0..<n {
                for c in 0..<n {
                    let s = Self.sticker(face, r, c, n: n)
                    pos.append(s.position)
                    nor.append(s.normal)
                }
            }
        }
        positions = pos
        normals = nor
        struct Key: Hashable { let p: SIMD3<Int>; let q: SIMD3<Int> }
        var index: [Key: Int] = [:]
        for i in pos.indices { index[Key(p: pos[i], q: nor[i])] = i }

        var perms = [[Int]](repeating: [], count: 27)
        for m in CubeMove.faceMoves + CubeMove.rotations {
            let spec = Self.axisSpec(m.axis)
            var perm = Array(pos.indices)
            for j in pos.indices where Self.inLayer(pos[j], axis: spec.axis, layer: spec.layer) {
                var p = pos[j], q = nor[j]
                for _ in 0..<m.turns {
                    p = Self.rotate(p, axis: spec.axis, sign: spec.sign)
                    q = Self.rotate(q, axis: spec.axis, sign: spec.sign)
                }
                perm[index[Key(p: p, q: q)]!] = j
            }
            perms[m.tableIndex] = perm
        }
        self.perms = perms
    }
}
