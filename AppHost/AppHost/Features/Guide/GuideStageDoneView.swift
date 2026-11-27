import SwiftUI

/// Hết một chặng của Teach me: chúc mừng + quét kiểm tra (Task 16) hoặc bỏ qua.
struct GuideStageDoneView: View {
    let kind: SolverStageKind
    let title: String
    let goal: String
    let onCheck: (() -> Void)?
    let onSkip: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.seal.fill")
                .scaledFont(size: 54, weight: .bold, design: .rounded)
                .foregroundColor(DSColor.statusGood)
            Text("Stage complete!")
                .scaledFont(size: 28, weight: .heavy, design: .rounded)
                .foregroundColor(DSColor.textPrimary)
            Text(title)
                .scaledFont(size: 19, weight: .bold, design: .rounded)
                .foregroundColor(DSColor.accentDark)
            Text(goal)
                .scaledFont(size: 15, weight: .medium, design: .rounded)
                .foregroundColor(DSColor.textSecondary)
                .multilineTextAlignment(.center)
            if let onCheck {
                Button("Check my cube", action: onCheck)
                    .buttonStyle(StyleThickButton())
            }
            Button("Skip check", action: onSkip)
                .buttonStyle(StyleThickButton(kind: onCheck == nil ? .primary : .secondary))
        }
        .padding(22)
        .frame(maxWidth: .infinity)
        .styleCard()
        .trackScreen("guide_stage_done")
    }
}
