import SwiftUI

/// Sơ đồ khối trải phẳng hình chữ thập: U trên; L F R B giữa; D dưới. Ô nghi viền cam nhấp nháy. iPhone vừa bề
/// ngang, iPad tối đa 560 pt.
struct ScanNetView: View {
    let facelets: [CubeColor?]
    let palette: CubePalette
    let suspects: Set<Int>
    let onTap: (Int) -> Void

    @State private var pulse = false

    /// (mặt, cột lưới 0…3, hàng lưới 0…2) của sơ đồ.
    private static let layout: [(CubeFace, Int, Int)] = [
        (.u, 1, 0), (.l, 0, 1), (.f, 1, 1), (.r, 2, 1), (.b, 3, 1), (.d, 1, 2),
    ]

    var body: some View {
        GeometryReader { geo in
            let gap: CGFloat = 6
            let faceSide = (geo.size.width - gap * 3) / 4
            let cell = faceSide / 3
            ZStack(alignment: .topLeading) {
                ForEach(Self.layout, id: \.0) { face, col, row in
                    faceGrid(face, cell: cell)
                        .offset(x: CGFloat(col) * (faceSide + gap), y: CGFloat(row) * (faceSide + gap))
                }
            }
        }
        .aspectRatio(4.0 / 3.0, contentMode: .fit)
        .frame(maxWidth: 560)
        .onAppear {
            withAnimation(.easeInOut(duration: 0.6).repeatForever(autoreverses: true)) { pulse = true }
        }
    }

    private func faceGrid(_ face: CubeFace, cell: CGFloat) -> some View {
        VStack(spacing: 0) {
            ForEach(0..<3, id: \.self) { r in
                HStack(spacing: 0) {
                    ForEach(0..<3, id: \.self) { c in
                        sticker(face.rawValue * 9 + r * 3 + c, size: cell)
                    }
                }
            }
        }
        .padding(2)
        .background(RoundedRectangle(cornerRadius: 8, style: .continuous).fill(Color(hex: 0x2B1D14)))
    }

    private func sticker(_ i: Int, size: CGFloat) -> some View {
        let color: Color = facelets[i].map { c in
            let rgb = palette.rgb(c)
            return Color(.sRGB, red: rgb.r, green: rgb.g, blue: rgb.b, opacity: 1)
        } ?? Color(hex: 0xE8DDD3)
        let suspect = suspects.contains(i)
        return Button { onTap(i) } label: {
            RoundedRectangle(cornerRadius: size * 0.18, style: .continuous)
                .fill(color)
                .overlay(
                    RoundedRectangle(cornerRadius: size * 0.18, style: .continuous)
                        .strokeBorder(DSColor.accent, lineWidth: suspect ? 3 : 0)
                        .opacity(suspect ? (pulse ? 1 : 0.25) : 0)
                )
                .padding(size * 0.06)
                .frame(width: size - 1.4, height: size - 1.4)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text(facelets[i].map { palette.name($0) } ?? String(localized: "empty")))
    }
}
