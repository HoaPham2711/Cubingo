import Foundation

/// Kết quả quét: khối theo nhãn nhóm màu + bảng màu đo được + độ tin cậy từng ô.
struct ScanResult: Equatable {
    let facelets: CubeFacelets
    let palette: CubePalette
    /// ΔE tới nhóm tốt thứ hai − ΔE tới nhóm được gán (tâm = 100). Thấp ⇒ đáng nghi.
    let confidence: [Double]
    /// Hai tâm quá giống nhau (ΔE < 15) ⇒ người dùng phải sửa tay.
    let ambiguousCenters: (CubeColor, CubeColor)?

    static func == (a: ScanResult, b: ScanResult) -> Bool {
        a.facelets == b.facelets && a.palette == b.palette && a.confidence == b.confidence
            && a.ambiguousCenters?.0 == b.ambiguousCenters?.0 && a.ambiguousCenters?.1 == b.ambiguousCenters?.1
    }
}

/// Phân nhóm màu toàn khối: tâm làm mốc (nhóm k = màu tâm mặt k), cân trắng theo tâm trắng, gán CÓ RÀNG BUỘC mỗi
/// nhóm đúng n² ô bằng Hungarian trên ΔE76 tới tâm.
enum ScanClusterer {
    static let ambiguousCenterDeltaE = 15.0
    /// Tâm dùng để cân trắng phải sáng (L* > 50) và ít sắc nhất với C* < 40 — đèn vàng ấm đẩy tâm trắng lên C* ≈ 27;
    /// tâm đen không phải mốc trắng.
    static let whiteReferenceMaxChroma = 40.0

    static func cluster(_ samples: [CubeRGB], n: Int) -> ScanResult {
        precondition(n == 3, "Đợt A chỉ quét 3×3")
        precondition(samples.count == 54, "cần 54 mẫu")
        let centerIndex = (0..<6).map { $0 * 9 + 4 }
        var balanced = samples
        let candidates = centerIndex.filter { CubeColorMath.lab(samples[$0]).x > 50 }
        if let w = candidates.min(by: { CubeColorMath.chroma(samples[$0]) < CubeColorMath.chroma(samples[$1]) }),
           CubeColorMath.chroma(samples[w]) < whiteReferenceMaxChroma {
            balanced = CubeColorMath.whiteBalanced(samples, white: samples[w])
        }
        let labs = balanced.map(CubeColorMath.lab)
        func dist(_ i: Int, _ k: Int) -> Double {
            let d = labs[i] - labs[centerIndex[k]]
            return (d * d).sum().squareRoot()
        }
        let others = (0..<54).filter { $0 % 9 != 4 }
        let perGroup = others.count / 6
        let cost = others.map { i in (0..<48).map { col in dist(i, col / perGroup) } }
        let assignment = ScanHungarian.assign(cost: cost)

        var stickers = (0..<54).map { CubeColor(raw: UInt8($0 / 9)) }
        var confidence = [Double](repeating: 100, count: 54)
        for (row, i) in others.enumerated() {
            let k = assignment[row] / perGroup
            stickers[i] = CubeColor(raw: UInt8(k))
            let mine = dist(i, k)
            let second = (0..<6).filter { $0 != k }.map { dist(i, $0) }.min()!
            confidence[i] = second - mine
        }
        var sums = [CubeColor: (CubeRGB, Int)]()
        for i in 0..<54 {
            let c = stickers[i], s = balanced[i]
            let cur = sums[c] ?? (CubeRGB(r: 0, g: 0, b: 0), 0)
            sums[c] = (CubeRGB(r: cur.0.r + s.r, g: cur.0.g + s.g, b: cur.0.b + s.b), cur.1 + 1)
        }
        let palette = CubePalette(colors: sums.mapValues { s, k in
            CubeRGB(r: s.r / Double(k), g: s.g / Double(k), b: s.b / Double(k))
        })
        var ambiguous: (CubeColor, CubeColor)?
        search: for a in 0..<6 {
            for b in (a + 1)..<6 where CubeColorMath.deltaE(balanced[centerIndex[a]], balanced[centerIndex[b]]) < ambiguousCenterDeltaE {
                ambiguous = (CubeColor(raw: UInt8(a)), CubeColor(raw: UInt8(b)))
                break search
            }
        }
        return ScanResult(facelets: CubeFacelets(n: 3, stickers: stickers), palette: palette,
                          confidence: confidence, ambiguousCenters: ambiguous)
    }
}
