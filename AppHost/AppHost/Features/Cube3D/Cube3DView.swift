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

/// Khối 3D bằng RealityKit (`RealityView`, camera ảo). Chỉ MỘT `Cube3DView` được sống trong một navigation stack:
/// `RealityView` thứ hai bị che (màn trước vẫn giữ trong stack) làm view trên cùng không vẽ. Luôn dừng ở `state`; có `animation` mới ⇒ dựng trạng thái
/// trước bước rồi quay lớp tới `state`. Góc nhìn chuẩn lệch 35° sang R, nâng 30° (thấy U, F, R); kéo để xoay xem,
/// thả ra tự về.
struct Cube3DView: View {
    let state: CubeFacelets
    let palette: CubePalette
    let animation: Cube3DAnimation?
    let speed: PrefsSpeed
    let highlight: CubeMove?
    /// Tư thế cả khối (màn quét / quét kiểm tra); `nil` = góc nhìn chuẩn.
    let pose: Cube3DPose?
    /// Màu thô cho từng ô (đè bảng màu).
    let paint: Cube3DPaint?
    /// Mặt có viền phát sáng (khung khối).
    let glow: CubeFace?
    let effect: Cube3DEffect?
    /// Ô đánh dấu đỏ liên tục (ô lệch khi kiểm tra).
    let marked: Set<Int>
    let accessibilityText: String?
    let onAnimationEnd: () -> Void

    init(state: CubeFacelets, palette: CubePalette, animation: Cube3DAnimation?, speed: PrefsSpeed,
         highlight: CubeMove?, pose: Cube3DPose? = nil, paint: Cube3DPaint? = nil, glow: CubeFace? = nil,
         effect: Cube3DEffect? = nil, marked: Set<Int> = [], accessibilityText: String? = nil,
         onAnimationEnd: @escaping () -> Void = {}) {
        self.state = state
        self.palette = palette
        self.animation = animation
        self.speed = speed
        self.highlight = highlight
        self.pose = pose
        self.paint = paint
        self.glow = glow
        self.effect = effect
        self.marked = marked
        self.accessibilityText = accessibilityText
        self.onAnimationEnd = onAnimationEnd
    }

    @State private var controller = Cube3DController()
    @State private var drag: CGSize = .zero

    var body: some View {
        RealityView { content in
            content.camera = .virtual
            controller.install(in: content)
            sync(animated: false)
        } update: { _ in
            sync(animated: true)
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
        .accessibilityLabel(accessibilityText.map { Text($0) } ?? Text("3D cube"))
    }

    private func sync(animated: Bool) {
        controller.update(state: state, palette: palette, animation: animation, speed: speed,
                          highlight: highlight, paint: paint, glow: glow, marked: marked, onEnd: onAnimationEnd)
        controller.setPose(pose, animated: animated)
        controller.play(effect)
    }
}

/// Giữ entity của khối giữa các lần SwiftUI cập nhật.
@MainActor
final class Cube3DController {
    private let world = Entity()
    /// Cha của `cubeRoot`, chỉ để lắc (không đụng tư thế / kéo xoay).
    private let shakeRoot = Entity()
    private let cubeRoot = Entity()
    private var shownPaint: Cube3DPaint??
    private var paint: Cube3DPaint?
    private var flashing: Set<Int> = []
    private var marked: Set<Int> = []
    private var shownMarked: Set<Int>?
    private var dragging = false
    /// Số lần diễn lại động tác (test).
    private(set) var replaysPlayed = 0
    private var shownRGB: [Int: CubeRGB] = [:]
    private var poseOrientation = simd_quatf(angle: 0, axis: SIMD3(0, 1, 0))
    private var poseToken: Int?
    private var poseTask: Task<Void, Never>?
    private var effectToken: Int?
    private var shakeTask: Task<Void, Never>?
    private var flashTask: Task<Void, Never>?
    /// Màu đang vẽ trên từng entity ô — chỉ gán lại vật liệu khi màu thật sự đổi (màu sống cập nhật ~15 lần/giây).
    private var entityRGB: [ObjectIdentifier: CubeRGB] = [:]
    /// Số lần gán vật liệu ô (test).
    private(set) var materialAssignments = 0
    private var glowFace: CubeFace?
    private var glowEntities: [CubeFace: Entity] = [:]
    private var glowTask: Task<Void, Never>?

    /// Màu ô chưa có màu (mặt chưa quét) — sáng hơn thân khối chút để vẫn thấy lưới ô.
    static let blankRGB = CubeRGB(r: 0.16, g: 0.16, b: 0.17)
    static let flashRGB = CubeRGB(r: 0.898, g: 0.282, b: 0.302)

    /// Màu đang vẽ của ô `index` (test).
    func displayedStickerRGB(_ index: Int) -> CubeRGB? { shownRGB[index] }

    /// Hướng đích của khối (góc nhìn chuẩn × tư thế), chưa tính kéo tay.
    var targetOrientation: simd_quatf { rest * poseOrientation }
    private var viewYaw = Cube3DController.yaw
    private var rest: simd_quatf {
        simd_quatf(angle: Self.pitch, axis: SIMD3(1, 0, 0)) * simd_quatf(angle: viewYaw, axis: SIMD3(0, 1, 0))
    }
    private var cubieEntities: [Int: Entity] = [:]
    private var stickerEntities: [Int: [SIMD3<Int>: ModelEntity]] = [:]
    private var scene: Cube3DScene?
    private var shownPalette: CubePalette?
    private var lastToken: Int?
    private var animating = false
    private var arrow: Entity?
    private var shownHighlight: CubeMove??
    private var installed = false
    private var animationTask: Task<Void, Never>?
    private var pivots: [Entity] = []

    /// Trạng thái khối đang hiện (test).
    var displayedFacelets: CubeFacelets? { scene?.facelets() }

    static let yaw: Float = -35 * .pi / 180
    static let pitch: Float = 30 * .pi / 180
    static var restOrientation: simd_quatf {
        simd_quatf(angle: pitch, axis: SIMD3(1, 0, 0)) * simd_quatf(angle: yaw, axis: SIMD3(0, 1, 0))
    }

    /// Gọi ở MỖI lần `RealityView` dựng content: SwiftUI có thể dựng lại `RealityView` mà vẫn giữ controller (@State)
    /// — cảnh phải được thêm vào content mới, không thì khối biến mất.
    func install(in content: RealityViewCameraContent) {
        if !installed {
            installed = true
            let camera = PerspectiveCamera()
            camera.camera.fieldOfViewInDegrees = 38
            camera.position = SIMD3(0, 0, 8.2)
            world.addChild(camera)
            world.addChild(shakeRoot)
            shakeRoot.addChild(cubeRoot)
            cubeRoot.orientation = targetOrientation
        }
        content.add(world)
    }

    func update(state: CubeFacelets, palette: CubePalette, animation: Cube3DAnimation?, speed: PrefsSpeed,
                highlight: CubeMove?, paint: Cube3DPaint? = nil, glow: CubeFace? = nil, marked: Set<Int> = [],
                onEnd: @escaping () -> Void) {
        if cubieEntities.isEmpty || scene?.n != state.n { build(n: state.n) }
        self.paint = paint
        self.marked = marked
        setGlow(glow)
        if let animation, animation.token != lastToken {
            lastToken = animation.token
            // Hoạt ảnh trước chưa xong (bấm Next/Back nhanh): huỷ, trả mọi khối con về gốc — không để lần hoàn tất cũ
            // vẽ đè trạng thái cũ lên trạng thái mới.
            cancelAnimation()
            let move = animation.reverse ? animation.move.inverse : animation.move
            let start = animation.reverse ? state.applying(animation.move) : state.applying(animation.move.inverse)
            // Đứng yên một nhịp với mũi tên của bước, rồi mới quay.
            show(Cube3DScene(start), palette: palette, highlight: animation.reverse ? nil : animation.move)
            animate(move, quarter: speed.quarterTurnSeconds, leadIn: speed.leadInSeconds) { [weak self] in
                guard let self else { return }
                self.show(Cube3DScene(state), palette: palette, highlight: highlight)
                onEnd()
            }
            return
        }
        guard !animating else { return }
        if scene?.facelets() != state || shownPalette != palette || shownHighlight != .some(highlight)
            || shownPaint != .some(paint) || shownMarked != marked {
            show(Cube3DScene(state), palette: palette, highlight: highlight)
        }
    }

    func setDrag(_ t: CGSize) {
        dragging = t != .zero
        guard dragging else { return }
        poseTask?.cancel()
        let yaw = viewYaw + Float(t.width) / 150
        let pitch = max(-80 * .pi / 180, min(80 * .pi / 180, Self.pitch + Float(t.height) / 150))
        cubeRoot.orientation = simd_quatf(angle: pitch, axis: SIMD3(1, 0, 0))
            * simd_quatf(angle: yaw, axis: SIMD3(0, 1, 0)) * poseOrientation
    }

    func resetView(duration: TimeInterval) {
        var t = cubeRoot.transform
        t.rotation = targetOrientation
        cubeRoot.move(to: t, relativeTo: shakeRoot, duration: duration, timingFunction: .easeInOut)
    }

    // MARK: - Tư thế, viền sáng, hiệu ứng

    /// Đổi hướng ⇒ quay mượt; `token` mới + `replayFrom` ⇒ về tức thì `replayFrom` rồi diễn lại động tác.
    func setPose(_ p: Cube3DPose?, animated: Bool) {
        let p = p ?? Cube3DPose(orientation: simd_quatf(angle: 0, axis: SIMD3(0, 1, 0)), token: poseToken ?? 0)
        // Đang kéo tay ⇒ bỏ lượt diễn lại (không giật khối khỏi tay người dùng).
        let replay = p.token != poseToken && poseToken != nil && p.replayFrom != nil && !dragging
        let yaw = p.viewFromLeft ? -Self.yaw : Self.yaw
        let yawChanged = yaw != viewYaw
        viewYaw = yaw
        guard p.orientation != poseOrientation || replay || yawChanged else {
            poseToken = p.token
            return
        }
        let previous = poseOrientation
        poseToken = p.token
        poseOrientation = p.orientation
        poseTask?.cancel()
        guard animated else {
            cubeRoot.orientation = targetOrientation
            return
        }
        var start = previous
        if replay, let from = p.replayFrom {
            replaysPlayed += 1
            start = from
            cubeRoot.orientation = rest * from
        }
        let path = Cube3DPose.waypoints(from: start, to: p.orientation, via: p.via)
        let each = Cube3DPose.turnSeconds * (path.count > 1 ? 0.65 : 1)
        let view = rest
        poseTask = Task { @MainActor [weak self] in
            for q in path {
                guard let self, !Task.isCancelled else { return }
                var t = self.cubeRoot.transform
                t.rotation = view * q
                self.cubeRoot.move(to: t, relativeTo: self.shakeRoot, duration: each,
                                   timingFunction: path.count > 1 ? .linear : .easeInOut)
                try? await Task.sleep(nanoseconds: UInt64(each * 1_000_000_000))
            }
        }
    }

    func play(_ e: Cube3DEffect?) {
        guard let e, e.token != effectToken else { return }
        effectToken = e.token
        switch e.kind {
        case .shake:
            // Lần lắc cũ bị thay ⇒ trả khối về thẳng trước (không để nghiêng dở).
            shakeTask?.cancel()
            shakeRoot.transform.rotation = simd_quatf(angle: 0, axis: SIMD3(0, 1, 0))
            shakeTask = Task { @MainActor [weak self] in
                for a: Float in [0.12, -0.12, 0.08, -0.08, 0] {
                    guard let self, !Task.isCancelled else { return }
                    var t = self.shakeRoot.transform
                    t.rotation = simd_quatf(angle: a, axis: SIMD3(0, 1, 0))
                    self.shakeRoot.move(to: t, relativeTo: self.world, duration: 0.07, timingFunction: .easeInOut)
                    try? await Task.sleep(nanoseconds: 70_000_000)
                }
            }
        case .flash(let indices):
            // Lần nháy cũ bị thay ⇒ ô cũ về màu thường ngay.
            flashTask?.cancel()
            if !flashing.isEmpty {
                flashing = []
                repaint()
            }
            flashTask = Task { @MainActor [weak self] in
                for on in [true, false, true, false] {
                    guard let self, !Task.isCancelled else { return }
                    self.flashing = on ? Set(indices) : []
                    self.repaint()
                    try? await Task.sleep(nanoseconds: 150_000_000)
                }
            }
        }
    }

    private func setGlow(_ face: CubeFace?) {
        guard face != glowFace else { return }
        glowFace = face
        for (f, e) in glowEntities { e.isEnabled = f == face }
        glowTask?.cancel()
        guard let face, let e = glowEntities[face] else { return }
        glowTask = Task { @MainActor [weak self] in
            var phase: Double = 0
            while !Task.isCancelled {
                guard self != nil else { return }
                phase += 0.05 / 1.2
                e.components.set(OpacityComponent(opacity: Float(0.55 + 0.45 * cos(phase * 2 * .pi))))
                try? await Task.sleep(nanoseconds: 50_000_000)
            }
        }
    }

    private func repaint() {
        if let s = scene, let p = shownPalette { show(s, palette: p, highlight: shownHighlight ?? nil) }
    }

    private func makeGlowFrames(n: Int) {
        glowEntities.values.forEach { $0.removeFromParent() }
        glowEntities = [:]
        let half = Float(n) / 2
        let mat = UnlitMaterial(color: Cube3DArrow.color)
        for face in CubeFace.allCases {
            let g = CubeGeometry.of(n: n)
            let nv = g.normals[face.rawValue * n * n]
            let normal = SIMD3<Float>(Float(nv.x), Float(nv.y), Float(nv.z))
            let root = Entity()
            let thick: Float = 0.07, len = 2 * half + 0.07
            for k in 0..<4 {
                let bar = ModelEntity(mesh: .generateBox(width: len, height: thick, depth: 0.04), materials: [mat])
                let along: Float = (k % 2 == 0 ? 1 : -1) * half
                bar.position = k < 2 ? SIMD3(0, along, 0) : SIMD3(along, 0, 0)
                if k >= 2 { bar.orientation = simd_quatf(angle: .pi / 2, axis: SIMD3(0, 0, 1)) }
                root.addChild(bar)
            }
            root.orientation = simd_quatf(from: SIMD3(0, 0, 1), to: normal)
            root.position = normal * (half + 0.03)
            root.isEnabled = false
            cubeRoot.addChild(root)
            glowEntities[face] = root
        }
    }

    // MARK: - Dựng

    private func build(n: Int) {
        cubeRoot.children.removeAll()
        cubieEntities = [:]
        stickerEntities = [:]
        entityRGB = [:]
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
        makeGlowFrames(n: n)
        glowFace = nil
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
        shownPaint = .some(paint)
        shownMarked = marked
        let lit = Set(highlight.map { s.members($0) } ?? [])
        for (i, c) in s.cubies.enumerated() {
            guard let e = cubieEntities[c.id] else { continue }
            e.position = SIMD3<Float>(Float(c.position.x), Float(c.position.y), Float(c.position.z)) / 2
            e.orientation = c.orientation
            for (normal, color) in c.stickers {
                let idx = s.faceletIndex(cubie: i, local: normal)
                var rgb = paint.map { $0.colors[idx] ?? Self.blankRGB } ?? palette.rgb(color)
                if flashing.contains(idx) || marked.contains(idx) { rgb = Self.flashRGB }
                shownRGB[idx] = rgb
                // Sáng nhẹ: đủ thấy lớp sắp quay mà không làm màu đổi tên (đỏ thành hồng…).
                let k: CGFloat = lit.contains(i) ? 0.12 : 0
                let drawn = CubeRGB(r: rgb.r + (1 - rgb.r) * k, g: rgb.g + (1 - rgb.g) * k, b: rgb.b + (1 - rgb.b) * k)
                guard let entity = stickerEntities[c.id]?[normal] else { continue }
                let key = ObjectIdentifier(entity)
                guard entityRGB[key] != drawn else { continue }
                entityRGB[key] = drawn
                materialAssignments += 1
                entity.model?.materials = [UnlitMaterial(color: UIColor(red: drawn.r, green: drawn.g, blue: drawn.b,
                                                                        alpha: 1))]
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

    private func cancelAnimation() {
        animationTask?.cancel()
        animationTask = nil
        for e in cubieEntities.values where e.parent !== cubeRoot { e.setParent(cubeRoot, preservingWorldTransform: true) }
        pivots.forEach { $0.removeFromParent() }
        pivots = []
        animating = false
    }

    /// Quay lớp: gom khối con vào entity cha tạm, quay cha, xong thì trả về gốc. Bước kép = hai nấc, mỗi nấc 0,75 ×
    /// thời lượng (tổng ×1,5).
    private func animate(_ m: CubeMove, quarter: Double, leadIn: Double = 0, completion: @escaping () -> Void) {
        guard var s = scene else { return completion() }
        animating = true
        let steps = m.turns == 2 ? [CubeMove(m.axis, 1), CubeMove(m.axis, 1)] : [m]
        let each = m.turns == 2 ? quarter * 0.75 : quarter
        let ids = s.members(m).map { s.cubies[$0].id }
        let token = lastToken
        animationTask = Task { @MainActor [weak self] in
            if leadIn > 0 { try? await Task.sleep(nanoseconds: UInt64(leadIn * 1_000_000_000)) }
            guard !Task.isCancelled, self?.lastToken == token else { return }
            self?.arrow?.removeFromParent()
            self?.arrow = nil
            for step in steps {
                guard let self, !Task.isCancelled else { return }
                let pivot = Entity()
                self.cubeRoot.addChild(pivot)
                self.pivots.append(pivot)
                for id in ids { self.cubieEntities[id]?.setParent(pivot, preservingWorldTransform: true) }
                let aa = Cube3DScene.axisAngle(step)
                var t = pivot.transform
                t.rotation = simd_quatf(angle: aa.radians, axis: aa.axis)
                pivot.move(to: t, relativeTo: self.cubeRoot, duration: each, timingFunction: .easeInOut)
                try? await Task.sleep(nanoseconds: UInt64(each * 1_000_000_000))
                guard !Task.isCancelled, self.lastToken == token else { return }
                for id in ids { self.cubieEntities[id]?.setParent(self.cubeRoot, preservingWorldTransform: true) }
                pivot.removeFromParent()
                self.pivots.removeAll { $0 === pivot }
                s.apply(step)
                self.scene = s
            }
            guard let self, !Task.isCancelled, self.lastToken == token else { return }
            self.animating = false
            self.animationTask = nil
            completion()
        }
    }
}
