import SwiftUI

/// Mũi tên cong vẽ đè lên khung camera, chỉ động tác người dùng cần làm với khối thật. Vẽ dần (0,9 s); `token` đổi ⇒
/// vẽ lại (lặp nhắc khi người dùng chưa xoay).
struct ScanTurnArrow: View {
    let turn: ScanTurn
    let token: Int
    @State private var progress: CGFloat = 0

    var body: some View {
        GeometryReader { geo in
            let rect = CGRect(origin: .zero, size: geo.size)
            ZStack {
                Self.path(turn, in: rect)
                    .trim(from: 0, to: progress)
                    .stroke(DSColor.accent, style: StrokeStyle(lineWidth: 9, lineCap: .round, lineJoin: .round))
                    .shadow(color: .black.opacity(0.45), radius: 4, y: 1)
                if turn == .flipTowardYou {
                    Text(verbatim: "×2")
                        .scaledFont(size: 26, weight: .heavy, design: .rounded)
                        .foregroundColor(DSColor.accent)
                        .shadow(color: .black.opacity(0.45), radius: 3, y: 1)
                        .position(x: rect.width * 0.72, y: rect.midY)
                        .opacity(progress)
                }
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
        .onAppear { draw() }
        .onChange(of: token) { _, _ in draw() }
    }

    private func draw() {
        progress = 0
        withAnimation(.easeOut(duration: 0.9)) { progress = 1 }
    }

    /// Điểm đầu / cuối / điểm điều khiển của cung (tỉ lệ theo `rect`), `nil` khi không có động tác.
    private static func curve(_ t: ScanTurn, in r: CGRect) -> (start: CGPoint, control: CGPoint, end: CGPoint)? {
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: r.minX + r.width * x, y: r.minY + r.height * y) }
        switch t {
        case .none: return nil
        case .left: return (p(0.82, 0.24), p(0.5, 0.04), p(0.18, 0.24))
        case .tiltTowardYou: return (p(0.84, 0.2), p(0.97, 0.5), p(0.84, 0.8))
        case .tiltAwayFromYou: return (p(0.84, 0.8), p(0.97, 0.5), p(0.84, 0.2))
        case .flipTowardYou: return (p(0.8, 0.08), p(0.99, 0.5), p(0.8, 0.92))
        }
    }

    static func endpoints(_ t: ScanTurn, in r: CGRect) -> (start: CGPoint, end: CGPoint)? {
        curve(t, in: r).map { ($0.start, $0.end) }
    }

    /// Cung + đầu mũi tên (hai nét theo tiếp tuyến tại điểm cuối).
    static func path(_ t: ScanTurn, in r: CGRect) -> Path {
        guard let c = curve(t, in: r) else { return Path() }
        var path = Path()
        path.move(to: c.start)
        path.addQuadCurve(to: c.end, control: c.control)
        let dx = c.end.x - c.control.x, dy = c.end.y - c.control.y
        let len = max(hypot(dx, dy), 0.001)
        let ux = dx / len, uy = dy / len
        let head = min(r.width, r.height) * 0.08
        for s: CGFloat in [1, -1] {
            // Xoay ngược tiếp tuyến ±35°.
            let a = CGFloat.pi * 35 / 180 * s
            let bx = -ux * cos(a) + uy * sin(a), by = -ux * sin(a) - uy * cos(a)
            path.move(to: c.end)
            path.addLine(to: CGPoint(x: c.end.x + bx * head, y: c.end.y + by * head))
        }
        return path
    }
}
