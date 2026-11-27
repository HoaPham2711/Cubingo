import Foundation

/// Trạng thái của luồng chọn khối → quét → kiểm tra → chọn cách giải → chỉ bước → xong.
@MainActor
final class FlowModel: ObservableObject {
    @Published var path: [FlowRoute] = []
    @Published private(set) var puzzle: FlowPuzzle?

    /// Chỉ nhận khối đang có; đẩy màn quét.
    func choose(_ p: FlowPuzzle) {
        guard p.isAvailable else { return }
        puzzle = p
        path = [.scan]
    }

    /// Về màn chọn khối, xoá mọi trạng thái khối.
    func startOver() {
        path = []
        puzzle = nil
    }
}
