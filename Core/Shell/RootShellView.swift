import SwiftUI

/// Khung điều hướng gốc. Hai "khung" — tab bar (compact: iPhone, iPad Split View hẹp) và sidebar kiểu Files/Mail
/// (regular: iPad, cửa sổ đủ rộng) — nhưng MỘT nguồn cho mọi thứ bên trong: mục cấp cao = `Tab.allCases`, nội dung
/// một tab = `content(tab)` (cùng một hàm cho cả hai khung), mục chỉ sidebar có = `sidebarRows`/`detailExtra`.
/// Đổi qua lại giữ đúng chỗ nhờ `nav.sidebarSelection`. Chọn khung theo `horizontalSizeClass`, KHÔNG theo
/// `userInterfaceIdiom` (iPad Split View hẹp là compact).
///
/// Khung không cấp `NavigationStack`: mỗi màn tab tự dựng stack riêng (giữ `path` của nó), `detailExtra` cũng vậy.
/// Cover/sheet của app gắn ở NGOÀI view này; đối tượng truyền xuống cover bằng `init` tường minh — `fullScreenCover`
/// không kế thừa environment, quên gắn `@EnvironmentObject` là crash.
struct RootShellView<Tab: ShellTab, Extra: Hashable, TabContent: View, Rows: View, Detail: View>: View {
    @ObservedObject private var nav: ShellNavigationModel<Tab, Extra>
    private let appName: String
    private let content: (Tab) -> TabContent
    private let sidebarRows: (Tab) -> Rows
    private let detailExtra: (Extra) -> Detail

    @Environment(\.horizontalSizeClass) private var sizeClass

    /// - Parameters:
    ///   - appName: tiêu đề sidebar (`AppConfig.displayName`) — tên riêng, hiển thị nguyên văn, không dịch.
    ///   - content: nội dung một tab — DÙNG CHUNG cho tab bar và cột chi tiết của sidebar.
    ///   - sidebarRows: các hàng CHỈ sidebar có, chèn ngay sau hàng của mỗi tab (trả rỗng nếu tab không có). Mỗi hàng
    ///     gắn `.tag(SidebarItem<Tab, Extra>.extra(x, parent: tab))` để `List(selection:)` chọn được. Muốn nhóm gập
    ///     được thì dùng `Section(isExpanded:)` + hàng riêng: label của `DisclosureGroup` KHÔNG nhận selection trong
    ///     sidebar (không tô sáng).
    ///   - detailExtra: cột chi tiết khi đang chọn một mục `.extra` (view được dựng lại theo từng giá trị — `.id`).
    init(nav: ShellNavigationModel<Tab, Extra>, appName: String,
         @ViewBuilder content: @escaping (Tab) -> TabContent,
         @ViewBuilder sidebarRows: @escaping (Tab) -> Rows,
         @ViewBuilder detailExtra: @escaping (Extra) -> Detail) {
        self.nav = nav
        self.appName = appName
        self.content = content
        self.sidebarRows = sidebarRows
        self.detailExtra = detailExtra
    }

    var body: some View {
        if sizeClass == .regular {
            sidebarLayout
        } else {
            tabs
        }
    }

    // MARK: - Compact: tab bar

    @ViewBuilder private var tabs: some View {
        if #available(iOS 18.0, *) {
            TabView(selection: nav.tabBinding) {
                ForEach(Tab.allCases, id: \.self) { tab in
                    SwiftUI.Tab(tab.title, systemImage: tab.systemImage, value: tab) { content(tab) }
                }
            }
        } else {
            TabView(selection: nav.tabBinding) {
                ForEach(Tab.allCases, id: \.self) { tab in
                    content(tab)
                        .tabItem { Label(tab.title, systemImage: tab.systemImage) }
                        .tag(tab)
                }
            }
        }
    }

    // MARK: - Regular: sidebar + cột chi tiết

    private var sidebarLayout: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            detail
        }
        .environment(\.selectSidebarItem, { [nav] value in
            if let item = SidebarItem<Tab, Extra>.erased(value) { nav.selectSidebar(item) }
        })
    }

    private var sidebar: some View {
        List(selection: nav.sidebarBinding) {
            ForEach(Tab.allCases, id: \.self) { tab in
                Label(tab.title, systemImage: tab.systemImage)
                    .tag(SidebarItem<Tab, Extra>.tab(tab))
                sidebarRows(tab)
            }
        }
        .listStyle(.sidebar)
        .navigationTitle(Text(verbatim: appName))
    }

    @ViewBuilder private var detail: some View {
        switch nav.sidebarSelection {
        case .tab(let tab):
            content(tab)
        case .extra(let extra, _):
            detailExtra(extra).id(extra)
        }
    }
}
