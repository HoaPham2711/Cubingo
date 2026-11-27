import Combine
import Foundation

/// Trạng thái Pro của người dùng — **điểm truy cập DUY NHẤT** cho mọi chỗ gating.
///
/// Nguồn sự thật là `StoreClient` (StoreKit 2). `UserDefaults` chỉ còn làm **cache khởi động
/// lạnh**: lấp vài trăm ms của khung hình đầu để màn đầu không hiện khoá rồi mới mở ra.
///
/// Luật một chiều: truy vấn QUYỀN hoàn tất mà rỗng ⇒ hạ quyền, kể cả offline (StoreKit 2 giữ
/// bản sao giao dịch có chữ ký ngay trên máy). Lỗi tải SẢN PHẨM/GIÁ — thứ duy nhất cần mạng —
/// không bao giờ được đụng tới trạng thái quyền.
///
/// Paywall tắt (`paywallEnabled == false`, công tắc cấu hình lúc chạy) = app miễn phí hoàn toàn: `isPro` luôn
/// true, không một lời gọi nào vào `StoreClient`, không event phễu mua, không gán `is_pro`.
///
/// Truyền TƯỜNG MINH qua `init` tới nơi cần (không `@EnvironmentObject`): `fullScreenCover` không kế thừa
/// environment object.
@MainActor
final class Entitlements: ObservableObject {

    enum LoadState: Equatable {
        case loading
        case ready
        case failed
    }

    /// Kết quả một lần bấm Khôi phục. Ba nhánh phải phân biệt được: nói với người ĐÃ trả tiền rằng
    /// họ chưa từng mua — chỉ vì mạng lỗi — là sai sự thật và đẻ ra khiếu nại hoàn tiền.
    enum RestoreOutcome: Equatable {
        case restored
        case noPurchasesFound
        case failed
    }

    static let key = "entitlements.isPro"
    /// Cache loại quyền (`ProProduct.Kind.rawValue`), cùng `defaults` với `key`. Thiếu/lạ ⇒ `nil`.
    static let kindKey = "entitlements.kind"

    /// Công tắc paywall (`AppConfig.features.paywall`). Đọc lúc chạy, không `#if`.
    let paywallEnabled: Bool

    @Published private(set) var isPro: Bool

    /// Loại quyền đang giữ (`nil` = không có, hoặc không suy được loại). Bất biến: `entitlementKind != nil` ⇒
    /// `isPro`. Cache khởi động lạnh như `isPro` (`kindKey`); paywall tắt ⇒ luôn `nil`, không cache. Override Pro của
    /// build INTERNAL KHÔNG bịa loại: chỉ giữ loại của giao dịch thật (nếu có).
    @Published private(set) var entitlementKind: ProProduct.Kind?

    /// `true` suốt thời gian `restore()` chạy (nút Restore ở paywall và Settings khoá + hiện vòng quay).
    @Published private(set) var isRestoring = false

    /// Hàng "Manage subscription": chỉ người đang Pro mà KHÔNG phải mua trọn đời (mua đứt không có gói để quản
    /// lý/huỷ — sheet hệ thống sẽ trống). Pro mà chưa rõ loại (`nil`: offline chưa đọc được chu kỳ, hay override Pro
    /// INTERNAL không có giao dịch) ⇒ vẫn hiện: thà thừa một hàng còn hơn giấu lối huỷ của người đang trả tiền.
    var canManageSubscription: Bool { isPro && entitlementKind != .lifetime }

    /// Gói vừa được bấm mua trong phiên này — CHỈ dùng cho analytics (`purchase_success`).
    /// KHÔNG phải nguồn sự thật về quyền: quyền vẫn chỉ đến từ StoreKit qua `refresh()`.
    private var lastPurchasedProductID: String?
    /// Lượt mua gần nhất có đi kèm intro offer không — chốt lúc bấm mua, xem `purchase(_:)`.
    private var lastPurchaseUsedTrial = false
    @Published private(set) var products: [ProProduct] = []
    @Published private(set) var loadState: LoadState = .loading
    @Published private(set) var isEligibleForTrial = false
    @Published private(set) var isPurchasing = false
    @Published private(set) var isPending = false
    @Published private(set) var purchaseError: String?
    /// Mã lỗi lần tải sản phẩm gần nhất (`nil` khi tải được) — xem `errorCode(_:)`.
    private(set) var productsErrorCode: String?

    private let client: StoreClient
    private let defaults: UserDefaults
    /// Cờ "máy nội bộ" (0/1) — Keychain nên sống qua gỡ app cài lại, xem `syncStoreEnvironment`.
    private let internalDeviceFlag: SecureCounterStore
    private var updatesTask: Task<Void, Never>?
    /// Bộ đếm thế hệ chống refresh() chồng lấn ghi đè kết quả mới bằng kết quả cũ hơn — xem
    /// comment trong `refresh()`.
    private var refreshGeneration = 0
    /// Lượt `restore()` đang chạy — lần gọi thứ hai chờ và trả kết quả của nó, không gọi `sync()` lần nữa.
    private var restoreTask: Task<RestoreOutcome, Never>?

    init(client: StoreClient, paywallEnabled: Bool = true, defaults: UserDefaults = .standard,
         internalDeviceFlag: SecureCounterStore = KeychainCounterStore(
            service: KeychainCounterStore.appService("internalDevice"), account: "seen")) {
        self.client = client
        self.paywallEnabled = paywallEnabled
        self.defaults = defaults
        self.internalDeviceFlag = internalDeviceFlag
        self.isPro = paywallEnabled
            ? Self.applyingInternalOverride(defaults.bool(forKey: Self.key), defaults: defaults)
            : true
        let cachedKind = defaults.string(forKey: Self.kindKey).flatMap(ProProduct.Kind.init(rawValue:))
        self.entitlementKind = paywallEnabled && isPro ? cachedKind : nil
    }

    /// Gọi đúng một lần lúc app khởi động. **Gắn listener TRƯỚC khi đọc quyền** — làm ngược lại
    /// là để hở một khe thời gian nuốt mất giao dịch đến trong khe đó.
    /// Gọi ở cấp App (listener phải nghe từ giây đầu, kể cả lúc đang onboarding). App KHÔNG gọi `start()` /
    /// `refresh()` khi chạy làm host unit test (`AppEnvironment.isUnitTestHost`): host test mà chạm StoreKit thật
    /// thì hộp thoại đăng nhập Apple ID treo cả suite.
    func start() {
        guard paywallEnabled, updatesTask == nil else { return }
        let stream = client.transactionUpdates()
        updatesTask = Task { [weak self] in
            for await _ in stream {
                await self?.refresh()
            }
        }
        Task {
            await refresh()
            await loadProducts()
        }
        // Task riêng: đọc `AppTransaction` không được làm chậm việc hiện quyền Pro.
        Task { await syncStoreEnvironment() }
    }

    /// Gắn user property `store_env` để báo cáo lọc được doanh thu TestFlight/sandbox khỏi doanh thu
    /// thật — cả hai đổ chung một dự án analytics vì cùng config `Release`. Môi trường cố định theo
    /// bản cài nên chỉ cần một lần lúc khởi động; analytics giữ thuộc tính này qua các phiên.
    /// Không đọc được thì KHÔNG gán — gán bừa `production` là nhuộm bẩn đúng nhóm cần sạch.
    ///
    /// `store_env = production` không loại được máy dev TẢI app từ App Store. Nên máy nào từng
    /// thấy môi trường khác production (TestFlight, bản Release cài từ Xcode — cùng bundle id,
    /// cùng Keychain với bản Store) thì ghi cờ vào Keychain và gắn `internal_device` từ đó về sau,
    /// kể cả sau khi gỡ app cài lại bản App Store. Cờ một chiều; máy khách không bao giờ có.
    func syncStoreEnvironment() async {
        guard paywallEnabled else { return }
        if let env = await client.storeEnvironment() {
            Track.set(.storeEnv(env))
            if env != "production" { try? internalDeviceFlag.write(1) }
        }
        if ((try? internalDeviceFlag.read()) ?? 0) > 0 { Track.set(.internalDevice) }
    }

    /// KHÔNG tuần tự hoá bằng actor/lock — dùng bộ đếm thế hệ. Hai lần gọi chồng nhau (vd.
    /// `start()` chạy song song listener và refresh khởi động) thì LẦN KẾT THÚC SAU luôn thắng vì
    /// nó ghi sau cùng, bất kể lần nào ĐỌC quyền mới hơn. Ca mất tiền cụ thể: refresh khởi động
    /// đọc trước (`false`), user vừa mua ở máy khác nên listener refresh đọc `true` và ghi Pro
    /// trước, rồi refresh khởi động tỉnh dậy ghi đè `false` ⇒ người vừa trả tiền mất Pro tới lần
    /// mở app sau.
    ///
    /// Subscription HẾT HẠN không bắn `Transaction.updates` ⇒ app phải gọi `refresh()` mỗi lần scene vào
    /// `.active`, nếu không người hết hạn vẫn giữ Pro tới lần mở app sau. (Không gọi khi chạy làm host unit test.)
    func refresh() async {
        guard paywallEnabled else { return }
        refreshGeneration += 1
        let gen = refreshGeneration
        let entitled = await client.currentEntitlement()
        // Lần refresh mới hơn đã chạy xong trong lúc mình await ⇒ kết quả của mình đã CŨ, bỏ đi.
        // Không có chốt này thì lần kết thúc sau thắng, chứ không phải lần đọc sau.
        guard gen == refreshGeneration else { return }
        // Quyền TRƯỚC, loại sau: đọc loại có thể chờ mạng (`Product.products(for:)` của LiveStoreClient) — `isPro` được
        // công bố (tính năng mở khoá khắp app) trước cú gọi đó. Spinner/đóng của chính paywall vẫn chờ `refresh()` trả về
        // (nợ ở docs/ROADMAP.md).
        setPro(Self.applyingInternalOverride(entitled, defaults: defaults))
        // Ask to Buy được duyệt xong thì hết "đang chờ" — nếu không, alert chờ-duyệt còn kẹt lại
        // chồng lên trạng thái đã Pro.
        if entitled { isPending = false }
        let kind = entitled ? await client.currentEntitlementKind() : nil
        let eligible = await client.isEligibleForIntroOffer()
        // Chốt lần hai: một refresh mới hơn có thể đã ghi quyền/loại trong lúc mình chờ loại.
        guard gen == refreshGeneration else { return }
        // Sau `setPro` (nó xoá loại khi hạ quyền): loại chỉ tồn tại khi đang Pro.
        setKind(isPro ? kind : nil)
        isEligibleForTrial = eligible
    }

    func loadProducts() async {
        guard paywallEnabled else { return }
        loadState = .loading
        do {
            let loaded = try await client.products()
            // Rỗng = "không có sản phẩm", không phải `.ready` với 0 gói: paywall sẵn sàng mà không có gói nào
            // thì CTA vẫn bật và cú bấm sau có thể tính tiền một id không hiển thị. Cùng định nghĩa với guard
            // trên danh sách đã map của `LiveStoreClient`, chốt lại ở đây cho mọi client.
            guard !loaded.isEmpty else { throw StoreError.productsUnavailable }
            products = loaded
            productsErrorCode = nil
            loadState = .ready
        } catch {
            // KHÔNG đụng tới isPro: đây là lỗi tải giá, không phải bằng chứng mất quyền.
            products = []
            // Giữ mã lỗi lại thay vì nuốt: lỗi này mà biến mất không dấu vết thì paywall chỉ còn nút mua
            // bị khoá ⇒ bấm "không phản ứng gì".
            productsErrorCode = Self.errorCode(error)
            loadState = .failed
        }
    }

    /// Lối vào DUY NHẤT của nút mua trên paywall. Nút luôn bấm được (trừ lúc đang mua/chờ
    /// duyệt) và MỌI cú bấm đều có phản hồi nhìn thấy được:
    /// - gói đã tải ⇒ mua như thường (`purchase`);
    /// - gói chưa tải / tải lỗi ⇒ tải lại. Vẫn lỗi ⇒ alert kèm mã lỗi + `purchase_fail`
    ///   (`reason` = mã lỗi tải sản phẩm). Tải được ⇒ DỪNG, không mua ngay: user chưa thấy giá
    ///   trên paywall thì không được tính tiền (Guideline 3.1.2) — giá hiện ra, họ bấm lại.
    ///
    /// Khoá CTA theo `loadState != .ready` là sai: khi StoreKit không trả sản phẩm, bấm mua im lặng hoàn
    /// toàn — không popup mua, không alert, không telemetry.
    func subscribe(_ productID: String) async {
        guard paywallEnabled, !isPurchasing, !isPending else { return }
        guard loadState == .ready else {
            isPurchasing = true
            purchaseError = nil
            defer { isPurchasing = false }
            await loadProducts()
            guard loadState == .ready else {
                let ten = tenSanPham(productID)
                let code = productsErrorCode ?? "products_unavailable"
                Track.log(.purchaseStart(product: ten, trial: muaCoDungThu(productID)))
                Track.log(.purchaseFail(product: ten, reason: code))
                purchaseError = Self.unavailableMessage(code: code)
                return
            }
            return
        }
        // Id không nằm trong danh sách ĐÃ TẢI (paywall không hiển thị nó) ⇒ "không có sản phẩm", không gọi mua.
        // API nhận chuỗi id nên app nào cũng có thể truyền nhầm (id cũ còn lưu, id lệch cấu hình) — tính tiền một
        // gói user chưa thấy giá là sai (Guideline 3.1.2). Cùng trạng thái lỗi + phễu như khi không tải được gói.
        guard products.contains(where: { $0.id == productID }) else {
            let code = Self.errorCode(StoreError.productsUnavailable)
            Track.log(.purchaseStart(product: tenSanPham(productID), trial: false))
            Track.log(.purchaseFail(product: tenSanPham(productID), reason: code))
            purchaseError = Self.unavailableMessage(code: code)
            return
        }
        await purchase(productID)
    }

    func purchase(_ productID: String) async {
        guard paywallEnabled else { return }
        isPurchasing = true
        purchaseError = nil
        // Ghi lại để `setPro` biết gói nào vừa được mua — `refresh()` chỉ nói "có quyền Pro",
        // không nói quyền đó đến từ gói nào.
        lastPurchasedProductID = productID
        // Chốt TRƯỚC khi mua: mua xong thì `isEligibleForTrial` đã thành false, hỏi lúc đó là sai.
        lastPurchaseUsedTrial = muaCoDungThu(productID)
        defer { isPurchasing = false }
        let ten = tenSanPham(productID)
        // Phễu mua hàng: start có đúng MỘT lối ra — success (bắn ở `setPro`), cancel, pending hoặc fail.
        Track.log(.purchaseStart(product: ten, trial: lastPurchaseUsedTrial))
        do {
            switch try await client.purchase(productID) {
            case .success:
                await refresh()
            case .pending:
                // Ask to Buy / xác thực ngân hàng: quyền sẽ về qua listener, có thể sau nhiều giờ.
                isPending = true
                Track.log(.purchasePending(product: ten))
            case .cancelled:
                Track.log(.purchaseCancel(product: ten))
            }
        } catch {
            let code = Self.errorCode(error)
            Track.log(.purchaseFail(product: ten, reason: code))
            purchaseError = error as? StoreError == .productsUnavailable
                ? Self.unavailableMessage(code: code)
                : String(localized: "Purchase could not be completed. Please try again.")
                    + "\n\n" + String(localized: "Error code: \(code)")
        }
    }

    /// StoreKit không trả sản phẩm (mất mạng, chưa đăng nhập App Store, sandbox TestFlight lỗi,
    /// product id lệch App Store Connect). Mã lỗi in kèm để user/tester chụp màn gửi lại được.
    private static func unavailableMessage(code: String) -> String {
        String(localized: "Purchases aren't available right now. Check your internet connection and that you're signed in to the App Store, then try again.")
            + "\n\n" + String(localized: "Error code: \(code)")
    }

    /// Mã lỗi ngắn, máy đọc được, cho alert + telemetry `purchase_fail.reason`.
    /// `StoreError` của mình ⇒ tên case; lỗi hệ thống (StoreKitError, NSURLError…) ⇒
    /// `<domain>#<code> <case>`.
    static func errorCode(_ error: Error) -> String {
        switch error as? StoreError {
        case .productsUnavailable?: return "products_unavailable"
        case .unverified?: return "unverified"
        case .purchaseFailed(let why)?: return "purchase_failed \(why)"
        case nil: break
        }
        let ns = error as NSError
        // Tên case của enum lỗi Swift ("networkError(...)" ⇒ "networkError") — đủ để tra tài liệu.
        // Chỉ nhận khi là định danh thuần: NSError/URLError mô tả kiểu "Error Domain=… Code=…".
        let caseName = String(String(describing: error).prefix { $0 != "(" })
        let isIdentifier = caseName.first?.isLetter == true
            && caseName.allSatisfy { $0.isLetter || $0.isNumber || $0 == "_" }
        let base = "\(ns.domain)#\(ns.code)"
        return isIdentifier ? "\(base) \(caseName)" : base
    }

    func dismissPurchaseError() {
        purchaseError = nil
    }

    func dismissPending() {
        isPending = false
    }

    /// `AppStore.sync()` bật hộp thoại nhập mật khẩu App Store nên CHỈ chạy khi user tự bấm.
    /// Lỗi sync (vd. mất mạng giữa chừng) KHÔNG được lẫn với "chưa từng mua" — nói sai với người
    /// đã trả tiền là đẻ ra khiếu nại hoàn tiền.
    /// Paywall tắt ⇒ không có gì để khôi phục: user đã có mọi thứ (`.restored`), không gọi store, không event.
    ///
    /// Gọi chồng (bấm ở paywall khi Settings đang khôi phục, bấm đúp) ⇒ KHÔNG gọi `sync()` lần hai (thêm một hộp
    /// thoại mật khẩu): chờ và trả kết quả lượt đang chạy. `isRestoring` hạ đúng một lần, do lượt đầu, kể cả khi lỗi.
    func restore() async -> RestoreOutcome {
        guard paywallEnabled else { return .restored }
        if let restoreTask { return await restoreTask.value }
        isRestoring = true
        let task = Task { await self.performRestore() }
        restoreTask = task
        let outcome = await task.value
        restoreTask = nil
        isRestoring = false
        return outcome
    }

    private func performRestore() async -> RestoreOutcome {
        do {
            try await client.sync()
        } catch {
            Track.log(.restoreResult(outcome: "failed"))
            return .failed
        }
        await refresh()
        Track.log(.restoreResult(outcome: isPro ? "restored" : "none"))
        return isPro ? .restored : .noPurchasesFound
    }

    private func setPro(_ value: Bool) {
        // Paywall tắt: `isPro` đứng yên ở true; không cache, không event, không `is_pro` (gán `true` cho mọi user
        // của app miễn phí là bơm rác vào chiều cắt lát Free/Pro của báo cáo).
        guard paywallEnabled else { return }
        // Chỉ bắn khi quyền CHUYỂN từ không sang có. `refresh()` chạy mỗi lần app vào foreground
        // và gọi `setPro(true)` cho người đã mua — bắn vô điều kiện là đếm mỗi lần mở app thành
        // một lần mua, và doanh thu trên dashboard sẽ vô nghĩa.
        let vuaLenPro = value && !isPro
        isPro = value
        defaults.set(value, forKey: Self.key)
        // Mất quyền ⇒ mất luôn loại (kể cả cache) — giữ bất biến `entitlementKind != nil ⇒ isPro`.
        if !value { setKind(nil) }
        if vuaLenPro {
            // `nil` khi quyền đến từ restore / Transaction.updates chứ không từ một cú bấm mua
            // trong phiên này — "unknown" đúng ngữ nghĩa: khôi phục không phải mua mới.
            Track.log(.purchaseSuccess(product: tenSanPham(lastPurchasedProductID),
                                       trial: lastPurchasedProductID != nil && lastPurchaseUsedTrial))
        }
        Track.set(.isPro(value))
    }

    private func setKind(_ kind: ProProduct.Kind?) {
        guard paywallEnabled else { return }
        entitlementKind = kind
        if let kind { defaults.set(kind.rawValue, forKey: Self.kindKey) }
        else { defaults.removeObject(forKey: Self.kindKey) }
    }

    /// Nhãn ngắn cho analytics, suy từ `kind` của gói ĐÃ TẢI (`monthly`/`yearly`/`lifetime`), không từ id.
    /// Gói chưa tải hoặc id lạ ⇒ `unknown`.
    private func tenSanPham(_ id: String?) -> String {
        guard let id, let p = products.first(where: { $0.id == id }) else { return "unknown" }
        return p.kind.analyticsName
    }

    /// Lượt mua này có đi kèm dùng thử không: group còn đủ điều kiện VÀ chính gói đó có offer dùng thử. Gói trọn
    /// đời không bao giờ có (`freeTrialDays == nil`). Gói chưa tải ⇒ chỉ biết điều kiện của group.
    private func muaCoDungThu(_ id: String) -> Bool {
        guard isEligibleForTrial else { return false }
        guard let p = products.first(where: { $0.id == id }) else { return true }
        return p.freeTrialDays != nil
    }

    /// Bản App Store: luôn trả nguyên quyền thật. Build INTERNAL: override Free/Pro (nếu có) thắng
    /// cả cache lẫn StoreKit — giao dịch StoreKit cục bộ (file `.storekit`) không huỷ được từ
    /// Settings, nên không có override thì máy test đã "mua" không bao giờ về lại Free.
    static func applyingInternalOverride(_ entitled: Bool, defaults: UserDefaults) -> Bool {
        #if INTERNAL
        switch InternalProOverride.current(defaults) {
        case .storeKit: return entitled
        case .free: return false
        case .pro: return true
        }
        #else
        return entitled
        #endif
    }

    #if INTERNAL
    /// Override cố định cho máy test (chỉ build INTERNAL), lưu UserDefaults, sống qua mở lại app.
    enum InternalProOverride: String, CaseIterable {
        case storeKit, free, pro
        static let key = "internal.proOverride"
        static func current(_ d: UserDefaults) -> Self {
            d.string(forKey: key).flatMap(Self.init(rawValue:)) ?? .storeKit
        }
    }

    var internalProOverride: InternalProOverride { InternalProOverride.current(defaults) }

    /// `.storeKit` xoá override rồi đọc lại quyền thật; `.free`/`.pro` áp ngay.
    // debug-symbol: required
    func setInternalProOverride(_ o: InternalProOverride) async {
        objectWillChange.send()
        if o == .storeKit { defaults.removeObject(forKey: InternalProOverride.key) }
        else { defaults.set(o.rawValue, forKey: InternalProOverride.key) }
        switch o {
        case .storeKit: await refresh()
        case .free: setPro(false)
        case .pro: setPro(true)
        }
    }

    /// Lối ghi DUY NHẤT ngoài `purchase()`, và nó chỉ tồn tại ở build có cờ `INTERNAL`
    /// (config Debug/Internal). Bản App Store không compile hàm này ⇒ không có đường nào bật Pro
    /// mà không trả tiền. Tên nằm ở mục `[source-only]` của `tools/release/debug_symbols.txt` (tên hàm bị strip khỏi
    /// binary nên không soi binary được) — chỗ dựa là `#if INTERNAL` + `lint_debug_symbols.py`.
    // debug-symbol: required
    func setProForInternalTesting(_ on: Bool) {
        setPro(on)
    }
    #endif
}

extension Entitlements {
    /// Dựng từ cấu hình app: mọi id trong `productIDs` cấp Pro; `features.paywall == false` ⇒ app miễn phí,
    /// `LiveStoreClient` được tạo nhưng không bao giờ bị gọi.
    /// Nối vòng đời: `start()` một lần ở cấp App, `refresh()` mỗi lần scene vào `.active` (hết hạn subscription
    /// không bắn `Transaction.updates`); cả hai bỏ qua khi `AppEnvironment.isUnitTestHost`.
    static func live(config: AppConfig) -> Entitlements {
        Entitlements(client: LiveStoreClient(productIDs: config.productIDs),
                     paywallEnabled: config.features.paywall)
    }
}
