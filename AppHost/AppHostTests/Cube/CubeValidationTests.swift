@testable import AppHost
import XCTest

final class CubeValidationTests: XCTestCase {
    private let red = CubeColor(raw: 1), orange = CubeColor(raw: 4)

    private func randomFacelets(seed: UInt64) -> CubeFacelets {
        var rng = CubeRandom(seed: seed)
        return CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
    }

    func testLoiDemMau() {
        var f = randomFacelets(seed: 3)
        let i = f.stickers.indices.first { $0 % 9 != 4 && f.stickers[$0] == orange }!
        f.stickers[i] = red
        guard case let .colorCount(over, under, overCount, underCount, suspects)? =
            CubeValidation.firstIssue(f, confidence: nil) else { return XCTFail("phải là lỗi đếm màu") }
        XCTAssertEqual(over, red)
        XCTAssertEqual(under, orange)
        XCTAssertEqual(overCount, 10)
        XCTAssertEqual(underCount, 8)
        XCTAssertEqual(suspects, [], "không có confidence ⇒ không đoán ô")
        var conf = Array(repeating: 30.0, count: 54)
        conf[i] = 2
        guard case let .colorCount(_, _, _, _, s2)? = CubeValidation.firstIssue(f, confidence: conf) else {
            return XCTFail("phải là lỗi đếm màu")
        }
        XCTAssertEqual(s2, [i])
    }

    func testMienKhongTonTai() {
        var f = CubeFacelets.solved(n: 3)
        // Cạnh UF (ô 7, 19) thành màu U + màu D; bù số đếm ở ô D của cạnh DR (32) ⇒ DR thành F+R (hợp lệ, trùng FR).
        f.stickers[19] = CubeColor(.d)
        f.stickers[32] = CubeColor(.f)
        guard case let .impossiblePiece(stickers)? = CubeValidation.firstIssue(f, confidence: nil) else {
            return XCTFail("phải là miếng không tồn tại")
        }
        XCTAssertTrue(stickers.contains(7) && stickers.contains(19), "\(stickers)")
    }

    func testGocNguocChieuGuongLaMienKhongTonTai() {
        var f = CubeFacelets.solved(n: 3)
        // Góc URF (8, 9, 20): đổi chỗ hai ô bên ⇒ bộ màu đúng nhưng ngược chiều.
        f.stickers.swapAt(9, 20)
        guard case let .impossiblePiece(stickers)? = CubeValidation.firstIssue(f, confidence: nil) else {
            return XCTFail("phải là miếng không tồn tại")
        }
        XCTAssertEqual(Set(stickers), [8, 9, 20])
    }

    func testGocXoanCanhLatDoiCho() {
        var twisted = CubeFacelets.solved(n: 3)
        let (a, b, c) = (twisted.stickers[8], twisted.stickers[9], twisted.stickers[20])
        twisted.stickers[8] = c; twisted.stickers[9] = a; twisted.stickers[20] = b
        XCTAssertEqual(CubeValidation.firstIssue(twisted, confidence: nil), .twistedCorner)

        var flipped = CubeFacelets.solved(n: 3)
        flipped.stickers.swapAt(7, 19)
        XCTAssertEqual(CubeValidation.firstIssue(flipped, confidence: nil), .flippedEdge)

        var swapped = CubeFacelets.solved(n: 3)
        swapped.stickers.swapAt(5, 7)
        swapped.stickers.swapAt(10, 19)
        XCTAssertEqual(CubeValidation.firstIssue(swapped, confidence: nil), .swappedPieces)

        XCTAssertNil(CubeValidation.firstIssue(.solved(n: 3), confidence: nil))
    }

    /// Xoay lưới ô của MỘT mặt k nấc theo chiều kim đồng hồ (như người dùng cầm nghiêng khi quét) — không đụng mặt bên.
    private func rotatingGrid(_ f: CubeFacelets, _ face: CubeFace, _ k: Int) -> CubeFacelets {
        var out = f
        for _ in 0..<k {
            let base = face.rawValue * 9
            let old = Array(out.stickers[base..<(base + 9)])
            for r in 0..<3 { for c in 0..<3 { out.stickers[base + r * 3 + c] = old[(2 - c) * 3 + r] } }
        }
        return out
    }

    func testSuaHuongQuetMatTrenDuoi() {
        var uniqueSeen = 0, ambiguousSeen = 0
        for seed in 0..<20 {
            let original = randomFacelets(seed: UInt64(100 + seed))
            for u in 0..<4 {
                for d in 0..<4 where (u, d) != (0, 0) {
                    let scanned = rotatingGrid(rotatingGrid(original, .u, u), .d, d)
                    // Đếm độc lập các tổ hợp sửa cho ra khối hợp lệ.
                    var valid: [CubeFacelets] = []
                    for uu in 0..<4 {
                        for dd in 0..<4 {
                            let g = rotatingGrid(rotatingGrid(scanned, .u, uu), .d, dd)
                            if CubeValidation.firstIssue(g, confidence: nil) == nil { valid.append(g) }
                        }
                    }
                    let repaired = CubeValidation.repairScanOrientation(scanned)
                    if valid.count == 1 {
                        uniqueSeen += 1
                        XCTAssertEqual(repaired, original, "seed \(seed) u\(u) d\(d)")
                    } else {
                        ambiguousSeen += 1
                        XCTAssertNil(repaired, "seed \(seed) u\(u) d\(d): \(valid.count) tổ hợp hợp lệ")
                    }
                }
            }
        }
        XCTAssertGreaterThan(uniqueSeen, 0)
        // Khối đã giải: mọi tổ hợp hợp lệ ⇒ không tự sửa.
        XCTAssertNil(CubeValidation.repairScanOrientation(.solved(n: 3)))
        // Khối đã hợp lệ sẵn và là tổ hợp duy nhất ⇒ không có gì để sửa.
        XCTAssertNil(CubeValidation.repairScanOrientation(randomFacelets(seed: 1)))
        _ = ambiguousSeen
    }
}
