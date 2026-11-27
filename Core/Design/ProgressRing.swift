import SwiftUI

/// Logic thuần cho ProgressRing — tách riêng để test không cần dựng SwiftUI view.
enum ProgressRingMath {
    /// Chuyển % (kẹp về 0...100) thành góc độ 0...360 cho conic-gradient/trim.
    static func degrees(forPercent percent: Int) -> Double {
        let clamped = max(0, min(100, percent))
        return Double(clamped) * 3.6
    }
}

/// Vòng tròn hiển thị % tiến độ quanh một nút/biểu tượng — `content` là view đặt ở giữa.
struct ProgressRing<Content: View>: View {
    /// `nil` = CHƯA CÓ số đo, khác hẳn `0` = đo được và đang ở 0%. Phân biệt hai cái này là bắt
    /// buộc khi vòng là nơi DUY NHẤT báo tiến độ: nguồn số đo có thể đứng im ở nil (vd user tắt
    /// tính năng đo), và vẽ cung 0% trong trường hợp đó là nói dối — trông y hệt "chạy mãi mà
    /// không tiến được chút nào".
    let percent: Int?
    let diameter: CGFloat
    @ViewBuilder let content: () -> Content

    var body: some View {
        ZStack {
            Circle()
                .stroke(DSColor.ringTrack, lineWidth: 6)
            if let percent {
                Circle()
                    .trim(from: 0, to: CGFloat(ProgressRingMath.degrees(forPercent: percent) / 360))
                    .stroke(DSColor.accent, style: StrokeStyle(lineWidth: 6, lineCap: .round))
                    .rotationEffect(.degrees(-90))
            }
            content()
        }
        .frame(width: diameter, height: diameter)
    }
}

#Preview {
    ZStack {
        Color.black.ignoresSafeArea()
        ProgressRing(percent: 62, diameter: 88) {
            Circle().fill(Color.red).frame(width: 32, height: 32)
        }
    }
}
