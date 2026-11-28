@testable import AppHost
import XCTest

final class ScanOrientationTests: XCTestCase {
    /// Bảng tính tay (spec "Thứ tự quét và động tác"): độc lập với cách `imageIndices` tính.
    func testChiSoAnhTheoBangTay() {
        let s = ScanProtocol.cube3
        XCTAssertEqual(s.map(\.face), [.f, .r, .b, .l, .u, .d])
        XCTAssertEqual(s.map(\.turn), [.none, .left, .left, .left, .tiltTowardYou, .flipTowardYou])
        XCTAssertEqual(s[0].image, Array(18...26))
        XCTAssertEqual(s[1].image, Array(9...17))
        XCTAssertEqual(s[2].image, Array(45...53))
        XCTAssertEqual(s[3].image, Array(36...44))
        // Từ L nghiêng mặt trên về phía mình: L ở dưới ảnh, B bên trái.
        XCTAssertEqual(s[4].image, [2, 5, 8, 1, 4, 7, 0, 3, 6])
        // Lật thêm 180°: R ở dưới, L ở trên, B bên trái.
        XCTAssertEqual(s[5].image, [33, 30, 27, 34, 31, 28, 35, 32, 29])
        for st in s { XCTAssertEqual(ScanOrientation.frontFace(st.orientation), st.face) }
    }

    func testKiemTraTrongManGiai() {
        XCTAssertEqual(ScanOrientation.imageIndices(ScanOrientation.rotation(.none)), Array(18...26))
        XCTAssertEqual(ScanOrientation.frontFace(ScanOrientation.rotation(.tiltTowardYou)), .u)
        XCTAssertEqual(ScanOrientation.frontFace(ScanOrientation.rotation(.tiltTowardYou).inverse), .d)
    }

    func testGhepAnhRaDungKhoi() {
        var rng = CubeRandom(seed: 9)
        let f = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
        let samples = ScanFixtures.samples(for: f, palette: .manualDefault, .daylight, seed: 3)
        let images = ScanProtocol.cube3.map { st in st.image.map { samples[$0] } }
        XCTAssertEqual(ScanProtocol.assemble(images), samples)
    }
}
