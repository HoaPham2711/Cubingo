import SwiftUI

/// Một nhóm trong thanh phân bố dung lượng. `title` đã localize tại nguồn (app bọc `String(localized:)`), `color`
/// lấy từ token biểu đồ (`DSColor.chartSeries1/2/3`).
///
/// Thứ tự và màu nên CỐ ĐỊNH theo nhóm, không theo độ lớn: đổi tập dữ liệu đang xem mà slice bị sơn lại thì người
/// đọc mất mốc so sánh giữa hai lần nhìn. Nhóm 0 byte nên bị loại trước khi đưa vào chart.
struct StorageSlice: Identifiable, Equatable {
    let id: String
    let title: String
    let bytes: Int64
    let color: Color
}

/// Phần tính thuần của biểu đồ (có test, view chỉ gọi lại): bề rộng segment, nhãn %, nhãn dung lượng.
/// Byte âm coi như 0; tổng 0 ⇒ không chia cho 0.
enum StorageBarMath {
    private static func clean(_ bytes: [Int64]) -> [Int64] { bytes.map { max($0, 0) } }

    /// Chia bề ngang `total` (đã gồm `gap` giữa các segment) theo byte. Lát 0 byte ⇒ 0. Lát > 0 có sàn `minSegment`
    /// để không "biến mất"; sàn mượn chỗ nên trừ lại ở lát lớn, và nếu vẫn quá (quá nhiều lát tại sàn) thì co đều
    /// ⇒ Σ width + gap × (n−1) ≤ total, không bao giờ tràn thanh.
    static func widths(bytes: [Int64], total: CGFloat, minSegment: CGFloat = 3, gap: CGFloat = 0) -> [CGFloat] {
        guard !bytes.isEmpty else { return [] }
        let b = clean(bytes)
        let sum = b.reduce(Int64(0), +)
        let usable = max(total - gap * CGFloat(b.count - 1), 0)
        guard sum > 0, usable > 0 else { return b.map { _ in 0 } }
        var w = b.map { $0 > 0 ? max(usable * CGFloat(Double($0) / Double(sum)), minSegment) : 0 }
        let thua = w.reduce(0, +) - usable
        if thua > 0 {
            let duDia = w.map { max($0 - minSegment, 0) }
            let tongDuDia = duDia.reduce(0, +)
            if tongDuDia > 0 {
                let bot = min(thua, tongDuDia)
                for i in w.indices { w[i] -= bot * duDia[i] / tongDuDia }
            }
            let con = w.reduce(0, +)
            if con > usable { let k = usable / con; w = w.map { $0 * k } }
        }
        return w
    }

    /// Nhãn % — phương pháp phần dư lớn nhất. Lát > 0 mà < 1 % ⇒ "<1%" và GIỮ 1 điểm % cho nó, nên các nhãn số cộng
    /// với 1 mỗi nhãn "<1%" luôn đúng 100 (không có "100%" đứng cạnh "<1%"). Lát 0 byte ⇒ "0%".
    static func percentLabels(bytes: [Int64]) -> [String] {
        let b = clean(bytes)
        let sum = b.reduce(Int64(0), +)
        guard sum > 0 else { return b.map { _ in "0%" } }
        let pct = b.map { Double($0) * 100 / Double(sum) }
        let nho = pct.indices.filter { b[$0] > 0 && pct[$0] < 1 }
        let lon = pct.indices.filter { pct[$0] >= 1 }
        let ngan = 100 - nho.count
        let tongLon = lon.reduce(0.0) { $0 + pct[$1] }
        var kq = Array(repeating: 0, count: b.count)
        if tongLon > 0, ngan > 0 {
            let quota = lon.map { pct[$0] * Double(ngan) / tongLon }
            var duoc = quota.map { Int($0.rounded(.down)) }
            var thieu = ngan - duoc.reduce(0, +)
            for k in quota.indices.sorted(by: { (quota[$0] - Double(duoc[$0]), $1) > (quota[$1] - Double(duoc[$1]), $0) }) {
                if thieu <= 0 { break }
                duoc[k] += 1; thieu -= 1
            }
            for (k, i) in lon.enumerated() { kq[i] = duoc[k] }
        }
        return b.indices.map { i in
            if b[i] == 0 { return "0%" }
            return pct[i] < 1 || kq[i] == 0 ? "<1%" : "\(kq[i])%"
        }
    }

    private static let fmt: ByteCountFormatter = {
        let f = ByteCountFormatter()
        f.countStyle = .file
        f.allowedUnits = [.useKB, .useMB, .useGB]
        // Mặc định `true` in 0 byte là "Zero KB".
        f.allowsNonnumericFormatting = false
        return f
    }()

    /// 0 ⇒ "0 KB" (không "Zero KB"); 1…1023 byte ⇒ "<1 KB" (formatter làm tròn xuống "0 KB" đọc như dữ liệu rác).
    static func sizeLabel(_ bytes: Int64) -> String {
        // Ngưỡng 1000 (không 1024): `countStyle = .file` là hệ thập phân — 1000 B đã in "1 KB".
        if bytes > 0, bytes < 1000 { return String(localized: "<1 KB") }
        return fmt.string(fromByteCount: max(bytes, 0))
    }
}

/// Thanh phân bố dung lượng xếp chồng + chú giải. Chỉ vẽ danh sách slice nhận vào — phân loại là việc của app.
///
/// Quy tắc giữ nguyên (skill `dataviz`): chú giải LUÔN có kèm nhãn trực tiếp (dung lượng + %) nên danh tính không
/// bao giờ chỉ dựa vào màu; chữ dùng token text chứ không dùng màu của slice; khe hở 2px giữa các segment; bo góc ở
/// hai đầu ngoài của thanh.
struct StorageBarChart: View {
    let slices: [StorageSlice]

    private let barHeight: CGFloat = 14
    private let gap: CGFloat = 2
    private let corner: CGFloat = 4
    /// Segment mỏng hơn mức này thì mắt không thấy — kéo lên sàn để nhóm nhỏ không "biến mất".
    private let minSegment: CGFloat = 3
    /// Cột % rộng 42pt ở cỡ chữ mặc định, rộng theo chữ — cố định thì cỡ trợ năng bẻ "100 %" thành ba dòng.
    @ScaledMetric(relativeTo: .caption) private var percentWidth: CGFloat = 42

    var body: some View {
        let bytes = slices.map(\.bytes)
        let nhan = StorageBarMath.percentLabels(bytes: bytes)
        VStack(alignment: .leading, spacing: 10) {
            if slices.isEmpty { thanhRong } else { thanh(bytes) }
            ForEach(Array(slices.enumerated()), id: \.element.id) { i, s in dongChuGiai(s, percent: nhan[i]) }
        }
        .padding(.vertical, 4)
    }

    private var thanhRong: some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: corner, style: .continuous)
                .fill(DSColor.hairlineOnCard)
                .frame(height: barHeight)
            Text("No data yet")
                .font(.caption)
                .foregroundColor(DSColor.textTertiary)
                .fixedSize()
        }
    }

    private func thanh(_ bytes: [Int64]) -> some View {
        GeometryReader { geo in
            HStack(spacing: gap) {
                ForEach(Array(StorageBarMath.widths(bytes: bytes, total: geo.size.width,
                                                          minSegment: minSegment, gap: gap).enumerated()), id: \.offset) { i, w in
                    Rectangle()
                        .fill(slices[i].color)
                        .frame(width: w)
                }
            }
            // Bo ở hai ĐẦU NGOÀI của cả thanh (không bo từng segment) — bo từng cái làm thanh trông như những viên
            // rời rạc thay vì một tổng thể chia phần.
            .clipShape(RoundedRectangle(cornerRadius: corner, style: .continuous))
        }
        .frame(height: barHeight)
    }

    private func dongChuGiai(_ s: StorageSlice, percent: String) -> some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: 3, style: .continuous)
                .fill(s.color)
                .frame(width: 10, height: 10)
            Text(verbatim: s.title)
                .font(.subheadline)
                .foregroundColor(DSColor.textPrimary)
            Spacer(minLength: 8)
            Text(verbatim: StorageBarMath.sizeLabel(s.bytes))
                .font(.subheadline.monospacedDigit())
                .foregroundColor(DSColor.textSecondary)
                .fixedSize()
            Text(verbatim: percent)
                .font(.caption.monospacedDigit())
                .foregroundColor(DSColor.textTertiary)
                .lineLimit(1)
                .frame(width: percentWidth, alignment: .trailing)
        }
    }
}

#Preview {
    StorageBarChart(slices: [
        StorageSlice(id: "a", title: "Series A", bytes: 600_000_000, color: DSColor.chartSeries1),
        StorageSlice(id: "b", title: "Series B", bytes: 150_000_000, color: DSColor.chartSeries2),
        StorageSlice(id: "c", title: "Series C", bytes: 900, color: DSColor.chartSeries3),
    ])
    .padding()
    .background(DSColor.cardBackground)
}
