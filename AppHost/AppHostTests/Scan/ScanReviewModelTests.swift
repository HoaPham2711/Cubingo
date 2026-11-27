@testable import AppHost
import XCTest

@MainActor
final class ScanReviewModelTests: XCTestCase {
    private func state(_ seed: UInt64) -> CubeFacelets {
        var rng = CubeRandom(seed: seed)
        return CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
    }

    private func scan(_ f: CubeFacelets, ambiguous: (CubeColor, CubeColor)? = nil) -> ScanResult {
        ScanResult(facelets: f, palette: .manualDefault, confidence: Array(repeating: 30, count: 54),
                   ambiguousCenters: ambiguous)
    }

    func testQuetDungThiOk() {
        let f = state(1)
        let m = ScanReviewModel(scan: scan(f))
        XCTAssertEqual(m.validate(), .ok(f))
        XCTAssertNil(m.issue)
    }

    func testDemMauVaSuaMotO() {
        let f = state(2)
        var bad = f
        let i = (0..<54).first { $0 % 9 != 4 && f.stickers[$0] == CubeColor(raw: 4) }!
        bad.stickers[i] = CubeColor(raw: 1)
        var conf = Array(repeating: 30.0, count: 54)
        conf[i] = 1
        let m = ScanReviewModel(scan: ScanResult(facelets: bad, palette: .manualDefault, confidence: conf,
                                                 ambiguousCenters: nil))
        guard case .issue(.colorCount)? = Optional(m.validate()) else { return XCTFail("phải là lỗi đếm màu") }
        XCTAssertTrue(m.suspects.contains(i))
        m.set(i, to: CubeColor(raw: 4))
        XCTAssertEqual(m.validate(), .ok(f))
        XCTAssertEqual(m.suspects, [])
    }

    func testMienKhongTonTaiChiRaO() {
        var f = CubeFacelets.solved(n: 3)
        f.stickers[19] = CubeColor(.d)
        f.stickers[32] = CubeColor(.f)
        let m = ScanReviewModel(scan: scan(f))
        guard case .issue(.impossiblePiece)? = Optional(m.validate()) else { return XCTFail("phải là miếng lạ") }
        XCTAssertTrue(m.suspects.isSuperset(of: [7, 19]))
    }

    func testTuSuaHuongMatTren() {
        // Tìm trạng thái mà xoay lưới U 1 nấc có tổ hợp sửa duy nhất.
        for seed in 3..<60 {
            let f = state(UInt64(seed))
            let rotated = CubeValidation.rotatingGrid(f, .u, 1)
            guard CubeValidation.repairScanOrientation(rotated) == f else { continue }
            let m = ScanReviewModel(scan: scan(rotated))
            XCTAssertEqual(m.validate(), .autoFixed(f))
            XCTAssertEqual(m.facelets, f.stickers.map { Optional($0) })
            return
        }
        XCTFail("không tìm được trạng thái mẫu")
    }

    func testNhapTayThieuOVaKhongTuSua() {
        let m = ScanReviewModel(manualCenters: ScanReviewModel.defaultManualCenters)
        XCTAssertEqual(m.validate(), .incomplete(missing: 48))
        XCTAssertEqual(m.palette.colorName(CubeColor(.f)), .green)
        for seed in 3..<60 {
            let f = state(UInt64(seed))
            let rotated = CubeValidation.rotatingGrid(f, .u, 1)
            guard CubeValidation.firstIssue(rotated, confidence: nil) != nil,
                  CubeValidation.repairScanOrientation(rotated) != nil else { continue }
            let manual = ScanReviewModel(manualCenters: ScanReviewModel.defaultManualCenters)
            for i in 0..<54 where i % 9 != 4 { manual.set(i, to: rotated.stickers[i]) }
            guard case .issue? = Optional(manual.validate()) else { return XCTFail("nhập tay không được tự sửa") }
            return
        }
        XCTFail("không tìm được trạng thái mẫu")
    }

    func testDoiTamNhapTayKhongTrung() {
        let m = ScanReviewModel(manualCenters: ScanReviewModel.defaultManualCenters)
        let before = m.palette
        m.setCenter(.f, to: .white)
        XCTAssertEqual(m.palette, before, "trắng đã là tâm U")
        m.setCenter(.f, to: .black)
        XCTAssertEqual(m.palette, before, "không có đen")
        m.setCenter(.f, to: .purple)
        XCTAssertEqual(m.palette.colorName(CubeColor(.f)), .purple)
    }

    func testTamGiongNhauChanChoToiKhiSua() {
        let f = state(4)
        let m = ScanReviewModel(scan: scan(f, ambiguous: (CubeColor(.r), CubeColor(.l))))
        XCTAssertEqual(m.validate(), .ambiguousCenters)
        // Sửa một ô của mặt khác ⇒ vẫn chặn.
        m.set(CubeFace.u.rawValue * 9, to: f.stickers[CubeFace.u.rawValue * 9])
        XCTAssertEqual(m.validate(), .ambiguousCenters)
        m.set(CubeFace.r.rawValue * 9, to: f.stickers[CubeFace.r.rawValue * 9])
        XCTAssertEqual(m.validate(), .ok(f))
    }

    func testThongBaoChepDungSpec() {
        let p = CubePalette.manualDefault
        XCTAssertEqual(ScanReviewText.message(.issue(.colorCount(over: CubeColor(raw: 1), under: CubeColor(raw: 4),
                                                                overCount: 10, underCount: 8, suspects: [])),
                                              palette: p),
                       "You have 10 red and 8 orange. One square is probably wrong.")
        XCTAssertEqual(ScanReviewText.message(.incomplete(missing: 48), palette: p), "48 squares left to fill.")
        XCTAssertEqual(ScanReviewText.message(.ok(.solved(n: 3)), palette: p), "Looks right — let's go!")
        XCTAssertEqual(ScanReviewText.message(.issue(.swappedPieces), palette: p),
                       "Two pieces are swapped — this happens when a cube was taken apart and put back.")
    }
}
