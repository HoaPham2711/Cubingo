@testable import AppHost
import XCTest

@MainActor
final class ProFeatureTests: XCTestCase {

    /// Tính năng mẫu của test — app thật khai enum của nó.
    private enum MauTinhNang: ProFeature {
        case coBan, caoCap
        var isProOnly: Bool { self == .caoCap }
        var analyticsName: String { self == .caoCap ? "premium_action" : "basic_action" }
    }

    private func make(isPro: Bool, paywallEnabled: Bool = true) async throws -> Entitlements {
        let name = "profeature-\(UUID().uuidString)"
        let d = try XCTUnwrap(UserDefaults(suiteName: name))
        addTeardownBlock { d.removePersistentDomain(forName: name) }
        let fake = FakeStoreClient()
        fake.entitled = isPro
        let e = Entitlements(client: fake, paywallEnabled: paywallEnabled, defaults: d,
                             internalDeviceFlag: MemoryCounterStore())
        await e.refresh()
        return e
    }

    func testTinhNangProBiKhoaKhiChuaMua() async throws {
        let e = try await make(isPro: false)
        XCTAssertTrue(e.isLocked(MauTinhNang.caoCap))
    }

    func testTinhNangProMoKhiDaMua() async throws {
        let e = try await make(isPro: true)
        XCTAssertFalse(e.isLocked(MauTinhNang.caoCap))
    }

    func testTinhNangThuongKhongBaoGioKhoa() async throws {
        let free = try await make(isPro: false)
        let pro = try await make(isPro: true)
        XCTAssertFalse(free.isLocked(MauTinhNang.coBan))
        XCTAssertFalse(pro.isLocked(MauTinhNang.coBan))
    }

    /// Paywall tắt = app miễn phí hoàn toàn: mọi tính năng mở.
    func testPaywallTatThiKhongTinhNangNaoBiKhoa() async throws {
        let e = try await make(isPro: false, paywallEnabled: false)
        XCTAssertFalse(e.isLocked(MauTinhNang.caoCap))
        XCTAssertFalse(e.isLocked(MauTinhNang.coBan))
    }

    /// Cổng chống spam: `isLocked` chạy trong vòng lặp dựng view và chạy lại mỗi lần SwiftUI render. Bắn event
    /// ở đó là hàng nghìn event rác mỗi phiên — `pro_gate_hit` chỉ bắn khi user CHẠM control khoá (việc của UI).
    func testHoiKhoaNhieuLanKhongBanEventNao() async throws {
        let e = try await make(isPro: false)
        let sink = RecordingSink()
        Track.install(sink)
        defer { Track.reset() }
        for _ in 0..<50 {
            _ = e.isLocked(MauTinhNang.caoCap)
            _ = e.isLocked(MauTinhNang.coBan)
        }
        XCTAssertTrue(sink.names.isEmpty, "isLocked chạy trong vòng lặp dựng view — bắn ở đó là spam")
    }
}
