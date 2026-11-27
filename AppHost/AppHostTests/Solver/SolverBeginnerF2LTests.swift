@testable import AppHost
import XCTest

/// Kiểm mục tiêu chặng trên facelet (độc lập với code của bộ giải): base ở D.
enum SolverGoal {
    /// Mặt có tâm màu `c`.
    static func face(of c: CubeColor, in f: CubeFacelets) -> CubeFace {
        CubeFace.allCases.first { f.center($0) == c }!
    }

    /// Chữ thập base ở D, ô bên khớp tâm bên.
    static func cross(_ f: CubeFacelets, base: CubeColor) -> Bool {
        guard f.center(.d) == base else { return false }
        return [1, 3, 5, 7].allSatisfy { f.color(.d, $0) == base }
            && [CubeFace.f, .r, .b, .l].allSatisfy { f.color($0, 7) == f.center($0) }
    }

    /// Tầng D hoàn chỉnh (cả hàng dưới của bốn mặt bên).
    static func firstLayer(_ f: CubeFacelets, base: CubeColor) -> Bool {
        guard f.center(.d) == base else { return false }
        return (0..<9).allSatisfy { f.color(.d, $0) == base }
            && [CubeFace.f, .r, .b, .l].allSatisfy { s in (6..<9).allSatisfy { f.color(s, $0) == f.center(s) } }
    }

    /// Hai tầng dưới hoàn chỉnh.
    static func twoLayers(_ f: CubeFacelets, base: CubeColor) -> Bool {
        firstLayer(f, base: base)
            && [CubeFace.f, .r, .b, .l].allSatisfy { s in (3..<9).allSatisfy { f.color(s, $0) == f.center(s) } }
    }
}

final class SolverBeginnerF2LTests: XCTestCase {
    private func scrambled(_ rng: inout CubeRandom) -> CubeFacelets {
        CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
    }

    /// 500 trạng thái ở -O0 ⇒ class có thể > 2 s (bằng chứng các luật chặng 1–3 đúng trên mọi ca thường gặp).
    func testChang1Den3TrenNamTramTrangThai() {
        var rng = CubeRandom(seed: 21)
        var longest = [0, 0, 0]
        for i in 0..<500 {
            let start = scrambled(&rng)
            let base = start.center(.u)
            let cross = SolverBeginnerF2L.cross(start, base: base)
            XCTAssertEqual(cross.kind, .cross)
            XCTAssertEqual(cross.start, start)
            XCTAssertTrue(SolverGoal.cross(cross.end, base: base), "cross \(i)")
            let corners = SolverBeginnerF2L.corners(cross.end, base: base)
            XCTAssertTrue(SolverGoal.firstLayer(corners.end, base: base), "corners \(i)")
            let middle = SolverBeginnerF2L.middle(corners.end, base: base)
            XCTAssertTrue(SolverGoal.twoLayers(middle.end, base: base), "middle \(i)")
            for (k, s) in [cross, corners, middle].enumerated() { longest[k] = max(longest[k], s.steps.count) }
        }
        // Trần rộng: chặng 2 lặp right trigger 1–5 lần mỗi góc (cách dạy "lặp tới khi xong" của spec 5.7); đo 2026-11-27
        // trên seed 21: dài nhất 16 / 105 / 63.
        XCTAssertLessThanOrEqual(longest[0], 40, "cross dài nhất \(longest[0])")
        XCTAssertLessThanOrEqual(longest[1], 120, "corners dài nhất \(longest[1])")
        XCTAssertLessThanOrEqual(longest[2], 90, "middle dài nhất \(longest[2])")
    }

    func testChangDaXongThiRong() {
        let solved = CubeFacelets.solved(n: 3)
        // base = màu tâm D ⇒ khối đã giải đạt mọi chặng mà không cần xoay.
        let base = solved.center(.d)
        XCTAssertEqual(SolverBeginnerF2L.cross(solved, base: base).steps, [])
        XCTAssertEqual(SolverBeginnerF2L.corners(solved, base: base).steps, [])
        XCTAssertEqual(SolverBeginnerF2L.middle(solved, base: base).steps, [])
        // base ở U: chặng đã đạt (cầm ngược) vẫn là rỗng.
        XCTAssertEqual(SolverBeginnerF2L.cross(solved, base: solved.center(.u)).steps, [])
    }

    func testThuatToanDungChuoi() {
        let expected: [SolverAlgorithm: String] = [
            .rightTrigger: "R U R' U'", .rightInsert: "U R U' R' U' F' U F", .leftInsert: "U' L' U L U F U' F'",
            .crossMaker: "F R U R' U' F'", .sune: "R U R' U R U2 R'", .cornerCycle: "R' F R' B2 R F' R' B2 R2",
            .edgeCycle: "R U' R U R U R U' R' U' R2",
        ]
        for a in SolverAlgorithm.allCases {
            XCTAssertEqual(a.moves.map(\.notation).joined(separator: " "), expected[a], "\(a)")
        }
    }

    func testBangMauKhacChuan() {
        // Cùng trạng thái, tô lại bảng màu (raw 1↔5, 2↔4) ⇒ các chặng vẫn đạt mục tiêu, số bước bằng nhau.
        let swap: [UInt8: UInt8] = [0: 0, 3: 3, 1: 5, 5: 1, 2: 4, 4: 2]
        var rng = CubeRandom(seed: 22)
        for _ in 0..<30 {
            let cubies = CubeRandom.state(using: &rng)
            let a = cubies.facelets(centers: cubeStandardCenters)
            let b = cubies.facelets(centers: cubeStandardCenters.mapValues { CubeColor(raw: swap[$0.raw]!) })
            let baseA = a.center(.u), baseB = b.center(.u)
            let sa = [SolverBeginnerF2L.cross(a, base: baseA)]
            let sb = [SolverBeginnerF2L.cross(b, base: baseB)]
            XCTAssertEqual(sa[0].steps.map(\.move), sb[0].steps.map(\.move))
            let ca = SolverBeginnerF2L.corners(sa[0].end, base: baseA), cb = SolverBeginnerF2L.corners(sb[0].end, base: baseB)
            XCTAssertEqual(ca.steps.map(\.move), cb.steps.map(\.move))
            let ma = SolverBeginnerF2L.middle(ca.end, base: baseA), mb = SolverBeginnerF2L.middle(cb.end, base: baseB)
            XCTAssertEqual(ma.steps.map(\.move), mb.steps.map(\.move))
            XCTAssertTrue(SolverGoal.twoLayers(mb.end, base: baseB))
        }
    }

    func testLyDoChiOBuocDauNhomVaXoayCoHold() {
        var rng = CubeRandom(seed: 23)
        let start = scrambled(&rng)
        let cross = SolverBeginnerF2L.cross(start, base: start.center(.r))
        XCTAssertTrue(cross.steps.first?.move.isRotation == true, "base ở R ⇒ bước đầu là xoay cả khối")
        var f = start
        for s in cross.steps {
            f = f.applying(s.move)
            if s.move.isRotation {
                let h = SolverHold.hold(of: f)
                XCTAssertEqual(s.reason, .hold(top: h.top, front: h.front))
            }
        }
        XCTAssertTrue(cross.steps.contains { if case .makeDaisy = $0.reason { return true } else { return false } })
        XCTAssertTrue(cross.steps.contains { if case .dropToCross = $0.reason { return true } else { return false } })
    }
}
