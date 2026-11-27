import CoreGraphics
import CoreVideo

/// Lấy màu 9 ô từ khung hình: khung = hình vuông giữa ảnh, cạnh 60 % cạnh ngắn; mỗi ô lấy trung bình vùng giữa 40 %.
/// Ảnh đã xoay đứng (camera đặt `videoRotationAngle = 90`), BGRA 8 bit.
enum ScanSampler {
    static let frameFraction: CGFloat = 0.6
    static let sampleFraction: CGFloat = 0.4

    static func frameRect(in size: CGSize) -> CGRect {
        let side = min(size.width, size.height) * frameFraction
        return CGRect(x: (size.width - side) / 2, y: (size.height - side) / 2, width: side, height: side)
    }

    /// Ô theo hàng (trên → dưới), trong hàng theo cột (trái → phải).
    static func cellRects(n: Int, in size: CGSize) -> [CGRect] {
        let f = frameRect(in: size)
        let cell = f.width / CGFloat(n)
        return (0..<(n * n)).map { i in
            CGRect(x: f.minX + CGFloat(i % n) * cell, y: f.minY + CGFloat(i / n) * cell, width: cell, height: cell)
        }
    }

    static func sampleRect(of cell: CGRect) -> CGRect {
        let inset = cell.width * (1 - sampleFraction) / 2
        return cell.insetBy(dx: inset, dy: inset)
    }

    static func sample(_ buffer: CVPixelBuffer, n: Int) -> [CubeRGB] {
        CVPixelBufferLockBaseAddress(buffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        let w = CVPixelBufferGetWidth(buffer), h = CVPixelBufferGetHeight(buffer)
        let row = CVPixelBufferGetBytesPerRow(buffer)
        guard let raw = CVPixelBufferGetBaseAddress(buffer) else { return [] }
        let base = raw.assumingMemoryBound(to: UInt8.self)
        return cellRects(n: n, in: CGSize(width: w, height: h)).map { cell in
            let r = sampleRect(of: cell)
            let x0 = max(Int(r.minX.rounded(.up)), 0), x1 = min(Int(r.maxX.rounded(.down)), w)
            let y0 = max(Int(r.minY.rounded(.up)), 0), y1 = min(Int(r.maxY.rounded(.down)), h)
            // Bước 2 px: đủ chính xác, nhanh gấp 4 lần.
            var sr = 0, sg = 0, sb = 0, count = 0
            for y in stride(from: y0, to: y1, by: 2) {
                let line = base + y * row
                for x in stride(from: x0, to: x1, by: 2) {
                    let p = line + x * 4
                    sb += Int(p[0])
                    sg += Int(p[1])
                    sr += Int(p[2])
                    count += 1
                }
            }
            guard count > 0 else { return CubeRGB(r: 0, g: 0, b: 0) }
            let d = Double(count) * 255
            return CubeRGB(r: Double(sr) / d, g: Double(sg) / d, b: Double(sb) / d)
        }
    }
}
