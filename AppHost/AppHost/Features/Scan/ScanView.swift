import QuartzCore
import SwiftUI

enum ScanCaptureMessage: Equatable { case notFirstSide, alreadyScanned }

/// Quét cả khối (6 mặt) hoặc chỉ một mặt để kiểm tra sau chặng.
enum ScanMode: Equatable {
    case full
    case checkFace(GuideCheckSpec, expected: CubeFacelets)
}

/// Đi qua `ScanProtocol.cube3`: nhận lưới 9 mẫu mỗi lần chụp, kiểm "đã về mặt đầu" và "mặt đã quét", lắp + phân nhóm
/// khi đủ 6 mặt.
@MainActor
final class ScanCaptureModel: ObservableObject {
    let steps = ScanProtocol.cube3
    @Published private(set) var stepIndex = 0
    @Published private(set) var grids: [CubeFace: [CubeRGB]] = [:]
    @Published private(set) var message: ScanCaptureMessage?
    @Published private(set) var result: ScanResult?
    private var lastCenter: CubeRGB?

    static let sameCenterDeltaE = 10.0
    static let firstSideDeltaE = 15.0

    var step: ScanStep { steps[min(stepIndex, steps.count - 1)] }
    var capturedCount: Int { grids.count }

    /// Tự chụp chỉ khi tâm đã đổi so với lần chụp trước (người dùng đã xoay khối).
    func allowsAutoCapture(_ s: [CubeRGB]) -> Bool {
        guard s.count == 9, result == nil else { return false }
        guard let lastCenter else { return true }
        return CubeColorMath.deltaE(s[4], lastCenter) >= Self.sameCenterDeltaE
    }

    /// `true` ⇒ đã nhận lưới (sang bước sau).
    @discardableResult
    func capture(_ s: [CubeRGB]) -> Bool {
        guard s.count == 9, result == nil else { return false }
        if let face = step.face {
            if grids.values.contains(where: { CubeColorMath.deltaE($0[4], s[4]) < Self.sameCenterDeltaE }) {
                message = .alreadyScanned
                return false
            }
            grids[face] = s
        } else {
            guard let first = grids[.f], CubeColorMath.deltaE(first[4], s[4]) < Self.firstSideDeltaE else {
                message = .notFirstSide
                return false
            }
        }
        message = nil
        lastCenter = s[4]
        stepIndex += 1
        if stepIndex >= steps.count {
            let samples = ScanProtocol.assemble(grids)
            AppInternalScanLog.record(samples)
            result = ScanClusterer.cluster(samples, n: 3)
        }
        return true
    }
}

/// Màn quét bằng camera: chữ hướng dẫn theo bước, màu sống trong 9 ô, tự chụp khi khung hình đứng yên, nút chụp tay,
/// mẹo ánh sáng, lối nhập tay.
struct ScanView: View {
    @ObservedObject var flow: FlowModel
    let deps: FlowDependencies
    var mode: ScanMode = .full
    /// Chế độ kiểm tra: lưới 9 mẫu vừa chụp.
    var onFace: (([CubeRGB]) -> Void)?
    var onSkip: (() -> Void)?

    private var checkFace: CubeFace? {
        if case let .checkFace(spec, _) = mode { return spec.face }
        return nil
    }

    @StateObject private var camera = ScanCamera()
    @StateObject private var model = ScanCaptureModel()
    @State private var stabilizer = ScanStabilizer()
    @State private var tip: ScanLightTip?

    var body: some View {
        VStack(spacing: 16) {
            if checkFace == nil { progressDots }
            instruction
            cameraArea
            feedback
            Spacer(minLength: 0)
            controls
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .frame(maxWidth: 560)
        .frame(maxWidth: .infinity)
        .styleBackground()
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            camera.start()
            camera.expect(checkFace ?? model.step.face ?? .f)
        }
        .onDisappear { camera.stop() }
        // Mọi khung, kể cả khung giống hệt khung trước (đứng yên tuyệt đối): `onChange` bỏ qua giá trị không đổi ⇒ bộ
        // ổn định không bao giờ đủ 0,6 s.
        .onReceive(camera.$samples) { handle($0) }
        .onChange(of: model.stepIndex) { _, _ in camera.expect(model.step.face ?? .f) }
        .onChange(of: model.result) { _, r in
            if let r { flow.didScan(r) }
        }
        .trackScreen("scan_camera")
    }

    // MARK: - Phần

    private var progressDots: some View {
        HStack(spacing: 8) {
            ForEach(0..<6, id: \.self) { i in
                Circle()
                    .fill(i < model.capturedCount ? DSColor.statusGood : Color.black.opacity(0.12))
                    .frame(width: 10, height: 10)
            }
        }
        .accessibilityElement()
        .accessibilityLabel(Text("\(model.capturedCount) of 6 sides scanned"))
    }

    private var instructionText: String {
        switch checkFace {
        case .d?: return String(localized: "Show us the bottom side")
        case .u?: return String(localized: "Show us the top side")
        case .some: return String(localized: "Show us the front side")
        case nil: return Self.text(model.step.instruction)
        }
    }

    private var instruction: some View {
        HStack(spacing: 12) {
            Image(systemName: checkFace == nil ? Self.arrow(model.step.instruction) : "checkmark.viewfinder")
                .scaledFont(size: 28, weight: .bold, design: .rounded)
                .foregroundColor(DSColor.accent)
                .frame(width: 44)
            Text(instructionText)
                .scaledFont(size: 20, weight: .heavy, design: .rounded)
                .foregroundColor(DSColor.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
    }

    private var cameraArea: some View {
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
                ScanGridOverlay(samples: camera.samples)
                    .frame(width: frame.width, height: frame.height)
                    .offset(x: frame.minX, y: frame.minY)
            }
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        }
        .aspectRatio(3.0 / 4.0, contentMode: .fit)
        .frame(maxHeight: 520)
    }

    @ViewBuilder
    private var feedback: some View {
        if let m = model.message {
            label(m == .notFirstSide ? String(localized: "That's not the first side yet")
                                     : String(localized: "This side was already scanned — turn once more"),
                  icon: "exclamationmark.circle.fill", color: DSColor.statusWarning)
        } else if let tip {
            label(tip == .tooDark ? String(localized: "Face a window or a lamp")
                                  : String(localized: "Too much glare — tilt the cube slightly"),
                  icon: "lightbulb.fill", color: DSColor.textSecondary)
        }
    }

    private func label(_ text: String, icon: String, color: Color) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
            Text(text).fixedSize(horizontal: false, vertical: true)
        }
        .scaledFont(size: 16, weight: .semibold, design: .rounded)
        .foregroundColor(color)
    }

    private var controls: some View {
        VStack(spacing: 12) {
            Button {
                capture(camera.samples)
            } label: {
                ZStack {
                    Circle().fill(Color.white).frame(width: 72, height: 72)
                    Circle().strokeBorder(DSColor.accent, lineWidth: 5).frame(width: 72, height: 72)
                }
            }
            .accessibilityLabel(Text("Capture this side"))
            if checkFace != nil {
                Button("Skip") { onSkip?() }
                    .scaledFont(size: 16, weight: .semibold, design: .rounded)
                    .foregroundColor(DSColor.accentDark)
            } else {
                Button("Enter colors manually") { flow.path.append(.review(manual: true)) }
                    .scaledFont(size: 16, weight: .semibold, design: .rounded)
                    .foregroundColor(DSColor.accentDark)
            }
        }
    }

    // MARK: - Logic

    private func handle(_ s: [CubeRGB]) {
        guard s.count == 9 else { return }
        tip = ScanLighting.tip(s)
        guard stabilizer.feed(s, at: CACurrentMediaTime()) else { return }
        if checkFace != nil || model.allowsAutoCapture(s) { capture(s) } else { stabilizer.reset() }
    }

    private func capture(_ s: [CubeRGB]) {
        if checkFace != nil {
            guard s.count == 9 else { return }
            deps.haptic(.capture)
            onFace?(s)
            stabilizer.reset()
            return
        }
        if model.capture(s) { deps.haptic(.capture) }
        stabilizer.reset()
    }

    static func text(_ i: ScanInstruction) -> String {
        switch i {
        case .start: return String(localized: "Point the camera at any side")
        case .turnLeft: return String(localized: "Turn the cube left — the next center should face you")
        case .backToFirst: return String(localized: "Turn left once more — the first side faces you again")
        case .tiltTopToYou: return String(localized: "Tilt the top toward you")
        case .tiltBottomToYou: return String(localized: "Tilt the other way to show the bottom")
        }
    }

    static func arrow(_ i: ScanInstruction) -> String {
        switch i {
        case .start: return "viewfinder"
        case .turnLeft: return "arrow.left"
        case .backToFirst: return "arrow.uturn.left"
        case .tiltTopToYou: return "arrow.down"
        case .tiltBottomToYou: return "arrow.up"
        }
    }
}

/// Lưới 3×3 trên khung lấy mẫu: viền trắng + chấm màu sống của từng ô.
private struct ScanGridOverlay: View {
    let samples: [CubeRGB]

    var body: some View {
        GeometryReader { geo in
            let cell = geo.size.width / 3
            ForEach(0..<9, id: \.self) { i in
                let c = i < samples.count ? samples[i] : CubeRGB(r: 0.5, g: 0.5, b: 0.5)
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .strokeBorder(Color.white.opacity(0.9), lineWidth: 2)
                    .background(
                        RoundedRectangle(cornerRadius: 6, style: .continuous)
                            .fill(Color(.sRGB, red: c.r, green: c.g, blue: c.b, opacity: 1))
                            .frame(width: cell * 0.36, height: cell * 0.36)
                    )
                    .frame(width: cell - 6, height: cell - 6)
                    .position(x: cell * (CGFloat(i % 3) + 0.5), y: cell * (CGFloat(i / 3) + 0.5))
            }
        }
        .accessibilityHidden(true)
    }
}
