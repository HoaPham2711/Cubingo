import SwiftUI

/// Khung camera dùng chung cho màn quét và quét kiểm tra trong màn giải: ảnh camera, khung 3×3, mũi tên động tác (khi
/// `arrow` khác `nil`), biểu tượng ánh sáng, và hàng nút tròn nhỏ ở trên.
struct ScanCameraPanel<Buttons: View>: View {
    @ObservedObject var camera: ScanCamera
    let arrow: ScanTurn?
    let arrowToken: Int
    let tip: ScanLightTip?
    @ViewBuilder let buttons: () -> Buttons

    var body: some View {
        GeometryReader { geo in
            let frame = camera.hasLivePreview
                ? ScanPreviewLayer.frameRect(in: geo.size)
                : ScanSampler.frameRect(in: geo.size)
            ZStack(alignment: .topLeading) {
                if camera.hasLivePreview {
                    ScanPreviewLayer(session: camera.session)
                } else {
                    Color(hex: 0x2B1D14)
                }
                ScanFrameOverlay()
                    .frame(width: frame.width, height: frame.height)
                    .offset(x: frame.minX, y: frame.minY)
                if let arrow {
                    let r = frame.insetBy(dx: -frame.width * 0.22, dy: -frame.height * 0.22)
                    ScanTurnArrow(turn: arrow, token: arrowToken)
                        .frame(width: r.width, height: r.height)
                        .offset(x: r.minX, y: r.minY)
                }
                HStack(spacing: 10, content: buttons)
                    .padding(12)
                if let tip {
                    Image(systemName: tip == .tooDark ? "lightbulb.fill" : "sun.max.fill")
                        .scaledFont(size: 20, weight: .bold, design: .rounded)
                        .foregroundColor(.yellow)
                        .padding(10)
                        .background(Circle().fill(Color.black.opacity(0.45)))
                        .symbolEffect(.pulse)
                        .padding(12)
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
                        .accessibilityLabel(Text(tip == .tooDark ? "Too dark" : "Too much glare"))
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        }
    }
}

/// Nút tròn nhỏ nền mờ đặt trên camera.
struct ScanRoundButton: View {
    let icon: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: icon)
                .scaledFont(size: 16, weight: .bold, design: .rounded)
                .foregroundColor(.white)
                .frame(width: 36, height: 36)
                .background(Circle().fill(Color.black.opacity(0.45)))
        }
        .accessibilityLabel(Text(label))
    }
}

/// Nút ✓ chụp (tròn, nền nhấn).
struct ScanShutterButton: View {
    let ready: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: "checkmark")
                .scaledFont(size: 28, weight: .heavy, design: .rounded)
                .foregroundColor(.white)
                .frame(width: 64, height: 64)
                .background(Circle().fill(DSColor.accent))
                .shadow(color: DSColor.accent.opacity(0.35), radius: 8, y: 3)
        }
        .opacity(ready ? 1 : 0.4)
        .accessibilityLabel(Text("Capture this side"))
    }
}

/// Khung 3×3 trên vùng lấy mẫu: viền nhấn + đường chia ô (không có chấm màu — màu sống hiện trên khối 3D).
struct ScanFrameOverlay: View {
    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width, h = geo.size.height
            ZStack {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .strokeBorder(DSColor.accent, lineWidth: 3)
                Path { p in
                    for k in 1...2 {
                        let x = w * CGFloat(k) / 3, y = h * CGFloat(k) / 3
                        p.move(to: CGPoint(x: x, y: 0))
                        p.addLine(to: CGPoint(x: x, y: h))
                        p.move(to: CGPoint(x: 0, y: y))
                        p.addLine(to: CGPoint(x: w, y: y))
                    }
                }
                .stroke(DSColor.accent.opacity(0.55), lineWidth: 1.5)
            }
        }
        .accessibilityHidden(true)
    }
}

/// Bố cục chung: camera ~55% trên (iPad ngang: 58% trái), phần còn lại cho khối.
struct ScanSplitLayout<Camera: View, Cube: View>: View {
    @ViewBuilder let camera: () -> Camera
    @ViewBuilder let cube: () -> Cube
    @Environment(\.horizontalSizeClass) private var sizeClass

    var body: some View {
        GeometryReader { geo in
            if sizeClass == .regular && geo.size.width > geo.size.height {
                HStack(spacing: 16) {
                    camera().frame(width: geo.size.width * 0.58)
                    cube()
                }
            } else {
                VStack(spacing: 8) {
                    camera().frame(height: geo.size.height * 0.55)
                    cube()
                }
            }
        }
    }
}
