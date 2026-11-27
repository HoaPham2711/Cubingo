import SwiftUI

/// Quyết định bố cục của paywall theo cỡ chữ — hàm THUẦN, có test (`PaywallLayoutTests`).
enum PaywallLayout {
    /// Cỡ chữ thường: chọn gói + CTA + điều khoản GHIM ở chân màn (bảng so sánh dài, giá không được nằm dưới đáy phải
    /// cuộn mới thấy). Cỡ chữ trợ năng (accessibility sizes): KHÔNG ghim — chân màn cao hơn cả màn hình, ghim thì đẩy
    /// nút mua/điều khoản ra ngoài màn, không cuộn tới được; khi đó cả khối nằm cuối vùng cuộn.
    static func pinsFooter(isAccessibilitySize: Bool) -> Bool {
        !isAccessibilitySize
    }
}

/// Paywall — bảng so sánh Free/Pro (app cấp qua `PaywallContent`) · gói lấy từ StoreKit thật
/// (`entitlements.products`: tháng, năm và/hoặc trọn đời) · CTA · Khôi phục · link điều khoản.
///
/// 4 trạng thái phủ hết vòng đời tải sản phẩm: `.loading` (đang hỏi StoreKit), `.ready` (đã có
/// giá thật để hiển thị), `.failed` (mất mạng — cho bấm thử lại, KHÔNG đụng tới `isPro`), và
/// đồng thời `isPurchasing`/`isPending` khoá nút trong lúc giao dịch đang xử lý hoặc chờ Ask to
/// Buy duyệt. Không có giá literal — giá cứng sai với mọi user ngoài một vùng.
///
/// Danh sách gói hình dạng nào cũng phải đúng: đủ ba gói, chỉ trọn đời, chỉ một subscription, rỗng/tải lỗi.
/// Câu chữ (CTA, điều khoản, hàng gói) do `PaywallCopy` quyết định — body này không chứa luật nào về copy.
///
/// Trình bày bằng `fullScreenCover` ở call site (app). Cover không có gesture vuốt-để-đóng.
struct PaywallView: View {
    /// Truyền TƯỜNG MINH thay vì `@EnvironmentObject`: mọi màn Pro đều được present bằng
    /// `fullScreenCover`, mà cover KHÔNG tự kế thừa environment object — quên gắn là crash lúc
    /// chạy (`EnvironmentObject.error()`; app nguồn đã crash đúng kiểu này). Là tham số thì compiler
    /// bắt lỗi ngay, không đợi tới device.
    @ObservedObject private var entitlements: Entitlements
    private let content: PaywallContent
    /// Headline ngữ cảnh (vd "hết lượt dùng thử") — `nil` dùng `content.defaultHeadline`. App truyền chuỗi đã
    /// localize (`String(localized:)`).
    private let headline: String?
    /// Gọi khi paywall đóng mà user vẫn chưa Pro (vd `ReviewPrompter.notePaywallDismissed`). Mua/khôi phục
    /// thành công thì KHÔNG gọi — đó không phải "bực mình".
    private let onDismissedWithoutPurchase: (() -> Void)?

    @Environment(\.dismiss) private var dismiss
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @State private var selectedID: String?
    @State private var restoreAlert: RestoreAlert?

    init(entitlements: Entitlements, content: PaywallContent, headline: String? = nil,
         onDismissedWithoutPurchase: (() -> Void)? = nil) {
        self.entitlements = entitlements
        self.content = content
        self.headline = headline
        self.onDismissedWithoutPurchase = onDismissedWithoutPurchase
    }

    // MARK: - Chọn gói (hàm thuần, có test)

    /// Gói chọn sẵn: id THẬT SỰ có trong `products` — ưu tiên loại `preselected`, không có thì phần tử đầu,
    /// danh sách rỗng ⇒ `nil`. Không bao giờ trả một id không hiển thị.
    static func initialSelection(products: [ProProduct], preselected: ProProduct.Kind) -> String? {
        products.first { $0.kind == preselected }?.id ?? products.first?.id
    }

    /// `selectedID` phải luôn trỏ vào một id THẬT SỰ có trong `entitlements.products`, nếu không hàng đó hiện
    /// radio "chưa chọn" trong khi CTA vẫn tính tiền id cũ chưa từng hiện giá (vd. chỉ tải được Monthly do
    /// Yearly bị App Store loại bỏ). Áp lại MỖI LẦN danh sách đổi: lựa chọn còn trong danh sách thì giữ, biến
    /// mất thì ghim về `initialSelection`.
    static func pinnedSelection(current: String?, products: [ProProduct],
                                preselected: ProProduct.Kind) -> String? {
        if let current, products.contains(where: { $0.id == current }) { return current }
        return initialSelection(products: products, preselected: preselected)
    }

    /// Gói đang được radio chọn. `nil` khi chưa có danh sách (đang tải / lỗi).
    private var selectedProduct: ProProduct? {
        entitlements.products.first { $0.id == selectedID }
    }

    private func pinSelection(_ products: [ProProduct]) {
        selectedID = Self.pinnedSelection(current: selectedID, products: products, preselected: content.preselectedKind)
    }

    /// Alert sau Khôi phục ở paywall — chuyển tiếp `RestoreAlert.make` (nguồn duy nhất, Settings dùng chung).
    static func restoreAlert(for outcome: Entitlements.RestoreOutcome) -> RestoreAlert? {
        RestoreAlert.make(outcome)
    }

    private var pinsFooter: Bool {
        PaywallLayout.pinsFooter(isAccessibilitySize: dynamicTypeSize.isAccessibilitySize)
    }

    var body: some View {
        ZStack {
            DSColor.pageBackground.ignoresSafeArea()
            VStack(spacing: 0) {
                header
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 20) {
                        // Đã localize tại nguồn (app) — Text(String) không tra catalog lần hai.
                        Text(headline ?? content.defaultHeadline)
                            .scaledFont(size: 28, weight: .bold)
                            .foregroundColor(DSColor.textPrimary)
                            .fixedSize(horizontal: false, vertical: true)
                        if !content.sections.isEmpty { comparisonTable }
                    }
                    .padding(20)
                    .readableContentWidth(DSLayout.formWidth, alignment: .leading) // iPad: cột đọc giữa
                    if !pinsFooter {
                        footerContent
                            .padding(.horizontal, 20).padding(.bottom, 16)
                            .readableContentWidth(DSLayout.formWidth)
                    }
                }
                if pinsFooter {
                    footer
                        .readableContentWidth(DSLayout.formWidth)
                }
            }
        }
        .task {
            if entitlements.loadState != .ready { await entitlements.loadProducts() }
            pinSelection(entitlements.products)
        }
        .onChange(of: entitlements.products) { _, products in pinSelection(products) }
        .alert(restoreAlert?.title ?? "",
               isPresented: Binding(get: { restoreAlert != nil },
                                    set: { if !$0 { restoreAlert = nil } })) {
            Button("Close", role: .cancel) { restoreAlert = nil }
        } message: {
            Text(verbatim: restoreAlert?.message ?? "")
        }
        .alert("Purchase failed",
               isPresented: Binding(get: { entitlements.purchaseError != nil },
                                    set: { if !$0 { entitlements.dismissPurchaseError() } })) {
            Button("Close", role: .cancel) { entitlements.dismissPurchaseError() }
        } message: {
            Text(entitlements.purchaseError ?? "")
        }
        // Ask to Buy: KHÔNG đóng paywall, KHÔNG báo lỗi — giao dịch có thể được duyệt sau nhiều giờ.
        // Binding hai chiều thật (không phải .constant): bấm OK phải hạ được cờ isPending, nếu
        // không alert bật lại ngay lần render sau và user kẹt không thoát ra được.
        .alert("Waiting for approval",
               isPresented: Binding(get: { entitlements.isPending },
                                    set: { if !$0 { entitlements.dismissPending() } })) {
            Button("OK", role: .cancel) { entitlements.dismissPending(); dismiss() }
        } message: {
            Text("This purchase needs approval. Pro unlocks automatically once it is approved.")
        }
        // `fullScreenCover` không có gesture vuốt-để-đóng, nên MỌI đường thoát (nút X, "Waiting
        // for approval" → OK) đều đi qua `dismiss()` rồi tới đây. `isPro` lúc `onDisappear` chạy
        // đã phản ánh đúng kết quả — mua thành công thì KHÔNG tính là "bực mình".
        .trackOverlayScreen("paywall")
        .onDisappear {
            if !entitlements.isPro { onDismissedWithoutPurchase?() }
        }
    }

    // MARK: - Gói

    @ViewBuilder
    private var planSection: some View {
        switch entitlements.loadState {
        case .loading:
            ProgressView().frame(maxWidth: .infinity).padding(.vertical, 14)
        case .failed:
            VStack(spacing: 10) {
                Text("Could not load purchase options.")
                    .font(.footnote).foregroundColor(DSColor.textSecondary)
                Button("Try again") { Task { await entitlements.loadProducts() } }
                    .foregroundColor(DSColor.accent)
            }
            .frame(maxWidth: .infinity).padding(.vertical, 6)
        case .ready:
            // Gói GHIM ở chân màn: bảng so sánh dài, giá không được nằm dưới đáy phải cuộn mới thấy.
            // Bố cục theo bề rộng THẬT (không theo idiom): các gói nằm cạnh nhau khi vừa (iPad, iPhone với 1–2
            // gói), không vừa (iPhone hẹp với 3 gói) thì xếp dọc thành hàng đủ rộng cho giá dài.
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 8) {
                    ForEach(entitlements.products) { planRow($0) }
                }
                VStack(spacing: 8) {
                    ForEach(entitlements.products) { planRow($0) }
                }
            }
        }
    }

    /// Chân màn GHIM (cỡ chữ thường): `footerContent` + nền + đường kẻ trên.
    private var footer: some View {
        footerContent
            .padding(.horizontal, 20).padding(.top, 10).padding(.bottom, 16)
            .background(DSColor.pageBackground)
            .overlay(alignment: .top) { Rectangle().fill(DSColor.hairlineOnCard).frame(height: 0.5) }
    }

    /// Chọn gói + CTA + điều khoản + link — ghim ở chân hay nằm cuối vùng cuộn tuỳ `PaywallLayout.pinsFooter`.
    private var footerContent: some View {
        VStack(spacing: 10) {
            planSection
            PrimaryCapsuleButton(title: selectedProduct.map {
                                     PaywallCopy.cta(for: $0, eligibleForTrial: entitlements.isEligibleForTrial)
                                 } ?? PaywallCopy.ctaWithoutProduct,
                                 systemImage: "checkmark") {
                // `subscribe` (không phải `purchase`): gói chưa tải được thì bấm = tải lại, vẫn lỗi
                // thì alert. KHÔNG khoá nút theo `loadState` — khoá như vậy chính là bug "bấm
                // mua không phản ứng gì" của app nguồn (TestFlight). `subscribe` cũng từ chối id không có
                // trong danh sách đã tải, nên chuỗi rỗng khi chưa chọn được gói không bao giờ bị tính tiền.
                Task {
                    await entitlements.subscribe(selectedID ?? "")
                    if entitlements.isPro { dismiss() }
                }
            }
            .disabled(entitlements.isPurchasing || entitlements.isPending)
            .opacity(!entitlements.isPurchasing && !entitlements.isPending ? 1 : 0.5)
            .overlay { if entitlements.isPurchasing { ProgressView() } }

            if let selectedProduct {
                Text(PaywallCopy.terms(for: selectedProduct, eligibleForTrial: entitlements.isEligibleForTrial))
                    .font(.caption2).foregroundColor(DSColor.textTertiary)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if content.termsURL != nil || content.privacyURL != nil {
                HStack(spacing: 16) {
                    if let terms = content.termsURL { Link("Terms", destination: terms) }
                    if let privacy = content.privacyURL { Link("Privacy Policy", destination: privacy) }
                }
                .font(.caption2).foregroundColor(DSColor.textTertiary)
            }
        }
    }

    private var header: some View {
        HStack {
            GlassIconButton(systemImage: "xmark") { dismiss() }
                .disabled(entitlements.isPurchasing)
            Spacer()
            Button {
                guard !entitlements.isRestoring else { return }
                Task {
                    let outcome = await entitlements.restore()
                    // Đã Pro thì đóng luôn paywall — đứng trước nút mua khi đã trả tiền là bug.
                    if outcome == .restored { dismiss() } else { restoreAlert = Self.restoreAlert(for: outcome) }
                }
            } label: {
                // Chữ giữ chỗ (ẩn) khi đang chạy để nút không đổi bề rộng.
                Text("Restore")
                    .opacity(entitlements.isRestoring ? 0 : 1)
                    .overlay { if entitlements.isRestoring { ProgressView() } }
            }
            .foregroundColor(DSColor.textSecondary)
            .disabled(entitlements.isPurchasing || entitlements.isRestoring)
        }
        .padding(.horizontal, 16).padding(.top, 8)
    }

    private func planRow(_ p: ProProduct) -> some View {
        Button { selectedID = p.id } label: {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(PaywallCopy.planTitle(p.kind))
                        .font(.headline).foregroundColor(DSColor.textPrimary)
                        // Không `lineLimit(1)`: ở cỡ chữ trợ năng tên gói phải xuống dòng thay vì bị cắt "…".
                        .fixedSize(horizontal: false, vertical: true)
                    Text(PaywallCopy.planPrice(p))
                        .font(.subheadline).foregroundColor(DSColor.textSecondary)
                        .lineLimit(1).minimumScaleFactor(0.7)
                }
                Spacer(minLength: 4)
                Image(systemName: selectedID == p.id ? "largecircle.fill.circle" : "circle")
                    .foregroundColor(selectedID == p.id ? DSColor.accent : DSColor.textTertiary)
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
            .frame(maxWidth: .infinity)
            .background(DSColor.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: DSRadius.card, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: DSRadius.card, style: .continuous)
                    .stroke(selectedID == p.id ? DSColor.accent : .clear, lineWidth: 1.5)
            )
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selectedID == p.id ? .isSelected : [])
    }

    // MARK: - Bảng so sánh

    private static let freeColumn: CGFloat = 78
    private static let proColumn: CGFloat = 92

    private var comparisonTable: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                Color.clear.frame(maxWidth: .infinity)
                Text("Free").font(.footnote.weight(.semibold)).foregroundColor(DSColor.textSecondary)
                    .frame(width: Self.freeColumn)
                Text("Pro").font(.footnote.weight(.bold)).foregroundColor(DSColor.accent)
                    .frame(width: Self.proColumn).frame(maxHeight: .infinity)
                    .padding(.vertical, 10)
                    .background(DSColor.accent.opacity(0.14))
            }
            .fixedSize(horizontal: false, vertical: true)
            // Chỉ số làm id (không dùng title): app có thể có hai dòng cùng tên ở hai nhóm khác nhau.
            ForEach(Array(content.sections.enumerated()), id: \.offset) { _, section in
                if let title = section.title, !title.isEmpty {
                    comparisonRow(title: title, isHeader: true, free: nil, pro: nil)
                }
                ForEach(Array(section.rows.enumerated()), id: \.offset) { _, row in
                    comparisonRow(title: row.title, isHeader: false, free: row.free, pro: row.pro)
                }
            }
        }
        .background(DSColor.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: DSRadius.card, style: .continuous))
    }

    /// Một dòng của bảng. Cột Pro tô nền suốt chiều cao (`maxHeight: .infinity` + `fixedSize` dọc ở HStack) để
    /// thành MỘT dải liền từ đầu tới cuối bảng.
    private func comparisonRow(title: String, isHeader: Bool, free: PaywallContent.Cell?,
                               pro: PaywallContent.Cell?) -> some View {
        HStack(spacing: 0) {
            Text(title)
                .font(isHeader ? .caption.weight(.semibold) : .subheadline)
                .foregroundColor(isHeader ? DSColor.textTertiary : DSColor.textPrimary)
                .textCase(isHeader ? .uppercase : nil)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.leading, 14).padding(.trailing, 6)
                .padding(.top, isHeader ? 14 : 10).padding(.bottom, isHeader ? 6 : 10)
            comparisonCell(free, isPro: false).frame(width: Self.freeColumn)
            comparisonCell(pro, isPro: true)
                .frame(width: Self.proColumn).frame(maxHeight: .infinity)
                .background(DSColor.accent.opacity(0.14))
        }
        .fixedSize(horizontal: false, vertical: true)
        .overlay(alignment: .top) {
            if !isHeader { Rectangle().fill(DSColor.hairlineOnCard).frame(height: 0.5) }
        }
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private func comparisonCell(_ cell: PaywallContent.Cell?, isPro: Bool) -> some View {
        switch cell {
        case nil:
            Color.clear
        case .yes?:
            Image(systemName: "checkmark").font(.footnote.weight(.bold))
                .foregroundColor(isPro ? DSColor.accent : DSColor.textSecondary)
                .accessibilityLabel(String(localized: "Included"))
        case .no?:
            Image(systemName: "minus").font(.footnote).foregroundColor(DSColor.textTertiary)
                .accessibilityLabel(String(localized: "Not included"))
        case .text(let t)?:
            // Đã localize tại nguồn (app, `PaywallContent`).
            Text(t).font(.footnote.weight(isPro ? .semibold : .regular))
                .foregroundColor(isPro ? DSColor.textPrimary : DSColor.textSecondary)
                .multilineTextAlignment(.center).minimumScaleFactor(0.8)
                .padding(.horizontal, 4)
        }
    }
}

// Canvas `#Preview` build cho Simulator ⇒ `&& targetEnvironment(simulator)` không mất gì, và mã preview không vào
// build Debug cho device (`tools/release/lint_preview_code.py`).
#if DEBUG && targetEnvironment(simulator)
/// Store giả CHỈ cho `#Preview` (build Debug): ba gói mẫu, chưa mua, còn đủ điều kiện dùng thử. Không chạm StoreKit.
/// Không phải fake của test (`CoreTests/Purchases/FakeStoreClient`) — test không được phụ thuộc file này.
@MainActor
private struct PaywallPreviewStore: StoreClient {
    var stub: [ProProduct]
    func products() async throws -> [ProProduct] {
        guard !stub.isEmpty else { throw StoreError.productsUnavailable }
        return stub
    }
    func currentEntitlement() async -> Bool { false }
    func currentEntitlementKind() async -> ProProduct.Kind? { nil }
    func isEligibleForIntroOffer() async -> Bool { true }
    func purchase(_ productID: String) async throws -> PurchaseOutcome { .cancelled }
    func sync() async throws {}
    func transactionUpdates() -> AsyncStream<Void> { AsyncStream { _ in } }
    func storeEnvironment() async -> String? { nil }
}

@MainActor
private func paywallPreview(_ products: [ProProduct]) -> some View {
    let defaults = UserDefaults(suiteName: "paywall.preview") ?? .standard
    // Chuỗi mẫu của #Preview: `String` thô (không `String(localized:)`) ⇒ không vào String Catalog.
    let content = PaywallContent(
        defaultHeadline: "Upgrade to Pro",
        sections: [.init(title: nil, rows: [
            .init(title: "Sample limit", free: .text("3"), pro: .text("Unlimited")),
            .init(title: "Sample feature", free: .no, pro: .yes),
        ])],
        termsURL: URL(string: "https://example.com/terms/"),
        privacyURL: URL(string: "https://example.com/privacy/"))
    return PaywallView(entitlements: Entitlements(client: PaywallPreviewStore(stub: products),
                                                  defaults: defaults, internalDeviceFlag: PreviewCounterStore()),
                       content: content)
}

private final class PreviewCounterStore: SecureCounterStore {
    func read() throws -> Int { 0 }
    func write(_ value: Int) throws {}
}

#Preview("Three plans") {
    paywallPreview([
        ProProduct(id: "preview.monthly", displayPrice: "$2.99", kind: .month, freeTrialDays: 7),
        ProProduct(id: "preview.yearly", displayPrice: "$19.99", kind: .year, freeTrialDays: 7),
        ProProduct(id: "preview.lifetime", displayPrice: "$49.99", kind: .lifetime),
    ])
}

#Preview("Lifetime only") {
    paywallPreview([ProProduct(id: "preview.lifetime", displayPrice: "$49.99", kind: .lifetime)])
}

#Preview("Load failed") {
    paywallPreview([])
}
#endif
