import SwiftUI

/// Quét kiểm tra một mặt sau chặng, NGAY TRONG màn giải (không đẩy route — một RealityView mỗi chồng): camera ở trên,
/// khối của màn giải ở dưới quay mặt cần kiểm ra trước và nhận màu camera sống; mũi tên chỉ cách đưa mặt đó vào camera.
struct GuideCheckPanel: View {
    @ObservedObject var session: GuideSession
    let kind: SolverStageKind
    let palette: CubePalette
    let white: CubeRGB?
    let deps: FlowDependencies
    let onMatched: () -> Void
    let onSkip: () -> Void
    let onRescan: () -> Void

    @StateObject private var camera = ScanCamera()
    @State private var live: [CubeRGB] = []
    @State private var tip: ScanLightTip?
    @State private var token = 0
    @State private var effect: Cube3DEffect?
    @State private var mismatch = false

    private var spec: GuideCheckSpec { GuideCheck.spec(kind) }
    private var onRequestedSide: Bool {
        GuideCheckFlow.isRequestedSide(GuideCheckFlow.faceGrid(live, face: spec.face), palette: palette, white: white,
                                       spec: spec, expected: session.state)
    }

    var body: some View {
        ScanSplitLayout(camera: { cameraPanel }, cube: { cubePanel })
            .overlay { if mismatch { mismatchOverlay } }
            .onAppear {
                camera.start()
                camera.expect(spec.face)
            }
            .onDisappear { camera.stop() }
            .onReceive(camera.$samples) { s in
                guard s.count == 9 else { return }
                live = live.count == 9 ? ScanCaptureModel.smooth(live, s) : s
                tip = ScanLighting.tip(s)
            }
            // Chưa thấy đúng mặt ⇒ nhắc lại mũi tên + động tác mẫu mỗi 2,5 s.
            .task {
                while !Task.isCancelled {
                    try? await Task.sleep(nanoseconds: ScanView.replaySeconds)
                    if !onRequestedSide { token += 1 }
                }
            }
            .trackScreen("guide_check")
    }

    private var cameraPanel: some View {
        let turn = GuideCheckFlow.checkTurn(spec.face)
        return ScanCameraPanel(camera: camera, arrow: turn != .none && !onRequestedSide ? turn : nil,
                               arrowToken: token, tip: tip) {
            Spacer()
            ScanRoundButton(icon: "forward.end.fill", label: String(localized: "Skip check"), action: onSkip)
        }
    }

    private var cubePanel: some View {
        let turn = GuideCheckFlow.checkTurn(spec.face)
        return VStack(spacing: 8) {
            Cube3DView(state: session.state, palette: palette, animation: nil, speed: deps.prefs.speed, highlight: nil,
                       pose: Cube3DPose(orientation: GuideCheckFlow.orientation(spec.face),
                                        replayFrom: turn == .none ? nil : ScanOrientation.rotation(.none),
                                        token: token),
                       paint: GuideCheckFlow.paint(state: session.state, palette: palette, face: spec.face,
                                                   live: onRequestedSide ? live : []),
                       glow: spec.face, effect: effect)
                .aspectRatio(1, contentMode: .fit)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .accessibilityLabel(Text(ScanText.turn(turn)))
            ScanShutterButton(ready: live.count == 9, action: press)
        }
    }

    private func press() {
        switch GuideCheckFlow.press(image: live, palette: palette, white: white, spec: spec, expected: session.state) {
        case .wrongSide:
            deps.haptic(.warning)
            effect = Cube3DEffect(kind: .shake, token: (effect?.token ?? 0) + 1)
        case .match:
            deps.haptic(.success)
            onMatched()
        case .mismatch(let ix):
            deps.haptic(.warning)
            effect = Cube3DEffect(kind: .flash(ix), token: (effect?.token ?? 0) + 1)
            mismatch = true
        }
    }

    private var mismatchOverlay: some View {
        VStack(spacing: 14) {
            Image(systemName: "arrow.triangle.2.circlepath.camera.fill")
                .scaledFont(size: 40, weight: .bold, design: .rounded)
                .foregroundColor(DSColor.accent)
            Text("That side doesn't match")
                .scaledFont(size: 22, weight: .heavy, design: .rounded)
                .foregroundColor(DSColor.textPrimary)
                .multilineTextAlignment(.center)
            Button(action: onRescan) {
                Label("Scan whole cube", systemImage: "camera.viewfinder")
            }
            .buttonStyle(StyleThickButton())
            Button(action: onSkip) {
                Label("Skip", systemImage: "forward.end.fill")
            }
            .buttonStyle(StyleThickButton(kind: .secondary))
        }
        .padding(20)
        .frame(maxWidth: 420)
        .styleCard()
        .padding(24)
    }
}
