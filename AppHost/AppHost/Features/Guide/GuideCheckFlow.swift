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

    /// Như `classify` nhưng cân trắng trước bằng mốc của lần quét đầu (bảng màu đo sau cân trắng).
    static func classify(_ samples: [CubeRGB], palette: CubePalette, white: CubeRGB?) -> [CubeColor] {
        classify(white.map { CubeColorMath.whiteBalanced(samples, white: $0) } ?? samples, palette: palette)
    }

    /// Mặt đang thấy có đúng là mặt được yêu cầu không (tâm khớp) — gác tự chụp ở chế độ kiểm tra.
    static func isRequestedSide(_ s: [CubeRGB], palette: CubePalette, white: CubeRGB?, spec: GuideCheckSpec,
                                expected: CubeFacelets) -> Bool {
        guard s.count == 9 else { return false }
        return classify(s, palette: palette, white: white)[4] == expected.center(spec.face)
    }

    static func outcome(samples: [CubeRGB], palette: CubePalette, white: CubeRGB?, spec: GuideCheckSpec,
                        expected: CubeFacelets) -> GuideCheckOutcome {
        GuideCheck.matches(classify(samples, palette: palette, white: white), expected: expected, spec: spec)
            ? .match : .mismatch
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
                    ScanCheckView(flow: flow, deps: deps,
                             mode: .checkFace(GuideCheck.spec(kind), expected: session.state),
                             onFace: { samples in
                                 let o = GuideCheckFlow.outcome(samples: samples, palette: palette,
                                                                white: flow.whiteReference,
                                                                spec: GuideCheck.spec(kind), expected: session.state)
                                 if o == .match {
                                     deps.haptic(.success)
                                     flow.checkMatched()
                                 } else {
                                     deps.haptic(.warning)
                                     mismatch = true
                                 }
                             },
                             onSkip: { flow.checkSkipped() },
                             acceptsFace: { samples in
                                 GuideCheckFlow.isRequestedSide(samples, palette: palette, white: flow.whiteReference,
                                                                spec: GuideCheck.spec(kind), expected: session.state)
                             })
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
