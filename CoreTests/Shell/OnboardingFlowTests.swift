import XCTest
@testable import AppHost

/// Trang giả cho test — Core không biết trang thật của app.
private enum FakePage: Hashable, CaseIterable {
    case welcome, one, two, three
}

/// Luồng trang tour: thứ tự, trang bỏ khi xem lại, trang cuối, số trang cho analytics.
final class OnboardingFlowTests: XCTestCase {

    private func flow(_ context: OnboardingFlow<FakePage>.Context) -> OnboardingFlow<FakePage> {
        OnboardingFlow(context: context, allPages: FakePage.allCases, skippedOnReplay: [.welcome])
    }

    /// Lần đầu: đủ mọi trang theo thứ tự — `skippedOnReplay` KHÔNG áp ở lần đầu.
    func testLanDauDuTrangTheoThuTu() {
        XCTAssertEqual(flow(.firstRun).pages, [.welcome, .one, .two, .three])
    }

    /// Xem lại từ Settings: bỏ các trang app đánh dấu (VD Welcome — công khai analytics đã thấy rồi).
    func testReplayBoTrangDaDanhDau() {
        XCTAssertEqual(flow(.replay).pages, [.one, .two, .three])
    }

    func testNextVaTrangCuoi() {
        let f = flow(.firstRun)
        XCTAssertEqual(f.next(after: .welcome), .one)
        XCTAssertEqual(f.next(after: .two), .three)
        XCTAssertNil(f.next(after: .three))
        XCTAssertTrue(f.isLast(.three))
        XCTAssertFalse(f.isLast(.one))
    }

    /// `skipped_at_page` 1-based theo trang của CHÍNH luồng đó.
    func testSoTrangMotGoc() {
        XCTAssertEqual(flow(.firstRun).pageNumber(.welcome), 1)
        XCTAssertEqual(flow(.firstRun).pageNumber(.two), 3)
        XCTAssertEqual(flow(.replay).pageNumber(.one), 1)
    }

    /// Ghim: trang không thuộc luồng (bị bỏ ở replay) trả 1, không trap.
    func testSoTrangCuaTrangKhongThuocLuongLaMot() {
        XCTAssertEqual(flow(.replay).pageNumber(.welcome), 1)
    }

    /// Trang mở đầu: trang yêu cầu nếu thuộc luồng; trang bị bỏ ở replay ⇒ trang đầu của luồng (không hiện lại).
    func testTrangMoDau() {
        XCTAssertEqual(flow(.firstRun).startPage(), .welcome)
        XCTAssertEqual(flow(.firstRun).startPage(preferred: .two), .two)
        XCTAssertEqual(flow(.replay).startPage(preferred: .welcome), .one)
        XCTAssertFalse(flow(.replay).isEmpty)
    }

    /// App chỉ có Welcome và bỏ nó khi xem lại ⇒ luồng rỗng: View kết thúc ngay, mọi hàm không trap.
    func testReplayBoHetTrangThiLuongRong() {
        let f = OnboardingFlow(context: .replay, allPages: [FakePage.welcome], skippedOnReplay: [.welcome])
        XCTAssertEqual(f.pages, [])
        XCTAssertTrue(f.isEmpty)
        XCTAssertNil(f.startPage())
        XCTAssertNil(f.startPage(preferred: .welcome), "trang đã đánh dấu bỏ không được hiện lại")
        XCTAssertNil(f.next(after: .welcome))
        XCTAssertFalse(f.isLast(.welcome))
        XCTAssertEqual(f.pageNumber(.welcome), 1)
        XCTAssertFalse(OnboardingFlow(context: .firstRun, allPages: [FakePage.welcome],
                                      skippedOnReplay: [.welcome]).isEmpty)
    }
}
