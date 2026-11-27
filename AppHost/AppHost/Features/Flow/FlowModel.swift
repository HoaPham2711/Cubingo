import Foundation

enum FlowAlert: Equatable { case solverFailed }

/// Ước lượng cho màn chọn cách giải.
enum FlowMode {
    /// Tổng số bước mặt (không tính bước xoay cả khối).
    static func estimate(teach stages: [SolverStage]) -> Int {
        stages.reduce(0) { $0 + $1.steps.filter { !$0.move.isRotation }.count }
    }
}

/// Trạng thái của luồng chọn khối → quét → kiểm tra → chọn cách giải → chỉ bước → xong.
@MainActor
final class FlowModel: ObservableObject {
    @Published var path: [FlowRoute] = []
    @Published private(set) var puzzle: FlowPuzzle?
    /// Kết quả quét gần nhất (màn kiểm tra đọc).
    @Published private(set) var scan: ScanResult?
    /// Khối đã kiểm (hợp lệ) và bảng màu của nó.
    @Published private(set) var cube: CubeFacelets?
    @Published private(set) var palette: CubePalette?
    /// Phiên chỉ bước đang chạy.
    @Published private(set) var session: GuideSession?
    @Published var alert: FlowAlert?
    /// Đang tìm lời giải Just solve it.
    @Published private(set) var isSolving = false
    /// Đang quét lại cả khối sau quét kiểm tra lệch (kết quả kiểm tra ⇒ lập lại lời giải, không mở phiên mới).
    @Published private(set) var isRechecking = false

    /// Chỉ nhận khối đang có; đẩy màn quét.
    func choose(_ p: FlowPuzzle) {
        guard p.isAvailable else { return }
        puzzle = p
        path = [.scan]
    }

    /// Quét xong ⇒ màn kiểm tra màu.
    func didScan(_ r: ScanResult) {
        scan = r
        path.append(.review(manual: false))
    }

    /// Khối hợp lệ ⇒ màn chọn cách giải.
    func didReview(_ f: CubeFacelets, palette: CubePalette) {
        if isRechecking, let old = session {
            replan(from: f, palette: palette, old: old)
            return
        }
        cube = f
        self.palette = palette
        path.append(.mode)
    }

    /// Dựng lời giải và mở màn chỉ bước. Teach me: 7 chặng từ màu nền của bảng màu. Just solve it: một chặng gói
    /// lời giải hai pha; lỗi/hết giờ ⇒ `alert`, không đổi route.
    func startGuide(_ mode: GuideMode, quickSolver: SolverQuick) async {
        guard let cube, let palette, !isSolving else { return }
        let base = palette.baseColor
        switch mode {
        case .teach:
            begin(GuideSession(mode: .teach, stages: SolverBeginner.solve(cube, base: base), base: base))
        case .quick:
            isSolving = true
            defer { isSolving = false }
            do {
                let moves = try await quickSolver.solve(try CubeCubies(facelets: cube))
                let steps = moves.map { SolverStep(move: $0, reason: nil, algorithm: nil) }
                begin(GuideSession(mode: .quick, stages: [SolverStage(kind: .cross, steps: steps, start: cube)],
                                   base: base))
            } catch {
                alert = .solverFailed
            }
        }
    }

    /// Mở màn chỉ bước với một phiên đã dựng (route preview dùng trực tiếp).
    func begin(_ s: GuideSession) {
        session = s
        path.append(.guide(s.mode))
    }

    /// Quét kiểm tra sau chặng.
    func startCheck() {
        guard path.last != .check else { return }
        path.append(.check)
    }

    /// Mặt chụp khớp ⇒ sang chặng sau, về màn chỉ bước.
    func checkMatched() {
        session?.continueAfterStage()
        if path.last == .check { path.removeLast() }
    }

    /// Bỏ qua kiểm tra (cả khi lệch).
    func checkSkipped() { checkMatched() }

    /// Lệch ⇒ quét lại cả khối.
    func startRescan() {
        isRechecking = true
        path.append(.scan)
    }

    /// Lời giải mới từ trạng thái vừa quét lại. Màu nền giữ đúng MÀU THẬT của phiên (nhãn có thể đổi vì lần quét này
    /// cầm khối khác hướng ⇒ tìm theo ΔE gần nhất); cùng nhãn ⇒ `replan` trên phiên cũ (giữ số bước, thời gian).
    private func replan(from f: CubeFacelets, palette p: CubePalette, old: GuideSession) {
        let target = (self.palette ?? p).rgb(old.base)
        let base = CubeColor.all.min {
            CubeColorMath.deltaE(p.rgb($0), target) < CubeColorMath.deltaE(p.rgb($1), target)
        }!
        cube = f
        palette = p
        let stages = SolverBeginner.solve(f, base: base)
        if base == old.base {
            old.replan(stages)
        } else {
            session = GuideSession(mode: .teach, stages: stages, base: base)
        }
        isRechecking = false
        if let i = path.lastIndex(of: .guide(.teach)) { path = Array(path.prefix(through: i)) }
    }

    /// Phiên xong ⇒ màn ăn mừng.
    func didFinishGuide() {
        guard session?.phase == .finished, path.last != .done else { return }
        path.append(.done)
    }

    /// Về màn chọn khối, xoá mọi trạng thái khối.
    func startOver() {
        path = []
        puzzle = nil
        scan = nil
        cube = nil
        palette = nil
        session = nil
        alert = nil
        isRechecking = false
    }
}
