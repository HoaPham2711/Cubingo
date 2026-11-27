@testable import AppHost
import XCTest

final class ScanCameraAuthTests: XCTestCase {
    func testTrangThaiQuyen() {
        XCTAssertEqual(ScanPermissionModel.screen(for: .denied), .denied)
        XCTAssertEqual(ScanPermissionModel.screen(for: .notDetermined), .explain)
        XCTAssertEqual(ScanPermissionModel.screen(for: .authorized), .camera)
        let fake = ScanCameraAuth(status: { .denied }, request: { false })
        XCTAssertEqual(ScanPermissionModel.screen(for: fake.status()), .denied)
    }
}

@MainActor
final class ScanCaptureModelTests: XCTestCase {
    private var grids: [CubeFace: [CubeRGB]] = [:]
    private var state: CubeFacelets!

    override func setUp() {
        var rng = CubeRandom(seed: 77)
        state = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
        let samples = ScanFixtures.samples(for: state, palette: .manualDefault, .daylight, seed: 4)
        for face in CubeFace.allCases { grids[face] = Array(samples[(face.rawValue * 9)..<(face.rawValue * 9 + 9)]) }
    }

    func testDiHetGiaoThucRaKetQua() {
        let m = ScanCaptureModel()
        for face: CubeFace in [.f, .r, .b, .l, .f, .u, .d] {
            XCTAssertNil(m.result)
            m.capture(grids[face]!)
            XCTAssertNil(m.message, "\(face)")
        }
        XCTAssertEqual(m.result?.facelets, state)
        XCTAssertEqual(m.capturedCount, 6)
    }

    func testQuayVeMatDauPhaiDungTamF() {
        let m = ScanCaptureModel()
        for face: CubeFace in [.f, .r, .b, .l] { m.capture(grids[face]!) }
        XCTAssertEqual(m.step.instruction, .backToFirst)
        m.capture(grids[.r]!)
        XCTAssertEqual(m.message, .notFirstSide)
        XCTAssertEqual(m.step.instruction, .backToFirst)
        m.capture(grids[.f]!)
        XCTAssertEqual(m.step.instruction, .tiltTopToYou)
    }

    func testMatDaQuetThiKhongNhan() {
        let m = ScanCaptureModel()
        m.capture(grids[.f]!)
        m.capture(grids[.f]!)
        XCTAssertEqual(m.message, .alreadyScanned)
        XCTAssertEqual(m.capturedCount, 1)
        // Tự chụp chỉ khi tâm khác tâm vừa chụp.
        XCTAssertFalse(m.allowsAutoCapture(grids[.f]!))
        XCTAssertTrue(m.allowsAutoCapture(grids[.r]!))
    }
}
