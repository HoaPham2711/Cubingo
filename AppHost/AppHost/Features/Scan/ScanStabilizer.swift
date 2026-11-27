import Foundation

/// Báo "khung hình đứng yên" để tự chụp: mọi ô lệch ≤ `maxDeltaE` so với khung trước suốt ≥ `window` giây. Báo MỘT
/// lần; muốn báo lại phải `reset()`.
struct ScanStabilizer {
    let window: TimeInterval
    let maxDeltaE: Double
    private var previous: [CubeRGB]?
    private var stableSince: TimeInterval?
    private var fired = false

    init(window: TimeInterval = 0.6, maxDeltaE: Double = 6) {
        self.window = window
        self.maxDeltaE = maxDeltaE
    }

    mutating func feed(_ s: [CubeRGB], at t: TimeInterval) -> Bool {
        defer { previous = s }
        guard let previous, previous.count == s.count,
              zip(previous, s).allSatisfy({ CubeColorMath.deltaE($0, $1) <= maxDeltaE }) else {
            stableSince = t
            return false
        }
        let since = stableSince ?? t
        stableSince = since
        guard !fired, t - since >= window - 1e-9 else { return false }
        fired = true
        return true
    }

    mutating func reset() {
        previous = nil
        stableSince = nil
        fired = false
    }
}
