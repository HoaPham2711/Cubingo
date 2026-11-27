import SwiftUI

/// Màn đầu: "Which cube do you have?" — lưới thẻ khối. Khối chưa có ⇒ mờ, nhãn SOON, chạm ⇒ alert.
struct FlowPickerView: View {
    @ObservedObject var flow: FlowModel
    let onOpenSettings: () -> Void

    @Environment(\.horizontalSizeClass) private var sizeClass
    @State private var showComingSoon = false

    private var columns: [GridItem] {
        Array(repeating: GridItem(.flexible(), spacing: 14), count: sizeClass == .regular ? 4 : 2)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack(alignment: .top) {
                    Text("Which cube do you have?")
                        .scaledFont(size: 30, weight: .heavy, design: .rounded)
                        .foregroundColor(DSColor.textPrimary)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 12)
                    Button(action: onOpenSettings) {
                        Image(systemName: "gearshape.fill")
                            .scaledFont(size: 20, weight: .semibold)
                            .foregroundColor(DSColor.textPrimary)
                            .frame(width: 44, height: 44)
                            .background(Circle().fill(Color.white))
                    }
                    .accessibilityLabel(Text("Settings"))
                }
                LazyVGrid(columns: columns, spacing: 14) {
                    ForEach(FlowPuzzle.allCases, id: \.self) { p in
                        Button {
                            if p.isAvailable { flow.choose(p) } else { showComingSoon = true }
                        } label: {
                            FlowPuzzleCard(puzzle: p)
                        }
                        .buttonStyle(.plain)
                    }
                }
                Text("Not sure? Count the squares on one side")
                    .scaledFont(size: 15, weight: .medium, design: .rounded)
                    .foregroundColor(DSColor.textSecondary)
                    .frame(maxWidth: .infinity)
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 16)
            .readableContentWidth()
        }
        .styleBackground()
        .toolbar(.hidden, for: .navigationBar)
        .alert("Coming in a future update", isPresented: $showComingSoon) {
            Button("OK", role: .cancel) {}
        }
        .trackScreen("flow_picker")
    }
}

/// Thẻ một khối: biểu tượng lưới màu + tên + mô tả; chưa có ⇒ mờ + nhãn SOON.
private struct FlowPuzzleCard: View {
    let puzzle: FlowPuzzle

    var body: some View {
        VStack(spacing: 10) {
            FlowPuzzleIcon(puzzle: puzzle)
                .frame(width: 76, height: 76)
                .padding(.top, 8)
            Text(puzzle.title)
                .scaledFont(size: 22, weight: .heavy, design: .rounded)
                .foregroundColor(DSColor.textPrimary)
                // Cỡ chữ trợ năng: co chữ thay vì ngắt giữa từ ("Pyrami d").
                .lineLimit(1)
                .minimumScaleFactor(0.5)
            Text(puzzle.subtitle)
                .scaledFont(size: 14, weight: .medium, design: .rounded)
                .foregroundColor(DSColor.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 170)
        .padding(12)
        .overlay(alignment: .topTrailing) {
            if !puzzle.isAvailable {
                Text("SOON")
                    .scaledFont(size: 11, weight: .heavy, design: .rounded)
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Capsule().fill(DSColor.textTertiary))
                    .padding(10)
            }
        }
        .opacity(puzzle.isAvailable ? 1 : 0.55)
        .styleCard()
        .accessibilityElement(children: .combine)
    }
}

/// Biểu tượng: lưới N×N ô bo góc nhiều màu (kim tự tháp: tam giác).
private struct FlowPuzzleIcon: View {
    let puzzle: FlowPuzzle
    private static let palette: [Color] = [
        Color(hex: 0xFF7A00), Color(hex: 0x2DBE60), Color(hex: 0x1E88E5),
        Color(hex: 0xFFD500), Color(hex: 0xE53935), Color(hex: 0xFFFFFF),
    ]

    var body: some View {
        if puzzle == .pyramid {
            Image(systemName: "triangle.fill")
                .resizable()
                .scaledToFit()
                .foregroundStyle(LinearGradient(colors: [Color(hex: 0xFFD500), Color(hex: 0xFF7A00)],
                                                startPoint: .top, endPoint: .bottom))
        } else {
            let n = puzzle.gridSize
            Grid(horizontalSpacing: 3, verticalSpacing: 3) {
                ForEach(0..<n, id: \.self) { r in
                    GridRow {
                        ForEach(0..<n, id: \.self) { c in
                            RoundedRectangle(cornerRadius: 4, style: .continuous)
                                .fill(Self.palette[(r * n + c * 2) % Self.palette.count])
                                .overlay(RoundedRectangle(cornerRadius: 4).strokeBorder(Color.black.opacity(0.08)))
                        }
                    }
                }
            }
            .padding(5)
            .background(RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Color(hex: 0x2B1D14)))
        }
    }
}
