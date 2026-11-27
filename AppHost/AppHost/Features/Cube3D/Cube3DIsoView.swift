import SwiftUI

/// Hình khối tĩnh (isometric, thấy U, F, R) vẽ bằng `Canvas` — cho màn không cần hoạt ảnh. Không dùng RealityKit: chỉ
/// được có MỘT `RealityView` sống trong navigation stack (xem `Cube3DView`).
struct Cube3DIsoView: View {
    let state: CubeFacelets
    let palette: CubePalette

    var body: some View {
        Canvas { ctx, size in
            let n = Double(state.n)
            let c30 = cos(Double.pi / 6), s30 = 0.5
            // Bề rộng hình chiếu = 2·n·cos30·s; chiều cao = (n + n·sin30·2)·s.
            let s = min(size.width / (2 * n * c30), size.height / (2 * n)) * 0.92
            let origin = CGPoint(x: size.width / 2, y: size.height / 2 + (n * s) / 2 - n * s * s30)
            func p(_ x: Double, _ y: Double, _ z: Double) -> CGPoint {
                // x: L→R, y: D→U, z: B→F; tâm khối ở giữa khung.
                let cx = x - n / 2, cy = y - n / 2, cz = z - n / 2
                return CGPoint(x: origin.x + (cx - cz) * c30 * s, y: origin.y + (-cy + (cx + cz) * s30) * s)
            }
            func quad(_ a: CGPoint, _ b: CGPoint, _ c: CGPoint, _ d: CGPoint, inset: Double) -> Path {
                let m = CGPoint(x: (a.x + b.x + c.x + d.x) / 4, y: (a.y + b.y + c.y + d.y) / 4)
                func i(_ q: CGPoint) -> CGPoint { CGPoint(x: q.x + (m.x - q.x) * inset, y: q.y + (m.y - q.y) * inset) }
                var path = Path()
                path.move(to: i(a)); path.addLine(to: i(b)); path.addLine(to: i(c)); path.addLine(to: i(d))
                path.closeSubpath()
                return path
            }
            // Thân khối.
            var body = Path()
            body.move(to: p(0, n, 0)); body.addLine(to: p(n, n, 0)); body.addLine(to: p(n, 0, 0))
            body.addLine(to: p(n, 0, n)); body.addLine(to: p(0, 0, n)); body.addLine(to: p(0, n, n))
            body.closeSubpath()
            ctx.fill(body, with: .color(Color(hex: 0x1A1412)))
            func fill(_ face: CubeFace, _ i: Int, _ path: Path) {
                let rgb = palette.rgb(state.color(face, i))
                ctx.fill(path, with: .color(Color(.sRGB, red: rgb.r, green: rgb.g, blue: rgb.b, opacity: 1)))
            }
            let k = state.n
            for r in 0..<k {
                for c in 0..<k {
                    let (rd, cd) = (Double(r), Double(c))
                    fill(.u, r * k + c, quad(p(cd, n, rd), p(cd + 1, n, rd), p(cd + 1, n, rd + 1), p(cd, n, rd + 1), inset: 0.16))
                    fill(.f, r * k + c, quad(p(cd, n - rd, n), p(cd + 1, n - rd, n), p(cd + 1, n - rd - 1, n),
                                            p(cd, n - rd - 1, n), inset: 0.16))
                    fill(.r, r * k + c, quad(p(n, n - rd, n - cd), p(n, n - rd, n - cd - 1), p(n, n - rd - 1, n - cd - 1),
                                            p(n, n - rd - 1, n - cd), inset: 0.16))
                }
            }
        }
        .accessibilityElement()
        .accessibilityLabel(Text("Your cube"))
    }
}
