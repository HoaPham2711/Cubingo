@testable import AppHost
import XCTest

final class SolverBeginnerTests: XCTestCase {
    private let base = CubeColor(.d)

    private static func permutations(_ a: [Int]) -> [[Int]] {
        guard a.count > 1 else { return [a] }
        return a.indices.flatMap { i -> [[Int]] in
            var rest = a
            let x = rest.remove(at: i)
            return permutations(rest).map { [x] + $0 }
        }
    }

    /// Mọi trạng thái tầng cuối hợp lệ có hai tầng dưới xong: định hướng góc (27) × định hướng cạnh (8) × hoán vị góc
    /// (24) × hoán vị cạnh (24), lọc chẵn lẻ ⇒ 62 208 trạng thái.
    static func lastLayerStates() -> [CubeCubies] {
        let perms = permutations([0, 1, 2, 3])
        var out: [CubeCubies] = []
        out.reserveCapacity(62_208)
        for cp in perms {
            for ep in perms where CubeCubies.parity(cp) == CubeCubies.parity(ep) {
                for co in 0..<27 {
                    let c3 = [co % 3, co / 3 % 3, co / 9]
                    let cos = c3 + [(3 - c3.reduce(0, +) % 3) % 3]
                    for eo in 0..<8 {
                        let e3 = [eo & 1, eo >> 1 & 1, eo >> 2 & 1]
                        let eos = e3 + [e3.reduce(0, +) % 2]
                        out.append(CubeCubies(cp: cp + [4, 5, 6, 7], co: cos + [0, 0, 0, 0],
                                              ep: ep + Array(4..<12), eo: eos + Array(repeating: 0, count: 8)))
                    }
                }
            }
        }
        return out
    }

    /// Vét cạn là bằng chứng DUY NHẤT cho các luật tầng cuối. Chạy song song trên các nhân của Simulator; vẫn có thể
    /// mất ~10–20 s ở -O0 ⇒ class này được phép > 2 s.
    func testVetCanTangCuoi() {
        let states = Self.lastLayerStates()
        XCTAssertEqual(states.count, 62_208)
        let lock = NSLock()
        var failures: [String] = []
        var longest = [0, 0, 0, 0]
        let chunks = 64
        DispatchQueue.concurrentPerform(iterations: chunks) { chunk in
            var localLongest = [0, 0, 0, 0]
            var localFail: [String] = []
            for i in stride(from: chunk, to: states.count, by: chunks) {
                let start = states[i].facelets(centers: cubeStandardCenters)
                let s4 = SolverBeginnerLastLayer.topCross(start)
                let s5 = SolverBeginnerLastLayer.topFace(s4.end)
                let s6 = SolverBeginnerLastLayer.topCorners(s5.end)
                let s7 = SolverBeginnerLastLayer.topEdges(s6.end)
                for (k, s) in [s4, s5, s6, s7].enumerated() { localLongest[k] = max(localLongest[k], s.steps.count) }
                if !s7.end.isSolved, localFail.count < 3 { localFail.append("trạng thái \(i)") }
            }
            lock.lock()
            failures += localFail
            for k in 0..<4 { longest[k] = max(longest[k], localLongest[k]) }
            lock.unlock()
        }
        XCTAssertEqual(failures, [])
        for k in 0..<4 { XCTAssertLessThanOrEqual(longest[k], 40, "chặng \(k + 4) dài nhất \(longest[k])") }
    }

    func testNamTramTrangThaiGiaiXong() {
        var rng = CubeRandom(seed: 31)
        for i in 0..<500 {
            let start = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
            let stages = SolverBeginner.solve(start, base: start.center(.u))
            XCTAssertEqual(stages.map(\.kind), SolverStageKind.allCases)
            XCTAssertTrue(start.applying(stages.flatMap { $0.steps.map(\.move) }).isSolved, "trạng thái \(i)")
            for k in 1..<7 { XCTAssertEqual(stages[k].start, stages[k - 1].end) }
            XCTAssertLessThanOrEqual(stages.reduce(0) { $0 + $1.steps.count }, 300, "trạng thái \(i)")
        }
    }

    func testKhoiDaGiaiChoRaToanChangRong() {
        let solved = CubeFacelets.solved(n: 3)
        for base in CubeColor.all {
            let stages = SolverBeginner.solve(solved, base: base)
            XCTAssertEqual(stages.count, 7)
            XCTAssertTrue(stages.allSatisfy(\.steps.isEmpty), "base \(base.raw)")
        }
        // Khối cầm nghiêng (đã giải) cũng vậy.
        let tilted = solved.applying(CubeMove.parse("x y")!)
        XCTAssertTrue(SolverBeginner.solve(tilted, base: CubeColor(raw: 0)).allSatisfy(\.steps.isEmpty))
    }

    func testMoiBuocXoayCaKhoiCoChipHoldDung() {
        var rng = CubeRandom(seed: 32)
        for _ in 0..<100 {
            let start = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
            var f = start
            for stage in SolverBeginner.solve(start, base: start.center(.l)) {
                for step in stage.steps {
                    f = f.applying(step.move)
                    if step.move.isRotation {
                        let h = SolverHold.hold(of: f)
                        XCTAssertEqual(step.reason, .hold(top: h.top, front: h.front))
                    }
                }
            }
            XCTAssertTrue(f.isSolved)
        }
    }

    func testChangDauBatDauBangHold() {
        // Tâm base ở F: bước đầu chặng 1 là xoay, chip hold đưa màu đối diện base lên trên.
        var rng = CubeRandom(seed: 33)
        let start = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
        let base = start.center(.f)
        let first = SolverBeginner.solve(start, base: base)[0].steps.first!
        XCTAssertTrue(first.move.isRotation)
        guard case let .hold(top, _)? = first.reason else { return XCTFail("phải là hold") }
        XCTAssertEqual(top, start.center(.b))
    }

    func testLyDoTangCuoi() {
        var rng = CubeRandom(seed: 34)
        let start = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
        let stages = SolverBeginner.solve(start, base: start.center(.d))
        let reasons = stages.flatMap { $0.steps.compactMap(\.reason) }
        XCTAssertTrue(reasons.contains(.makeTopCross) || stages[3].steps.isEmpty)
        XCTAssertTrue(reasons.contains(.orientTopCorners) || stages[4].steps.isEmpty)
        XCTAssertTrue(stages[4].steps.allSatisfy { $0.move.isRotation || $0.move.face == .u || $0.algorithm == .sune })
    }
}
