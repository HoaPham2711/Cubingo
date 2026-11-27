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
        // Mặt phẳng của cung: ngay ngoài mặt của lớp (bước mặt) hoặc giữa khối (xoay cả khối, bán kính lớn hơn).
        let offset: Float = spec.layer == 0 ? 0 : Float(spec.layer) * (half + 0.12)
        let radius: Float = spec.layer == 0 ? half * 1.35 : half * 0.8
        let center = axis * offset
        // Hai vector vuông góc với trục.
        let u: SIMD3<Float> = abs(axis.x) > 0.5 ? SIMD3(0, 1, 0) : SIMD3(1, 0, 0)
        let v = simd_cross(axis, u)
        let span = (aa.radians < 0 ? -1 : 1) * Float.pi * 0.55
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
            let seg = ModelEntity(mesh: .generateCylinder(height: len * 0.9, radius: 0.045), materials: [material])
            seg.position = (a + b) / 2
            seg.orientation = simd_quatf(from: SIMD3(0, 1, 0), to: simd_normalize(b - a))
            root.addChild(seg)
        }
        let tip = point(1), before = point(0.97)
        let cone = ModelEntity(mesh: .generateCone(height: 0.3, radius: 0.13), materials: [material])
        cone.position = tip
        cone.orientation = simd_quatf(from: SIMD3(0, 1, 0), to: simd_normalize(tip - before))
        root.addChild(cone)
        return root
    }
}
