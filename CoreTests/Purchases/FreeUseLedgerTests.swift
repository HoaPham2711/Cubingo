@testable import AppHost
import XCTest

final class FreeUseLedgerTests: XCTestCase {

    func testMoiCaiDuSoLuotCauHinh() {
        let l = FreeUseLedger(limit: 10, store: MemoryCounterStore())
        XCTAssertEqual(l.used, 0)
        XCTAssertEqual(l.remaining, 10)
    }

    func testConsumeTruMotLuot() throws {
        let s = MemoryCounterStore()
        let l = FreeUseLedger(limit: 10, store: s)
        try l.consume()
        XCTAssertEqual(l.remaining, 9)
        XCTAssertEqual(s.value, 1, "phải ghi xuống store, không chỉ trong RAM")
    }

    /// Không bao giờ âm — kể cả khi store bị ghi số lớn hơn trần (vd lỡ tay test).
    func testRemainingKhongAm() throws {
        let s = MemoryCounterStore(); s.value = 15
        XCTAssertEqual(FreeUseLedger(limit: 10, store: s).remaining, 0)
    }

    /// Đọc lại từ store mỗi lần — instance mới (app mở lại) thấy đúng số đã dùng.
    func testInstanceMoiDocLaiStore() throws {
        let s = MemoryCounterStore()
        try FreeUseLedger(limit: 10, store: s).consume()
        try FreeUseLedger(limit: 10, store: s).consume()
        XCTAssertEqual(FreeUseLedger(limit: 10, store: s).remaining, 8)
    }

    func testGhiLoiThiNemVaKhongDoiSo() {
        let s = MemoryCounterStore(); s.failWrite = true
        let l = FreeUseLedger(limit: 10, store: s)
        XCTAssertThrowsError(try l.consume())
        XCTAssertEqual(l.remaining, 10)
    }

    /// Trả lượt cho việc thất bại mà user không nhận được gì; không xuống dưới 0.
    func testRefundTraMotLuotVaKhongXuongDuoi0() throws {
        let s = MemoryCounterStore(); s.value = 2
        let l = FreeUseLedger(limit: 10, store: s)
        try l.refund()
        XCTAssertEqual(s.value, 1)
        try l.refund()
        try l.refund()
        XCTAssertEqual(s.value, 0, "không được âm")
    }

    /// Đọc store lỗi: hiển thị coi như 0 đã dùng (không chặn user), nhưng `consume` KHÔNG được ghi đè bộ đếm thật
    /// bằng `0 + 1` — đó là reset lượt free lặng lẽ.
    func testDocLoiThiConsumeNemVaKhongGhiDeBoDem() {
        let s = MemoryCounterStore(); s.value = 7; s.failRead = true
        let l = FreeUseLedger(limit: 10, store: s)
        XCTAssertEqual(l.used, 0)
        XCTAssertThrowsError(try l.consume())
        XCTAssertThrowsError(try l.refund())
        XCTAssertEqual(s.writeCount, 0)
        XCTAssertEqual(s.value, 7)
    }

    /// Keychain thật chạy được trong test host (Simulator) — gác lỗi query/attribute sai.
    func testKeychainRoundTrip() throws {
        let k = KeychainCounterStore(service: "test.freeUse.\(UUID().uuidString)", account: "used")
        defer { k.deleteForTesting() }

        // run_tests.py build CODE_SIGNING_ALLOWED=NO ⇒ sim không có entitlement Keychain.
        // Hành vi thật (gỡ app cài lại giữ bộ đếm) phải kiểm trên device / bản ký.
        do {
            // Gán ra biến: `try` bên trong XCTAssertEqual bị XCTest nuốt thành failure, không tới `catch`.
            let truoc = try k.read()
            XCTAssertEqual(truoc, 0)
            try k.write(0)
        } catch let e as KeychainCounterStore.KeychainError where e.status == errSecMissingEntitlement {
            throw XCTSkip("Keychain cần app được ký — chạy trên device/bản ký")
        }

        try k.write(3)
        XCTAssertEqual(try k.read(), 3)
        try k.write(4)   // lần hai đi nhánh update, không phải add
        XCTAssertEqual(try k.read(), 4)
    }

    /// Lỗi không có `LocalizedError` hiện ra alert là "…error 2." — thông báo phải là câu người đọc.
    func testKeychainErrorCoThongBaoDocDuoc() {
        let d = KeychainCounterStore.KeychainError(status: errSecInteractionNotAllowed).localizedDescription
        XCTAssertFalse(d.contains("AppHost."), d)
        XCTAssertFalse(d.contains("couldn’t be completed"), d)
    }

    func testKeychainServiceTheoBundleIdVaTinhNang() {
        let service = KeychainCounterStore.appService("freeUse")
        XCTAssertTrue(service.hasSuffix(".freeUse"), service)
        XCTAssertTrue(service.hasPrefix(Bundle.main.bundleIdentifier ?? "app"), service)
    }

    // MARK: - FreeUseGate

    func testCanStartKhiConLuotHoacDaMua() {
        XCTAssertTrue(FreeUseGate.canStart(isPro: true, remaining: 0))
        XCTAssertTrue(FreeUseGate.canStart(isPro: false, remaining: 1))
    }

    /// Hết lượt phải chặn ngay lúc bắt đầu — không để user làm xong mới biết.
    func testFreeHetLuotThiChan() {
        XCTAssertFalse(FreeUseGate.canStart(isPro: false, remaining: 0))
    }
}
