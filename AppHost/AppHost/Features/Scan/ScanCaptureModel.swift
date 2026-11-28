import simd
import SwiftUI

enum ScanCaptureOutcome: Equatable {
    /// Chưa có lưới 9 mẫu.
    case notReady
    /// Đã nhận mặt, sang bước sau.
    case accepted
    /// Tâm trùng một mặt đã quét ⇒ không nhận.
    case duplicate(CubeFace)
    /// Đủ 6 mặt ⇒ kết quả phân nhóm.
    case finished(ScanResult)
}

/// Mô hình màn quét (thuần, có test): nhận mẫu camera, làm mượt màu sống, chụp khi người dùng bấm ✓, từ chối mặt trùng,
/// chờ người dùng xoay sang mặt mới, hoàn tác, xuất màu cho khối 3D. Không tự chụp.
@MainActor
final class ScanCaptureModel: ObservableObject {
    let steps = ScanProtocol.cube3
    @Published private(set) var stepIndex = 0
    /// Màu sống (đã làm mượt) của mặt đang thấy; rỗng khi chưa có khung hợp lệ.
    @Published private(set) var live: [CubeRGB] = []
    /// Vừa chụp xong, chờ camera thấy một tâm khác (người dùng đã xoay).
    @Published private(set) var awaitingTurn = false
    @Published private(set) var result: ScanResult?
    /// Ảnh đã chụp theo thứ tự bước.
    private var images: [[CubeRGB]] = []

    /// Hệ số trung bình trượt mỗi khung (mẫu ≤ 15 Hz ⇒ thời hằng khoảng 0,2 s).
    static let smoothing = 0.35
    static let sameCenterDeltaE = 10.0

    var step: ScanStep { steps[min(stepIndex, steps.count - 1)] }
    var capturedCount: Int { images.count }
    var canUndo: Bool { !images.isEmpty }

    func observe(_ s: [CubeRGB]) {
        guard s.count == 9 else { return }
        if awaitingTurn {
            guard let last = images.last, CubeColorMath.deltaE(s[4], last[4]) >= Self.sameCenterDeltaE else {
                live = s
                return
            }
            awaitingTurn = false
            live = s
            return
        }
        guard live.count == 9 else {
            live = s
            return
        }
        live = Self.smooth(live, s)
    }

    /// Trung bình trượt hàm mũ một khung.
    static func smooth(_ old: [CubeRGB], _ new: [CubeRGB]) -> [CubeRGB] {
        let a = smoothing
        return zip(old, new).map { o, n in
            CubeRGB(r: o.r + a * (n.r - o.r), g: o.g + a * (n.g - o.g), b: o.b + a * (n.b - o.b))
        }
    }

    @discardableResult
    func capture() -> ScanCaptureOutcome {
        if images.count == steps.count { return finish() }
        guard live.count == 9 else { return .notReady }
        if let i = images.firstIndex(where: { CubeColorMath.deltaE($0[4], live[4]) < Self.sameCenterDeltaE }) {
            return .duplicate(steps[i].face)
        }
        images.append(live)
        stepIndex = images.count
        awaitingTurn = true
        return images.count == steps.count ? finish() : .accepted
    }

    private func finish() -> ScanCaptureOutcome {
        let samples = ScanProtocol.assemble(images)
        AppInternalScanLog.record(samples)
        let r = ScanClusterer.cluster(samples, n: 3)
        result = r
        return .finished(r)
    }

    func undoLast() {
        guard canUndo else { return }
        images.removeLast()
        stepIndex = images.count
        awaitingTurn = false
        result = nil
        live = []
    }

    func reset() {
        images = []
        stepIndex = 0
        awaitingTurn = false
        result = nil
        live = []
    }

    /// Màu cho khối 3D: các mặt đã chụp + màu sống của mặt đang quét (khi không chờ xoay).
    var paint: Cube3DPaint {
        var c: [Int: CubeRGB] = [:]
        for (step, img) in zip(steps, images) { for (k, idx) in step.image.enumerated() { c[idx] = img[k] } }
        if stepIndex < steps.count, !awaitingTurn, live.count == 9 {
            for (k, idx) in step.image.enumerated() { c[idx] = live[k] }
        }
        return Cube3DPaint(colors: c)
    }

    var glowFace: CubeFace? { stepIndex < steps.count ? step.face : nil }

    /// Hướng khối của bước hiện tại (đủ 6 ⇒ giữ bước cuối).
    var pose: simd_quatf { step.orientation }
}
