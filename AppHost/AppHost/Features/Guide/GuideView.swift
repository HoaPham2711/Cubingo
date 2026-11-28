import SwiftUI

/// Màn chỉ từng bước: tên chặng + tiến độ, khối 3D có hoạt ảnh, chip hướng cầm, thẻ bước, Back · Replay · Next.
/// Regular size class: hai cột (3D trái; thẻ bước + danh sách bước phải).
struct GuideView: View {
    @ObservedObject var session: GuideSession
    let palette: CubePalette
    @ObservedObject var prefs: PrefsStore
    let onFinish: () -> Void
    /// Quét kiểm tra sau chặng (Teach me). `nil` ⇒ ẩn nút "Check my cube".
    var check: GuideCheckHooks?

    @Environment(\.horizontalSizeClass) private var sizeClass
    @State private var showNotation = false
    /// Đang quét kiểm tra ngay trong màn này (camera + khối, ẩn thẻ bước và nút điều khiển).
    @State private var checking = false
    /// Tự chạy liên tiếp từng bước.
    @State private var autoplay = false
    @State private var autoplayTick = 0

    private var top: CubeColor { SolverPieces.opposite(of: session.base, in: session.state) }

    var body: some View {
        Group {
            if checking, let check, case .stageDone(let kind) = session.phase {
                GuideCheckPanel(session: session, kind: kind, palette: palette, white: check.white, deps: check.deps,
                                onMatched: { checking = false; check.onMatched() },
                                onSkip: { checking = false; check.onSkipped() },
                                onRescan: { checking = false; check.onRescan() })
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
            } else if sizeClass == .regular {
                HStack(alignment: .top, spacing: 24) {
                    VStack(spacing: 14) {
                        header
                        cube
                    }
                    .frame(maxWidth: .infinity)
                    VStack(spacing: 14) {
                        panel
                        if session.phase == .step { stepList }
                    }
                    .frame(width: 380)
                }
                .padding(24)
            } else {
                // Khối lấy hết chỗ trống còn lại (tối thiểu 320 pt); chữ to quá thì cuộn.
                GeometryReader { geo in
                    ScrollView {
                        VStack(spacing: 14) {
                            header
                            cube.frame(minHeight: 320, maxHeight: .infinity)
                            panel
                        }
                        .padding(.horizontal, 20)
                        .padding(.vertical, 8)
                        .frame(minHeight: geo.size.height)
                    }
                }
            }
        }
        .styleBackground()
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Menu {
                    Picker("Animation speed", selection: $prefs.speed) {
                        ForEach(PrefsSpeed.allCases, id: \.self) { Text($0.label).tag($0) }
                    }
                } label: {
                    Image(systemName: "speedometer")
                }
                .accessibilityLabel(Text("Animation speed"))
                Button { showNotation = true } label: { Image(systemName: "questionmark.circle") }
                    .accessibilityLabel(Text("Move notation"))
            }
        }
        .sheet(isPresented: $showNotation) { GuideNotationSheet() }
        .onAppear(perform: openCheckForPreview)
        .onChange(of: session.phase, initial: true) { _, phase in
            if phase != .step { autoplay = false }
            if phase == .finished { onFinish() }
        }
        // Một bước quay xong ⇒ chờ một nhịp rồi tự làm bước kế (nếu vẫn đang tự chạy).
        .task(id: autoplayTick) {
            guard autoplay, autoplayTick > 0 else { return }
            try? await Task.sleep(nanoseconds: UInt64(GuideAutoplay.gap(prefs.speed) * 1_000_000_000))
            guard autoplay, !Task.isCancelled else { return }
            if !GuideAutoplay.tick(session) { autoplay = false }
        }
        .trackScreen("guide_steps")
    }

    // MARK: - Phần

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            if session.mode == .teach {
                Text(GuideText.stageHeader(session.currentStage.kind, base: palette.name(session.base),
                                           top: palette.name(top)))
                    .scaledFont(size: 20, weight: .heavy, design: .rounded)
                    .foregroundColor(DSColor.textPrimary)
                HStack {
                    ProgressView(value: Double(session.stepIndex), total: Double(max(session.stepCount, 1)))
                        .tint(DSColor.accent)
                    Text(GuideText.progress(step: min(session.stepIndex + 1, session.stepCount), of: session.stepCount))
                        .scaledFont(size: 15, weight: .bold, design: .rounded)
                        .foregroundColor(DSColor.textSecondary)
                        .monospacedDigit()
                }
            } else {
                Text(GuideText.quickProgress(step: min(session.stepIndex + 1, session.stepCount), of: session.stepCount))
                    .scaledFont(size: 20, weight: .heavy, design: .rounded)
                    .foregroundColor(DSColor.textPrimary)
                    .monospacedDigit()
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var cube: some View {
        Cube3DView(state: session.state, palette: palette, animation: session.animation, speed: prefs.speed,
                   highlight: session.currentStep?.move,
                   onAnimationEnd: { if autoplay { autoplayTick += 1 } })
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    @ViewBuilder
    private var panel: some View {
        switch session.phase {
        case .stageDone(let kind):
            GuideStageDoneView(kind: kind,
                               title: GuideText.stageTitle(kind, base: palette.name(session.base), top: palette.name(top)),
                               goal: GuideText.stageGoal(kind, base: palette.name(session.base), top: palette.name(top)),
                               onCheck: check.map { c in { startCheck(c) } },
                               onSkip: { session.continueAfterStage() })
            controls(nextEnabled: false)
        case .finished:
            EmptyView()
        case .step:
            if let chip = holdChip {
                GuideHoldChip(top: chip.top, front: chip.front, palette: palette)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            if let step = session.currentStep {
                GuideStepCard(move: step.move, showNotation: prefs.showNotation,
                              reason: session.mode == .teach ? reasonText : nil,
                              algorithm: session.mode == .teach ? step.algorithm : nil)
            }
            controls(nextEnabled: true)
        }
    }

    private func controls(nextEnabled: Bool) -> some View {
        HStack(spacing: 12) {
            Button { autoplay = false; session.back() } label: { Image(systemName: "chevron.backward") }
                .buttonStyle(StyleThickButton(kind: .secondary))
                .frame(width: 64)
                .accessibilityLabel(Text("Back"))
            Button { autoplay = false; session.replay() } label: { Image(systemName: "arrow.counterclockwise") }
                .buttonStyle(StyleThickButton(kind: .secondary))
                .frame(width: 64)
                .accessibilityLabel(Text("Replay"))
            Button { toggleAutoplay() } label: { Image(systemName: autoplay ? "pause.fill" : "play.fill") }
                .buttonStyle(StyleThickButton(kind: .secondary))
                .frame(width: 64)
                .disabled(!nextEnabled)
                .opacity(nextEnabled ? 1 : 0.4)
                .accessibilityLabel(Text(autoplay ? "Pause" : "Play all steps"))
            Button("Next") { autoplay = false; session.next() }
                .buttonStyle(StyleThickButton())
                .disabled(!nextEnabled)
                .opacity(nextEnabled ? 1 : 0.4)
        }
    }

    private func toggleAutoplay() {
        if autoplay {
            autoplay = false
        } else {
            autoplay = true
            if !GuideAutoplay.tick(session) { autoplay = false }
        }
    }

    private var stepList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 6) {
                    ForEach(Array(session.currentStage.steps.enumerated()), id: \.offset) { i, step in
                        HStack(spacing: 12) {
                            Text(verbatim: step.move.notation)
                                .scaledFont(size: 17, weight: .black, design: .rounded)
                                .frame(width: 40, alignment: .leading)
                            Text(GuideText.sentence(step.move))
                                .scaledFont(size: 14, weight: .medium, design: .rounded)
                        }
                        .foregroundColor(i == session.stepIndex ? DSColor.accent
                                         : (i < session.stepIndex ? DSColor.textTertiary : DSColor.textPrimary))
                        .id(i)
                    }
                }
                .padding(14)
            }
            .frame(maxHeight: 320)
            .styleCard()
            .onChange(of: session.stepIndex) { _, i in withAnimation { proxy.scrollTo(i, anchor: .center) } }
        }
    }

    // MARK: - Quét kiểm tra

    private func startCheck(_ c: GuideCheckHooks) {
        if c.deps.cameraAuth.status() == .authorized { checking = true } else { c.onSkipped() }
    }

    private func openCheckForPreview() {
        #if targetEnvironment(simulator)
        if GuidePreviewSeed.openCheck, let check { startCheck(check) }
        #endif
    }

    // MARK: - Chữ

    /// Chip hiện ở bước đầu mỗi chặng (và luôn ở bước đầu Just solve it) và ở mọi bước xoay cả khối.
    private var holdChip: (top: CubeColor, front: CubeColor)? {
        if case let .hold(t, f)? = session.currentStep?.reason { return (t, f) }
        return session.stepIndex == 0 ? session.hold : nil
    }

    /// Lý do của nhóm đang làm = lý do gần nhất (không phải hold) từ đầu chặng tới bước hiện tại.
    private var reasonText: String? {
        let steps = session.currentStage.steps
        guard session.stepIndex < steps.count else { return nil }
        for i in stride(from: session.stepIndex, through: 0, by: -1) {
            if let r = steps[i].reason, !Self.isHold(r) {
                return GuideText.reason(r, palette: palette, base: session.base, top: top)
            }
        }
        return nil
    }

    private static func isHold(_ r: SolverReason) -> Bool {
        if case .hold = r { return true }
        return false
    }
}

/// Những gì màn giải cần để quét kiểm tra sau chặng.
struct GuideCheckHooks {
    let deps: FlowDependencies
    let white: CubeRGB?
    let onMatched: () -> Void
    let onSkipped: () -> Void
    let onRescan: () -> Void
}
