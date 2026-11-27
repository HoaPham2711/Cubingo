import Foundation

/// Version dạng `MAJOR.MINOR.PATCH` (số thành phần tuỳ ý) so sánh THEO SỐ từng thành phần —
/// so chuỗi sẽ cho `1.10` < `1.9`. Thành phần thiếu coi là 0 (`1.2` == `1.2.0`).
/// Chuỗi có thành phần không phải số nguyên không âm → `nil` (người gọi coi như "không nhắc").
struct AppVersion: Comparable {
    let components: [Int]

    init?(_ string: String) {
        let parts = string.trimmingCharacters(in: .whitespaces)
            .split(separator: ".", omittingEmptySubsequences: false)
        var out: [Int] = []
        for p in parts {
            guard !p.isEmpty, p.allSatisfy(\.isASCIIDigit), let n = Int(p) else { return nil }
            out.append(n)
        }
        guard !out.isEmpty else { return nil }
        components = out
    }

    private static func padded(_ a: AppVersion, _ b: AppVersion) -> ([Int], [Int]) {
        let n = max(a.components.count, b.components.count)
        return (a.components + Array(repeating: 0, count: n - a.components.count),
                b.components + Array(repeating: 0, count: n - b.components.count))
    }

    static func == (a: AppVersion, b: AppVersion) -> Bool {
        let (x, y) = padded(a, b)
        return x == y
    }

    static func < (a: AppVersion, b: AppVersion) -> Bool {
        let (x, y) = padded(a, b)
        return x.lexicographicallyPrecedes(y)
    }
}

private extension Character {
    var isASCIIDigit: Bool { ("0"..."9").contains(self) }
}
