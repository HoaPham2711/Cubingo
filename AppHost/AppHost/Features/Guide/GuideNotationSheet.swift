import SwiftUI

/// Bảng ký hiệu: 18 bước mặt + 9 bước xoay cả khối, mỗi bước một câu.
struct GuideNotationSheet: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section("Turning one side") { rows(CubeMove.faceMoves) }
                Section("Turning the whole cube") { rows(CubeMove.rotations) }
            }
            .navigationTitle("Move notation")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
            }
        }
        .trackScreen("guide_notation")
    }

    private func rows(_ moves: [CubeMove]) -> some View {
        ForEach(moves, id: \.self) { m in
            HStack(spacing: 14) {
                Text(verbatim: m.notation)
                    .scaledFont(size: 20, weight: .black, design: .rounded)
                    .foregroundColor(DSColor.accent)
                    .frame(width: 44, alignment: .leading)
                Text(GuideText.sentence(m))
                    .scaledFont(size: 16, weight: .medium, design: .rounded)
                    .foregroundColor(DSColor.textPrimary)
            }
        }
    }
}
