import SwiftUI

/// Thẻ một bước: ký hiệu to (ẩn khi tắt trong Settings) + câu hướng dẫn + (Teach me) lý do và tên công thức.
struct GuideStepCard: View {
    let move: CubeMove
    let showNotation: Bool
    let reason: String?
    let algorithm: SolverAlgorithm?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline, spacing: 14) {
                if showNotation {
                    Text(verbatim: move.notation)
                        .scaledFont(size: 40, weight: .black, design: .rounded)
                        .foregroundColor(DSColor.accent)
                        .accessibilityHidden(true)
                }
                Text(GuideText.sentence(move))
                    .scaledFont(size: 21, weight: .heavy, design: .rounded)
                    .foregroundColor(DSColor.textPrimary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let algorithm {
                Text(GuideText.algorithmName(algorithm))
                    .scaledFont(size: 13, weight: .heavy, design: .rounded)
                    .foregroundColor(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(Capsule().fill(DSColor.accent))
            }
            if let reason {
                Text(reason)
                    .scaledFont(size: 15, weight: .medium, design: .rounded)
                    .foregroundColor(DSColor.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .styleCard()
    }
}
