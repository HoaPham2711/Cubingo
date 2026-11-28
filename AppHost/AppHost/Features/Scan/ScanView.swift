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

    static let replaySeconds: UInt64 = 2_500_000_000

    var body: some View {
        ScanSplitLayout(camera: { cameraPanel }, cube: { cubePanel })
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
        ScanCameraPanel(camera: camera,
                        arrow: model.awaitingTurn && model.stepIndex < model.steps.count ? model.step.turn : nil,
                        arrowToken: arrowToken, tip: tip) {
            ScanRoundButton(icon: "chevron.left", label: String(localized: "Back")) { flow.scanBack() }
            Spacer()
            ScanRoundButton(icon: "square.grid.3x3", label: String(localized: "Enter colors manually")) {
                flow.path.append(.review(manual: true))
            }
            if model.canUndo {
                ScanRoundButton(icon: "arrow.uturn.backward", label: String(localized: "Undo last side")) {
                    model.undoLast()
                }
            }
        }
    }

    // MARK: - Khối

    private var pose: Cube3DPose {
        let i = model.stepIndex
        let from = model.awaitingTurn && i > 0 && i < model.steps.count ? model.steps[i - 1].orientation : nil
        return Cube3DPose(orientation: model.pose, replayFrom: from, token: poseToken, viewFromLeft: true,
                          via: ScanProtocol.flipMidpoint)
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
                ScanShutterButton(ready: model.live.count == 9 || model.capturedCount == model.steps.count,
                                  action: press)
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
