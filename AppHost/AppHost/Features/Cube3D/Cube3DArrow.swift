import RealityKit
import simd
import UIKit

/// Mũi tên THẲNG (ngang hoặc dọc) vẽ sát một mặt thấy được, dọc theo dải ô của lớp sắp quay, chỉ chiều các ô chạy:
/// trục x (R, L, x) ⇒ dọc trên mặt trước; trục y (U, D, y) ⇒ ngang trên mặt trước; trục z (F, B, z) ⇒ ngang trên mặt trên.
/// Bước kép ⇒ hai đầu mũi tên.
enum Cube3DArrow {
    static let color = UIColor(red: 1, green: 0.48, blue: 0, alpha: 1)

    struct Segment: Equatable {
        let start: SIMD3<Float>
        let end: SIMD3<Float>
        let double: Bool
    }

    /// `half` = nửa cạnh khối trong toạ độ cảnh (khối 3×3 cạnh 3 ⇒ 1,5).
    static func segment(_ m: CubeMove, half: Float) -> Segment {
        let aa = Cube3DScene.axisAngle(m)
        let spec = CubeGeometry.axisSpec(m.axis)
        let offset: Float = spec.layer == 0 ? 0 : Float(spec.layer) * (half - 0.5)
        let lift = half + 0.08
        // Mặt hiển thị và hướng của dải: x/y ⇒ mặt trước (+z); z ⇒ mặt trên (+y).
        var p = SIMD3<Float>(0, 0, 0)
        var along = SIMD3<Float>(0, 0, 0)
        switch spec.axis {
        case 0: p = SIMD3(offset, 0, lift); along = SIMD3(0, 1, 0)
        case 1: p = SIMD3(0, offset, lift); along = SIMD3(1, 0, 0)
        default: p = SIMD3(0, lift, offset); along = SIMD3(1, 0, 0)
        }
        // Vận tốc của điểm trên dải khi lớp quay (quy tắc bàn tay phải) ⇒ chiều mũi tên.
        let omega = aa.axis * (aa.radians < 0 ? -1 : 1)
        let v = simd_cross(omega, p)
        let dir: Float = simd_dot(v, along) < 0 ? -1 : 1
        let len = half * 0.85
        return Segment(start: p - along * dir * len, end: p + along * dir * len, double: m.turns == 2)
    }

    @MainActor
    static func make(_ m: CubeMove, half: Float) -> Entity {
        let root = Entity()
        let s = segment(m, half: half)
        let material = UnlitMaterial(color: color)
        let dir = simd_normalize(s.end - s.start)
        let head: Float = 0.42
        let shaftEnd = s.end - dir * head
        let shaftLen = simd_length(shaftEnd - s.start)
        let shaft = ModelEntity(mesh: .generateCylinder(height: shaftLen, radius: 0.075), materials: [material])
        shaft.position = (s.start + shaftEnd) / 2
        shaft.orientation = simd_quatf(from: SIMD3(0, 1, 0), to: dir)
        root.addChild(shaft)
        for k in 0..<(s.double ? 2 : 1) {
            let cone = ModelEntity(mesh: .generateCone(height: head, radius: 0.2), materials: [material])
            cone.position = s.end - dir * (head / 2 + Float(k) * head * 0.9)
            cone.orientation = simd_quatf(from: SIMD3(0, 1, 0), to: dir)
            root.addChild(cone)
        }
        return root
    }
}
