import XCTest
@testable import AppHost

/// Link vào app: chỉ `https` đúng host đang chạy được nhận; đường dẫn/query tách đúng; giao qua presenter What's New
/// (sheet đang mở ⇒ chờ đóng, link mới nhất thắng). Host giả `thu.invalid` — không bao giờ là host thật.
@MainActor
final class AppLinkRouterTests: XCTestCase {
    private let host = "thu.invalid"

    private func url(_ s: String) -> URL { URL(string: s)! }

    func testHostDungTraVeDuongDan() {
        XCTAssertEqual(AppLinkRouter.parse(url("https://thu.invalid/items/42"), expectedHost: host),
                       AppLink(path: ["items", "42"], query: [:]))
        // Host không phân biệt hoa thường; dấu "/" cuối không tạo đoạn rỗng.
        XCTAssertEqual(AppLinkRouter.parse(url("https://THU.invalid/items/"), expectedHost: host)?.path, ["items"])
    }

    func testHostLaBiBo() {
        XCTAssertNil(AppLinkRouter.parse(url("https://khac.invalid/items"), expectedHost: host))
        XCTAssertNil(AppLinkRouter.parse(url("https://dev.thu.invalid/items"), expectedHost: host), "host con ≠ host")
        XCTAssertNil(AppLinkRouter.parse(url("https://thu.invalid.evil.example/items"), expectedHost: host))
        // App không có web (host rỗng/vắng) ⇒ không link nào vào được.
        XCTAssertNil(AppLinkRouter.parse(url("https://thu.invalid/items"), expectedHost: nil))
        XCTAssertNil(AppLinkRouter.parse(url("https://thu.invalid/items"), expectedHost: ""))
    }

    func testHttpBiBo() {
        XCTAssertNil(AppLinkRouter.parse(url("http://thu.invalid/items"), expectedHost: host))
        XCTAssertNil(AppLinkRouter.parse(url("thuapp://thu.invalid/items"), expectedHost: host))
        XCTAssertNil(AppLinkRouter.parse(url("/items"), expectedHost: host), "URL tương đối không có host")
    }

    func testDuongDanRongLaGoc() {
        XCTAssertEqual(AppLinkRouter.parse(url("https://thu.invalid"), expectedHost: host), AppLink(path: [], query: [:]))
        XCTAssertEqual(AppLinkRouter.parse(url("https://thu.invalid/"), expectedHost: host)?.path, [])
        XCTAssertEqual(AppLinkRouter.parse(url("https://thu.invalid//"), expectedHost: host)?.path, [])
    }

    func testPercentEncodingDuocGiaiMa() {
        XCTAssertEqual(AppLinkRouter.parse(url("https://thu.invalid/items/c%C3%A0%20ph%C3%AA"), expectedHost: host)?.path,
                       ["items", "cà phê"])
        // `%2F` nằm TRONG một đoạn — giải mã sau khi tách, không thành dấu phân cách.
        XCTAssertEqual(AppLinkRouter.parse(url("https://thu.invalid/a%2Fb/c"), expectedHost: host)?.path, ["a/b", "c"])
    }

    func testQueryDuocDoc() {
        let link = AppLinkRouter.parse(url("https://thu.invalid/items?src=banner&q=c%C3%A0%20ph%C3%AA&flag&src=mail"),
                                       expectedHost: host)
        XCTAssertEqual(link, AppLink(path: ["items"], query: ["src": "mail", "q": "cà phê", "flag": ""]))
    }

    func testCongVaUserinfoBiBo() {
        XCTAssertNil(AppLinkRouter.parse(url("https://thu.invalid:8443/items"), expectedHost: host))
        XCTAssertNil(AppLinkRouter.parse(url("https://thu.invalid:443/items"), expectedHost: host), "cổng tường minh")
        XCTAssertNil(AppLinkRouter.parse(url("https://ai@thu.invalid/items"), expectedHost: host))
        XCTAssertNil(AppLinkRouter.parse(url("https://ai:mk@thu.invalid/items"), expectedHost: host))
    }

    /// Hành vi chốt cho ca biên: so host NGUYÊN VĂN (dấu chấm cuối ⇒ khác), `+` trong query giữ là `+` (ngữ nghĩa
    /// URLComponents, không phải form-encoding), IDN chỉ khớp khi cấu hình và URL cùng dạng punycode. Không crash.
    func testCaBienHostVaQuery() {
        XCTAssertNil(AppLinkRouter.parse(url("https://thu.invalid./items"), expectedHost: host))
        XCTAssertEqual(AppLinkRouter.parse(url("https://thu.invalid/items?q=a+b&r=a%20b"), expectedHost: host)?.query,
                       ["q": "a+b", "r": "a b"])
        let puny = "xn--th-yct.invalid"
        XCTAssertEqual(AppLinkRouter.parse(url("https://xn--th-yct.invalid/items"), expectedHost: puny)?.path, ["items"])
        XCTAssertNil(AppLinkRouter.parse(url("https://xn--th-yct.invalid/items"), expectedHost: "thử.invalid"))
        if let unicode = URL(string: "https://thử.invalid/items") {
            _ = AppLinkRouter.parse(unicode, expectedHost: puny)   // dạng nào cũng được, miễn không crash
            _ = AppLinkRouter.parse(unicode, expectedHost: "thử.invalid")
        }
    }

    // MARK: - Giao qua presenter What's New

    private var suiteName = ""
    private var defaults: UserDefaults!

    override func setUp() {
        super.setUp()
        suiteName = "AppLinkRouterTests.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)!
    }

    override func tearDown() {
        Track.reset()
        defaults.removePersistentDomain(forName: suiteName)
        defaults = nil
        super.tearDown()
    }

    private func presenter() -> WhatsNewPresenter {
        let cards = [WhatsNewCard(id: "a", version: .unreleased, priority: 5, systemImage: "star", title: "a", body: "a",
                                  ctaTitle: "a", action: WhatsNewAction(key: "go"), usedOnDisk: { _ in false })]
        let state = WhatsNewState(defaults: defaults)
        state.recordSeen(AppVersion("1.0.0")!)
        return WhatsNewPresenter(cards: cards, current: AppVersion("1.1.0")!, hasSeenOnboarding: true,
                                 ledger: FeatureUsageLedger(cards: cards, defaults: defaults), state: state,
                                 probe: ClosureUsageProbe([:]), isEnabled: true, runSeed: { $0() },
                                 scheduleWatchdog: { _, _ in })
    }

    func testRouteKhongSheetThiApNgay_hostSaiThiBo() {
        let p = presenter()
        var got: [AppLink] = []
        XCTAssertTrue(AppLinkRouter.route(url("https://thu.invalid/items"), expectedHost: host, whatsNew: p) {
            got.append($0)
        })
        XCTAssertEqual(got, [AppLink(path: ["items"], query: [:])])
        XCTAssertFalse(AppLinkRouter.route(url("https://khac.invalid/items"), expectedHost: host, whatsNew: p) {
            got.append($0)
        })
        XCTAssertEqual(got.count, 1, "host lạ ⇒ không giao gì")
    }

    /// Link tới TRƯỚC lượt `evaluate` (mở app nguội từ link sau khi cập nhật): app giao link ngay rồi xoá trạng thái
    /// của nó, nhưng What's New vẫn không được hiện đè lên màn của link — suốt lượt dùng đó, tới khi app vào nền.
    func testLinkToiTruocKhiDanhGiaThiWhatsNewKhongHienDe() async {
        let p = presenter()
        let resolve: WhatsNewResolver = { WhatsNewResolvedAction(key: $0.key) }
        // Cổng như AppShellView dựng: link của app đã giao + xoá ⇒ appLinkPending false.
        func gate() -> Bool {
            p.presentGate(sceneActive: true, coverShown: false, modalPresented: false, extraBlockers: false,
                          appLinkPending: false).allowsPresent
        }
        XCTAssertTrue(gate(), "đối chứng: chưa có link thì cổng mở")
        AppLinkRouter.route(url("https://thu.invalid/items"), expectedHost: host, whatsNew: p) { _ in }
        XCTAssertFalse(gate())
        await p.evaluate(resolve: resolve, canPresent: gate())
        XCTAssertNil(p.presentation, "link vừa mở ⇒ không hiện What's New đè lên")
        await p.evaluate(resolve: resolve, canPresent: gate())
        XCTAssertNil(p.presentation, "lượt evaluate sau trong CÙNG lượt dùng vẫn không hiện")
        p.sceneDidEnterBackground()
        XCTAssertTrue(gate())
        await p.evaluate(resolve: resolve, canPresent: gate())
        XCTAssertNotNil(p.presentation, "lượt dùng sau ⇒ What's New hiện bình thường")
    }

    func testHostSaiKhongDongCongWhatsNew() {
        let p = presenter()
        AppLinkRouter.route(url("https://khac.invalid/items"), expectedHost: host, whatsNew: p) { _ in }
        XCTAssertFalse(p.appLinkOpenedThisActivation)
    }

    func testRouteKhiSheetMoThiChoDong_linkMoiNhatThang() async {
        let p = presenter()
        await p.evaluate(resolve: { WhatsNewResolvedAction(key: $0.key) }, canPresent: true)
        XCTAssertNotNil(p.presentation, "điều kiện test: sheet phải được đặt")
        p.sheetDidAppear()
        var got: [AppLink] = []
        AppLinkRouter.route(url("https://thu.invalid/a"), expectedHost: host, whatsNew: p) { got.append($0) }
        AppLinkRouter.route(url("https://thu.invalid/b"), expectedHost: host, whatsNew: p) { got.append($0) }
        XCTAssertEqual(got, [], "sheet còn trên màn ⇒ chưa mở link")
        p.sheetDidDismiss()
        XCTAssertEqual(got, [AppLink(path: ["b"], query: [:])])
    }
}
