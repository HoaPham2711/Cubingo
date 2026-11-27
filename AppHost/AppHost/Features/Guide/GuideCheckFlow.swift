import SwiftUI

enum GuideCheckOutcome: Equatable { case match, mismatch }

/// Quét kiểm tra một mặt sau chặng: gán mỗi ô màu gần nhất của bảng màu (ΔE76) rồi so với trạng thái mong đợi.
enum GuideCheckFlow {
    static func classify(_ samples: [CubeRGB], palette: CubePalette) -> [CubeColor] {
        let keys = palette.colors.keys.sorted { $0.raw < $1.raw }
        return samples.map { s in
            keys.min { CubeColorMath.deltaE(s, palette.rgb($0)) < CubeColorMath.deltaE(s, palette.rgb($1)) }!
        }
    }

    static func outcome(samples: [CubeRGB], palette: CubePalette, spec: GuideCheckSpec,
                        expected: CubeFacelets) -> GuideCheckOutcome {
        GuideCheck.matches(classify(samples, palette: palette), expected: expected, spec: spec) ? .match : .mismatch
    }
}

/// Đích `.check`: chụp MỘT mặt theo `GuideCheck.spec` của chặng vừa xong. Khớp ⇒ sang chặng sau. Lệch ⇒ mời quét lại
/// cả khối (lập lại lời giải từ trạng thái mới, giữ màu nền).
struct GuideCheckView: View {
    @ObservedObject var flow: FlowModel
    let deps: FlowDependencies
    @State private var mismatch = false

    var body: some View {
        Group {
            if let session = flow.session, case .stageDone(let kind) = session.phase, let palette = flow.palette {
                if mismatch {
                    mismatchView
                } else if deps.cameraAuth.status() == .authorized {
                    ScanView(flow: flow, deps: deps,
                             mode: .checkFace(GuideCheck.spec(kind), expected: session.state),
                             onFace: { samples in
                                 let o = GuideCheckFlow.outcome(samples: samples, palette: palette,
                                                                spec: GuideCheck.spec(kind), expected: session.state)
                                 if o == .match {
                                     deps.haptic(.success)
                                     flow.checkMatched()
                                 } else {
                                     deps.haptic(.warning)
                                     mismatch = true
                                 }
                             },
                             onSkip: { flow.checkSkipped() })
                } else {
                    ScanPermissionView(screen: .denied, onAllow: {}, onManual: { flow.checkSkipped() })
                }
            }
        }
        .trackScreen("guide_check")
    }

    private var mismatchView: some View {
        VStack(spacing: 18) {
            Spacer()
            Image(systemName: "arrow.triangle.2.circlepath.camera.fill")
                .scaledFont(size: 54, weight: .bold, design: .rounded)
                .foregroundColor(DSColor.accent)
            Text("Looks different from what we expected — no worries")
                .scaledFont(size: 24, weight: .heavy, design: .rounded)
                .foregroundColor(DSColor.textPrimary)
                .multilineTextAlignment(.center)
            Text("Scan the whole cube and we'll make a new plan from where you are.")
                .scaledFont(size: 16, weight: .medium, design: .rounded)
                .foregroundColor(DSColor.textSecondary)
                .multilineTextAlignment(.center)
            Spacer()
            Button("Scan the whole cube") { flow.startRescan() }
                .buttonStyle(StyleThickButton())
            Button("Skip check") { flow.checkSkipped() }
                .buttonStyle(StyleThickButton(kind: .secondary))
        }
        .padding(24)
        .frame(maxWidth: 560)
        .frame(maxWidth: .infinity)
        .styleBackground()
    }
}
