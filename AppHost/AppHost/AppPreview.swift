import SwiftUI

/// Route `-uiPreview <tên>` của app (chụp ảnh trên Simulator, `tools/dev/ui_shots.py`). Thêm route: thêm `case`,
/// dựng màn ở `AppShellView` (đọc `AppPreview.current`), thêm vào bảng của skill `ui-preview-sim`. `ui_shots.py all`
/// đọc danh sách `case` của enum này — một nguồn.
///
/// Type biên dịch ở mọi config nhưng VÔ HẠI trên device: `current` đọc qua `UIPreviewLaunch.rawRoute`, luôn `nil` ở
/// build device. Seed/ép trạng thái chỉ có trong `#if targetEnvironment(simulator)` (`AppPreviewSeed`,
/// seed riêng của từng tính năng).
enum AppPreview: String, UIPreviewRoute {
    case home, onboarding, settings, paywall, whatsNew, feedback
    // Route của tính năng (sau sáu route khung).
    case scan

    var isOnboarding: Bool {
        switch self {
        case .onboarding: return true
        default: return false
        }
    }

    /// Tab mở đầu của khung chính (`AppShellView`).
    var initialTab: AppTab {
        switch self {
        case .settings: return .settings
        default: return .home
        }
    }

    /// Trang mở đầu của tour cho route onboarding (`nil` ⇒ trang đầu).
    var onboardingInitialPage: AppOnboarding.Page? {
        nil
    }

    /// Route đang chạy; device luôn `nil`.
    static var current: AppPreview? { UIPreviewLaunch.rawRoute.flatMap(AppPreview.init(rawValue:)) }

    /// Route cần StoreKit THẬT. Rỗng: route `paywall` vẽ bằng store giả của Simulator (`AppPreviewStore`) — file
    /// `.storekit` gắn ở Run action của scheme KHÔNG được áp cho app do XCUITest mở qua `xcodebuild test` (đã thử:
    /// paywall báo "Could not load purchase options"), còn sandbox thật bật hộp thoại đăng nhập che màn.
    static let routesNeedingStore: Set<String> = []

    /// Dựng sẵn trạng thái luồng cho route của tính năng (chỉ Simulator; device không làm gì).
    @MainActor
    static func prepareFlow(_ flow: FlowModel) {
        #if targetEnvironment(simulator)
        AppPreviewSeed.prepareFlow(flow)
        #endif
    }
}

#if targetEnvironment(simulator)
/// Trạng thái tất định cho route preview — chạy trong `App.init()` TRƯỚC `WhatsNewHost.make` (nó đọc cờ onboarding
/// một lần) và trước chuỗi khởi động. Chỉ ghi UserDefaults (không ghi tmp) nên không phụ thuộc thứ tự với `purgeTmp`.
enum AppPreviewSeed {
    /// Suite RIÊNG cho What's New của route `whatsNew` — không đụng trạng thái `whatsNew.*` thật của sim; làm lại từ
    /// đầu mỗi lần mở để ảnh không phụ thuộc lần dùng trước.
    static let whatsNewSuite = "uiPreview.whatsNew"

    /// `defaults` presenter What's New dùng cho route hiện tại (`.standard` ngoài route `whatsNew`).
    static var whatsNewDefaults: UserDefaults {
        AppPreview.current == .whatsNew ? (UserDefaults(suiteName: whatsNewSuite) ?? .standard) : .standard
    }

    /// Quyền thay `Entitlements.live` cho route hiện tại (store giả, suite `uiPreview.*`); `nil` ⇒ dùng bản thật
    /// (không route, hoặc route không cần).
    @MainActor
    static func entitlements() -> Entitlements? {
        return nil
    }

    /// Link giả mà route preview "nhận" ~1 s sau khi mở (đi đúng đường `onOpenURL` ⇒ `AppLinkRouter`); `nil` ⇒ route
    /// không giả link, hoặc app không có host web.
    static func incomingLink(webHost: String?) -> URL? {
        guard let webHost, !webHost.isEmpty else { return nil }
        return nil
    }

    /// Đưa luồng tới màn của route.
    @MainActor
    static func prepareFlow(_ flow: FlowModel) {
        guard flow.path.isEmpty else { return }
        switch AppPreview.current {
        case .scan: flow.choose(.cube3)
        default: break
        }
    }

    @MainActor
    static func prepare() {
        guard let route = AppPreview.current else { return }
        // onboarding ⇒ hiện tour; mọi route khác ⇒ vào thẳng app.
        UserDefaults.standard.set(!route.isOnboarding, forKey: WhatsNewHost.hasSeenOnboardingKey)
        if route == .whatsNew {
            let d = whatsNewDefaults
            d.removePersistentDomain(forName: whatsNewSuite)
            // Khách cũ (đã qua onboarding) vừa cập nhật từ một bản trước mọi thẻ: chưa dùng thẻ nào, không seed từ đĩa.
            d.set(true, forKey: WhatsNewHost.hasSeenOnboardingKey)
            d.set([String](), forKey: FeatureUsageLedger.usedCardsKey)
            d.set(true, forKey: FeatureUsageLedger.diskSeededKey)
            d.set("0.0.1", forKey: WhatsNewState.lastSeenKey)
        }
    }
}

/// Mở sẵn màn của route `paywall` (cover, như từ Settings) và `feedback` (form trong stack, như push từ Settings) —
/// chỉ để chụp ảnh. `isShown` báo cho cổng What's New của khung chính.
private struct AppPreviewPresentations: ViewModifier {
    let paywall: PaywallContent
    let config: AppConfig
    let feedbackTransport: FeedbackTransport?
    @Binding var isShown: Bool
    @State private var showPaywall = AppPreview.current == .paywall
    @State private var showFeedback = AppPreview.current == .feedback
    /// Quyền riêng của ảnh chụp paywall: store giả, cache Pro ở suite riêng (không đụng trạng thái thật của sim).
    @StateObject private var previewEntitlements = Entitlements(
        client: AppPreviewStore(), paywallEnabled: true,
        defaults: UserDefaults(suiteName: "uiPreview.paywall") ?? .standard,
        internalDeviceFlag: AppPreviewStore.NoCounter())

    func body(content: Content) -> some View {
        content
            .onAppear { isShown = showPaywall || showFeedback }
            .fullScreenCover(isPresented: $showPaywall, onDismiss: { isShown = false }) {
                // `start()` như ở cấp App: đọc quyền + đủ điều kiện dùng thử (khách mới) rồi mới tải gói.
                PaywallView(entitlements: previewEntitlements, content: paywall)
                    .onAppear { previewEntitlements.start() }
            }
            .sheet(isPresented: $showFeedback, onDismiss: { isShown = false }) {
                if let feedbackTransport {
                    NavigationStack {
                        FeedbackView(type: .bug, transport: feedbackTransport,
                                     diagnostics: DiagnosticsSnapshot.current(),
                                     support: SupportConfig(config: config))
                    }
                } else {
                    // Khối Web API tắt ⇒ app không có form phản hồi (Settings chỉ có "Contact us"). Chuỗi chỉ của
                    // ảnh preview trên Simulator — `Text(verbatim:)`, không vào String Catalog.
                    Text(verbatim: "Web API block is off: no feedback form (Settings offers Contact us only).")
                        .foregroundColor(DSColor.textSecondary)
                        .multilineTextAlignment(.center)
                        .padding(24)
                }
            }
    }
}

/// Store giả của route `paywall` — ba gói, giá và dùng thử KHỚP `AppHost/StoreKitConfig/Products.storekit`
/// (`SmokeTests.testStoreGiaCuaPreviewKhopFileStorekit` gác lệch). Id lấy từ cấu hình (`ProductIDs`) theo đuôi.
/// Không bao giờ mua được (`purchase` ⇒ huỷ). Chỉ Simulator.
@MainActor
struct AppPreviewStore: StoreClient {
    struct NoCounter: SecureCounterStore {
        func read() throws -> Int { 0 }
        func write(_ value: Int) throws {}
    }

    /// (đuôi id, giá, loại, ngày dùng thử) — đọc ở `Products.storekit`.
    static let plans: [(suffix: String, price: String, kind: ProProduct.Kind, trialDays: Int?)] = [
        ("monthly", "$2.99", .month, 7),
        ("yearly", "$19.99", .year, 7),
        ("lifetime", "$49.99", .lifetime, nil),
    ]

    static func products(productIDs: [String]) -> [ProProduct] {
        plans.compactMap { plan in
            productIDs.first { $0.hasSuffix(plan.suffix) }.map {
                ProProduct(id: $0, displayPrice: plan.price, kind: plan.kind, freeTrialDays: plan.trialDays)
            }
        }
    }

    func products() async throws -> [ProProduct] {
        let p = Self.products(productIDs: AppConfig.current.productIDs)
        guard !p.isEmpty else { throw StoreError.productsUnavailable }
        return p
    }
    func currentEntitlement() async -> Bool { false }
    func currentEntitlementKind() async -> ProProduct.Kind? { nil }
    func isEligibleForIntroOffer() async -> Bool { true }
    func purchase(_ productID: String) async throws -> PurchaseOutcome { .cancelled }
    func sync() async throws {}
    func transactionUpdates() -> AsyncStream<Void> { AsyncStream { _ in } }
    func storeEnvironment() async -> String? { nil }
}
#endif

extension View {
    /// Cover/sheet của route preview (Simulator); `self` nguyên vẹn ở build device.
    @ViewBuilder
    func appPreviewPresentations(paywall: PaywallContent, config: AppConfig,
                                 feedbackTransport: FeedbackTransport?, isShown: Binding<Bool>) -> some View {
        #if targetEnvironment(simulator)
        // Chỉ khi đang chạy route preview: lần chạy thường trên Simulator không dựng gì thêm (kể cả `Entitlements` giả).
        if AppPreview.current != nil {
            modifier(AppPreviewPresentations(paywall: paywall, config: config,
                                             feedbackTransport: feedbackTransport, isShown: isShown))
        } else {
            self
        }
        #else
        self
        #endif
    }
}
