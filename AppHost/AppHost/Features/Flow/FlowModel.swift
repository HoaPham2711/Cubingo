import Foundation

/// Trạng thái của luồng chọn khối → quét → kiểm tra → chọn cách giải → chỉ bước → xong.
@MainActor
final class FlowModel: ObservableObject {
    @Published var path: [FlowRoute] = []
    @Published private(set) var puzzle: FlowPuzzle?
    /// Kết quả quét gần nhất (màn kiểm tra đọc).
    @Published private(set) var scan: ScanResult?

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

    /// Về màn chọn khối, xoá mọi trạng thái khối.
    func startOver() {
        path = []
        puzzle = nil
        scan = nil
    }
}
