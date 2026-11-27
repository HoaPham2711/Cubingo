import RealityKit
import simd
import SwiftUI
import UIKit

/// Yêu cầu phát hoạt ảnh một bước. `token` đổi ⇒ chạy (lại) — Replay phát cùng bước với token mới.
struct Cube3DAnimation: Equatable {
    let move: CubeMove
    /// `true` ⇒ phát bước NGƯỢC (Back): khối đi từ `state.applying(move)` về `state`.
    let reverse: Bool
    let token: Int
}

/// Khối 3D bằng RealityKit (`RealityView`, camera ảo). Luôn dừng ở `state`; có `animation` mới ⇒ dựng trạng thái
/// trước bước rồi quay lớp tới `state`. Góc nhìn chuẩn lệch 35° sang R, nâng 30° (thấy U, F, R); kéo để xoay xem,
/// thả ra tự về.
struct Cube3DView: View {
    let state: CubeFacelets
    let palette: CubePalette
    let animation: Cube3DAnimation?
    let speed: PrefsSpeed
    let highlight: CubeMove?
    let onAnimationEnd: () -> Void

    init(state: CubeFacelets, palette: CubePalette, animation: Cube3DAnimation?, speed: PrefsSpeed,
         highlight: CubeMove?, onAnimationEnd: @escaping () -> Void = {}) {
        self.state = state
        self.palette = palette
        self.animation = animation
        self.speed = speed
        self.highlight = highlight
        self.onAnimationEnd = onAnimationEnd
    }

    @State private var controller = Cube3DController()
    @State private var drag: CGSize = .zero

    var body: some View {
        RealityView { content in
            content.camera = .virtual
            controller.install(in: content)
            controller.update(state: state, palette: palette, animation: animation, speed: speed,
                              highlight: highlight, onEnd: onAnimationEnd)
        } update: { _ in
            controller.update(state: state, palette: palette, animation: animation, speed: speed,
                              highlight: highlight, onEnd: onAnimationEnd)
            controller.setDrag(drag)
        }
        .gesture(
            DragGesture()
                .onChanged { drag = $0.translation }
                .onEnded { _ in
                    drag = .zero
                    controller.resetView(duration: 0.4)
                }
        )
        .accessibilityElement()
        .accessibilityLabel(Text("3D cube"))
    }
}

/// Giữ entity của khối giữa các lần SwiftUI cập nhật.
@MainActor
final class Cube3DController {
    private let world = Entity()
    private let cubeRoot = Entity()
    private var cubieEntities: [Int: Entity] = [:]
    private var stickerEntities: [Int: [SIMD3<Int>: ModelEntity]] = [:]
    private var scene: Cube3DScene?
    private var shownPalette: CubePalette?
    private var lastToken: Int?
    private var animating = false
    private var arrow: Entity?
    private var shownHighlight: CubeMove??
    private var installed = false

    static let yaw: Float = -35 * .pi / 180
    static let pitch: Float = 30 * .pi / 180
    static var restOrientation: simd_quatf {
        simd_quatf(angle: pitch, axis: SIMD3(1, 0, 0)) * simd_quatf(angle: yaw, axis: SIMD3(0, 1, 0))
    }

    func install(in content: RealityViewCameraContent) {
        guard !installed else { return }
        installed = true
        let camera = PerspectiveCamera()
        camera.camera.fieldOfViewInDegrees = 38
        camera.position = SIMD3(0, 0, 8.2)
        world.addChild(camera)
        world.addChild(cubeRoot)
        cubeRoot.orientation = Self.restOrientation
        content.add(world)
    }

    func update(state: CubeFacelets, palette: CubePalette, animation: Cube3DAnimation?, speed: PrefsSpeed,
                highlight: CubeMove?, onEnd: @escaping () -> Void) {
        if cubieEntities.isEmpty || scene?.n != state.n { build(n: state.n) }
        if let animation, animation.token != lastToken {
            lastToken = animation.token
            let move = animation.reverse ? animation.move.inverse : animation.move
            let start = animation.reverse ? state.applying(animation.move) : state.applying(animation.move.inverse)
            show(Cube3DScene(start), palette: palette, highlight: nil)
            animate(move, quarter: speed.quarterTurnSeconds) { [weak self] in
                guard let self else { return }
                self.show(Cube3DScene(state), palette: palette, highlight: highlight)
                onEnd()
            }
            return
        }
        guard !animating else { return }
        if scene?.facelets() != state || shownPalette != palette || shownHighlight != .some(highlight) {
            show(Cube3DScene(state), palette: palette, highlight: highlight)
        }
    }

    func setDrag(_ t: CGSize) {
        guard t != .zero else { return }
        let yaw = Self.yaw + Float(t.width) / 150
        let pitch = max(-80 * .pi / 180, min(80 * .pi / 180, Self.pitch + Float(t.height) / 150))
        cubeRoot.orientation = simd_quatf(angle: pitch, axis: SIMD3(1, 0, 0)) * simd_quatf(angle: yaw, axis: SIMD3(0, 1, 0))
    }

    func resetView(duration: TimeInterval) {
        var t = cubeRoot.transform
        t.rotation = Self.restOrientation
        cubeRoot.move(to: t, relativeTo: world, duration: duration, timingFunction: .easeInOut)
    }

    // MARK: - Dựng

    private func build(n: Int) {
        cubeRoot.children.removeAll()
        cubieEntities = [:]
        stickerEntities = [:]
        let body = SimpleMaterial(color: UIColor(white: 0.08, alpha: 1), roughness: 0.7, isMetallic: false)
        let base = Cube3DScene(.solved(n: n))
        for c in base.cubies {
            let e = ModelEntity(mesh: .generateBox(size: 0.95, cornerRadius: 0.12), materials: [body])
            var stickers: [SIMD3<Int>: ModelEntity] = [:]
            for normal in c.stickers.keys {
                let nf = SIMD3<Float>(Float(normal.x), Float(normal.y), Float(normal.z))
                let s = ModelEntity(mesh: .generateBox(width: 0.8, height: 0.8, depth: 0.02, cornerRadius: 0.1),
                                    materials: [UnlitMaterial(color: .gray)])
                s.position = nf * 0.48
                s.orientation = simd_quatf(from: SIMD3(0, 0, 1), to: nf)
                e.addChild(s)
                stickers[normal] = s
            }
            cubeRoot.addChild(e)
            cubieEntities[c.id] = e
            stickerEntities[c.id] = stickers
        }
        let light = DirectionalLight()
        light.light.intensity = 2500
        light.look(at: .zero, from: SIMD3(2, 4, 5), relativeTo: nil)
        world.addChild(light)
        scene = base
    }

    private func show(_ s: Cube3DScene, palette: CubePalette, highlight: CubeMove?) {
        scene = s
        shownPalette = palette
        shownHighlight = .some(highlight)
        let lit = Set(highlight.map { s.members($0) } ?? [])
        for (i, c) in s.cubies.enumerated() {
            guard let e = cubieEntities[c.id] else { continue }
            e.position = SIMD3<Float>(Float(c.position.x), Float(c.position.y), Float(c.position.z)) / 2
            e.orientation = c.orientation
            for (normal, color) in c.stickers {
                let rgb = palette.rgb(color)
                let k: CGFloat = lit.contains(i) ? 0.28 : 0
                let ui = UIColor(red: rgb.r + (1 - rgb.r) * k, green: rgb.g + (1 - rgb.g) * k,
                                 blue: rgb.b + (1 - rgb.b) * k, alpha: 1)
                stickerEntities[c.id]?[normal]?.model?.materials = [UnlitMaterial(color: ui)]
            }
        }
        arrow?.removeFromParent()
        arrow = nil
        if let highlight {
            let a = Cube3DArrow.make(highlight, half: Float(s.n) / 2)
            cubeRoot.addChild(a)
            arrow = a
        }
    }

    /// Quay lớp: gom khối con vào entity cha tạm, quay cha, xong thì trả về gốc. Bước kép = hai nấc, mỗi nấc 0,75 ×
    /// thời lượng (tổng ×1,5).
    private func animate(_ m: CubeMove, quarter: Double, completion: @escaping () -> Void) {
        guard var s = scene else { return completion() }
        animating = true
        arrow?.removeFromParent()
        arrow = nil
        let steps = m.turns == 2 ? [CubeMove(m.axis, 1), CubeMove(m.axis, 1)] : [m]
        let each = m.turns == 2 ? quarter * 0.75 : quarter
        let ids = s.members(m).map { s.cubies[$0].id }
        Task { @MainActor [weak self] in
            for step in steps {
                guard let self else { return }
                let pivot = Entity()
                self.cubeRoot.addChild(pivot)
                for id in ids { self.cubieEntities[id]?.setParent(pivot, preservingWorldTransform: true) }
                let aa = Cube3DScene.axisAngle(step)
                var t = pivot.transform
                t.rotation = simd_quatf(angle: aa.radians, axis: aa.axis)
                pivot.move(to: t, relativeTo: self.cubeRoot, duration: each, timingFunction: .easeInOut)
                try? await Task.sleep(nanoseconds: UInt64(each * 1_000_000_000))
                for id in ids { self.cubieEntities[id]?.setParent(self.cubeRoot, preservingWorldTransform: true) }
                pivot.removeFromParent()
                s.apply(step)
                self.scene = s
            }
            self?.animating = false
            completion()
        }
    }
}
