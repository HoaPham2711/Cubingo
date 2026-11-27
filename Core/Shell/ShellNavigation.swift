import SwiftUI

/// Mục điều hướng cấp cao của app — MỘT nguồn cho CẢ tab bar (compact) lẫn sidebar iPad (regular): app khai một
/// `enum` tuân protocol này, thêm case là cả hai bố cục cùng có (nội dung dựng ở closure `content` của
/// `RootShellView`, `switch` đầy đủ ở phía app ⇒ quên là build lỗi).
///
/// Luồng modal (camera, trình soạn toàn màn…) KHÔNG phải tab — mở bằng `fullScreenCover`. Lý do: SwiftUI giữ view
/// của tab sống sau lần hiển thị đầu, tài nguyên gắn vòng đời màn (camera, phiên cảm biến) sẽ chạy ngầm. Cũng không
/// dựng "tab giả" mở cover: chạm vào thì tab bar nháy highlight rồi bật về tab cũ trong lúc cover đang trượt lên.
protocol ShellTab: Hashable, CaseIterable where AllCases: RandomAccessCollection {
    /// Đã localize — đi qua biến `String` nên app PHẢI bọc `String(localized:)` tại chỗ viết literal.
    var title: String { get }
    /// Bản outline — tab bar tự tô `.fill`, sidebar giữ outline (đúng chuẩn hệ thống).
    var systemImage: String { get }
}

/// Mục của sidebar iPad: một tab cấp cao, hoặc mục CHỈ có ở sidebar (VD "xem tất cả", từng thư mục trong cây — ở tab
/// bar các thứ này nằm sâu hơn trong stack của tab cha). `parent` = tab chứa mục đó khi co về tab bar.
enum SidebarItem<Tab: ShellTab, Extra: Hashable>: Hashable {
    case tab(Tab)
    case extra(Extra, parent: Tab)

    /// Ép giá trị `AnyHashable` (đường `selectSidebarItem` của environment) về đúng `SidebarItem<Tab, Extra>`;
    /// khác kiểu ⇒ `nil` (bị bỏ qua, không crash).
    static func erased(_ value: AnyHashable) -> SidebarItem<Tab, Extra>? {
        value.base as? SidebarItem<Tab, Extra>
    }

    /// Tab tương ứng — để khi co về compact (tab bar) vẫn đứng đúng chỗ.
    var tab: Tab {
        switch self {
        case .tab(let t): return t
        case .extra(_, let parent): return parent
        }
    }
}

/// Trạng thái điều hướng gốc tab bar ↔ sidebar. Tách khỏi View để test được mà không phải dựng SwiftUI.
///
/// Hàng đợi cover (mở/đóng các `fullScreenCover` nối tiếp) KHÔNG nằm ở đây — app tự giữ. Nguyên lý phải giữ ở
/// phía app: SwiftUI KHÔNG present hai `fullScreenCover` chồng nhau, nên mọi chuyển cover đi qua hàm của model +
/// `onDismiss` của cover đang đóng — KHÔNG "vá" bằng `asyncAfter`.
@MainActor
final class ShellNavigationModel<Tab: ShellTab, Extra: Hashable>: ObservableObject {

    /// Tab đang hiển thị.
    @Published private(set) var selection: Tab

    /// Mục đang chọn trên sidebar iPad. Luôn khớp `selection` (`sidebarSelection.tab == selection`)
    /// ⇒ đổi qua lại compact ↔ regular (Split View, xoay) không lạc chỗ.
    @Published private(set) var sidebarSelection: SidebarItem<Tab, Extra>

    init(initial: Tab) {
        selection = initial
        sidebarSelection = .tab(initial)
    }

    /// Điểm vào khi user chạm tab bar (hoặc lối tắt, deep-link). Sidebar đang ở mục con của đúng tab này thì giữ
    /// nguyên, khác tab thì về gốc tab.
    /// Chỉ gán khi giá trị ĐỔI: `@Published` phát `objectWillChange` cả khi gán giá trị cũ ⇒ chạm lại tab đang đứng
    /// sẽ vẽ lại cả cây gốc vô ích.
    func select(_ tab: Tab) {
        if selection != tab { selection = tab }
        if sidebarSelection.tab != tab { sidebarSelection = .tab(tab) }
    }

    /// Điểm vào khi user chọn trên sidebar iPad. Cùng luật "chỉ gán khi đổi" như `select`.
    func selectSidebar(_ item: SidebarItem<Tab, Extra>) {
        if sidebarSelection != item { sidebarSelection = item }
        if selection != item.tab { selection = item.tab }
    }

    /// Binding cho `TabView(selection:)`.
    var tabBinding: Binding<Tab> {
        Binding(get: { self.selection },
                set: { self.select($0) })
    }

    /// Binding cho `List(selection:)` của sidebar — `nil` (bỏ chọn) bị bỏ qua: sidebar luôn có một mục.
    var sidebarBinding: Binding<SidebarItem<Tab, Extra>?> {
        Binding(get: { self.sidebarSelection },
                set: { if let item = $0 { self.selectSidebar(item) } })
    }
}

extension EnvironmentValues {
    /// Có giá trị ⇔ đang ở bố cục sidebar iPad (`RootShellView` gắn). Màn con dùng để nhảy sang một mục sidebar
    /// thay vì tự push (VD "See all" ⇒ mục "xem tất cả" trên sidebar) và ẩn lối tắt đã có trên sidebar.
    /// Tham số là `SidebarItem<Tab, Extra>` của app bọc `AnyHashable` (environment không generic được); giá trị
    /// khác kiểu bị bỏ qua.
    @Entry var selectSidebarItem: ((AnyHashable) -> Void)? = nil
}
