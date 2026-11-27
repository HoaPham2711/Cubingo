import SwiftUI

/// Đích push của Settings. `feedback` do lõi tự dựng (`FeedbackView`, khi app có `FeedbackTransport`); `whatsNew` và
/// `custom` đi qua closure `destination` của app (danh sách What's New cần presenter/runner của app). Hàng của app
/// đẩy đích bằng `NavigationLink(value: SettingsRoute.custom(...))`.
///
/// App KHÔNG nên tự đẩy `.feedback` khi `feedbackTransport == nil`: khi đó không có form, route rơi xuống
/// `destination` của app (app phải tự vẽ gì đó cho nó).
enum SettingsRoute: Hashable {
    case feedback, whatsNew, custom(AnyHashable)
}

/// Mọi thứ Settings cần từ app, truyền TƯỜNG MINH (không `@EnvironmentObject`: `fullScreenCover` không kế thừa
/// environment). Dựng MỘT lần ở cấp gốc của app.
struct SettingsDependencies {
    let config: AppConfig
    let entitlements: Entitlements
    let updateChecker: UpdateChecker
    let reviewPrompter: ReviewPrompter
    let paywall: PaywallContent
    /// `nil` ⇒ không có form phản hồi, chỉ có "Contact us" (mailto). Mở Mail không xác nhận được là đã gửi, nên form
    /// (báo "Thanks!") chỉ được nối khi app có kênh gửi thật (web API).
    let feedbackTransport: FeedbackTransport?
    /// Dòng chẩn đoán riêng của app đính kèm phản hồi/mailto (ngoài sáu dòng lõi). Gọi lúc người dùng bấm, không gọi
    /// trong `body`.
    let diagnosticsExtras: () -> [DiagnosticsField]
}

/// Phần logic thuần của Settings — hàng/nhóm nào hiện, ánh xạ kết quả, link. Có test (`SettingsModelTests`).
enum SettingsModel {

    /// Mặc định của toggle "Share usage data" — PHẢI khớp `TelemetryConsent.isEnabled` trên máy chưa từng ghi (mô
    /// hình opt-out). Lệch nhau thì UI hiện BẬT trong khi hệ thống đang TẮT (hoặc ngược lại). Một nguồn: tham chiếu
    /// thẳng `TelemetryConsent.defaultValue`; test ghim vẫn giữ.
    static let shareUsageDataDefault = TelemetryConsent.defaultValue

    /// Nhóm Account chỉ khi bật paywall — app miễn phí hoàn toàn không hiện gì về Pro.
    static func showsAccount(config: AppConfig) -> Bool {
        config.features.paywall
    }

    static func showsFeedbackForm(transport: FeedbackTransport?) -> Bool {
        transport != nil
    }

    /// Có App Store id ⇒ có hàng "Rate the app" (và mới có kiểm tra cập nhật).
    static func showsRateRow(config: AppConfig) -> Bool {
        reviewURL(config: config) != nil
    }

    /// Có hộp thư hỗ trợ ⇒ có hàng "Contact us".
    static func showsContactRow(config: AppConfig) -> Bool {
        SupportConfig(config: config).email != nil
    }

    private static func trimmedStoreID(_ config: AppConfig) -> String? {
        let id = config.appStoreID?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return id.isEmpty ? nil : id
    }

    /// Link viết đánh giá trên App Store; `nil` khi app chưa có App Store id.
    static func reviewURL(config: AppConfig) -> URL? {
        guard let id = trimmedStoreID(config) else { return nil }
        return URL(string: "https://apps.apple.com/app/id\(id)?action=write-review")
    }

    /// Version cho hàng "Update to …": chỉ khi app có App Store id VÀ checker báo có bản mới.
    static func updateVersion(config: AppConfig, status: UpdateStatus) -> String? {
        guard trimmedStoreID(config) != nil, case .available(let version, _, _) = status else { return nil }
        return version
    }

    /// Alert sau Khôi phục ở Settings — chỉ chuyển tiếp `RestoreAlert.make` (nguồn duy nhất, paywall dùng chung).
    static func restoreAlert(for outcome: Entitlements.RestoreOutcome) -> RestoreAlert? {
        RestoreAlert.make(outcome)
    }

    /// Chỉ `.failed` là bực mình do app (chặn hỏi đánh giá trong phiên); chưa từng mua là kết quả hợp lệ.
    static func countsAsReviewFriction(_ outcome: Entitlements.RestoreOutcome) -> Bool {
        outcome == .failed
    }

    struct LinkRow: Identifiable, Equatable {
        let id: String
        let title: String
        let url: URL
    }

    /// Hàng link pháp lý/web ở nhóm About. Link nào `nil` (app không có web) ⇒ không có hàng đó.
    static func linkRows(_ links: AppLinks) -> [LinkRow] {
        let all: [(String, String, URL?)] = [
            ("privacy", String(localized: "Privacy policy"), links.privacy),
            ("terms", String(localized: "Terms of use"), links.terms),
            ("site", String(localized: "Website"), links.site),
        ]
        return all.compactMap { id, title, url in url.map { LinkRow(id: id, title: title, url: $0) } }
    }

    static func versionText(config: AppConfig) -> String {
        let v = config.version.isEmpty ? "—" : config.version
        let b = config.build.isEmpty ? "—" : config.build
        return "\(v) (\(b))"
    }
}

/// Màn Settings có khe cắm. Lõi tự giữ các nhóm: Account (ẩn khi paywall tắt), Data (Share usage data), Help (tour,
/// hiện lại tip, phản hồi, Contact us, Rate, ngôn ngữ), About (cập nhật, link, phiên bản). App cắm thêm:
/// - `appSections`: các nhóm riêng của app (đặt giữa Account và Data);
/// - `helpRows`: hàng riêng đầu nhóm Help (VD `NavigationLink(value: SettingsRoute.whatsNew)`, hướng dẫn…);
/// - `internalSection`: mục dev — app tự bọc `#if INTERNAL` (lõi không viết UI nội bộ ở đây);
/// - `destination`: đích của `.whatsNew` và `.custom(...)` (cả `.feedback` khi app không có transport mà vẫn đẩy);
/// - `onReplayTour`: mở lại tour (app trình bày bằng `.appTourSheet`); `replayTourAvailable == false` (VD
///   `OnboardingFlow(context: .replay, …).isEmpty`) ⇒ ẩn hàng.
///
/// Dùng `NavigationPath` để deep-link được về sau. Bố cục: cột đọc `.readableContentWidth` (iPad), không theo idiom.
struct SettingsView<AppSections: View, HelpRows: View, Internal: View, Dest: View>: View {
    private let deps: SettingsDependencies
    @ObservedObject private var entitlements: Entitlements
    @ObservedObject private var updateChecker: UpdateChecker
    private let appSections: () -> AppSections
    private let helpRows: () -> HelpRows
    private let internalSection: () -> Internal
    private let destination: (SettingsRoute) -> Dest
    private let onReplayTour: () -> Void
    private let replayTourAvailable: Bool

    @StateObject private var accountState = SettingsAccountState()
    /// Mặc định PHẢI khớp `TelemetryConsent` — xem `SettingsModel.shareUsageDataDefault`.
    @AppStorage(TelemetryConsent.defaultsKey) private var shareUsageData = SettingsModel.shareUsageDataDefault
    @State private var language = AppLanguage.load()
    @State private var showTipsResetNotice = false
    @State private var showLanguageRestartAlert = false
    @State private var path = NavigationPath()
    /// Loại phản hồi của lần đẩy `.feedback` gần nhất (hàng "Report a bug" / "Request a feature").
    @State private var feedbackType: FeedbackType = .bug
    /// Chẩn đoán chụp lúc bấm mở form — `DiagnosticsSnapshot.current` gọi syscall dung lượng đĩa, không để nó chạy
    /// lại mỗi lần `body` tính lại.
    @State private var feedbackDiagnostics: DiagnosticsSnapshot?
    /// Máy không mở được Mail/App Store/link ⇒ đã copy vào clipboard; alert này là xác nhận duy nhất cho hành động đó,
    /// đừng để nút bấm vào không làm gì. Nội dung đổi theo hành động vừa fallback.
    @State private var copiedFallbackMessage: String?

    init(deps: SettingsDependencies,
         @ViewBuilder appSections: @escaping () -> AppSections,
         @ViewBuilder helpRows: @escaping () -> HelpRows,
         @ViewBuilder internalSection: @escaping () -> Internal,
         @ViewBuilder destination: @escaping (SettingsRoute) -> Dest,
         onReplayTour: @escaping () -> Void,
         replayTourAvailable: Bool = true) {
        self.deps = deps
        self.entitlements = deps.entitlements
        self.updateChecker = deps.updateChecker
        self.appSections = appSections
        self.helpRows = helpRows
        self.internalSection = internalSection
        self.destination = destination
        self.onReplayTour = onReplayTour
        self.replayTourAvailable = replayTourAvailable
    }

    private var config: AppConfig { deps.config }

    private func diagnosticsNow() -> DiagnosticsSnapshot {
        DiagnosticsSnapshot.current(extras: deps.diagnosticsExtras())
    }

    var body: some View {
        NavigationStack(path: $path) {
            ZStack {
                DSColor.pageBackground.ignoresSafeArea()
                List {
                    // iPad: tiêu đề lớn trong cột (cùng `readableColumnNavigationTitle` bên dưới); iPhone: không vẽ gì.
                    ReadableColumnTitle(Text("Settings"))
                    if SettingsModel.showsAccount(config: config) {
                        SettingsAccountSection(entitlements: entitlements, state: accountState,
                                               reviewPrompter: deps.reviewPrompter)
                    }
                    appSections()
                    duLieuSection
                    troGiupSection
                    gioiThieuSection
                    internalSection()
                }
                .scrollContentBackground(.hidden)
                .readableContentWidth()
            }
            .readableColumnNavigationTitle(Text("Settings"))
            .trackScreen("settings")
            .navigationDestination(for: SettingsRoute.self) { route in
                routeView(route)
            }
            .onChange(of: shareUsageData) { _, bat in
                // Phòng thủ hai lớp nằm trong `consentDidChange`: SDK ngừng thu VÀ facade thôi chuyển tiếp.
                TelemetryBootstrap.consentDidChange(bat)
            }
            .settingsAccountPresentations(state: accountState, entitlements: entitlements,
                                          paywall: deps.paywall, reviewPrompter: deps.reviewPrompter)
            .alert("Restart required", isPresented: $showLanguageRestartAlert) {
                Button("OK", role: .cancel) {}
            } message: {
                Text("Close and reopen the app to apply the new language.")
            }
            .alert("Tips reset", isPresented: $showTipsResetNotice) {
                Button("OK", role: .cancel) {}
            } message: {
                Text("Tips will appear again the next time you open the app.")
            }
            .alert("Copied", isPresented: Binding(get: { copiedFallbackMessage != nil },
                                                  set: { if !$0 { copiedFallbackMessage = nil } })) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(verbatim: copiedFallbackMessage ?? "")
            }
        }
    }

    @ViewBuilder
    private func routeView(_ route: SettingsRoute) -> some View {
        if route == .feedback, let transport = deps.feedbackTransport {
            FeedbackView(type: feedbackType, transport: transport,
                         diagnostics: feedbackDiagnostics ?? diagnosticsNow(),
                         support: SupportConfig(config: config),
                         onSent: deps.reviewPrompter.noteFeedbackSent)
                .trackOverlayScreen("feedback")
        } else {
            destination(route)
        }
    }

    // MARK: - Data

    private var duLieuSection: some View {
        Section {
            Toggle(isOn: $shareUsageData) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Share usage data").foregroundColor(DSColor.textPrimary)
                    Text("Anonymous usage statistics that help improve the app. You can turn this off at any time.")
                        .font(.footnote)
                        .foregroundColor(DSColor.textSecondary)
                }
            }
            .tint(DSColor.accent)
        } header: {
            Text("Data")
        }
    }

    // MARK: - Help

    private var troGiupSection: some View {
        Section {
            helpRows()
            if replayTourAvailable {
                Button("Show app tour") { onReplayTour() }
                    .foregroundColor(DSColor.textPrimary)
            }
            // TipKit chỉ xoá được datastore TRƯỚC khi configure ⇒ có hiệu lực ở lần mở app sau (alert nói rõ).
            Button("Show tips again") {
                AppTips.requestReset()
                showTipsResetNotice = true
            }
            .foregroundColor(DSColor.textPrimary)
            if SettingsModel.showsFeedbackForm(transport: deps.feedbackTransport) {
                pushRow("Report a bug") { openFeedback(.bug) }
                pushRow("Request a feature") { openFeedback(.feature) }
            }
            if SettingsModel.showsContactRow(config: config) {
                Button("Contact us") {
                    // Logic mở-mail-rồi-fallback dùng chung với `FeedbackView` qua `SupportContact`/`SupportMailOpener`.
                    SupportContact.contactUs(support: SupportConfig(config: config), diagnostics: diagnosticsNow()) {
                        copiedFallbackMessage = SupportContact.copiedAddressMessage
                    }
                }
                .foregroundColor(DSColor.textPrimary)
            }
            if let url = SettingsModel.reviewURL(config: config) {
                Button("Rate the app") {
                    // Qua `SupportMailOpener` (không gọi thẳng `UIApplication.open`): không mở được (Simulator, máy đã
                    // gỡ App Store) thì copy link + báo, không chết im lặng.
                    SupportMailOpener.open(url, copyingOnFailure: url.absoluteString) {
                        copiedFallbackMessage = String(localized:
                            "Couldn't open the App Store. We copied the review link to your clipboard instead.")
                    }
                }
                .foregroundColor(DSColor.textPrimary)
            }
            // Ẩn khi chưa có bản dịch nào ngoài tiếng Anh — xem `AppLanguage.isPickerVisible(localizations:)`.
            if AppLanguage.isPickerVisible() {
                Picker("Language", selection: $language) {
                    ForEach(AppLanguage.available()) { lang in
                        Text(verbatim: lang.title).tag(lang)
                    }
                }
                .foregroundColor(DSColor.textPrimary)
                .onChange(of: language) { _, newValue in
                    // Có hiệu lực từ lần khởi động SAU ⇒ phải báo khởi động lại.
                    newValue.apply()
                    showLanguageRestartAlert = true
                }
            }
        } header: {
            Text("Help")
        }
    }

    private func openFeedback(_ type: FeedbackType) {
        feedbackType = type
        feedbackDiagnostics = diagnosticsNow()
        path.append(SettingsRoute.feedback)
    }

    private func pushRow(_ title: LocalizedStringKey, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(title).foregroundColor(DSColor.textPrimary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundColor(DSColor.textTertiary)
            }
        }
    }

    // MARK: - About

    private var gioiThieuSection: some View {
        Section {
            // Không bị × của banner Home ảnh hưởng — hiện mọi lúc Store có bản mới hơn. KHÔNG log `update_prompt`:
            // sự kiện đó chỉ đến từ banner Home (một bề mặt ⇒ "shown"/"open_store" không cộng dồn hai nơi).
            if let version = SettingsModel.updateVersion(config: config, status: updateChecker.status),
               case .available(_, let url, _) = updateChecker.status {
                Button("Update to \(version)") {
                    SupportMailOpener.open(url, copyingOnFailure: url.absoluteString) {
                        copiedFallbackMessage = String(localized:
                            "Couldn't open the App Store. We copied the link to your clipboard instead.")
                    }
                }
                .foregroundColor(DSColor.accent)
            }
            ForEach(SettingsModel.linkRows(AppLinks(config: config))) { row in
                Button {
                    SupportMailOpener.open(row.url, copyingOnFailure: row.url.absoluteString) {
                        copiedFallbackMessage = String(localized:
                            "Couldn't open the link. We copied it to your clipboard instead.")
                    }
                } label: {
                    HStack {
                        Text(verbatim: row.title).foregroundColor(DSColor.textPrimary)
                        Spacer()
                        Image(systemName: "arrow.up.right")
                            .font(.caption.weight(.semibold))
                            .foregroundColor(DSColor.textTertiary)
                    }
                }
            }
            HStack {
                Text("Version").foregroundColor(DSColor.textPrimary)
                Spacer()
                Text(verbatim: SettingsModel.versionText(config: config)).foregroundColor(DSColor.textSecondary)
            }
        } header: {
            Text("About")
        }
    }
}
