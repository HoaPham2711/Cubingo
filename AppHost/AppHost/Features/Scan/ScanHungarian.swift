import Foundation

/// Bài toán gán tối thiểu (thuật toán Hungarian với thế vị, O(n³)) trên ma trận vuông.
enum ScanHungarian {
    /// `result[i]` = cột gán cho hàng i, tổng chi phí nhỏ nhất.
    static func assign(cost: [[Double]]) -> [Int] {
        let n = cost.count
        guard n > 0 else { return [] }
        let inf = Double.infinity
        var u = [Double](repeating: 0, count: n + 1), v = [Double](repeating: 0, count: n + 1)
        var p = [Int](repeating: 0, count: n + 1), way = [Int](repeating: 0, count: n + 1)
        for i in 1...n {
            p[0] = i
            var j0 = 0
            var minv = [Double](repeating: inf, count: n + 1)
            var used = [Bool](repeating: false, count: n + 1)
            repeat {
                used[j0] = true
                let i0 = p[j0]
                var delta = inf, j1 = 0
                for j in 1...n where !used[j] {
                    let cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j] {
                        minv[j] = cur
                        way[j] = j0
                    }
                    if minv[j] < delta {
                        delta = minv[j]
                        j1 = j
                    }
                }
                for j in 0...n {
                    if used[j] {
                        u[p[j]] += delta
                        v[j] -= delta
                    } else {
                        minv[j] -= delta
                    }
                }
                j0 = j1
            } while p[j0] != 0
            repeat {
                let j1 = way[j0]
                p[j0] = p[j1]
                j0 = j1
            } while j0 != 0
        }
        var result = [Int](repeating: 0, count: n)
        for j in 1...n where p[j] > 0 { result[p[j] - 1] = j - 1 }
        return result
    }
}
