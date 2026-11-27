import Foundation

// Sinh `kociemba-tables.bin` cho bộ giải Just solve it. Dùng: `main <đường file ra>`.
// Biên dịch cùng file nguồn của app (xem gen_tables.sh) — định dạng ghi là định dạng app đọc.

let args = CommandLine.arguments
guard args.count == 2 else {
    FileHandle.standardError.write(Data("usage: \(args[0]) <output.bin>\n".utf8))
    exit(2)
}
let start = Date()
let tables = SolverKociembaTables.build()
let data = tables.encoded()
// Tự kiểm: đọc lại đúng bằng code của app.
do {
    let back = try SolverKociembaTables.load(data: data)
    guard back.encoded() == data else { fatalError("đọc lại không khớp") }
} catch {
    fatalError("đọc lại lỗi: \(error)")
}
try data.write(to: URL(fileURLWithPath: args[1]))
let secs = String(format: "%.1f", Date().timeIntervalSince(start))
print("\(args[1]) · \(data.count) bytes · \(secs) s")
