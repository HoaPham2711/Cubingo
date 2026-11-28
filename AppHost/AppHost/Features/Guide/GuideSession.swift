import Foundation

enum GuidePhase: Equatable {
    case step
    case stageDone(SolverStageKind)
    case finished
}

/// Máy trạng thái chỉ từng bước. Bất biến: `state` = trạng thái đầu áp mọi bước đã làm (bước đang hiện CHƯA làm).
/// Chặng rỗng luôn bị bỏ qua (không bao giờ hiện "0 / 0"). Quick = một chặng gói lời giải ngắn.
@MainActor
final class GuideSession: ObservableObject {
    let mode: GuideMode
    /// Màu nền của lời giải (Teach me) — giữ qua `replan`.
    let base: CubeColor
    private(set) var stages: [SolverStage]
    @Published private(set) var stageIndex = 0
    @Published private(set) var stepIndex = 0
    @Published private(set) var state: CubeFacelets
    @Published private(set) var animation: Cube3DAnimation?
    @Published private(set) var phase: GuidePhase = .step
    @Published private(set) var movesDone = 0

    private let clock: () -> Date
    private let startedAt: Date
    private var token = 0

    init(mode: GuideMode, stages: [SolverStage], base: CubeColor, clock: @escaping () -> Date = Date.init) {
        precondition(!stages.isEmpty, "cần ít nhất một chặng")
        self.mode = mode
        self.stages = stages
        self.base = base
        self.clock = clock
        startedAt = clock()
        state = stages[0].start
        enterFirstNonEmpty(from: 0)
    }

    var currentStage: SolverStage { stages[stageIndex] }
    var stepCount: Int { currentStage.steps.count }
    var currentStep: SolverStep? { phase == .step && stepIndex < stepCount ? currentStage.steps[stepIndex] : nil }
    var hold: (top: CubeColor, front: CubeColor) { SolverHold.hold(of: state) }
    var elapsed: TimeInterval { clock().timeIntervalSince(startedAt) }

    /// Số chặng có bước (thanh tiến độ Teach me).
    var nonEmptyStageCount: Int { stages.filter { !$0.steps.isEmpty }.count }

    func next() {
        guard let step = currentStep else { return }
        state = state.applying(step.move)
        play(step.move, reverse: false)
        if !step.move.isRotation { movesDone += 1 }
        stepIndex += 1
        if stepIndex >= stepCount {
            if mode == .quick || nextNonEmpty(after: stageIndex) == nil {
                phase = .finished
            } else {
                phase = .stageDone(currentStage.kind)
            }
        }
    }

    func back() {
        if phase != .step || stepIndex > 0 {
            // Lùi trong chặng hiện tại (kể cả từ màn "Stage complete" / "Solved" về bước cuối).
            guard stepIndex > 0 else { return }
            phase = .step
            stepIndex -= 1
        } else {
            guard let prev = previousNonEmpty(before: stageIndex) else { return }
            stageIndex = prev
            stepIndex = stepCount - 1
        }
        let move = currentStage.steps[stepIndex].move
        state = state.applying(move.inverse)
        if !move.isRotation { movesDone -= 1 }
        play(move, reverse: true)
    }

    /// Phát lại bước vừa làm (không đổi trạng thái).
    func replay() {
        let move: CubeMove?
        if stepIndex > 0 {
            move = currentStage.steps[stepIndex - 1].move
        } else if let prev = previousNonEmpty(before: stageIndex) {
            move = stages[prev].steps.last?.move
        } else {
            move = nil
        }
        guard let move else { return }
        // Bước ngược của chặng trước khi đang ở bước 0 cũng là "vừa làm" — state đã là sau bước đó.
        play(move, reverse: false)
    }

    func continueAfterStage() {
        guard case .stageDone = phase else { return }
        if let k = nextNonEmpty(after: stageIndex) {
            stageIndex = k
            stepIndex = 0
            state = stages[k].start
            phase = .step
            // Nước cuối của chặng trước không còn là việc của khối: khối dựng lại (sau quét kiểm tra) không phát lại nó.
            animation = nil
        } else {
            phase = .finished
        }
    }

    /// Thay lời giải từ trạng thái mới (sau quét kiểm tra lệch), vào chặng đầu không rỗng.
    func replan(_ newStages: [SolverStage]) {
        precondition(!newStages.isEmpty, "cần ít nhất một chặng")
        stages = newStages
        state = newStages[0].start
        animation = nil
        enterFirstNonEmpty(from: 0)
    }

    // MARK: - Phụ trợ

    private func enterFirstNonEmpty(from i: Int) {
        if let k = stages.indices.first(where: { $0 >= i && !stages[$0].steps.isEmpty }) {
            stageIndex = k
            stepIndex = 0
            state = stages[k].start
            phase = .step
        } else {
            stageIndex = stages.count - 1
            stepIndex = 0
            phase = .finished
        }
    }

    private func nextNonEmpty(after i: Int) -> Int? {
        stages.indices.first { $0 > i && !stages[$0].steps.isEmpty }
    }

    private func previousNonEmpty(before i: Int) -> Int? {
        stages.indices.last { $0 < i && !stages[$0].steps.isEmpty }
    }

    private func play(_ move: CubeMove, reverse: Bool) {
        token += 1
        animation = Cube3DAnimation(move: move, reverse: reverse, token: token)
    }
}
