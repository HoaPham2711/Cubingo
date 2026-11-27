import XCTest
@testable import AppHost

/// Các cổng:
/// 1. Chuỗi gửi đi không bao giờ vượt trần — đo bằng utf8.count, KHỚP với
///    `FeedbackDraft.validate()` (không phải `.count`).
/// 2. Chuỗi gửi đi **không chứa gì ngoài whitelist**: nhãn lõi (ghim nguyên danh sách) + nhãn
///    extras do app khai. Cổng này tồn tại vì rò dữ liệu do vô ý là loại lỗi không có triệu
///    chứng: nó chạy đúng, test xanh, và chỉ lộ khi có người soi dữ liệu đã gửi.
/// 3. Câu quyền riêng tư dưới form sinh từ ĐÚNG những nhãn được gửi — không bao giờ nói ít hơn
///    thực tế.
/// 4. Cắt theo BYTE không được cắt giữa ký tự UTF-8 nhiều byte.
final class DiagnosticsSnapshotTests: XCTestCase {

    private func mau(logTail: String = "tail-ok",
                     extras: [DiagnosticsField] = [DiagnosticsField(label: "plan", value: "gold")])
        -> DiagnosticsSnapshot {
        DiagnosticsSnapshot(appVersion: "1.2", build: "42", deviceModel: "iPhone15,3",
                            systemVersion: "18.0", locale: "vi_VN", freeDiskMB: 1234,
                            extras: extras, logTail: logTail)
    }

    func testChuaDuMoiTruongWhitelist() {
        let t = mau().text
        for phai in ["1.2", "42", "iPhone15,3", "18.0", "vi_VN", "1234", "plan: gold", "tail-ok"] {
            XCTAssertTrue(t.contains(phai), "thiếu trường \(phai) trong chẩn đoán")
        }
    }

    /// Trần đo bằng utf8.count, KHÔNG phải .count — khớp `FeedbackDraft.validate()`. ASCII "x"
    /// thì count == utf8.count nên test này một mình không lộ bug cắt theo ký tự; test tiếng
    /// Việt bên dưới mới gác điều đó.
    func testKhongVuotTranDuLogRatDai() {
        let t = mau(logTail: String(repeating: "x", count: 500_000)).text
        XCTAssertLessThanOrEqual(t.utf8.count, FeedbackDraft.maxDiagnosticsLength)
    }

    /// Cắt từ ĐUÔI lên: dòng log gần thời điểm lỗi nhất mới là dòng có giá trị.
    func testCatGiuPhanDuoiCuaLog() {
        let log = String(repeating: "a", count: 20_000) + "DONG-CUOI-CUNG"
        XCTAssertTrue(mau(logTail: log).text.contains("DONG-CUOI-CUNG"))
    }

    /// Không extras thì không có dòng nào ngoài sáu dòng lõi; không log thì không có phần `log:`.
    func testKhongExtrasKhongLogThiChiCoDongLoi() {
        let dong = mau(logTail: "", extras: []).text.split(separator: "\n")
        XCTAssertEqual(dong.count, DiagnosticsSnapshot.coreLabels.count)
        XCTAssertFalse(mau(logTail: "", extras: []).text.contains("log:"))
    }

    /// Danh sách nhãn lõi được GHIM nguyên văn: thêm/bớt/đổi tên một trường của snapshot buộc
    /// phải sửa test này — một thay đổi có chủ đích và nhìn thấy được (kèm soát lại câu quyền
    /// riêng tư và ngân sách độ dài).
    func testNhanLoiDuocGhim() {
        XCTAssertEqual(DiagnosticsSnapshot.coreLabels,
                       ["app version", "build", "device model", "iOS version", "locale", "free storage"])
    }

    /// Cổng rò dữ liệu: mọi dòng phải mang nhãn nằm trong whitelist (lõi + extras đã khai), trừ log.
    func testKhongCoTruongLaNgoaiWhitelist() {
        let cho = Set(DiagnosticsSnapshot.coreLabels + ["plan"])
        let t = mau().text
        let phanDau = t.components(separatedBy: "\nlog:\n").first ?? t
        let dong = phanDau.split(separator: "\n")
        XCTAssertEqual(dong.count, DiagnosticsSnapshot.coreLabels.count + 1)
        for d in dong {
            guard let nhan = d.split(separator: ":").first else { continue }
            XCTAssertTrue(cho.contains(String(nhan).trimmingCharacters(in: .whitespaces)),
                          "trường lạ lọt vào chẩn đoán: \(d)")
        }
    }

    /// CỔNG THẬT: log toàn ký tự tiếng Việt nhiều byte ("ệ" = 3 byte UTF-8) đủ dài để vượt trần.
    /// Nếu cắt theo `.count` (số ký tự) thay vì `.utf8.count` (số byte), kết quả NẶNG HƠN trần
    /// byte dù "ngắn" về số ký tự — `FeedbackDraft.validate()` (đo bằng utf8.count) sẽ ném
    /// `.diagnosticsTooLong` và toàn bộ log biến mất khỏi báo lỗi, không ai hiểu vì sao. Test
    /// dựng `FeedbackDraft` thật từ snapshot và gọi `validate()`.
    func testCatKhongVuotTranVoiLogTiengViet() {
        let log = String(repeating: "ệ", count: 20_000)
        let t = mau(logTail: log).text

        // (a) Không vượt trần byte.
        XCTAssertLessThanOrEqual(t.utf8.count, FeedbackDraft.maxDiagnosticsLength)

        // (b) Không có ký tự thay thế U+FFFD do cắt giữa byte của một ký tự nhiều byte.
        XCTAssertFalse(t.contains("\u{FFFD}"), "chuỗi chứa ký tự thay thế — đã cắt giữa một ký tự UTF-8")

        // (c) Nối với FeedbackDraft: validate() không được ném.
        let draft = FeedbackDraft(type: .bug, message: "test", email: nil, diagnostics: t)
        XCTAssertNoThrow(try draft.validate())
    }

    // MARK: - Câu quyền riêng tư

    func testCauQuyenRiengTuKhopNhanThat() {
        let s = DiagnosticsSnapshot.current(extras: [.init(label: "plan", value: "gold")])
        XCTAssertTrue(s.privacySummary.contains("plan"))
        for label in DiagnosticsSnapshot.coreLabels {
            XCTAssertTrue(s.privacySummary.localizedCaseInsensitiveContains(label), "câu thiếu nhãn \(label)")
        }
    }

    /// Mọi nhãn thật sự nằm trong `text` đều có mặt trong câu — kể cả extras nhiều cái.
    func testMoiNhanTrongTextDeuCoTrongCau() {
        let extras = [DiagnosticsField(label: "plan", value: "gold"),
                      DiagnosticsField(label: "region", value: "x")]
        let s = mau(extras: extras)
        for label in DiagnosticsSnapshot.coreLabels + extras.map(\.label) {
            XCTAssertTrue(s.text.contains("\(label):"))
            XCTAssertTrue(s.privacySummary.localizedCaseInsensitiveContains(label))
        }
    }

    func testCauKhongNhacExtrasKhiKhongCo() {
        let s = mau(logTail: "", extras: []).privacySummary
        XCTAssertFalse(s.contains("plan"))
        XCTAssertFalse(s.contains("recent log lines"))
    }

    /// Có đính log thì câu PHẢI nói có log — không được nói ít hơn thực tế.
    func testCauNoiCoLogKhiCoDinhLog() {
        XCTAssertTrue(mau(logTail: "x").privacySummary.contains("recent log lines"))
    }

    // MARK: - Extras bị loại

    func testNhanNgoaiDanhSachBiLoaiKhoiBanGui() {
        let extras: [DiagnosticsField] = [
            .init(label: "", value: "leak-empty"),
            .init(label: "   ", value: "leak-blank"),
            .init(label: "BUILD", value: "leak-core-upper"),
            .init(label: "build", value: "leak-core"),
            .init(label: " locale ", value: "leak-core-padded"),
            .init(label: "log", value: "leak-reserved"),
            .init(label: "a:b", value: "leak-colon"),
            .init(label: "multi\nline", value: "leak-newline"),
            .init(label: "plan", value: "gold"),
            .init(label: "Plan", value: "leak-dup"),
        ]
        let s = mau(logTail: "", extras: extras)
        XCTAssertEqual(s.extras, [DiagnosticsField(label: "plan", value: "gold")])
        XCTAssertFalse(s.text.contains("leak"), "extras bị loại vẫn lọt vào chuỗi gửi đi")
        XCTAssertFalse(s.privacySummary.contains("multi"))
        XCTAssertFalse(s.privacySummary.contains("a:b"))
        XCTAssertEqual(s.text.split(separator: "\n").count, DiagnosticsSnapshot.coreLabels.count + 1)
    }

    /// Giá trị extras có xuống dòng không được dựng thêm "dòng" giả (vd. giả phần log).
    func testGiaTriExtrasKhongTheGiaDong() {
        let s = mau(logTail: "", extras: [.init(label: "plan", value: "gold\nlog:\nforged")])
        XCTAssertFalse(s.text.contains("\nlog:"))
        XCTAssertEqual(s.text.split(separator: "\n").count, DiagnosticsSnapshot.coreLabels.count + 1)
    }

    // MARK: - Phần đầu được bảo vệ khi cắt byte

    private func dongTruocLog(_ t: String) -> [Substring] {
        (t.components(separatedBy: "\nlog:\n").first ?? t).split(separator: "\n", omittingEmptySubsequences: false)
    }

    private func kiemPhanDau(_ s: DiagnosticsSnapshot, file: StaticString = #filePath, line: UInt = #line) {
        let t = s.text
        let dong = dongTruocLog(t)
        let cho = Set(DiagnosticsSnapshot.coreLabels + s.extras.map(\.label))
        XCTAssertEqual(dong.count, DiagnosticsSnapshot.coreLabels.count + s.extras.count, file: file, line: line)
        guard dong.count >= DiagnosticsSnapshot.coreLabels.count else {
            return XCTFail("mất dòng lõi: chỉ còn \(dong.count) dòng trước log", file: file, line: line)
        }
        for (i, nhan) in DiagnosticsSnapshot.coreLabels.enumerated() {
            XCTAssertTrue(dong[i].hasPrefix("\(nhan): "), "dòng lõi \(nhan) mất/hỏng: \(dong[i])", file: file, line: line)
        }
        for d in dong {
            guard let nhan = d.components(separatedBy: ": ").first else { continue }
            XCTAssertTrue(cho.contains(nhan), "dòng không nguyên nhãn: \(d.prefix(60))", file: file, line: line)
        }
        XCTAssertLessThanOrEqual(t.utf8.count, FeedbackDraft.maxDiagnosticsLength, file: file, line: line)
        XCTAssertFalse(t.contains("\u{FFFD}"), file: file, line: line)
    }

    func testExtraGiaTriRatDaiKhongLogVanDuLoiVaNhanNguyen() {
        let s = mau(logTail: "", extras: [.init(label: "plan", value: String(repeating: "x", count: 20_000))])
        kiemPhanDau(s)
        XCTAssertEqual(s.extras.first?.value.utf8.count, DiagnosticsSnapshot.maxExtraValueLength)
        XCTAssertTrue(s.text.contains("plan: xxx"))
    }

    func testGiaTriExtraTiengVietCatTheoByteKhongDutKyTu() {
        let s = mau(logTail: "", extras: [.init(label: "plan", value: String(repeating: "ệ", count: 1000))])
        guard let v = s.extras.first?.value else { return XCTFail("extra bị loại oan") }
        XCTAssertLessThanOrEqual(v.utf8.count, DiagnosticsSnapshot.maxExtraValueLength)
        XCTAssertEqual(v, String(repeating: "ệ", count: v.count))
        kiemPhanDau(s)
    }

    func testNhieuExtrasVaLogTiengVietDaiVanDuLoi() {
        let extras = (0..<40).map { DiagnosticsField(label: "extra\($0)", value: String(repeating: "ệ", count: 400)) }
        let s = mau(logTail: String(repeating: "ệ", count: 20_000), extras: extras)
        XCTAssertLessThan(s.extras.count, extras.count, "extras vượt trần phần đầu phải bị loại")
        XCTAssertGreaterThan(s.extras.count, 0)
        kiemPhanDau(s)
        XCTAssertTrue(s.text.contains("\nlog:\n"))
        XCTAssertNoThrow(try FeedbackDraft(type: .bug, message: "x", email: nil, diagnostics: s.text).validate())
    }

    func testCauChiLietKeExtrasThucSuCoTrongText() {
        let extras = (0..<40).map { DiagnosticsField(label: "extra\($0)", value: String(repeating: "x", count: 400)) }
        let s = mau(logTail: "", extras: extras)
        for e in extras {
            let coTrongText = s.text.contains("\n\(e.label): ")
            XCTAssertEqual(s.privacySummary.contains("\(e.label),") || s.privacySummary.contains("\(e.label) ")
                           || s.privacySummary.contains("\(e.label)."), coTrongText, e.label)
        }
        XCTAssertTrue(s.text.contains("extra0: "))
        XCTAssertFalse(s.text.contains("extra39: "))
    }

    func testCauNoiLogDungTheoViecTextCoMucLog() {
        // Có log, còn chỗ ⇒ text có mục log và câu nói có.
        let co = mau(logTail: "x", extras: [])
        XCTAssertTrue(co.text.contains("\nlog:\n"))
        XCTAssertTrue(co.privacySummary.contains("recent log lines"))
        // Giá trị lõi lớn tới mức hết ngân sách log ⇒ không in mục log rỗng và câu không nhắc log.
        let het = DiagnosticsSnapshot(appVersion: String(repeating: "v", count: 12_000), build: "1",
                                      deviceModel: "m", systemVersion: "1", locale: "en", freeDiskMB: 1,
                                      logTail: "dòng log")
        XCTAssertFalse(het.text.contains("\nlog:"))
        XCTAssertFalse(het.privacySummary.contains("recent log lines"))
    }

    func testNganSachLogTheoPhanDau() {
        let extras = (0..<6).map { DiagnosticsField(label: "extra\($0)", value: String(repeating: "x", count: 480)) }
        let s = mau(logTail: String(repeating: "a", count: 20_000), extras: extras)
        kiemPhanDau(s)
        XCTAssertTrue(s.text.hasSuffix("aaaa"))
    }
}
