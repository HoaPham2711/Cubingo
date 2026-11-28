import SwiftUI

/// Chọn cách giải: khối 3D vừa quét + Teach me (mặc định) / Just solve it. Khối đã giải ⇒ chúc mừng.
struct FlowModeView: View {
    @ObservedObject var flow: FlowModel
    let deps: FlowDependencies
    @State private var teachEstimate: Int?

    private var solved: Bool { flow.cube?.isSolved ?? false }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text(solved ? "Already solved! Nice." : "How do you want to solve it?")
                    .scaledFont(size: 28, weight: .heavy, design: .rounded)
                    .foregroundColor(DSColor.textPrimary)
                // Hình tĩnh (Canvas), không RealityView: màn chỉ bước đẩy lên trên phải là RealityView duy nhất.
                if let cube = flow.cube, let palette = flow.palette {
                    Cube3DIsoView(state: cube, palette: palette)
                        .frame(maxWidth: .infinity)
                        .frame(height: 260)
                }
                if solved {
                    Button("Scan another cube") { flow.startOver() }
                        .buttonStyle(StyleThickButton())
                } else {
                    modeCard(title: String(localized: "Teach me"),
                             subtitle: String(localized: "Learn the beginner method in 7 stages"),
                             detail: teachEstimate.map { String(localized: "About \($0) moves") },
                             icon: "graduationcap.fill", selected: true) {
                        Task { await flow.startGuide(.teach, quickSolver: deps.quickSolver) }
                    }
                    modeCard(title: String(localized: "Just solve it"),
                             subtitle: String(localized: "Shortest way, about 20 moves"),
                             detail: nil, icon: "bolt.fill", selected: false) {
                        Task { await flow.startGuide(.quick, quickSolver: deps.quickSolver) }
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .readableContentWidth()
        }
        .styleBackground()
        .navigationBarTitleDisplayMode(.inline)
        // Màn quét đã rời chồng (một RealityView mỗi chồng) ⇒ quay lại = quét lại từ đầu.
        .navigationBarBackButtonHidden(true)
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                Button { flow.rescanFromMode() } label: { Image(systemName: "chevron.left") }
                    .accessibilityLabel(Text("Scan again"))
            }
        }
        .overlay {
            if flow.isSolving {
                VStack(spacing: 12) {
                    ProgressView().controlSize(.large).tint(DSColor.accent)
                    Text("Finding the shortest way…")
                        .scaledFont(size: 17, weight: .bold, design: .rounded)
                        .foregroundColor(DSColor.textPrimary)
                }
                .padding(24)
                .styleCard()
            }
        }
        .alert("Couldn't find a solution. Try Teach me instead.",
               isPresented: Binding(get: { flow.alert == .solverFailed }, set: { if !$0 { flow.alert = nil } })) {
            Button("OK", role: .cancel) {}
        }
        .task {
            guard teachEstimate == nil, let cube = flow.cube, let palette = flow.palette, !cube.isSolved else { return }
            teachEstimate = FlowMode.estimate(teach: SolverBeginner.solve(cube, base: palette.baseColor))
        }
        .trackScreen("flow_mode")
    }

    private func modeCard(title: String, subtitle: String, detail: String?, icon: String, selected: Bool,
                          action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 16) {
                Image(systemName: icon)
                    .scaledFont(size: 26, weight: .bold, design: .rounded)
                    .foregroundColor(selected ? .white : DSColor.accent)
                    .frame(width: 54, height: 54)
                    .background(Circle().fill(selected ? DSColor.accent : DSColor.accent.opacity(0.12)))
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .scaledFont(size: 20, weight: .heavy, design: .rounded)
                        .foregroundColor(DSColor.textPrimary)
                    Text(subtitle)
                        .scaledFont(size: 15, weight: .medium, design: .rounded)
                        .foregroundColor(DSColor.textSecondary)
                    if let detail {
                        Text(detail)
                            .scaledFont(size: 13, weight: .bold, design: .rounded)
                            .foregroundColor(DSColor.accentDark)
                    }
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").foregroundColor(DSColor.textTertiary)
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .styleCard(selected: selected)
        }
        .buttonStyle(.plain)
        .disabled(flow.isSolving)
    }
}
