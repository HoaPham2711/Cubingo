import Foundation

/// Bộ sinh số có seed (SplitMix64) — tất định cho test, seed preview và công cụ nội bộ.
struct CubeRandom: RandomNumberGenerator {
    private var state: UInt64

    init(seed: UInt64) { state = seed }

    mutating func next() -> UInt64 {
        state &+= 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }

    /// Trạng thái hợp lệ đều trên mọi trạng thái giải được: hoán vị + định hướng ngẫu nhiên, tổng xoắn ≡ 0 (mod 3),
    /// tổng lật chẵn, chẵn lẻ hai hoán vị khớp (đổi hai cạnh cuối nếu lệch).
    static func state(using rng: inout some RandomNumberGenerator) -> CubeCubies {
        var c = CubeCubies.solved
        c.cp.shuffle(using: &rng)
        c.ep.shuffle(using: &rng)
        if CubeCubies.parity(c.cp) != CubeCubies.parity(c.ep) { c.ep.swapAt(10, 11) }
        for i in 0..<7 { c.co[i] = Int.random(in: 0..<3, using: &rng) }
        c.co[7] = (3 - c.co[0..<7].reduce(0, +) % 3) % 3
        for i in 0..<11 { c.eo[i] = Int.random(in: 0..<2, using: &rng) }
        c.eo[11] = c.eo[0..<11].reduce(0, +) % 2
        return c
    }
}
