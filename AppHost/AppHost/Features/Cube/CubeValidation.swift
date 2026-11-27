import Foundation

/// Lỗi đầu tiên của một khối nhập vào (spec 5.4).
enum CubeIssue: Equatable {
    /// Màu `over` thừa, `under` thiếu; `suspects` = các ô màu thừa có độ tin cậy thấp nhất (đủ số ô thừa).
    case colorCount(over: CubeColor, under: CubeColor, overCount: Int, underCount: Int, suspects: [Int])
    case impossiblePiece(stickers: [Int])
    case twistedCorner
    case flippedEdge
    case swappedPieces
}

enum CubeValidation {
    /// Thứ tự kiểm: đếm màu ⇒ miếng không tồn tại ⇒ xoắn góc ⇒ lật cạnh ⇒ đổi chỗ. `nil` ⇒ khối giải được.
    static func firstIssue(_ f: CubeFacelets, confidence: [Double]?) -> CubeIssue? {
        var counts: [CubeColor: Int] = [:]
        for c in f.stickers { counts[c, default: 0] += 1 }
        let need = f.n * f.n
        // Màu nhãn có thể vắng hẳn (đếm 0) — xét đủ sáu nhãn của các tâm và mọi màu xuất hiện.
        var colors = Set(counts.keys)
        if f.n == 3 { for face in CubeFace.allCases { colors.insert(f.center(face)) } }
        if colors.count < 6 { for c in CubeColor.all { colors.insert(c) } }
        let sorted = colors.sorted { $0.raw < $1.raw }
        if sorted.contains(where: { counts[$0, default: 0] != need }) {
            let over = sorted.max { counts[$0, default: 0] < counts[$1, default: 0] }!
            let under = sorted.min { counts[$0, default: 0] < counts[$1, default: 0] }!
            let extra = counts[over, default: 0] - need
            var suspects: [Int] = []
            if let confidence, extra > 0 {
                let center = need / 2
                suspects = f.stickers.indices
                    .filter { f.stickers[$0] == over && !(f.n == 3 && $0 % need == center) }
                    .sorted { confidence[$0] < confidence[$1] }
                    .prefix(extra)
                    .sorted()
            }
            return .colorCount(over: over, under: under, overCount: counts[over, default: 0],
                               underCount: counts[under, default: 0], suspects: suspects)
        }
        let cubies: CubeCubies
        do {
            cubies = try CubeCubies(facelets: f)
        } catch {
            switch error {
            case .impossiblePiece(let stickers): return .impossiblePiece(stickers: stickers)
            }
        }
        if cubies.cornerTwistSum % 3 != 0 { return .twistedCorner }
        if cubies.edgeFlipSum % 2 != 0 { return .flippedEdge }
        if !cubies.permutationParityMatches { return .swappedPieces }
        return nil
    }

    /// Người dùng hay nghiêng sai mặt trên/dưới khi quét: thử 16 tổ hợp xoay lưới U (0…3 nấc) × D (0…3). Trả tổ hợp
    /// KHÁC (0,0) nếu nó là tổ hợp hợp lệ DUY NHẤT; ngược lại `nil` (không tự sửa khi mơ hồ).
    static func repairScanOrientation(_ f: CubeFacelets) -> CubeFacelets? {
        guard f.n == 3 else { return nil }
        var found: CubeFacelets?
        var foundIsIdentity = false
        var hits = 0
        for u in 0..<4 {
            for d in 0..<4 {
                let g = rotatingGrid(rotatingGrid(f, .u, u), .d, d)
                guard firstIssue(g, confidence: nil) == nil else { continue }
                hits += 1
                if hits > 1 { return nil }
                found = g
                foundIsIdentity = u == 0 && d == 0
            }
        }
        return foundIsIdentity ? nil : found
    }

    /// Xoay lưới ô của một mặt k nấc theo chiều kim đồng hồ (nhìn vào mặt đó), không đụng mặt bên.
    static func rotatingGrid(_ f: CubeFacelets, _ face: CubeFace, _ k: Int) -> CubeFacelets {
        var out = f
        let n = f.n, base = face.rawValue * n * n
        for _ in 0..<(k % 4) {
            let old = Array(out.stickers[base..<(base + n * n)])
            for r in 0..<n { for c in 0..<n { out.stickers[base + r * n + c] = old[(n - 1 - c) * n + r] } }
        }
        return out
    }
}
