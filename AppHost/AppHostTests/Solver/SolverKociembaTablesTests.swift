@testable import AppHost
import XCTest

/// Bảng nạp một lần cho mọi test của bộ giải (nạp ~4 MB ở -O0 mất cỡ trăm ms).
let solverTestTables: SolverKociembaTables = {
    do { return try SolverKociembaTables.load(bundle: .main) } catch { fatalError("không nạp được bảng: \(error)") }
}()

final class SolverKociembaTablesTests: XCTestCase {
    typealias K = SolverKociembaCoords

    func testNapDuocVaDungKichThuoc() {
        let t = solverTestTables
        XCTAssertEqual(t.twistMove.count, 2187 * 18)
        XCTAssertEqual(t.flipMove.count, 2048 * 18)
        XCTAssertEqual(t.sliceSortedMove.count, 11880 * 18)
        XCTAssertEqual(t.cornersMove.count, 40320 * 10)
        XCTAssertEqual(t.udEdgesMove.count, 40320 * 10)
        XCTAssertEqual(t.twistSlicePrune.count, 2187 * 495)
        XCTAssertEqual(t.flipSlicePrune.count, 2048 * 495)
        XCTAssertEqual(t.cornersSlicePrune.count, 40320 * 24)
        XCTAssertEqual(t.udEdgesSlicePrune.count, 40320 * 24)
    }

    func testToaDoHaiChieuVaKhoiDaGiai() {
        let s = CubeCubies.solved
        XCTAssertEqual([K.twist(s), K.flip(s), K.sliceSorted(s), K.corners(s), K.udEdges(s)], [0, 0, 0, 0, 0])
        var rng = CubeRandom(seed: 4)
        for _ in 0..<100 {
            let c = CubeRandom.state(using: &rng)
            XCTAssertEqual(K.twist(K.cube(twist: K.twist(c))), K.twist(c))
            XCTAssertEqual(K.flip(K.cube(flip: K.flip(c))), K.flip(c))
            XCTAssertEqual(K.sliceSorted(K.cube(sliceSorted: K.sliceSorted(c))), K.sliceSorted(c))
            XCTAssertEqual(K.corners(K.cube(corners: K.corners(c))), K.corners(c))
            XCTAssertTrue((0..<2187).contains(K.twist(c)))
            XCTAssertTrue((0..<11880).contains(K.sliceSorted(c)))
        }
        for i in [0, 1, 777, 40319] { XCTAssertEqual(K.udEdges(K.cube(udEdges: i)), i) }
    }

    func testMoveTableKhopTinhLai() {
        let t = solverTestTables
        var rng = CubeRandom(seed: 3)
        for _ in 0..<200 {
            let m = Int.random(in: 0..<18, using: &rng)
            let mv = CubeCubies.move(CubeMove.faceMoves[m])
            let tw = Int.random(in: 0..<2187, using: &rng)
            XCTAssertEqual(Int(t.twistMove[tw * 18 + m]), K.twist(K.cube(twist: tw).multiplied(mv)))
            let fl = Int.random(in: 0..<2048, using: &rng)
            XCTAssertEqual(Int(t.flipMove[fl * 18 + m]), K.flip(K.cube(flip: fl).multiplied(mv)))
            let sl = Int.random(in: 0..<11880, using: &rng)
            XCTAssertEqual(Int(t.sliceSortedMove[sl * 18 + m]), K.sliceSorted(K.cube(sliceSorted: sl).multiplied(mv)))
            let p = Int.random(in: 0..<10, using: &rng)
            let pm = CubeCubies.move(CubeMove.faceMoves[K.phase2Moves[p]])
            let co = Int.random(in: 0..<40320, using: &rng)
            XCTAssertEqual(Int(t.cornersMove[co * 10 + p]), K.corners(K.cube(corners: co).multiplied(pm)))
            let ud = Int.random(in: 0..<40320, using: &rng)
            XCTAssertEqual(Int(t.udEdgesMove[ud * 10 + p]), K.udEdges(K.cube(udEdges: ud).multiplied(pm)))
        }
    }

    func testPruneTableGocBangKhong() {
        let t = solverTestTables
        XCTAssertEqual(t.twistSlicePrune[0], 0)
        XCTAssertEqual(t.flipSlicePrune[0], 0)
        XCTAssertEqual(t.cornersSlicePrune[0], 0)
        XCTAssertEqual(t.udEdgesSlicePrune[0], 0)
        for m in CubeMove.faceMoves {
            let c = CubeCubies.solved.multiplied(.move(m))
            let ts = K.twist(c) * 495 + K.sliceSorted(c) / 24
            XCTAssertLessThanOrEqual(t.twistSlicePrune[ts], 1, m.notation)
            let fs = K.flip(c) * 495 + K.sliceSorted(c) / 24
            XCTAssertLessThanOrEqual(t.flipSlicePrune[fs], 1, m.notation)
        }
        // Một bước pha 2 cách solved ⇒ prune pha 2 đúng bằng 1.
        for p in 0..<10 {
            let c = CubeCubies.solved.multiplied(.move(CubeMove.faceMoves[K.phase2Moves[p]]))
            XCTAssertEqual(t.cornersSlicePrune[K.corners(c) * 24 + K.sliceSorted(c) % 24], 1)
        }
    }

    func testFileHongThiNem() throws {
        XCTAssertThrowsError(try SolverKociembaTables.load(data: Data("KCB0".utf8)))
        XCTAssertThrowsError(try SolverKociembaTables.load(data: Data()))
        let url = try XCTUnwrap(Bundle.main.url(forResource: "kociemba-tables", withExtension: "bin"))
        let full = try Data(contentsOf: url)
        XCTAssertThrowsError(try SolverKociembaTables.load(data: full.prefix(full.count - 10)))
        XCTAssertThrowsError(try SolverKociembaTables.load(data: full.prefix(40)))
    }
}
