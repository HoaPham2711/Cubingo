import SwiftUI

/// Điểm nối What's New của app. Lõi giữ luật (khi nào hiện, ghi gì, thẻ nào); app cấp ba thứ riêng: catalog
/// (`[WhatsNewCard]`), đích nút thẻ (`WhatsNewResolver` + `WhatsNewRunner`) và dấu vết "đã dùng" trên máy (`UsageProbe`).
///
/// App còn phải tự làm, theo đúng thứ tự (lý do ở comment của từng hàm):
/// 1. Dựng MỘT lần ở cấp App: `let (presenter, ledger) = WhatsNewHost.make(...)`.
/// 2. Ngoài host unit test: `Track.installUsageObserver(ledger)` TRƯỚC khi khởi động telemetry — để không lỡ event nào
///    của lần mở (event tự bắn ngay khi SDK configure).
/// 3. Onboarding xong: `presenter.onboardingFinished()` TRƯỚC khi bật cờ `hasSeenOnboardingKey`.
/// 4. Link ngoài tới: `if !presenter.routeIncomingLink({ mở link }) { mở link }`.
/// 5. View gốc: `.whatsNewSheet(presenter:resolve:run:)`; gọi `presenter.evaluate(resolve:canPresent:)` khi app active
///    và rảnh, `canPresent` = `presenter.presentGate(...).allowsPresent` (đọc lại giá trị thật mỗi lần), và tính
///    `presenter.presentation != nil` vào cổng "đang có cover" của app.
enum WhatsNewHost {
    /// Cờ "đã xem onboarding" trong `defaults` — vỏ app ghi khi onboarding xong (cùng key với `@AppStorage` của nó).
    static let hasSeenOnboardingKey = "hasSeenOnboarding"

    /// Dựng presenter + ledger dùng CHUNG một danh sách thẻ và một `defaults` (ledger ghi, presenter đọc + seed).
    /// KHÔNG tự gắn ledger vào `Track` (thứ tự gắn là việc của App — bước 2 ở trên).
    ///
    /// Presenter tắt (host unit test, route `-uiPreview` không thuộc `whatsNew*`, bản cài hỏng) ⇒ KHÔNG đọc cờ
    /// onboarding; ledger/state chỉ được giữ tham chiếu, presenter tắt không bao giờ đọc/ghi chúng. Cờ onboarding đọc
    /// MỘT lần ở đây: gọi `make` SAU khi route `-uiPreview` (nếu có) đã kịp ghi trạng thái của nó.
    /// `installedVersion` mặc định là `CFBundleShortVersionString` của app.
    @MainActor
    static func make(cards: [WhatsNewCard], probe: UsageProbe, isUnitTestHost: Bool, previewRoute: String?,
                     defaults: UserDefaults = .standard,
                     installedVersion: String? = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String)
        -> (presenter: WhatsNewPresenter, ledger: FeatureUsageLedger) {
        let ledger = FeatureUsageLedger(cards: cards, defaults: defaults)
        let installed = installedVersion.flatMap(AppVersion.init)
        let enabled = installed != nil
            && WhatsNewPresenter.isEnabled(isUnitTestHost: isUnitTestHost, previewRoute: previewRoute)
        let presenter = WhatsNewPresenter(
            cards: cards,
            current: installed ?? AppVersion("0")!,
            hasSeenOnboarding: enabled && defaults.bool(forKey: hasSeenOnboardingKey),
            ledger: ledger,
            state: WhatsNewState(defaults: defaults),
            probe: probe,
            isEnabled: enabled)
        return (presenter, ledger)
    }
}

private struct WhatsNewSheetHost: ViewModifier {
    @ObservedObject var presenter: WhatsNewPresenter
    let resolve: WhatsNewResolver
    let run: WhatsNewRunner

    func body(content: Content) -> some View {
        // MỌI lối đóng (Continue, nút thẻ, kéo xuống, link ngoài tới) đều đặt `presentation = nil` ⇒ SwiftUI gọi
        // `onDismiss` này — chỗ DUY NHẤT gọi `sheetDidDismiss` và chạy nút thẻ (sau khi sheet đã trượt xuống hẳn).
        content.sheet(item: $presenter.presentation, onDismiss: dismissed) { shown in
            WhatsNewSheet(presentation: shown, cards: presenter.cards, current: presenter.current, resolve: resolve,
                          onAppear: { presenter.sheetDidAppear() },
                          onAction: { card, action, surface in
                              presenter.chooseAction(card, action, surface: surface, in: shown)
                          },
                          onContinue: { presenter.presentation = nil })
        }
    }

    private func dismissed() {
        if let chosen = presenter.sheetDidDismiss() { run(chosen) }
    }
}

extension View {
    /// Gắn ở view GỐC: present sheet What's New theo `presenter.presentation`, giao nút thẻ đã bấm cho `run` khi sheet
    /// đóng hẳn (link ngoài tới lúc sheet mở thắng nút thẻ). Presenter truyền tường minh, không qua environment.
    func whatsNewSheet(presenter: WhatsNewPresenter, resolve: @escaping WhatsNewResolver,
                       run: @escaping WhatsNewRunner) -> some View {
        modifier(WhatsNewSheetHost(presenter: presenter, resolve: resolve, run: run))
    }
}
