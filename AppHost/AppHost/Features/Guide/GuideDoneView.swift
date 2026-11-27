import SwiftUI

/// Màn xong: confetti 1,5 s + rung + số bước và thời gian.
struct GuideDoneView: View {
    @ObservedObject var flow: FlowModel
    let deps: FlowDependencies
    @State private var start = Date()

    private var moves: Int { flow.session?.movesDone ?? 0 }
    private var elapsed: String {
        let t = Int(flow.session?.elapsed ?? 0)
        return String(format: "%d:%02d", t / 60, t % 60)
    }

    var body: some View {
        ZStack {
            VStack(spacing: 18) {
                Spacer()
                Image(systemName: "star.circle.fill")
                    .scaledFont(size: 80, weight: .bold, design: .rounded)
                    .foregroundColor(DSColor.accent)
                Text("Solved!")
                    .scaledFont(size: 40, weight: .black, design: .rounded)
                    .foregroundColor(DSColor.textPrimary)
                Text("\(moves) moves · \(elapsed)")
                    .scaledFont(size: 20, weight: .bold, design: .rounded)
                    .foregroundColor(DSColor.textSecondary)
                Spacer()
                Button("Solve another cube") { flow.startOver() }
                    .buttonStyle(StyleThickButton())
            }
            .padding(24)
            .frame(maxWidth: 560)
            GuideConfetti(start: start)
                .allowsHitTesting(false)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .styleBackground()
        .navigationBarBackButtonHidden(true)
        .onAppear {
            start = Date()
            deps.haptic(.success)
        }
        .trackScreen("guide_done")
    }
}

/// Hạt confetti vẽ bằng `Canvas` trong 1,5 s rồi tắt.
private struct GuideConfetti: View {
    let start: Date
    private static let colors: [Color] = [
        Color(hex: 0xFF7A00), Color(hex: 0x2DBE60), Color(hex: 0x1E88E5), Color(hex: 0xFFD500), Color(hex: 0xE53935),
    ]

    var body: some View {
        TimelineView(.animation) { context in
            let t = context.date.timeIntervalSince(start)
            Canvas { ctx, size in
                guard t < 1.5 else { return }
                for i in 0..<60 {
                    let seed = Double(i)
                    let x = (sin(seed * 12.9898) * 0.5 + 0.5) * size.width
                    let speed = 300 + (sin(seed * 78.233) * 0.5 + 0.5) * 400
                    let y = -20 + speed * t
                    let rect = CGRect(x: x + sin(t * 6 + seed) * 20, y: y, width: 8, height: 12)
                    ctx.opacity = max(0, 1 - t / 1.5)
                    ctx.fill(Path(roundedRect: rect, cornerRadius: 2), with: .color(Self.colors[i % Self.colors.count]))
                }
            }
        }
        .accessibilityHidden(true)
    }
}
