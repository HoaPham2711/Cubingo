import XCTest
@testable import AppHost

/// `FeedbackViewModel` là lớp mỏng nối `FeedbackDraft`/`FeedbackTransport` (đã có, đã test) với
/// SwiftUI — test ở đây chỉ nhắm luồng trạng thái (idle/sending/sent/failed), KHÔNG lặp lại test
/// validate() đã có ở `FeedbackDraftTests`.
@MainActor
final class FeedbackViewModelTests: XCTestCase {

    private let chanDoan = DiagnosticsSnapshot(
        appVersion: "1.2", build: "42", deviceModel: "iPhone15,3", systemVersion: "18.0",
        locale: "en_US", freeDiskMB: 100)

    private let coMail = SupportConfig(email: "help@example.com", subject: "Support request")
    private let khongMail = SupportConfig(email: nil, subject: "Support request")

    private func dung(_ t: FakeFeedbackTransport, support: SupportConfig? = nil) -> FeedbackViewModel {
        FeedbackViewModel(type: .bug, transport: t, diagnostics: chanDoan, support: support ?? coMail)
    }

    func testGuiThanhCongDoiSangSent() async {
        let t = FakeFeedbackTransport()
        let vm = dung(t)
        vm.message = "co loi"
        await vm.send()
        XCTAssertEqual(vm.state, .sent)
        XCTAssertEqual(t.sent.count, 1)
        XCTAssertEqual(t.sent.first?.message, "co loi")
    }

    /// Chẩn đoán phải đi kèm — user không bao giờ tự gõ những trường này, và thiếu chúng thì
    /// báo lỗi gần như vô dụng.
    func testChanDoanDuocGuiKem() async {
        let t = FakeFeedbackTransport()
        let vm = dung(t)
        vm.message = "x"
        await vm.send()
        XCTAssertTrue(t.sent.first?.diagnostics.contains("iPhone15,3") == true)
    }

    func testMessageRongThiKhongRaMang() async {
        let t = FakeFeedbackTransport()
        let vm = dung(t)
        vm.message = "   "
        await vm.send()
        XCTAssertTrue(t.sent.isEmpty)
        guard case .failed = vm.state else { return XCTFail("phải ở trạng thái failed") }
    }

    func testLoiMangDoiSangFailedVaGiuNguyenNoiDung() async {
        let t = FakeFeedbackTransport()
        t.errorToThrow = FeedbackSendError.offline
        let vm = dung(t)
        vm.message = "noi dung quy"
        await vm.send()
        guard case .failed = vm.state else { return XCTFail("phải ở trạng thái failed") }
        // Xoá nội dung user vừa gõ khi gửi hỏng là cách nhanh nhất để mất luôn phản hồi đó.
        XCTAssertEqual(vm.message, "noi dung quy")
    }

    func testEmailRongVanGuiDuoc() async {
        let t = FakeFeedbackTransport()
        let vm = dung(t)
        vm.message = "x"
        vm.email = ""
        await vm.send()
        XCTAssertEqual(vm.state, .sent)
        XCTAssertNil(t.sent.first?.email)
    }

    /// `.diagnosticsTooLong` là lỗi NỘI BỘ (app tự sinh chẩn đoán, user không gõ) — thông báo
    /// phải không đổ lỗi cho user rút ngắn thứ họ không viết.
    ///
    /// Ép lỗi này qua `transport.errorToThrow` thay vì bơm một `logTail` khổng lồ: `.text` của
    /// `DiagnosticsSnapshot` tự cắt về đúng `maxDiagnosticsLength` làm "chốt chặn cuối", nên
    /// `draft.validate()` trong `send()` KHÔNG BAO GIỜ thấy chẩn đoán vượt trần trong thực tế —
    /// case này vẫn phải được xử lý đúng nếu nó xảy ra qua đường khác (validate() ở tầng
    /// transport, luật cắt đổi về sau...).
    func testChanDoanQuaDaiRaThongBaoNoiBoKhongDoLoiChoUser() async {
        let t = FakeFeedbackTransport()
        t.errorToThrow = FeedbackValidationError.diagnosticsTooLong
        let vm = dung(t)
        vm.message = "x"
        await vm.send()
        guard case .failed(let noiDung) = vm.state else { return XCTFail("phải ở trạng thái failed") }
        XCTAssertFalse(noiDung.lowercased().contains("shorten"),
                        "user không gõ chẩn đoán nên không thể bảo họ rút ngắn nó")
        XCTAssertTrue(t.sent.isEmpty)
    }

    /// `onSent` phải thật sự được gọi khi gửi thành công — không chỉ tồn tại cho có chữ ký.
    func testOnSentDuocGoiKhiGuiThanhCong() async {
        let t = FakeFeedbackTransport()
        var soLanGoi = 0
        let vm = FeedbackViewModel(type: .bug, transport: t, diagnostics: chanDoan, support: coMail,
                                    onSent: { soLanGoi += 1 })
        vm.message = "x"
        await vm.send()
        XCTAssertEqual(soLanGoi, 1)
    }

    func testOnSentKhongDuocGoiKhiGuiThatBai() async {
        let t = FakeFeedbackTransport()
        t.errorToThrow = FeedbackSendError.offline
        var soLanGoi = 0
        let vm = FeedbackViewModel(type: .bug, transport: t, diagnostics: chanDoan, support: coMail,
                                    onSent: { soLanGoi += 1 })
        vm.message = "x"
        await vm.send()
        XCTAssertEqual(soLanGoi, 0)
    }

    // MARK: - Lối thoát gửi mail chỉ có khi app cấu hình địa chỉ

    func testCoDiaChiThiThongBaoLoiMoiGuiMail() {
        // `.rejected` bị bỏ qua có chủ đích: ở build INTERNAL nó trả chuỗi debug kèm mã HTTP.
        let loi: [Error] = [FeedbackValidationError.diagnosticsTooLong, URLError(.unknown)]
        for e in loi {
            XCTAssertTrue(FeedbackViewModel.moTa(e, canEmail: true).lowercased().contains("email us"), "\(e)")
        }
        XCTAssertTrue(vmCanEmail(coMail))
    }

    /// App không cấu hình địa chỉ hỗ trợ ⇒ không có nút "Email us instead" ⇒ thông báo lỗi cũng
    /// không được dặn user "email us".
    func testKhongCoDiaChiThiThongBaoKhongMoiGuiMail() {
        let loi: [Error] = [FeedbackValidationError.diagnosticsTooLong, FeedbackSendError.rejected(500),
                            FeedbackSendError.offline]
        for e in loi {
            XCTAssertFalse(FeedbackViewModel.moTa(e, canEmail: false).lowercased().contains("email"),
                           "\(e)")
        }
        XCTAssertFalse(vmCanEmail(khongMail))
    }

    func testThongBaoLoiTrongVMTheoCauHinhHoTro() async {
        let t = FakeFeedbackTransport()
        t.errorToThrow = FeedbackSendError.rejected(500)
        let vm = dung(t, support: khongMail)
        vm.message = "x"
        await vm.send()
        guard case .failed(let noiDung) = vm.state else { return XCTFail("phải ở trạng thái failed") }
        XCTAssertFalse(noiDung.lowercased().contains("email"))
    }

    /// Gửi hỏng (mạng hoặc máy chủ từ chối) + có hộp thư ⇒ mời gửi qua Mail; chưa hỏng thì không.
    func testGuiLoiHienLoiMail() async {
        for loi in [FeedbackSendError.offline, FeedbackSendError.rejected(500)] {
            let t = FakeFeedbackTransport()
            t.errorToThrow = loi
            let vm = dung(t)
            XCTAssertFalse(vm.offersMailFallback, "chưa gửi thì chưa mời")
            vm.message = "x"
            await vm.send()
            XCTAssertTrue(vm.offersMailFallback, "\(loi)")
        }
    }

    func testGuiLoiKhongCoHopThuThiKhongMoiMail() async {
        let t = FakeFeedbackTransport()
        t.errorToThrow = FeedbackSendError.offline
        let vm = dung(t, support: khongMail)
        vm.message = "x"
        await vm.send()
        XCTAssertFalse(vm.offersMailFallback)
    }

    func testGuiThanhCongKhongMoiMail() async {
        let vm = dung(FakeFeedbackTransport())
        vm.message = "x"
        await vm.send()
        XCTAssertFalse(vm.offersMailFallback)
    }

    private func vmCanEmail(_ support: SupportConfig) -> Bool {
        dung(FakeFeedbackTransport(), support: support).canEmail
    }

    #if INTERNAL
    /// Build nội bộ: kèm mã HTTP để chẩn đoán trên device không cắm Xcode (chuỗi thô, không localize).
    func testLoiTuChoiNoiBoKemMaHTTP() {
        XCTAssertTrue(FeedbackViewModel.moTa(FeedbackSendError.rejected(422), canEmail: true).contains("422"))
    }
    #endif
}
