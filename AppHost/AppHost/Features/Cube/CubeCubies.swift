import Foundation

/// Miếng không thể có trên khối thật.
enum CubePieceError: Error, Equatable {
    /// Bộ màu không là miếng nào (hai màu đối diện, trùng màu, góc ngược chiều gương, hoặc trùng một miếng khác);
    /// `stickers` là chỉ số facelet của (các) miếng đó.
    case impossiblePiece(stickers: [Int])
}

/// Trạng thái khối 3×3 theo miếng (chuẩn Kociemba): `cp[i]`/`ep[i]` = miếng đang ở vị trí i, `co`/`eo` = định hướng.
/// Thứ tự góc `URF UFL ULB UBR DFR DLF DBL DRB`, cạnh `UR UF UL UB DR DF DL DB FR FL BL BR`. Chỉ `import Foundation`:
/// tool `tools/app/kociemba/` biên dịch lại file này.
struct CubeCubies: Hashable {
    var cp: [Int]
    var co: [Int]
    var ep: [Int]
    var eo: [Int]

    static let solved = CubeCubies(cp: Array(0..<8), co: Array(repeating: 0, count: 8),
                                   ep: Array(0..<12), eo: Array(repeating: 0, count: 12))

    /// Chỉ số facelet (chuỗi Kociemba) của mỗi góc, theo chiều kim đồng hồ bắt đầu từ ô U/D.
    static let cornerFacelet: [[Int]] = [
        [8, 9, 20], [6, 18, 38], [0, 36, 47], [2, 45, 11],
        [29, 26, 15], [27, 44, 24], [33, 53, 42], [35, 17, 51],
    ]
    /// Chỉ số facelet của mỗi cạnh (ô U/D hoặc F/B trước).
    static let edgeFacelet: [[Int]] = [
        [5, 10], [7, 19], [3, 37], [1, 46], [32, 16], [28, 25],
        [30, 43], [34, 52], [23, 12], [21, 41], [50, 39], [48, 14],
    ]
    static let cornerColor: [[CubeFace]] = [
        [.u, .r, .f], [.u, .f, .l], [.u, .l, .b], [.u, .b, .r],
        [.d, .f, .r], [.d, .l, .f], [.d, .b, .l], [.d, .r, .b],
    ]
    static let edgeColor: [[CubeFace]] = [
        [.u, .r], [.u, .f], [.u, .l], [.u, .b], [.d, .r], [.d, .f],
        [.d, .l], [.d, .b], [.f, .r], [.f, .l], [.b, .l], [.b, .r],
    ]

    init(cp: [Int], co: [Int], ep: [Int], eo: [Int]) {
        self.cp = cp
        self.co = co
        self.ep = ep
        self.eo = eo
    }

    /// Đọc từ facelet 3×3; nhãn màu đổi theo 6 tâm (màu của tâm U ⇒ mặt U…).
    init(facelets f: CubeFacelets) throws(CubePieceError) {
        precondition(f.n == 3, "cubie chỉ cho 3×3")
        var faceOf: [CubeColor: CubeFace] = [:]
        for face in CubeFace.allCases {
            let c = f.center(face)
            if let other = faceOf[c] {
                throw .impossiblePiece(stickers: [other.rawValue * 9 + 4, face.rawValue * 9 + 4])
            }
            faceOf[c] = face
        }
        func face(_ i: Int) -> CubeFace? { faceOf[f.stickers[i]] }

        var cp = [Int](repeating: -1, count: 8), co = [Int](repeating: 0, count: 8)
        for i in 0..<8 {
            let idx = Self.cornerFacelet[i]
            guard let ori = (0..<3).first(where: { face(idx[$0]) == .u || face(idx[$0]) == .d }),
                  let c1 = face(idx[(ori + 1) % 3]), let c2 = face(idx[(ori + 2) % 3]),
                  let j = (0..<8).first(where: {
                      Self.cornerColor[$0][0] == face(idx[ori]) && Self.cornerColor[$0][1] == c1
                          && Self.cornerColor[$0][2] == c2
                  })
            else { throw .impossiblePiece(stickers: idx) }
            cp[i] = j
            co[i] = ori
        }
        var ep = [Int](repeating: -1, count: 12), eo = [Int](repeating: 0, count: 12)
        for i in 0..<12 {
            let idx = Self.edgeFacelet[i]
            guard let a = face(idx[0]), let b = face(idx[1]) else { throw .impossiblePiece(stickers: idx) }
            if let j = (0..<12).first(where: { Self.edgeColor[$0] == [a, b] }) {
                ep[i] = j
                eo[i] = 0
            } else if let j = (0..<12).first(where: { Self.edgeColor[$0] == [b, a] }) {
                ep[i] = j
                eo[i] = 1
            } else {
                throw .impossiblePiece(stickers: idx)
            }
        }
        // Một miếng xuất hiện hai lần ⇒ cả hai vị trí đều đáng nghi.
        for j in 0..<8 {
            let at = cp.indices.filter { cp[$0] == j }
            if at.count > 1 { throw .impossiblePiece(stickers: at.flatMap { Self.cornerFacelet[$0] }) }
        }
        for j in 0..<12 {
            let at = ep.indices.filter { ep[$0] == j }
            if at.count > 1 { throw .impossiblePiece(stickers: at.flatMap { Self.edgeFacelet[$0] }) }
        }
        self.init(cp: cp, co: co, ep: ep, eo: eo)
    }

    /// Facelet với màu tâm cho trước (mặt ⇒ màu).
    func facelets(centers: [CubeFace: CubeColor]) -> CubeFacelets {
        var s = [CubeColor](repeating: CubeColor(raw: 0), count: 54)
        for face in CubeFace.allCases { s[face.rawValue * 9 + 4] = centers[face]! }
        for i in 0..<8 {
            for k in 0..<3 {
                s[Self.cornerFacelet[i][(k + co[i]) % 3]] = centers[Self.cornerColor[cp[i]][k]]!
            }
        }
        for i in 0..<12 {
            for k in 0..<2 {
                s[Self.edgeFacelet[i][(k + eo[i]) % 2]] = centers[Self.edgeColor[ep[i]][k]]!
            }
        }
        return CubeFacelets(n: 3, stickers: s)
    }

    /// `self` rồi áp `other` (Kociemba `multiply`).
    func multiplied(_ other: CubeCubies) -> CubeCubies {
        var r = self
        for i in 0..<8 {
            r.cp[i] = cp[other.cp[i]]
            r.co[i] = (co[other.cp[i]] + other.co[i]) % 3
        }
        for i in 0..<12 {
            r.ep[i] = ep[other.ep[i]]
            r.eo[i] = (eo[other.ep[i]] + other.eo[i]) % 2
        }
        return r
    }

    /// Áp một dãy bước mặt.
    func applying(_ ms: [CubeMove]) -> CubeCubies {
        ms.reduce(self) { $0.multiplied(.move($1)) }
    }

    /// Khối cubie của một bước mặt (bước xoay cả khối không có ở mức cubie — precondition).
    static func move(_ m: CubeMove) -> CubeCubies {
        guard let f = m.face else { preconditionFailure("CubeCubies chỉ nhận bước mặt") }
        let base = baseMoves[f.rawValue]
        var r = solved
        for _ in 0..<m.turns { r = r.multiplied(base) }
        return r
    }

    /// Sáu bước cơ bản U R F D L B (bảng chuẩn của thuật toán hai pha).
    static let baseMoves: [CubeCubies] = [
        CubeCubies(cp: [3, 0, 1, 2, 4, 5, 6, 7], co: [0, 0, 0, 0, 0, 0, 0, 0],
                   ep: [3, 0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11], eo: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        CubeCubies(cp: [4, 1, 2, 0, 7, 5, 6, 3], co: [2, 0, 0, 1, 1, 0, 0, 2],
                   ep: [8, 1, 2, 3, 11, 5, 6, 7, 4, 9, 10, 0], eo: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        CubeCubies(cp: [1, 5, 2, 3, 0, 4, 6, 7], co: [1, 2, 0, 0, 2, 1, 0, 0],
                   ep: [0, 9, 2, 3, 4, 8, 6, 7, 1, 5, 10, 11], eo: [0, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0]),
        CubeCubies(cp: [0, 1, 2, 3, 5, 6, 7, 4], co: [0, 0, 0, 0, 0, 0, 0, 0],
                   ep: [0, 1, 2, 3, 5, 6, 7, 4, 8, 9, 10, 11], eo: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        CubeCubies(cp: [0, 2, 6, 3, 4, 1, 5, 7], co: [0, 1, 2, 0, 0, 2, 1, 0],
                   ep: [0, 1, 10, 3, 4, 5, 9, 7, 8, 2, 6, 11], eo: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        CubeCubies(cp: [0, 1, 3, 7, 4, 5, 2, 6], co: [0, 0, 1, 2, 0, 0, 2, 1],
                   ep: [0, 1, 2, 11, 4, 5, 6, 10, 8, 9, 3, 7], eo: [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 1]),
    ]

    var cornerTwistSum: Int { co.reduce(0, +) }
    var edgeFlipSum: Int { eo.reduce(0, +) }

    /// Chẵn lẻ của hoán vị góc bằng của hoán vị cạnh (điều kiện để khối giải được).
    var permutationParityMatches: Bool { Self.parity(cp) == Self.parity(ep) }

    static func parity(_ p: [Int]) -> Int {
        var s = 0
        for i in 0..<p.count { for j in (i + 1)..<p.count where p[i] > p[j] { s += 1 } }
        return s % 2
    }
}
