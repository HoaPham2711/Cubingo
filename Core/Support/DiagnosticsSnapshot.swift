import Foundation
import UIKit

/// Một dòng chẩn đoán riêng của app (ngoài sáu dòng lõi): nhãn + giá trị. App tự quyết thêm gì;
/// lõi chỉ nhận qua `DiagnosticsSnapshot.init`/`current(extras:)`, lọc nhãn, và nói đúng nhãn đó
/// trong câu quyền riêng tư.
struct DiagnosticsField: Equatable {
    let label: String
    let value: String
}

/// Chẩn đoán kèm theo phản hồi. Mọi giá trị **bơm qua init** — `current()` là chỗ duy nhất đọc
/// môi trường thật, nhờ đó toàn bộ luật cắt/định dạng test được mà không dựng thiết bị.
///
/// Danh sách trường là WHITELIST, không phải gợi ý: nhãn lõi (`coreLabels`, test ghim nguyên
/// danh sách) + nhãn extras do app khai (đã lọc ở `init`). Có test chặn trường lạ lọt vào. Thêm
/// trường lõi mới = sửa test ghim + cân lại ngân sách độ dài + soát lại câu quyền riêng tư (câu
/// này sinh từ chính các nhãn đó nên không thể nói ít hơn thực tế).
///
/// RULING C: `FeedbackDraft.validate()` ép trần `maxDiagnosticsLength` bằng `utf8.count`, KHÔNG
/// phải số ký tự. Nếu cắt ở đây theo `.count` thì một log tiếng Việt "ngắn" về số ký tự vẫn có
/// thể NẶNG hơn trần byte → validate() ném `.diagnosticsTooLong` và log biến mất hoàn toàn, không
/// có manh mối. Vì vậy mọi phép cắt trong file này đo bằng `utf8.count` và không bao giờ cắt giữa
/// một ký tự nhiều byte (xem `cutByUTF8ByteLimit`).
///
/// Bố cục chống mất dữ liệu: `cutByUTF8ByteLimit` giữ ĐUÔI nên phần ĐẦU (sáu dòng lõi + extras) phải
/// được bảo vệ khỏi bị cắt. Vì vậy phần đầu có trần riêng (`maxHeadLength`): mỗi giá trị extra bị
/// cắt giữ ĐẦU theo `maxExtraValueLength`, extra nào không còn chỗ trong phần đầu bị loại ngay ở
/// `init` (nên `extras`, `text`, `privacySummary` luôn cùng một nguồn). Phần BỊ CẮT là log: ngân
/// sách log = trần tổng − byte phần đầu − dòng phân cách. Chốt chặn cuối ở `text` chỉ là lưới an toàn.
///
/// Log: không call site nào tự đính log; `logTail` mặc định rỗng và không có cơ chế đính log tự
/// động. Nếu có đính thì câu quyền riêng tư nói rõ có "recent log lines".
struct DiagnosticsSnapshot {
    /// Nhãn lõi — đúng thứ tự các dòng đầu của `text`, và là nguồn của câu quyền riêng tư.
    static let coreLabels = ["app version", "build", "device model", "iOS version", "locale", "free storage"]

    /// Nhãn dành riêng cho phần log, không extras nào được mượn.
    private static let logLabel = "log"

    /// Trần cứng của đuôi log (còn bị ngân sách còn lại sau phần đầu giới hạn thêm).
    static let maxLogTailLength = 11000
    /// Trần byte của phần đầu (lõi + extras). Lõi chỉ ~150 byte; phần còn lại dành cho extras.
    static let maxHeadLength = 3000
    /// Trần byte mỗi giá trị extra (cắt giữ ĐẦU giá trị) và mỗi nhãn extra (nhãn dài hơn bị loại).
    static let maxExtraValueLength = 500
    static let maxExtraLabelLength = 64
    private static let logSeparator = "\nlog:\n"

    let appVersion: String
    let build: String
    let deviceModel: String
    let systemVersion: String
    let locale: String
    let freeDiskMB: Int
    /// Extras đã lọc: nhãn rỗng, trùng nhãn lõi/`log` (không phân biệt hoa thường), chứa xuống dòng
    /// hoặc dấu `:`, hay trùng extras đứng trước đều BỊ BỎ — vừa không gửi đi, vừa không vào câu
    /// quyền riêng tư. Giá trị bị ép về một dòng để không dựng "dòng" giả.
    let extras: [DiagnosticsField]
    let logTail: String

    init(appVersion: String, build: String, deviceModel: String, systemVersion: String,
         locale: String, freeDiskMB: Int, extras: [DiagnosticsField] = [], logTail: String = "") {
        self.appVersion = appVersion
        self.build = build
        self.deviceModel = deviceModel
        self.systemVersion = systemVersion
        self.locale = locale
        self.freeDiskMB = freeDiskMB
        let lines = Self.coreLines(appVersion: appVersion, build: build, deviceModel: deviceModel,
                                   systemVersion: systemVersion, locale: locale, freeDiskMB: freeDiskMB)
        self.extras = Self.loc(extras, coreHeadBytes: lines.joined(separator: "\n").utf8.count)
        self.logTail = logTail
    }

    private static func coreLines(appVersion: String, build: String, deviceModel: String,
                                  systemVersion: String, locale: String, freeDiskMB: Int) -> [String] {
        [
            "\(coreLabels[0]): \(appVersion)",
            "\(coreLabels[1]): \(build)",
            "\(coreLabels[2]): \(deviceModel)",
            "\(coreLabels[3]): \(systemVersion)",
            "\(coreLabels[4]): \(locale)",
            "\(coreLabels[5]): \(freeDiskMB) MB",
        ]
    }

    private static func loc(_ raw: [DiagnosticsField], coreHeadBytes: Int) -> [DiagnosticsField] {
        var daDung = Set((coreLabels + [logLabel]).map { $0.lowercased() })
        var giu: [DiagnosticsField] = []
        var conLai = maxHeadLength - coreHeadBytes
        for f in raw {
            let nhan = f.label.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !nhan.isEmpty,
                  nhan.utf8.count <= maxExtraLabelLength,
                  nhan.rangeOfCharacter(from: CharacterSet(charactersIn: "\n\r:")) == nil,
                  daDung.insert(nhan.lowercased()).inserted else { continue }
            let giaTri = cutHeadByUTF8ByteLimit(
                f.value.components(separatedBy: .newlines).joined(separator: " ")
                    .trimmingCharacters(in: .whitespaces),
                limit: maxExtraValueLength)
            // "\n" + "nhãn: giá trị"; hết chỗ trong phần đầu ⇒ loại hẳn (không gửi, không vào câu).
            let chiPhi = 1 + nhan.utf8.count + 2 + giaTri.utf8.count
            guard chiPhi <= conLai else { continue }
            conLai -= chiPhi
            giu.append(DiagnosticsField(label: nhan, value: giaTri))
        }
        return giu
    }

    /// Phần đầu: sáu dòng lõi + extras đã lọc. Luôn nguyên vẹn (không bao giờ bị cắt).
    private var head: String {
        let lines = Self.coreLines(appVersion: appVersion, build: build, deviceModel: deviceModel,
                                   systemVersion: systemVersion, locale: locale, freeDiskMB: freeDiskMB)
            + extras.map { "\($0.label): \($0.value)" }
        return lines.joined(separator: "\n")
    }

    /// Đuôi log thực sự được gửi (rỗng ⇒ không có mục `log:`). Ngân sách = trần tổng − phần đầu − dòng phân cách.
    private var includedLog: String {
        guard !logTail.isEmpty else { return "" }
        let nganSach = FeedbackDraft.maxDiagnosticsLength - head.utf8.count - Self.logSeparator.utf8.count
        return Self.cutByUTF8ByteLimit(logTail, limit: min(Self.maxLogTailLength, max(0, nganSach)))
    }

    var text: String {
        // Cắt log từ ĐUÔI: dòng gần lỗi nhất mới có giá trị chẩn đoán. Đo bằng byte UTF-8, không
        // phải ký tự (RULING C) — khớp đơn vị `FeedbackDraft.validate()` dùng.
        let log = includedLog
        let dayDu = log.isEmpty ? head : head + Self.logSeparator + log
        // Lưới an toàn cuối: phần đầu và ngân sách log đã đảm bảo ≤ trần, đây chỉ chặn lỗi bất ngờ.
        return Self.cutByUTF8ByteLimit(dayDu, limit: FeedbackDraft.maxDiagnosticsLength)
    }

    /// Câu dưới form: liệt kê ĐÚNG các nhãn đang được gửi (lõi + extras đã lọc, + log nếu có) nên
    /// không bao giờ nói ít hơn thực tế. Đã localize (nhãn lõi là tiếng Anh cố định, nhãn extras do
    /// app đặt) — view hiển thị `verbatim`. Khi thêm ngôn ngữ: chỉ localize nhãn lõi cho CÂU hiển thị;
    /// nhãn trong bản GỬI đi (`text`) giữ cố định tiếng Anh.
    var privacySummary: String {
        var nhan = Self.coreLabels + extras.map(\.label)
        if !includedLog.isEmpty { nhan.append("recent log lines") }
        let danhSach = ListFormatter.localizedString(byJoining: nhan)
        return String(localized: "Sends your \(danhSach). Nothing else from your device is included.")
    }

    /// Giữ ĐUÔI của `text`, cắt sao cho `result.utf8.count <= limit`, KHÔNG BAO GIỜ cắt giữa một
    /// ký tự UTF-8 nhiều byte (cắt thô sinh chuỗi hỏng / ký tự thay thế U+FFFD).
    ///
    /// Cách làm: tìm nhị phân số ký tự (grapheme cluster) lớn nhất của phần đuôi mà tổng byte
    /// vẫn lọt trần. Luôn bỏ nguyên một ký tự một lần nên biên cắt luôn trùng biên ký tự —
    /// không bao giờ đứt giữa chuỗi byte của một scalar.
    static func cutByUTF8ByteLimit(_ text: String, limit: Int) -> String {
        guard limit > 0 else { return "" }
        guard text.utf8.count > limit else { return text }

        // Nhị phân trên số ký tự (không phải byte) để tránh vòng lặp bỏ-từng-ký-tự trên input
        // rất dài (ví dụ log 500 000 ký tự) — phải rẻ ngay cả khi limit nhỏ hơn nhiều độ dài input.
        var low = 0
        var high = text.count
        // Tìm số ký tự lớn nhất mà phần đuôi vẫn <= limit.
        while low < high {
            let mid = (low + high + 1) / 2
            let candidate = String(text.suffix(mid))
            if candidate.utf8.count <= limit {
                low = mid
            } else {
                high = mid - 1
            }
        }
        return String(text.suffix(low))
    }

    /// Giữ ĐẦU của `text`, cắt sao cho `result.utf8.count <= limit`, không đứt giữa ký tự.
    static func cutHeadByUTF8ByteLimit(_ text: String, limit: Int) -> String {
        guard limit > 0 else { return "" }
        guard text.utf8.count > limit else { return text }
        var low = 0
        var high = text.count
        while low < high {
            let mid = (low + high + 1) / 2
            if String(text.prefix(mid)).utf8.count <= limit { low = mid } else { high = mid - 1 }
        }
        return String(text.prefix(low))
    }

    static func current(extras: [DiagnosticsField] = [], logTail: String = "") -> DiagnosticsSnapshot {
        let info = Bundle.main.infoDictionary
        var may = utsname()
        uname(&may)
        let model = withUnsafePointer(to: &may.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: 1) { String(validatingUTF8: $0) ?? "?" }
        }
        let free = (try? URL(fileURLWithPath: NSHomeDirectory())
            .resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey])
            .volumeAvailableCapacityForImportantUsage) ?? 0
        return DiagnosticsSnapshot(
            appVersion: info?["CFBundleShortVersionString"] as? String ?? "?",
            build: info?["CFBundleVersion"] as? String ?? "?",
            deviceModel: model,
            systemVersion: UIDevice.current.systemVersion,
            locale: Locale.current.identifier,
            freeDiskMB: Int((free ?? 0) / 1_000_000),
            extras: extras,
            logTail: logTail)
    }
}
