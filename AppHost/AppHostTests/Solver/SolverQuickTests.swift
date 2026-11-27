@testable import AppHost
import XCTest

/// Chạy ở -O0: mỗi lời giải cỡ 0,05–0,5 s ⇒ class này được phép > 2 s (30 trạng thái ngẫu nhiên là bằng chứng chính
/// rằng Just solve it không bao giờ chỉ sai bước).
final class SolverQuickTests: XCTestCase {
    private let solver = SolverQuick(tables: { solverTestTables })

    func testLoiGiaiLuonDungTrenTrangThaiNgauNhien() async throws {
        var rng = CubeRandom(seed: 11)
        for i in 0..<30 {
            let c = CubeRandom.state(using: &rng)
            let moves = try await solver.solve(c, timeout: .seconds(3))
            XCTAssertEqual(c.applying(moves), .solved, "trạng thái \(i)")
            XCTAssertLessThanOrEqual(moves.count, 30)
            XCTAssertFalse(moves.contains(where: \.isRotation))
        }
    }

    func testKhoiDaGiaiVaMotBuoc() async throws {
        let none = try await solver.solve(.solved)
        XCTAssertEqual(none, [])
        for m in CubeMove.faceMoves {
            let c = CubeCubies.solved.multiplied(.move(m))
            let s = try await solver.solve(c)
            XCTAssertEqual(s, [m.inverse], m.notation)
        }
    }

    func testSuperflip() async throws {
        var c = CubeCubies.solved
        c.eo = Array(repeating: 1, count: 12)
        let moves = try await solver.solve(c, timeout: .seconds(5))
        XCTAssertEqual(c.applying(moves), .solved)
    }

    func testHuyDuoc() async {
        var c = CubeCubies.solved
        c.eo = Array(repeating: 1, count: 12)
        let solver = self.solver
        let task = Task { try await solver.solve(c, maxLength: 18, timeout: .seconds(30)) }
        task.cancel()
        do {
            _ = try await task.value
            XCTFail("phải ném CancellationError")
        } catch {
            XCTAssertTrue(error is CancellationError, "\(error)")
        }
    }

    func testNapBangLoiThiNem() async {
        struct Boom: Error {}
        let broken = SolverQuick(tables: { throw Boom() })
        do {
            _ = try await broken.solve(.solved)
            XCTFail("phải ném")
        } catch {
            XCTAssertTrue(error is Boom)
        }
    }
}
