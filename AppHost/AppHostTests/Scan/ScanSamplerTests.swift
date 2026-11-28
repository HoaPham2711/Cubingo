@testable import AppHost
import CoreVideo
import XCTest

final class ScanSamplerTests: XCTestCase {
    func testCellRectsNamTrongKhungVuongGiua() {
        let size = CGSize(width: 1080, height: 1920)
        let frame = ScanSampler.frameRect(in: size)
        XCTAssertEqual(frame.width, 648, accuracy: 0.001)
        XCTAssertEqual(frame.midX, 540, accuracy: 0.001)
        XCTAssertEqual(frame.midY, 960, accuracy: 0.001)
        let cells = ScanSampler.cellRects(n: 3, in: size)
        XCTAssertEqual(cells.count, 9)
        XCTAssertEqual(cells[4].midX, 540, accuracy: 0.001)
        XCTAssertEqual(cells[0].width, 216, accuracy: 0.001)
        XCTAssertEqual(cells[0].minX, frame.minX, accuracy: 0.001)
        XCTAssertEqual(cells[8].maxY, frame.maxY, accuracy: 0.001)
        XCTAssertEqual(ScanSampler.sampleRect(of: cells[0]).width, 86.4, accuracy: 0.001)
        XCTAssertEqual(ScanSampler.sampleRect(of: cells[0]).midX, cells[0].midX, accuracy: 0.001)
    }

    func testLayMauTuPixelBufferTongHop() throws {
        let w = 300, h = 300
        var pb: CVPixelBuffer?
        CVPixelBufferCreate(nil, w, h, kCVPixelFormatType_32BGRA, nil, &pb)
        let buffer = try XCTUnwrap(pb)
        let colors: [(UInt8, UInt8, UInt8)] = (0..<9).map { (i: Int) -> (UInt8, UInt8, UInt8) in
            let r = UInt8(20 * i), g = UInt8(255 - 20 * i), b = UInt8(100 + 10 * i)
            return (r, g, b)
        }
        let cells = ScanSampler.cellRects(n: 3, in: CGSize(width: w, height: h))
        CVPixelBufferLockBaseAddress(buffer, [])
        let base = CVPixelBufferGetBaseAddress(buffer)!.assumingMemoryBound(to: UInt8.self)
        let row = CVPixelBufferGetBytesPerRow(buffer)
        for y in 0..<h {
            for x in 0..<w {
                let p = base + y * row + x * 4
                let k = cells.firstIndex { $0.contains(CGPoint(x: Double(x) + 0.5, y: Double(y) + 0.5)) }
                let (r, g, b) = k.map { colors[$0] } ?? (0, 0, 0)
                p[0] = b; p[1] = g; p[2] = r; p[3] = 255
            }
        }
        CVPixelBufferUnlockBaseAddress(buffer, [])
        let s = ScanSampler.sample(buffer, n: 3)
        XCTAssertEqual(s.count, 9)
        for (i, c) in colors.enumerated() {
            XCTAssertEqual(s[i].r, Double(c.0) / 255, accuracy: 1.0 / 255)
            XCTAssertEqual(s[i].g, Double(c.1) / 255, accuracy: 1.0 / 255)
            XCTAssertEqual(s[i].b, Double(c.2) / 255, accuracy: 1.0 / 255)
        }
    }

    /// Camera để xa hoặc ánh sáng kém: ô lẫn viền đen / bóng (tới 40 %) và vệt chói — màu lấy ra vẫn là màu ô.
    func testMauOBoVienDenVaVetChoi() {
        let sticker = (r: 200, g: 40, b: 30)
        var px: [(Int, Int, Int)] = Array(repeating: sticker, count: 55)
        px += Array(repeating: (12, 12, 14), count: 40)
        px += Array(repeating: (255, 255, 255), count: 5)
        px.shuffle()
        let c = ScanSampler.robustColor(px)
        XCTAssertEqual(c.r, 200.0 / 255, accuracy: 0.02)
        XCTAssertEqual(c.g, 40.0 / 255, accuracy: 0.02)
        XCTAssertEqual(c.b, 30.0 / 255, accuracy: 0.02)
        // Ô đều màu thì như trung bình thường.
        let flat = ScanSampler.robustColor(Array(repeating: (100, 150, 200), count: 30))
        XCTAssertEqual(flat.g, 150.0 / 255, accuracy: 0.005)
        XCTAssertEqual(ScanSampler.robustColor([]).r, 0)
    }
}
