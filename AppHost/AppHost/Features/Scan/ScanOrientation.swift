import simd

/// Động tác người dùng làm với cả khối trước khi chụp một mặt.
enum ScanTurn: Equatable {
    /// Không có (mặt đầu tiên, hoặc mặt trước khi kiểm tra).
    case none
    /// Xoay cả khối sang trái 90°: mặt phải ra trước.
    case left
    /// Lật mặt trên về phía mình 90°: mặt trên ra trước.
    case tiltTowardYou
    /// Lật tiếp 180° cùng chiều `tiltTowardYou`.
    case flipTowardYou
}

/// Toán hướng khối khi quét (thuần, không RealityKit). Khung khối: x sang phải (R), y lên (U), z về phía camera (F) —
/// như `CubeGeometry`. Quaternion đưa khung khối sang khung thế giới; camera nhìn từ +z về −z, ảnh đọc theo hàng
/// (hàng 0 trên cùng = y lớn nhất, cột 0 bên trái = x nhỏ nhất).
enum ScanOrientation {
    static func rotation(_ t: ScanTurn) -> simd_quatf {
        switch t {
        case .none: return simd_quatf(angle: 0, axis: SIMD3(0, 1, 0))
        case .left: return simd_quatf(angle: -.pi / 2, axis: SIMD3(0, 1, 0))
        case .tiltTowardYou: return simd_quatf(angle: .pi / 2, axis: SIMD3(1, 0, 0))
        case .flipTowardYou: return simd_quatf(angle: .pi, axis: SIMD3(1, 0, 0))
        }
    }

    /// 9 chỉ số facelet (thứ tự Kociemba) camera thấy, theo thứ tự đọc ảnh.
    static func imageIndices(_ q: simd_quatf, n: Int = 3) -> [Int] {
        let g = CubeGeometry.of(n: n)
        let front = g.normals.indices.filter { round(q.act(vec(g.normals[$0]))) == SIMD3(0, 0, 1) }
        return front.sorted { a, b in
            let pa = q.act(vec(g.positions[a])), pb = q.act(vec(g.positions[b]))
            if abs(pa.y - pb.y) > 0.5 { return pa.y > pb.y }
            return pa.x < pb.x
        }
    }

    /// Mặt (theo nhãn khung khối) đang hướng vào camera.
    static func frontFace(_ q: simd_quatf, n: Int = 3) -> CubeFace {
        let g = CubeGeometry.of(n: n)
        let i = g.normals.indices.first { round(q.act(vec(g.normals[$0]))) == SIMD3(0, 0, 1) }!
        return CubeFace(rawValue: i / (n * n))!
    }

    private static func vec(_ v: SIMD3<Int>) -> SIMD3<Float> { SIMD3(Float(v.x), Float(v.y), Float(v.z)) }
    private static func round(_ v: SIMD3<Float>) -> SIMD3<Int> {
        SIMD3(Int(v.x.rounded()), Int(v.y.rounded()), Int(v.z.rounded()))
    }
}
