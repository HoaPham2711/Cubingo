import SwiftUI

/// Tour onboarding dạng pager: nút Skip, chấm trang, nút Next/Start. App cấp nội dung từng trang qua `page`
/// (thường dựng từ `OnboardingInfoPage`/`OnboardingPageScaffold`) và giữ state riêng của trang (lựa chọn…) ở phía app.
///
/// Lần đầu: root rẽ nhánh bằng cờ `WhatsNewHost.hasSeenOnboardingKey` — app đặt cờ true trong `onFinish` (khi bấm
/// CTA/Skip), không suy từ dữ liệu đã có. Xem lại: `appTourSheet` với `flow.context == .replay`.
///
/// KHÔNG dựng overlay xin quyền giả lập: hộp thoại hệ thống thật hiện khi app thật sự cần quyền (lúc mở màn dùng
/// camera/vị trí…), không phải ngay sau onboarding.
struct OnboardingView<Page: Hashable, PageView: View>: View {
    private let flow: OnboardingFlow<Page>
    private let onFinish: () -> Void
    private let pageView: (Page) -> PageView

    /// `nil` ⇔ luồng rỗng (`flow.isEmpty`).
    @State private var page: Page?
    /// Chặn gọi `onFinish` lần hai cho tour rỗng (`onAppear` có thể chạy lại).
    @State private var finishedEmpty = false

    /// `initialPage` không thuộc luồng (VD trang bị bỏ ở replay) ⇒ bắt đầu từ trang đầu. Luồng rỗng (mọi trang bị bỏ
    /// ở replay) ⇒ không vẽ trang nào, gọi `onFinish()` một lần khi xuất hiện, không bắn `onboarding_done`/screen.
    init(flow: OnboardingFlow<Page>, initialPage: Page? = nil, onFinish: @escaping () -> Void,
         @ViewBuilder page: @escaping (Page) -> PageView) {
        self.flow = flow
        self.onFinish = onFinish
        self.pageView = page
        _page = State(initialValue: flow.startPage(preferred: initialPage))
    }

    var body: some View {
        ZStack {
            // Nền theo token, không màu riêng của app: gradient accent nhạt từ đỉnh xuống đen.
            RadialGradient(
                colors: [DSColor.accent.opacity(0.12), .black],
                center: .top,
                startRadius: 0,
                endRadius: 420
            )
            .ignoresSafeArea()

            if let current = page {
                pager(current)
            }
        }
        .onAppear {
            guard flow.isEmpty, !finishedEmpty else { return }
            finishedEmpty = true
            onFinish()
        }
    }

    private func pager(_ current: Page) -> some View {
        VStack(spacing: 0) {
            skipBar(current)
            TabView(selection: $page) {
                ForEach(flow.pages, id: \.self) { p in
                    pageView(p).tag(Optional(p))
                }
            }
            // Chấm trang tự vẽ (`pageDots`) chứ không dùng index của `.page`: index hệ thống nổi ĐÈ lên đáy nội
            // dung — từng che dòng công khai analytics ở trang đầu.
            .tabViewStyle(.page(indexDisplayMode: .never))
            // `screen_view` từng trang — chỉ lần đầu (xem lại tour đã có màn `app_tour`).
            .onAppear { trackPage(current) }
            .onChange(of: page) { _, p in if let p { trackPage(p) } }

            pageDots(current)

            PrimaryCapsuleButton(title: flow.isLast(current) ? String(localized: "Start")
                                                             : String(localized: "Next")) {
                if let n = flow.next(after: current) {
                    withAnimation { page = n }
                } else {
                    finish(skipped: false, at: current)
                }
            }
            .padding(.horizontal, 28)
            // iPad: nút không kéo giãn cả màn (iPhone: no-op).
            .readableContentWidth(DSLayout.formWidth)
            .padding(.top, 14)
            .padding(.bottom, 20)
        }
    }

    /// Skip ẩn ở trang cuối — ở đó nút chính đã là Start.
    private func skipBar(_ current: Page) -> some View {
        HStack {
            Spacer()
            Button("Skip") { finish(skipped: true, at: current) }
                .scaledFont(size: 15, weight: .medium)
                .foregroundColor(DSColor.textSecondary)
                .opacity(flow.isLast(current) ? 0 : 1)
                .disabled(flow.isLast(current))
        }
        .padding(.horizontal, 20)
        .frame(minHeight: 44)
    }

    private func pageDots(_ current: Page) -> some View {
        HStack(spacing: 8) {
            ForEach(flow.pages, id: \.self) { p in
                Circle()
                    .fill(p == current ? DSColor.accent : DSColor.textTertiary.opacity(0.5))
                    .frame(width: 7, height: 7)
            }
        }
        .padding(.top, 10)
        .accessibilityHidden(true)
    }

    private func trackPage(_ p: Page) {
        guard flow.context == .firstRun else { return }
        ScreenTracker.shared.enter("onboarding_\(flow.pageNumber(p))")
    }

    /// Xem lại tour không bắn `onboarding_done` lần hai — nguồn xem lại đã có `tour_replay`.
    private func finish(skipped: Bool, at current: Page) {
        if flow.context == .firstRun {
            Track.log(.onboardingDone(skippedAtPage: skipped ? flow.pageNumber(current) : 0))
        }
        onFinish()
    }
}

extension View {
    /// Mở lại tour toàn màn — một chỗ cho Settings và Help. `source` đi vào `tour_replay` (VD "settings").
    /// `tour` dựng `OnboardingView` với `OnboardingFlow(context: .replay, …)` và đóng bằng
    /// `isPresented.wrappedValue = false` trong `onFinish`.
    func appTourSheet<Tour: View>(isPresented: Binding<Bool>, source: String,
                                  @ViewBuilder tour: @escaping () -> Tour) -> some View {
        fullScreenCover(isPresented: isPresented) {
            tour()
                // Chế độ giao diện theo theme của app (bản chuẩn: tối — quyết định 11 của plan P2).
                .preferredColorScheme(DSTheme.current.colorScheme)
                .onAppear { Track.log(.tourReplay(source: source)) }
                .trackOverlayScreen("app_tour")
        }
    }
}

#Preview {
    OnboardingView(flow: OnboardingFlow(context: .firstRun, allPages: [1, 2, 3]), onFinish: {}) { n in
        OnboardingPageScaffold {
            Text(verbatim: "Page \(n)")
                .foregroundColor(DSColor.textPrimary)
        }
    }
}
