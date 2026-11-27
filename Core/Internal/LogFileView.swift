#if INTERNAL
import SwiftUI

// MARK: - Dữ liệu log (thuần, test được)

/// Tách log thành dòng + tìm trong log cho `LogFileView`.
///
/// Vì sao không nạp cả file vào MỘT `Text`: file log dài tới vài MB, một `Text` cỡ đó SwiftUI không dựng nổi (màn
/// trắng, phải export sang Mac mới đọc được). Tách theo dòng rồi hiện bằng `List` (dựng lười) thì chỉ vài chục dòng
/// trên màn được vẽ.
enum InternalLogText {
    /// Dòng dài hơn ngưỡng này cắt bớt khi HIỆN (vẫn tìm trên cả dòng) — dump một dòng vài chục KB làm một ô `List`
    /// tự đo rất chậm.
    static let maxDisplayChars = 4000

    /// Tách theo byte `\n` (bỏ `\r` cuối dòng). Giải mã UTF-8 lỏng: log có thể bị cắt giữa ký tự khi app chết lúc
    /// đang ghi (`String(contentsOf:)` sẽ trả nil ⇒ không đọc được gì). File kết thúc bằng `\n` không sinh thêm dòng
    /// rỗng cuối.
    static func lines(of data: Data) -> [String] {
        var out = data.split(separator: 0x0A, omittingEmptySubsequences: false).map { chunk -> String in
            let body = chunk.last == 0x0D ? chunk.dropLast() : chunk[...]
            return String(decoding: body, as: UTF8.self)
        }
        if out.count > 1, out.last?.isEmpty == true { out.removeLast() }
        if out == [""] { return [] }
        return out
    }

    /// Chỉ số (0-based) các dòng chứa `query`, không phân biệt hoa thường. Query rỗng ⇒ [].
    static func matches(_ lines: [String], query: String) -> [Int] {
        guard !query.isEmpty else { return [] }
        var out = [Int]()
        for (i, l) in lines.enumerated() where l.range(of: query, options: .caseInsensitive) != nil {
            out.append(i)
        }
        return out
    }

    /// Vị trí trong `matches` để đứng lúc mở: lần khớp đầu tiên tại/sau `line` (0-based); không có thì lần khớp đầu.
    static func matchIndex(near line: Int?, in matches: [Int]) -> Int {
        guard let line, !matches.isEmpty else { return 0 }
        return matches.firstIndex { $0 >= line } ?? 0
    }

    static func displayText(_ s: String) -> String {
        s.count > maxDisplayChars
            ? String(s.prefix(maxDisplayChars)) + " … (+\(s.count - maxDisplayChars) ký tự)"
            : s
    }

    /// Tô nền MỌI lần khớp `query` (không phân biệt hoa thường) trong `s`; chữ giữ nguyên.
    static func highlighted(_ s: String, query: String) -> AttributedString {
        var out = AttributedString(s)
        guard !query.isEmpty else { return out }
        var from = s.startIndex
        while from < s.endIndex,
              let r = s.range(of: query, options: .caseInsensitive, range: from..<s.endIndex) {
            if let lo = AttributedString.Index(r.lowerBound, within: out),
               let hi = AttributedString.Index(r.upperBound, within: out) {
                out[lo..<hi].backgroundColor = Color.yellow.opacity(0.5)
            }
            from = r.upperBound
        }
        return out
    }
}

// MARK: - Viewer

/// Viewer log monospace: số dòng, dựng lười (log vài MB vẫn mở tức thì), tìm trong log với lên/xuống giữa các lần
/// khớp, lọc "chỉ dòng khớp", nhảy đầu/cuối file. `focusLine` (1-based) = cuộn tới dòng đó lúc mở và tô nền.
/// Chỉ build nội bộ: bản App Store không có lối nào mở log.
struct LogFileView: View {
    let url: URL
    var focusLine: Int?

    @State private var lines: [String]?
    @State private var query: String
    @State private var matches: [Int] = []
    /// Vị trí trong `matches` đang đứng.
    @State private var current = 0
    @State private var searching = false
    @State private var onlyMatches = false
    @State private var showShare = false
    /// Yêu cầu cuộn tới dòng (0-based). `scrollTick` tăng mỗi lần để cuộn được cả khi đứng lại cùng dòng. (Hai state
    /// rời thay vì một struct lồng: lint `debug_symbols.txt` bắt khai mọi type lồng trong vùng INTERNAL.)
    @State private var scrollLine = 0
    @State private var scrollTick = 0

    init(url: URL, focusLine: Int? = nil, initialQuery: String = "") {
        self.url = url
        self.focusLine = focusLine
        _query = State(initialValue: initialQuery)
    }

    private var trimmed: String { query.trimmingCharacters(in: .whitespacesAndNewlines) }
    private var currentLine: Int? { matches.indices.contains(current) ? matches[current] : nil }

    var body: some View {
        ScrollViewReader { proxy in
            Group {
                if let lines {
                    if lines.isEmpty {
                        dtext("File log rỗng.").font(.caption).foregroundColor(.secondary)
                    } else {
                        list(lines)
                    }
                } else {
                    HStack { ProgressView(); dtext("Đang đọc log…").font(.caption) }
                }
            }
            .onChange(of: scrollTick) { _, _ in
                withAnimation(nil) { proxy.scrollTo(scrollLine, anchor: .center) }
            }
        }
        .navigationTitle(dtext(url.lastPathComponent))
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always),
                    prompt: dtext("Tìm trong log"))
        .textInputAutocapitalization(.never)
        .autocorrectionDisabled()
        .onSubmit(of: .search) { step(+1) }
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                Menu {
                    Button { jump(to: 0) } label: {
                        Label { dtext("Đầu file") } icon: { Image(systemName: "arrow.up.to.line") }
                    }
                    Button { jump(to: (lines?.count ?? 1) - 1) } label: {
                        Label { dtext("Cuối file") } icon: { Image(systemName: "arrow.down.to.line") }
                    }
                } label: { Image(systemName: "arrow.up.arrow.down") }
                .disabled(lines?.isEmpty ?? true)
                Button { showShare = true } label: { Image(systemName: "square.and.arrow.up") }
            }
        }
        // Không dùng `.bottomBar`: trên iOS 26 tab bar nổi đè lên nó và không ẩn được. `safeAreaInset` luôn nằm TRÊN
        // tab bar.
        .safeAreaInset(edge: .bottom, spacing: 0) {
            if !trimmed.isEmpty {
                searchBar
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .frame(maxWidth: .infinity)
                    .background(.ultraThinMaterial)
            }
        }
        .sheet(isPresented: $showShare) { ShareSheet(items: [url]) }
        .task { await load() }
        // Đổi query ⇒ task cũ tự huỷ (debounce gõ phím).
        .task(id: "\(trimmed)|\(lines?.count ?? -1)") { await runSearch() }
    }

    private func list(_ lines: [String]) -> some View {
        let q = trimmed
        let rows: [Int] = onlyMatches && !q.isEmpty ? matches : Array(lines.indices)
        let width = CGFloat(max(3, String(lines.count).count)) * 7.5
        return List(rows, id: \.self) { i in
            let text = InternalLogText.displayText(lines[i])
            HStack(alignment: .top, spacing: 6) {
                Text(verbatim: "\(i + 1)").foregroundColor(.secondary)
                    .frame(width: width, alignment: .trailing)
                Group {
                    if !q.isEmpty, text.range(of: q, options: .caseInsensitive) != nil {
                        Text(InternalLogText.highlighted(text, query: q))
                    } else {
                        Text(verbatim: text)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
            }
            .font(.system(size: 11, design: .monospaced))
            .listRowInsets(EdgeInsets(top: 1, leading: 6, bottom: 1, trailing: 6))
            .listRowSeparator(.hidden)
            .listRowBackground(rowBackground(i))
            .id(i)
        }
        .listStyle(.plain)
        .environment(\.defaultMinListRowHeight, 12)
    }

    private func rowBackground(_ i: Int) -> Color {
        if i == currentLine { return Color.orange.opacity(0.35) }
        if let f = focusLine, i == f - 1, trimmed.isEmpty { return Color.yellow.opacity(0.35) }
        return Color.clear
    }

    private var searchBar: some View {
        HStack(spacing: 22) {
            if searching {
                ProgressView()
            } else {
                dtext(matches.isEmpty ? "Không khớp" : "\(current + 1)/\(matches.count) dòng")
                    .font(.caption.monospacedDigit())
            }
            Spacer()
            Button { onlyMatches.toggle() } label: {
                Image(systemName: onlyMatches
                      ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
            }
            .disabled(matches.isEmpty)
            Button { step(-1) } label: { Image(systemName: "chevron.up") }
                .disabled(matches.isEmpty)
            Button { step(+1) } label: { Image(systemName: "chevron.down") }
                .disabled(matches.isEmpty)
        }
    }

    private func requestScroll(to line: Int) {
        scrollLine = line
        scrollTick += 1
    }

    private func load() async {
        guard lines == nil else { return }
        let url = url
        let loaded = await Task.detached(priority: .userInitiated) { () -> [String] in
            guard let data = try? Data(contentsOf: url) else { return ["Couldn't read file."] }
            return InternalLogText.lines(of: data)
        }.value
        lines = loaded
        if let f = focusLine, trimmed.isEmpty {
            // Đợi `List` dựng xong rồi mới cuộn.
            let line = min(max(0, f - 1), loaded.count - 1)
            DispatchQueue.main.async { requestScroll(to: line) }
        }
    }

    private func runSearch() async {
        guard let lines else { return }
        let q = trimmed
        guard !q.isEmpty else {
            matches = []; current = 0; searching = false
            return
        }
        searching = true
        try? await Task.sleep(for: .milliseconds(250))
        if Task.isCancelled { return }
        let found = await Task.detached(priority: .userInitiated) {
            InternalLogText.matches(lines, query: q)
        }.value
        if Task.isCancelled { return }
        // Lần đầu (mở với `focusLine`) đứng ở lần khớp tại dòng được chỉ; về sau giữ vị trí gần dòng đang đứng.
        let anchor = currentLine ?? focusLine.map { $0 - 1 }
        matches = found
        current = InternalLogText.matchIndex(near: anchor, in: found)
        searching = false
        if let l = currentLine { DispatchQueue.main.async { requestScroll(to: l) } }
    }

    private func step(_ d: Int) {
        guard !matches.isEmpty else { return }
        current = (current + d + matches.count) % matches.count
        requestScroll(to: matches[current])
    }

    private func jump(to line: Int) {
        guard let lines, !lines.isEmpty else { return }
        // Đang lọc chỉ dòng khớp thì dòng đích có thể không có trong danh sách — bỏ lọc.
        onlyMatches = false
        let target = min(max(0, line), lines.count - 1)
        DispatchQueue.main.async { requestScroll(to: target) }
    }
}
#endif
