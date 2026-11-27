import Foundation

/// Logic thuần của tour onboarding — tách khỏi View để test thứ tự trang và số liệu analytics. App khai `Page`
/// (thường là `enum ...: CaseIterable`) và truyền danh sách trang theo thứ tự.
struct OnboardingFlow<Page: Hashable> {
    /// `firstRun`: mở app lần đầu. `replay`: mở lại từ Settings/Help — bỏ các trang trong `skippedOnReplay`
    /// (VD trang Welcome: logo + dòng công khai analytics user đã thấy rồi).
    enum Context { case firstRun, replay }

    let context: Context
    let allPages: [Page]
    let skippedOnReplay: Set<Page>

    init(context: Context, allPages: [Page], skippedOnReplay: Set<Page> = []) {
        self.context = context
        self.allPages = allPages
        self.skippedOnReplay = skippedOnReplay
    }

    var pages: [Page] {
        context == .firstRun ? allPages : allPages.filter { !skippedOnReplay.contains($0) }
    }

    /// Tour không có trang nào (VD app chỉ có Welcome và bỏ nó khi xem lại) ⇒ View kết thúc ngay, không vẽ gì.
    var isEmpty: Bool { pages.isEmpty }

    /// Trang mở đầu: `preferred` nếu thuộc luồng (trang bị bỏ ở replay thì không), không thì trang đầu; `nil` khi
    /// luồng rỗng. KHÔNG rơi về `allPages` — trang đã đánh dấu bỏ không được hiện lại.
    func startPage(preferred: Page? = nil) -> Page? {
        let p = pages
        return preferred.flatMap { p.contains($0) ? $0 : nil } ?? p.first
    }

    func next(after page: Page) -> Page? {
        let p = pages
        guard let i = p.firstIndex(of: page), i + 1 < p.count else { return nil }
        return p[i + 1]
    }

    func isLast(_ page: Page) -> Bool { page == pages.last }

    /// 1-based — giá trị `skipped_at_page` của `onboarding_done`. Trang KHÔNG thuộc luồng (bị bỏ ở replay, hoặc luồng
    /// rỗng) trả 1 — không trap; View chỉ gọi với trang đang hiển thị nên ca này không xảy ra trong luồng thật.
    func pageNumber(_ page: Page) -> Int { (pages.firstIndex(of: page) ?? 0) + 1 }
}
