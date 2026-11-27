import Foundation

/// Lỗi định dạng file bảng.
enum SolverKociembaTablesError: Error, Equatable {
    case missingResource
    case badHeader
    case truncated
    case badTable(String)
}

/// Bảng tra của thuật toán hai pha — sinh trước bằng `tools/app/kociemba/gen_tables.sh`, nhúng làm resource
/// `kociemba-tables.bin`, bất biến sau khi nạp (an toàn đọc từ nhiều luồng). Chỉ `import Foundation`: tool biên dịch
/// lại file này để ghi đúng định dạng mà app đọc.
///
/// Định dạng: ASCII `KCB1`, `UInt32` số bảng; mỗi bảng = `UInt8` độ dài tên + tên UTF-8 + `UInt8` kiểu (1 = UInt16,
/// 2 = nibble) + `UInt32` số phần tử + dữ liệu little-endian.
final class SolverKociembaTables: @unchecked Sendable {
    typealias K = SolverKociembaCoords

    let twistMove: [UInt16]
    let flipMove: [UInt16]
    let sliceSortedMove: [UInt16]
    let cornersMove: [UInt16]
    let udEdgesMove: [UInt16]
    let twistSlicePrune: SolverNibbleTable
    let flipSlicePrune: SolverNibbleTable
    let cornersSlicePrune: SolverNibbleTable
    let udEdgesSlicePrune: SolverNibbleTable

    static let moveTableSpecs: [(name: String, count: Int)] = [
        ("twistMove", 2187 * 18), ("flipMove", 2048 * 18), ("sliceSortedMove", 11880 * 18),
        ("cornersMove", 40320 * 10), ("udEdgesMove", 40320 * 10),
    ]
    static let pruneTableSpecs: [(name: String, count: Int)] = [
        ("twistSlicePrune", 2187 * 495), ("flipSlicePrune", 2048 * 495),
        ("cornersSlicePrune", 40320 * 24), ("udEdgesSlicePrune", 40320 * 24),
    ]

    init(moves: [[UInt16]], prunes: [SolverNibbleTable]) {
        twistMove = moves[0]
        flipMove = moves[1]
        sliceSortedMove = moves[2]
        cornersMove = moves[3]
        udEdgesMove = moves[4]
        twistSlicePrune = prunes[0]
        flipSlicePrune = prunes[1]
        cornersSlicePrune = prunes[2]
        udEdgesSlicePrune = prunes[3]
    }

    static func load(bundle: Bundle) throws -> SolverKociembaTables {
        guard let url = bundle.url(forResource: "kociemba-tables", withExtension: "bin") else {
            throw SolverKociembaTablesError.missingResource
        }
        return try load(data: Data(contentsOf: url, options: .mappedIfSafe))
    }

    static func load(data: Data) throws -> SolverKociembaTables {
        var r = Reader(data: data)
        guard try r.bytes(4) == Array("KCB1".utf8) else { throw SolverKociembaTablesError.badHeader }
        let n = Int(try r.u32())
        guard n == moveTableSpecs.count + pruneTableSpecs.count else { throw SolverKociembaTablesError.badHeader }
        var moves: [[UInt16]] = []
        var prunes: [SolverNibbleTable] = []
        for spec in moveTableSpecs + pruneTableSpecs {
            let nameLen = Int(try r.u8())
            guard let name = String(bytes: try r.bytes(nameLen), encoding: .utf8), name == spec.name else {
                throw SolverKociembaTablesError.badTable(spec.name)
            }
            let kind = try r.u8()
            let count = Int(try r.u32())
            guard count == spec.count else { throw SolverKociembaTablesError.badTable(spec.name) }
            switch kind {
            case 1:
                moves.append(try r.u16Array(count))
            case 2:
                prunes.append(SolverNibbleTable(count: count, bytes: try r.bytes((count + 1) / 2)))
            default:
                throw SolverKociembaTablesError.badTable(spec.name)
            }
        }
        guard moves.count == moveTableSpecs.count, prunes.count == pruneTableSpecs.count else {
            throw SolverKociembaTablesError.badHeader
        }
        return SolverKociembaTables(moves: moves, prunes: prunes)
    }

    /// Ghi ra định dạng trên (tool dùng).
    func encoded() -> Data {
        var out = Data("KCB1".utf8)
        func u32(_ v: Int) { withUnsafeBytes(of: UInt32(v).littleEndian) { out.append(contentsOf: $0) } }
        func header(_ name: String, kind: UInt8, count: Int) {
            out.append(UInt8(name.utf8.count))
            out.append(contentsOf: Array(name.utf8))
            out.append(kind)
            u32(count)
        }
        u32(Self.moveTableSpecs.count + Self.pruneTableSpecs.count)
        for (spec, table) in zip(Self.moveTableSpecs, [twistMove, flipMove, sliceSortedMove, cornersMove, udEdgesMove]) {
            header(spec.name, kind: 1, count: table.count)
            for v in table { withUnsafeBytes(of: v.littleEndian) { out.append(contentsOf: $0) } }
        }
        for (spec, table) in zip(Self.pruneTableSpecs,
                                 [twistSlicePrune, flipSlicePrune, cornersSlicePrune, udEdgesSlicePrune]) {
            header(spec.name, kind: 2, count: table.count)
            out.append(contentsOf: table.bytes)
        }
        return out
    }

    /// Tính mọi bảng từ đầu (chỉ chạy trong tool `-O`; ở -O0 mất cả phút).
    static func build() -> SolverKociembaTables {
        let all = Array(0..<18)
        let twistMove = K.buildMoveTable(count: K.twistCount, moves: all, get: K.twist, set: K.cube(twist:))
        let flipMove = K.buildMoveTable(count: K.flipCount, moves: all, get: K.flip, set: K.cube(flip:))
        let sliceMove = K.buildMoveTable(count: K.sliceSortedCount, moves: all, get: K.sliceSorted,
                                         set: K.cube(sliceSorted:))
        let cornersMove = K.buildMoveTable(count: K.cornersCount, moves: K.phase2Moves, get: K.corners,
                                           set: K.cube(corners:))
        let udMove = K.buildMoveTable(count: K.udEdgesCount, moves: K.phase2Moves, get: K.udEdges,
                                      set: K.cube(udEdges:))
        // Toạ độ tổ hợp tầng giữa (pha 1) đi theo `sliceSorted` của đại diện có thứ tự 0.
        let sliceA: (Int, Int) -> Int = { a, m in Int(sliceMove[(a * 24) * 18 + m]) / 24 }
        let twistSlice = K.buildPruneTable(countA: K.twistCount, countB: K.sliceCount, moveCount: 18,
                                           moveA: { Int(twistMove[$0 * 18 + $1]) }, moveB: sliceA)
        let flipSlice = K.buildPruneTable(countA: K.flipCount, countB: K.sliceCount, moveCount: 18,
                                          moveA: { Int(flipMove[$0 * 18 + $1]) }, moveB: sliceA)
        let slice2: (Int, Int) -> Int = { b, m in Int(sliceMove[b * 18 + K.phase2Moves[m]]) % 24 }
        let cornersSlice = K.buildPruneTable(countA: K.cornersCount, countB: K.slicePhase2Count, moveCount: 10,
                                             moveA: { Int(cornersMove[$0 * 10 + $1]) }, moveB: slice2)
        let udSlice = K.buildPruneTable(countA: K.udEdgesCount, countB: K.slicePhase2Count, moveCount: 10,
                                        moveA: { Int(udMove[$0 * 10 + $1]) }, moveB: slice2)
        return SolverKociembaTables(moves: [twistMove, flipMove, sliceMove, cornersMove, udMove],
                                    prunes: [twistSlice, flipSlice, cornersSlice, udSlice])
    }

    private struct Reader {
        let data: Data
        var offset: Int

        init(data: Data) {
            self.data = data
            offset = data.startIndex
        }

        mutating func bytes(_ n: Int) throws -> [UInt8] {
            guard n >= 0, data.endIndex - offset >= n else { throw SolverKociembaTablesError.truncated }
            defer { offset += n }
            return [UInt8](data[offset..<(offset + n)])
        }

        mutating func u8() throws -> UInt8 { try bytes(1)[0] }

        mutating func u32() throws -> UInt32 {
            let b = try bytes(4)
            return UInt32(b[0]) | UInt32(b[1]) << 8 | UInt32(b[2]) << 16 | UInt32(b[3]) << 24
        }

        mutating func u16Array(_ count: Int) throws -> [UInt16] {
            let n = count * 2
            guard data.endIndex - offset >= n else { throw SolverKociembaTablesError.truncated }
            var out = [UInt16](repeating: 0, count: count)
            out.withUnsafeMutableBytes { dst in
                data.copyBytes(to: dst.bindMemory(to: UInt8.self), from: offset..<(offset + n))
            }
            offset += n
            // File little-endian; mọi thiết bị Apple hiện tại cũng little-endian — đổi chỉ khi khác.
            if UInt16(1).littleEndian != 1 { out = out.map { UInt16(littleEndian: $0) } }
            return out
        }
    }
}
