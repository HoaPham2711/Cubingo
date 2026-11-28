import simd
import SwiftUI

/// Chữ của màn quét — CHỈ cho VoiceOver (màn quét không hiện câu hướng dẫn nào).
enum ScanText {
    static func turn(_ t: ScanTurn) -> String {
        switch t {
        case .none: return String(localized: "Point the camera at any side")
        case .left: return String(localized: "Next: turn the whole cube left")
        case .tiltTowardYou: return String(localized: "Next: tilt the top toward you")
        case .flipTowardYou: return String(localized: "Next: tilt the same way twice to show the bottom")
        case .tiltAwayFromYou: return String(localized: "Next: tilt the bottom toward you")
        }
    }

    static func accessibility(step: ScanStep, captured: Int, awaitingTurn: Bool) -> String {
        if captured >= ScanProtocol.cube3.count { return String(localized: "All 6 sides scanned") }
        let count = String(localized: "\(captured) of 6 sides scanned.")
        let next = awaitingTurn ? turn(step.turn) : String(localized: "Hold the side in the frame, then tap Capture")
        return count + " " + next
    }
}

/// Màn quét cả khối (spec thiết kế lại màn quét): camera ở trên (iPad ngang: bên trái), khối 3D ở dưới nhận màu camera
/// sống; nút ✓ chụp từng mặt; chụp xong mũi tên + khối diễn mẫu động tác tới mặt kế tiếp, lặp tới khi người dùng xoay.
struct ScanView: View {
    @ObservedObject var flow: FlowModel
    let deps: FlowDependencies

    @StateObject private var camera = ScanCamera()
    @StateObject private var model = ScanCaptureModel()
    @State private var tip: ScanLightTip?
    @State private var arrowToken = 0
    @State private var poseToken = 0
    @State private var effect: Cube3DEffect?
    @Environment(\.horizontalSizeClass) private var sizeClass

    static let replaySeconds: UInt64 = 2_500_000_000

    var body: some View {
        GeometryReader { geo in
            let wide = sizeClass == .regular && geo.size.width > geo.size.height
            Group {
                if wide {
                    HStack(spacing: 16) {
                        cameraPanel.frame(width: geo.size.width * 0.58)
                        cubePanel
                    }
                } else {
                    VStack(spacing: 8) {
                        cameraPanel.frame(height: geo.size.height * 0.55)
                        cubePanel
                    }
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .styleBackground()
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .onAppear {
            applyPreviewPreset()
            camera.start()
            camera.expect(model.step)
        }
        .onDisappear { camera.stop() }
        .onReceive(camera.$samples) { s in
            guard s.count == 9 else { return }
            model.observe(s)
            tip = ScanLighting.tip(s)
        }
        .onChange(of: model.stepIndex) { _, _ in camera.expect(model.step) }
        // Chưa xoay ⇒ nhắc lại mũi tên và động tác mẫu mỗi 2,5 s.
        .task(id: model.awaitingTurn) {
            while model.awaitingTurn, !Task.isCancelled {
                try? await Task.sleep(nanoseconds: Self.replaySeconds)
                guard model.awaitingTurn, !Task.isCancelled else { return }
                arrowToken += 1
                poseToken += 1
            }
        }
        .trackScreen("scan_camera")
    }

    // MARK: - Camera

    private var cameraPanel: some View {
        GeometryReader { geo in
            let frame = camera.hasLivePreview
                ? ScanPreviewLayer.frameRect(in: geo.size)
                : ScanSampler.frameRect(in: geo.size)
            ZStack(alignment: .topLeading) {
                if camera.hasLivePreview {
                    ScanPreviewLayer(session: camera.session)
                } else {
                    Color(hex: 0x2B1D14)
                }
                ScanFrameOverlay()
                    .frame(width: frame.width, height: frame.height)
                    .offset(x: frame.minX, y: frame.minY)
                if model.awaitingTurn, model.stepIndex < model.steps.count {
                    let r = frame.insetBy(dx: -frame.width * 0.22, dy: -frame.height * 0.22)
                    ScanTurnArrow(turn: model.step.turn, token: arrowToken)
                        .frame(width: r.width, height: r.height)
                        .offset(x: r.minX, y: r.minY)
                }
                topButtons
                if let tip {
                    Image(systemName: tip == .tooDark ? "lightbulb.fill" : "sun.max.fill")
                        .scaledFont(size: 20, weight: .bold, design: .rounded)
                        .foregroundColor(.yellow)
                        .padding(10)
                        .background(Circle().fill(Color.black.opacity(0.45)))
                        .symbolEffect(.pulse)
                        .padding(12)
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
                        .accessibilityLabel(Text(tip == .tooDark ? "Too dark" : "Too much glare"))
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        }
    }

    private var topButtons: some View {
        HStack(spacing: 10) {
            roundButton("chevron.left", label: String(localized: "Back")) { flow.scanBack() }
            Spacer()
            roundButton("square.grid.3x3", label: String(localized: "Enter colors manually")) {
                flow.path.append(.review(manual: true))
            }
            if model.canUndo {
                roundButton("arrow.uturn.backward", label: String(localized: "Undo last side")) { model.undoLast() }
            }
        }
        .padding(12)
    }

    private func roundButton(_ icon: String, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon)
                .scaledFont(size: 16, weight: .bold, design: .rounded)
                .foregroundColor(.white)
                .frame(width: 36, height: 36)
                .background(Circle().fill(Color.black.opacity(0.45)))
        }
        .accessibilityLabel(Text(label))
    }

    // MARK: - Khối

    private var pose: Cube3DPose {
        let i = model.stepIndex
        let from = model.awaitingTurn && i > 0 && i < model.steps.count ? model.steps[i - 1].orientation : nil
        return Cube3DPose(orientation: model.pose, replayFrom: from, token: poseToken, viewFromLeft: true)
    }

    private var cubePanel: some View {
        VStack(spacing: 8) {
            Cube3DView(state: .solved(n: 3), palette: .manualDefault, animation: nil, speed: deps.prefs.speed,
                       highlight: nil, pose: pose, paint: model.paint, glow: model.glowFace, effect: effect)
                .aspectRatio(1, contentMode: .fit)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .accessibilityLabel(Text(ScanText.accessibility(step: model.step, captured: model.capturedCount,
                                                                awaitingTurn: model.awaitingTurn)))
            ZStack {
                Button(action: press) {
                    Image(systemName: "checkmark")
                        .scaledFont(size: 28, weight: .heavy, design: .rounded)
                        .foregroundColor(.white)
                        .frame(width: 64, height: 64)
                        .background(Circle().fill(DSColor.accent))
                        .shadow(color: DSColor.accent.opacity(0.35), radius: 8, y: 3)
                }
                .opacity(model.live.count == 9 || model.capturedCount == model.steps.count ? 1 : 0.4)
                .accessibilityLabel(Text("Capture this side"))
                Text(verbatim: "\(model.capturedCount)/6")
                    .scaledFont(size: 15, weight: .bold, design: .rounded)
                    .foregroundColor(DSColor.textSecondary)
                    .frame(maxWidth: .infinity, alignment: .trailing)
                    .accessibilityHidden(true)
            }
        }
    }

    private func press() {
        switch model.capture() {
        case .accepted:
            deps.haptic(.capture)
            arrowToken += 1
        case .duplicate(let face):
            deps.haptic(.warning)
            let ix = model.steps.first { $0.face == face }?.image ?? []
            effect = Cube3DEffect(kind: .shake, token: (effect?.token ?? 0) + 1)
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 350_000_000)
                effect = Cube3DEffect(kind: .flash(ix), token: (effect?.token ?? 0) + 1)
            }
        case .finished(let r):
            deps.haptic(.success)
            flow.didScan(r)
        case .notReady:
            break
        }
    }

    private func applyPreviewPreset() {
        #if targetEnvironment(simulator)
        ScanPreviewSeed.apply(to: model)
        #endif
    }
}

/// Khung 3×3 trên vùng lấy mẫu: viền nhấn + đường chia ô (không có chấm màu — màu sống hiện trên khối 3D).
private struct ScanFrameOverlay: View {
    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width, h = geo.size.height
            ZStack {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .strokeBorder(DSColor.accent, lineWidth: 3)
                Path { p in
                    for k in 1...2 {
                        let x = w * CGFloat(k) / 3, y = h * CGFloat(k) / 3
                        p.move(to: CGPoint(x: x, y: 0))
                        p.addLine(to: CGPoint(x: x, y: h))
                        p.move(to: CGPoint(x: 0, y: y))
                        p.addLine(to: CGPoint(x: w, y: y))
                    }
                }
                .stroke(DSColor.accent.opacity(0.55), lineWidth: 1.5)
            }
        }
        .accessibilityHidden(true)
    }
}
