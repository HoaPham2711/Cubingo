import Foundation

/// Trạng thái khối theo ô: `n*n*6` nhãn màu, thứ tự Kociemba (U1…U9 R… F… D… L… B…, mỗi mặt đọc theo hàng).
struct CubeFacelets: Hashable {
    let n: Int
    var stickers: [CubeColor]

    init(n: Int, stickers: [CubeColor]) {
        precondition(stickers.count == 6 * n * n, "sai số ô")
        self.n = n
        self.stickers = stickers
    }

    /// Khối đã giải: ô của mặt k mang `CubeColor(raw: k)`.
    static func solved(n: Int) -> CubeFacelets {
        CubeFacelets(n: n, stickers: CubeFace.allCases.flatMap { Array(repeating: CubeColor($0), count: n * n) })
    }

    func applying(_ m: CubeMove) -> CubeFacelets {
        let perm = CubeGeometry.of(n: n).permutation(m)
        return CubeFacelets(n: n, stickers: perm.map { stickers[$0] })
    }

    func applying(_ ms: [CubeMove]) -> CubeFacelets {
        ms.reduce(self) { $0.applying($1) }
    }

    /// Mỗi mặt một màu (không đòi đúng nhãn — khối cầm hướng nào cũng được).
    var isSolved: Bool {
        let k = n * n
        return (0..<6).allSatisfy { f in
            let first = stickers[f * k]
            return stickers[(f * k)..<((f + 1) * k)].allSatisfy { $0 == first }
        }
    }

    func color(_ face: CubeFace, _ index: Int) -> CubeColor {
        stickers[face.rawValue * n * n + index]
    }

    /// Màu tâm (chỉ 3×3).
    func center(_ face: CubeFace) -> CubeColor {
        precondition(n == 3, "2×2 không có tâm")
        return color(face, 4)
    }

    /// Chuỗi 54 chữ (3×3): chữ của mặt có tâm cùng màu. Chỉ dùng cho test và tool.
    var kociemba: String {
        let byColor = Dictionary(CubeFace.allCases.map { (center($0), $0.letter) }, uniquingKeysWith: { a, _ in a })
        return String(stickers.map { byColor[$0] ?? "?" })
    }

    /// Đọc chuỗi 54 chữ U/R/F/D/L/B; chữ của mặt k ⇒ `CubeColor(raw: k)`.
    init?(kociemba s: String) {
        guard s.count == 54 else { return nil }
        var out: [CubeColor] = []
        for ch in s {
            guard let f = CubeFace(letter: ch) else { return nil }
            out.append(CubeColor(f))
        }
        self.init(n: 3, stickers: out)
    }
}
