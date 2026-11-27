import XCTest
@testable import AppHost

/// `WhatsNewHost.make` — điểm dựng presenter + ledger dùng chung một danh sách thẻ và một UserDefaults. Bản đang cài
/// truyền tường minh (không đọc bundle thật), UserDefaults suite riêng.
@MainActor
final class WhatsNewHostTests: XCTestCase {

    private var suiteName = ""
    private var defaults: UserDefaults!

    override func setUp() {
        super.setUp()
        suiteName = "WhatsNewHostTests.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)!
    }

    override func tearDown() {
        Track.removeUsageObserver()
        Track.reset()
        defaults.removePersistentDomain(forName: suiteName)
        defaults = nil
        super.tearDown()
    }

    private let cards = [
        WhatsNewCard(id: "a", version: .released("1.1.0"), priority: 5, systemImage: "star", title: "A", body: "A",
                     ctaTitle: "A", action: WhatsNewAction(key: "go"),
                     usedWhen: { $0.isNamed(ShellEventName.paywallView) }),
        WhatsNewCard(id: "b", version: .released("1.1.0"), priority: 4, systemImage: "star", title: "B", body: "B",
                     ctaTitle: "B", action: WhatsNewAction(key: "go")),
    ]

    private func make(isUnitTestHost: Bool = false, previewRoute: String? = nil,
                      installed: String? = "1.1.0") -> (presenter: WhatsNewPresenter, ledger: FeatureUsageLedger) {
        WhatsNewHost.make(cards: cards, probe: ClosureUsageProbe([:]), isUnitTestHost: isUnitTestHost,
                          previewRoute: previewRoute, defaults: defaults, installedVersion: installed)
    }

    private let resolve: WhatsNewResolver = { WhatsNewResolvedAction(key: $0.key) }

    /// Khoá ghim: cùng key với `@AppStorage("hasSeenOnboarding")` của app đã phát hành — đổi giá trị là mọi khách cũ
    /// bị coi như mới cài (thấy lại onboarding, What's New tắt). Lõi chỉ được nhắc cờ qua hằng này.
    func test_hasSeenOnboardingKey_isPinned() {
        XCTAssertEqual(WhatsNewHost.hasSeenOnboardingKey, "hasSeenOnboarding")
    }

    /// Host unit test / route preview khác / bản cài hỏng ⇒ presenter tắt và KHÔNG đọc cờ onboarding.
    func test_disabledCases_presenterOff() async {
        defaults.set(true, forKey: WhatsNewHost.hasSeenOnboardingKey)
        for (label, built) in [("host test", make(isUnitTestHost: true)),
                               ("route preview khác", make(previewRoute: "home")),
                               ("bản cài hỏng", make(installed: "abc")),
                               ("không có bản cài", make(installed: nil))] {
            XCTAssertFalse(built.presenter.isEnabled, label)
            await built.presenter.evaluate(resolve: resolve, canPresent: true)
            XCTAssertNil(built.presenter.presentation, label)
        }
        XCTAssertNil(defaults.object(forKey: WhatsNewState.lastSeenKey))
        XCTAssertNil(defaults.object(forKey: FeatureUsageLedger.diskSeededKey))
    }

    /// Khách cũ (đã qua onboarding, chưa có mốc lastSeen) ⇒ thấy sheet; bản lấy từ `installedVersion`.
    func test_existingUser_readsOnboardingFlag_andShows() async {
        defaults.set(true, forKey: WhatsNewHost.hasSeenOnboardingKey)
        let built = make()
        XCTAssertTrue(built.presenter.isEnabled)
        XCTAssertEqual(built.presenter.current, AppVersion("1.1.0"))
        await built.presenter.evaluate(resolve: resolve, canPresent: true)
        XCTAssertEqual(built.presenter.presentation?.cards.map(\.id), ["a", "b"])
    }

    /// Cài mới (cờ onboarding chưa bật) ⇒ không hiện, ghi mốc ngay.
    func test_freshInstall_doesNotShow() async {
        let built = make()
        await built.presenter.evaluate(resolve: resolve, canPresent: true)
        XCTAssertNil(built.presenter.presentation)
        XCTAssertEqual(WhatsNewState(defaults: defaults).lastSeen, AppVersion("1.1.0"))
    }

    /// Ledger trả về là ĐÚNG ledger presenter đọc: ghi nhận qua `Track` ⇒ thẻ đã dùng biến khỏi sheet. `make` không
    /// tự gắn observer (app gắn TRƯỚC sink, ngoài host test).
    func test_ledgerSharedWithPresenter_andNotInstalledByMake() async {
        defaults.set(true, forKey: WhatsNewHost.hasSeenOnboardingKey)
        let built = make()
        Track.log(.paywallView(source: "settings"))
        XCTAssertEqual(built.ledger.usedCards, [], "make không được tự gắn observer vào Track")
        Track.installUsageObserver(built.ledger)
        Track.log(.paywallView(source: "settings"))
        await built.presenter.evaluate(resolve: resolve, canPresent: true)
        XCTAssertEqual(built.presenter.presentation?.cards.map(\.id), ["b"])
    }
}
