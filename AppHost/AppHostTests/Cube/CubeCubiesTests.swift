@testable import AppHost
import XCTest

/// Tâm chuẩn: mặt k mang `CubeColor(raw: k)`.
let cubeStandardCenters: [CubeFace: CubeColor] = Dictionary(uniqueKeysWithValues: CubeFace.allCases.map { ($0, CubeColor($0)) })

final class CubeCubiesTests: XCTestCase {
    func testFaceletCubieHaiChieu() throws {
        var rng = CubeRandom(seed: 7)
        for _ in 0..<200 {
            let c = CubeRandom.state(using: &rng)
            XCTAssertEqual(try CubeCubies(facelets: c.facelets(centers: cubeStandardCenters)), c)
        }
        XCTAssertEqual(try CubeCubies(facelets: .solved(n: 3)), .solved)
    }

    func testBuocMatTrenCubieKhopFacelet() throws {
        for m in CubeMove.faceMoves {
            XCTAssertEqual(try CubeCubies(facelets: CubeFacelets.solved(n: 3).applying(m)), CubeCubies.move(m), m.notation)
        }
    }

    func testNhanCubieBangApBuoc() throws {
        var rng = CubeRandom(seed: 8)
        let start = CubeRandom.state(using: &rng)
        var c = start
        var f = start.facelets(centers: cubeStandardCenters)
        for i in 0..<60 {
            let m = CubeMove.faceMoves[(i * 7) % 18]
            c = c.multiplied(CubeCubies.move(m))
            f = f.applying(m)
            XCTAssertEqual(try CubeCubies(facelets: f), c)
        }
    }

    func testDoiNhanTheoTam() throws {
        // Bảng màu hoán vị: raw 0↔2, 1↔5 — khối vẫn ra đúng trạng thái cubie.
        let swap: [UInt8: UInt8] = [0: 2, 2: 0, 1: 5, 5: 1, 3: 3, 4: 4]
        var rng = CubeRandom(seed: 12)
        for _ in 0..<50 {
            let c = CubeRandom.state(using: &rng)
            let centers = cubeStandardCenters.mapValues { CubeColor(raw: swap[$0.raw]!) }
            XCTAssertEqual(try CubeCubies(facelets: c.facelets(centers: centers)), c)
        }
    }

    func testTrangThaiNgauNhienLuonHopLe() {
        var rng = CubeRandom(seed: 5)
        for _ in 0..<500 {
            let c = CubeRandom.state(using: &rng)
            XCTAssertEqual(c.cornerTwistSum % 3, 0)
            XCTAssertEqual(c.edgeFlipSum % 2, 0)
            XCTAssertTrue(c.permutationParityMatches)
            XCTAssertNil(CubeValidation.firstIssue(c.facelets(centers: cubeStandardCenters), confidence: nil))
        }
    }

    func testRandomCoSeedTatDinh() {
        var a = CubeRandom(seed: 99), b = CubeRandom(seed: 99)
        XCTAssertEqual(CubeRandom.state(using: &a), CubeRandom.state(using: &b))
        XCTAssertNotEqual(CubeRandom.state(using: &a), .solved)
    }
}
