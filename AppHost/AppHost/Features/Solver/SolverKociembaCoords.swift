import Foundation

/// Toạ độ của thuật toán hai pha (mô tả công khai của Kociemba; tự viết, không chép mã copyleft) + dựng bảng.
/// Chỉ `import Foundation`: tool `tools/app/kociemba/` biên dịch file này cùng `CubeCubies.swift` bằng `swiftc -O`.
///
/// - `twist` 0…2186: định hướng 7 góc đầu (cơ số 3).
/// - `flip` 0…2047: định hướng 11 cạnh đầu (cơ số 2).
/// - `sliceSorted` 0…11879 = 24 × (vị trí 4 cạnh tầng giữa FR FL BL BR, tổ hợp 0…494) + (thứ tự của chúng, 0…23).
///   Pha 1 dùng `sliceSorted / 24` (0 ⇔ bốn cạnh nằm ở tầng giữa); pha 2 dùng `sliceSorted % 24`.
/// - `corners` 0…40319: hoán vị 8 góc. `udEdges` 0…40319: hoán vị 8 cạnh U/D — chỉ xác định dưới nhóm pha 2.
enum SolverKociembaCoords {
    /// 10 bước của pha 2 (chỉ số trong `CubeMove.faceMoves`): U U2 U' D D2 D' R2 L2 F2 B2.
    static let phase2Moves: [Int] = [0, 1, 2, 9, 10, 11, 4, 13, 7, 16]

    static let twistCount = 2187, flipCount = 2048, sliceSortedCount = 11880, sliceCount = 495
    static let cornersCount = 40320, udEdgesCount = 40320, slicePhase2Count = 24

    // MARK: - Đọc toạ độ

    static func twist(_ c: CubeCubies) -> Int { (0..<7).reduce(0) { 3 * $0 + c.co[$1] } }
    static func flip(_ c: CubeCubies) -> Int { (0..<11).reduce(0) { 2 * $0 + c.eo[$1] } }

    static func sliceSorted(_ c: CubeCubies) -> Int {
        var a = 0, x = 0
        var edge4 = [Int](repeating: 0, count: 4)
        for j in stride(from: 11, through: 0, by: -1) where c.ep[j] >= 8 {
            a += binomial(11 - j, x + 1)
            edge4[3 - x] = c.ep[j]
            x += 1
        }
        var b = 0
        for j in stride(from: 3, through: 1, by: -1) {
            var k = 0
            while edge4[j] != j + 8 {
                rotateLeft(&edge4, 0, j)
                k += 1
            }
            b = (j + 1) * b + k
        }
        return 24 * a + b
    }

    static func corners(_ c: CubeCubies) -> Int { permutationIndex(c.cp) }
    static func udEdges(_ c: CubeCubies) -> Int { permutationIndex(Array(c.ep[0..<8])) }

    // MARK: - Dựng khối đại diện của một toạ độ (các phần khác = đã giải)

    static func cube(twist t: Int) -> CubeCubies {
        var c = CubeCubies.solved, t = t, s = 0
        for i in stride(from: 6, through: 0, by: -1) {
            c.co[i] = t % 3
            s += c.co[i]
            t /= 3
        }
        c.co[7] = (3 - s % 3) % 3
        return c
    }

    static func cube(flip f: Int) -> CubeCubies {
        var c = CubeCubies.solved, f = f, s = 0
        for i in stride(from: 10, through: 0, by: -1) {
            c.eo[i] = f % 2
            s += c.eo[i]
            f /= 2
        }
        c.eo[11] = s % 2
        return c
    }

    static func cube(sliceSorted idx: Int) -> CubeCubies {
        var slice = [8, 9, 10, 11]
        let other = [0, 1, 2, 3, 4, 5, 6, 7]
        var b = idx % 24, a = idx / 24
        for j in 1...3 {
            var k = b % (j + 1)
            b /= j + 1
            while k > 0 {
                rotateRight(&slice, 0, j)
                k -= 1
            }
        }
        var ep = [Int](repeating: -1, count: 12)
        var x = 3
        for j in 0..<12 where x >= 0 && a - binomial(11 - j, x + 1) >= 0 {
            ep[j] = slice[3 - x]
            a -= binomial(11 - j, x + 1)
            x -= 1
        }
        x = 0
        for j in 0..<12 where ep[j] == -1 {
            ep[j] = other[x]
            x += 1
        }
        var c = CubeCubies.solved
        c.ep = ep
        return c
    }

    static func cube(corners idx: Int) -> CubeCubies {
        var c = CubeCubies.solved
        c.cp = permutation(index: idx, count: 8)
        return c
    }

    static func cube(udEdges idx: Int) -> CubeCubies {
        var c = CubeCubies.solved
        c.ep = permutation(index: idx, count: 8) + [8, 9, 10, 11]
        return c
    }

    // MARK: - Dựng bảng

    /// Bảng bước `[UInt16]`: `table[coord * moves.count + m]` = toạ độ sau bước `moves[m]` (chỉ số trong `faceMoves`).
    static func buildMoveTable(count: Int, moves: [Int], get: (CubeCubies) -> Int,
                               set: (Int) -> CubeCubies) -> [UInt16] {
        let cubes = moves.map { CubeCubies.move(CubeMove.faceMoves[$0]) }
        var table = [UInt16](repeating: 0, count: count * moves.count)
        for i in 0..<count {
            let c = set(i)
            for (m, mv) in cubes.enumerated() { table[i * moves.count + m] = UInt16(get(c.multiplied(mv))) }
        }
        return table
    }

    /// Bảng cắt tỉa tích hai toạ độ (chỉ số `a * countB + b`): độ sâu BFS từ (0, 0), nén 4 bit/ô (`0xF` = chưa tới).
    /// `moveA`/`moveB` trả toạ độ sau bước thứ m (0..<moveCount).
    static func buildPruneTable(countA: Int, countB: Int, moveCount: Int,
                                moveA: (Int, Int) -> Int, moveB: (Int, Int) -> Int) -> SolverNibbleTable {
        let total = countA * countB
        var depthOf = [UInt8](repeating: 0xF, count: total)
        depthOf[0] = 0
        var frontier = [0]
        var depth: UInt8 = 0
        while !frontier.isEmpty {
            var next: [Int] = []
            for idx in frontier {
                let a = idx / countB, b = idx % countB
                for m in 0..<moveCount {
                    let n = moveA(a, m) * countB + moveB(b, m)
                    if depthOf[n] == 0xF {
                        precondition(depth + 1 < 0xF, "độ sâu vượt 4 bit")
                        depthOf[n] = depth + 1
                        next.append(n)
                    }
                }
            }
            frontier = next
            depth += 1
        }
        return SolverNibbleTable(values: depthOf)
    }

    // MARK: - Phụ trợ

    static func binomial(_ n: Int, _ k: Int) -> Int {
        guard n >= k, k >= 0 else { return 0 }
        var r = 1
        for i in 0..<k { r = r * (n - i) / (i + 1) }
        return r
    }

    static func rotateLeft(_ a: inout [Int], _ l: Int, _ r: Int) {
        let t = a[l]
        for i in l..<r { a[i] = a[i + 1] }
        a[r] = t
    }

    static func rotateRight(_ a: inout [Int], _ l: Int, _ r: Int) {
        let t = a[r]
        for i in stride(from: r, to: l, by: -1) { a[i] = a[i - 1] }
        a[l] = t
    }

    static func permutationIndex(_ p: [Int]) -> Int {
        var perm = p, b = 0
        for j in stride(from: perm.count - 1, through: 1, by: -1) {
            var k = 0
            while perm[j] != j {
                rotateLeft(&perm, 0, j)
                k += 1
            }
            b = (j + 1) * b + k
        }
        return b
    }

    static func permutation(index: Int, count: Int) -> [Int] {
        var perm = Array(0..<count), idx = index
        for j in 1..<count {
            var k = idx % (j + 1)
            idx /= j + 1
            while k > 0 {
                rotateRight(&perm, 0, j)
                k -= 1
            }
        }
        return perm
    }
}

/// Bảng 4 bit/ô (hai ô một byte, ô chẵn ở 4 bit thấp).
struct SolverNibbleTable: Equatable {
    let count: Int
    let bytes: [UInt8]

    init(count: Int, bytes: [UInt8]) {
        self.count = count
        self.bytes = bytes
    }

    init(values: [UInt8]) {
        count = values.count
        var b = [UInt8](repeating: 0, count: (values.count + 1) / 2)
        for i in values.indices {
            b[i >> 1] |= (values[i] & 0xF) << ((i & 1) * 4)
        }
        bytes = b
    }

    subscript(i: Int) -> UInt8 { (bytes[i >> 1] >> ((i & 1) * 4)) & 0xF }
}
