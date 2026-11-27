import RealityKit
import simd
import UIKit

/// Mũi tên cong quanh trục của lớp sắp quay: 8 trụ nhỏ dọc một cung + đầu nón, theo đúng chiều của bước.
enum Cube3DArrow {
    static let color = UIColor(red: 1, green: 0.48, blue: 0, alpha: 1)

    /// `half` = nửa cạnh khối trong toạ độ cảnh (khối 3×3 cạnh 3 ⇒ 1,5).
    @MainActor
    static func make(_ m: CubeMove, half: Float) -> Entity {
        let root = Entity()
        let aa = Cube3DScene.axisAngle(m)
        let spec = CubeGeometry.axisSpec(m.axis)
        let axis = aa.axis
        // Vòng quanh lớp (giữa lớp ngoài; xoay cả khối: giữa khối), bán kính lớn hơn khối, cung hướng về phía camera
        // của góc nhìn chuẩn — lớp ở mặt khuất (L, D, B) vẫn thấy mũi tên.
        let offset: Float = spec.layer == 0 ? 0 : Float(spec.layer) * (half - 0.5)
        let radius: Float = half * (spec.layer == 0 ? 1.45 : 1.3)
        let center = axis * offset
        let view = simd_normalize(SIMD3<Float>(0.45, 0.5, 0.75))
        let u = simd_normalize(view - simd_dot(view, axis) * axis)
        let v = simd_cross(axis, u)
        let span = (aa.radians < 0 ? -1 : 1) * Float.pi * 0.6
        let start: Float = -span / 2
        let material = UnlitMaterial(color: color)
        func point(_ t: Float) -> SIMD3<Float> {
            let a = start + span * t
            return center + radius * (cos(a) * u + sin(a) * v)
        }
        let segments = 8
        for i in 0..<segments {
            let a = point(Float(i) / Float(segments)), b = point(Float(i + 1) / Float(segments))
            let len = simd_length(b - a)
            let seg = ModelEntity(mesh: .generateCylinder(height: len * 0.9, radius: 0.06), materials: [material])
            seg.position = (a + b) / 2
            seg.orientation = simd_quatf(from: SIMD3(0, 1, 0), to: simd_normalize(b - a))
            root.addChild(seg)
        }
        let tip = point(1), before = point(0.97)
        let cone = ModelEntity(mesh: .generateCone(height: 0.36, radius: 0.16), materials: [material])
        cone.position = tip
        cone.orientation = simd_quatf(from: SIMD3(0, 1, 0), to: simd_normalize(tip - before))
        root.addChild(cone)
        return root
    }
}
