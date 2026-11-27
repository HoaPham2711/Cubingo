import simd

/// Một khối con: vị trí (toạ độ nhân đôi như `CubeGeometry`), hướng (quaternion từ hướng ban đầu), nhãn màu theo
/// pháp tuyến BAN ĐẦU (khung của chính khối con).
struct Cube3DCubie: Equatable {
    let id: Int
    var position: SIMD3<Int>
    var orientation: simd_quatf
    let stickers: [SIMD3<Int>: CubeColor]

    /// Hướng có làm tròn (so sánh sau nhiều phép quay số thực).
    func worldNormal(_ local: SIMD3<Int>) -> SIMD3<Int> {
        let v = orientation.act(SIMD3<Float>(Float(local.x), Float(local.y), Float(local.z)))
        return SIMD3(Int(v.x.rounded()), Int(v.y.rounded()), Int(v.z.rounded()))
    }

    static func == (a: Cube3DCubie, b: Cube3DCubie) -> Bool {
        a.id == b.id && a.position == b.position && a.stickers == b.stickers
            && a.stickers.keys.allSatisfy { a.worldNormal($0) == b.worldNormal($0) }
    }
}

/// Mô hình cảnh 3D thuần (không RealityKit) — nguồn sự thật cho `Cube3DView`: test chứng minh cảnh luôn khớp facelet.
struct Cube3DScene: Equatable {
    let n: Int
    private(set) var cubies: [Cube3DCubie]

    init(_ f: CubeFacelets) {
        n = f.n
        let g = CubeGeometry.of(n: f.n)
        var byPosition: [SIMD3<Int>: [SIMD3<Int>: CubeColor]] = [:]
        for i in g.positions.indices { byPosition[g.positions[i], default: [:]][g.normals[i]] = f.stickers[i] }
        let keys = byPosition.keys.sorted { ($0.x, $0.y, $0.z) < ($1.x, $1.y, $1.z) }
        cubies = keys.enumerated().map { id, p in
            Cube3DCubie(id: id, position: p, orientation: simd_quatf(angle: 0, axis: SIMD3(0, 1, 0)),
                        stickers: byPosition[p]!)
        }
    }

    /// Chỉ số (trong `cubies`) của các khối con thuộc lớp mà bước quay.
    func members(_ m: CubeMove) -> [Int] {
        let spec = CubeGeometry.axisSpec(m.axis)
        return cubies.indices.filter { CubeGeometry.inLayer(cubies[$0].position, axis: spec.axis, layer: spec.layer) }
    }

    /// Trục dương + góc (quy tắc bàn tay phải): R = (+x, −π/2), L = (+x, +π/2), U2 = (+y, −π); bước ngược = quay ngược 90°.
    static func axisAngle(_ m: CubeMove) -> (axis: SIMD3<Float>, radians: Float) {
        let spec = CubeGeometry.axisSpec(m.axis)
        var axis = SIMD3<Float>(0, 0, 0)
        axis[spec.axis] = 1
        let quarters: Float = m.turns == 3 ? -1 : Float(m.turns)
        return (axis, Float(spec.sign) * quarters * .pi / 2)
    }

    mutating func apply(_ m: CubeMove) {
        let spec = CubeGeometry.axisSpec(m.axis)
        let aa = Self.axisAngle(m)
        let q = simd_quatf(angle: aa.radians, axis: aa.axis)
        for i in members(m) {
            var p = cubies[i].position
            for _ in 0..<m.turns { p = CubeGeometry.rotate(p, axis: spec.axis, sign: spec.sign) }
            cubies[i].position = p
            cubies[i].orientation = simd_normalize(q * cubies[i].orientation)
        }
    }

    func facelets() -> CubeFacelets {
        let index = Self.stickerIndex(n: n)
        var stickers = [CubeColor](repeating: CubeColor(raw: 0), count: 6 * n * n)
        for c in cubies {
            for (local, color) in c.stickers {
                stickers[index[Key(position: c.position, normal: c.worldNormal(local))]!] = color
            }
        }
        return CubeFacelets(n: n, stickers: stickers)
    }

    private struct Key: Hashable {
        let position: SIMD3<Int>
        let normal: SIMD3<Int>
    }

    private static func stickerIndex(n: Int) -> [Key: Int] {
        let g = CubeGeometry.of(n: n)
        var d: [Key: Int] = [:]
        for i in g.positions.indices { d[Key(position: g.positions[i], normal: g.normals[i])] = i }
        return d
    }
}
