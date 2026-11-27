import XCTest
import SwiftUI
@testable import AppHost

/// Tab giả cho test — Core không biết tab thật của app.
private enum FakeTab: ShellTab {
    case a, b, c

    var title: String {
        switch self {
        case .a: return "A"
        case .b: return "B"
        case .c: return "C"
        }
    }

    var systemImage: String {
        switch self {
        case .a: return "house"
        case .b: return "folder"
        case .c: return "gearshape"
        }
    }
}

private typealias Item = SidebarItem<FakeTab, String>

/// Điều hướng gốc tab bar ↔ sidebar (chuyển từ `RootNavigationModelTests` của nguồn, bỏ phần cover).
@MainActor
final class ShellNavigationModelTests: XCTestCase {

    private func model(_ initial: FakeTab = .a) -> ShellNavigationModel<FakeTab, String> {
        ShellNavigationModel(initial: initial)
    }

    /// Bất biến: mục sidebar luôn thuộc đúng tab đang chọn — co về tab bar (Split View, xoay) không lạc.
    private func assertDongBo(_ m: ShellNavigationModel<FakeTab, String>,
                              file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertEqual(m.sidebarSelection.tab, m.selection, file: file, line: line)
    }

    func testMacDinhLaTabKhoiTao() {
        let m = model()
        XCTAssertEqual(m.selection, .a)
        XCTAssertEqual(m.sidebarSelection, .tab(.a))
        assertDongBo(m)
    }

    func testKhoiTaoTabKhac() {
        let m = model(.c)
        XCTAssertEqual(m.selection, .c)
        XCTAssertEqual(m.sidebarSelection, .tab(.c))
    }

    func testChonTabThatThiDoiTab() {
        let m = model()
        m.select(.c)
        XCTAssertEqual(m.selection, .c)
        assertDongBo(m)
    }

    func testChonTabB() {
        let m = model()
        m.select(.b)
        XCTAssertEqual(m.selection, .b)
        XCTAssertEqual(m.sidebarSelection, .tab(.b))
    }

    func testTabBindingSetTabThat() {
        let m = model()
        m.tabBinding.wrappedValue = .c
        XCTAssertEqual(m.tabBinding.wrappedValue, .c)
        XCTAssertEqual(m.selection, .c)
        assertDongBo(m)
    }

    func testChonMucConTrenSidebarThiTabLaTabCha() {
        let m = model()
        m.selectSidebar(.extra("K", parent: .b))
        XCTAssertEqual(m.selection, .b)
        assertDongBo(m)
    }

    /// Mục chỉ có ở sidebar thuộc tab đầu (kiểu "xem tất cả" của tab gốc).
    func testMucConThuocTabA() {
        let m = model(.c)
        m.selectSidebar(.extra("all", parent: .a))
        XCTAssertEqual(m.selection, .a)
        assertDongBo(m)
    }

    /// Chọn tab khác (tab bar, lối tắt, deep-link) ⇒ sidebar về gốc tab đó.
    func testChonTabKhacThiSidebarVeGocTab() {
        let m = model()
        m.selectSidebar(.extra("K", parent: .b))
        m.select(.c)
        XCTAssertEqual(m.sidebarSelection, .tab(.c))
        assertDongBo(m)
    }

    /// Chọn LẠI đúng tab đang đứng (VD co về tab bar rồi chạm tab đó) không được đá khỏi mục con đang xem.
    func testChonLaiCungTabGiuMucCon() {
        let m = model()
        m.selectSidebar(.extra("K", parent: .b))
        m.select(.b)
        XCTAssertEqual(m.sidebarSelection, .extra("K", parent: .b))
        assertDongBo(m)
    }

    /// Cùng luật khi chạm tab bar (qua binding).
    func testTabBindingChonLaiCungTabGiuMucCon() {
        let m = model()
        m.selectSidebar(.extra("K", parent: .b))
        m.tabBinding.wrappedValue = .b
        XCTAssertEqual(m.sidebarSelection, .extra("K", parent: .b))
    }

    /// Đứng ở mục con, sang tab khác rồi quay lại: về GỐC tab, không khôi phục mục con cũ.
    func testChonMucConRoiDoiTabThiVeGocTab() {
        let m = model()
        m.selectSidebar(.extra("K", parent: .b))
        m.select(.a)
        XCTAssertEqual(m.sidebarSelection, .tab(.a))
        assertDongBo(m)
        m.select(.b)
        XCTAssertEqual(m.sidebarSelection, .tab(.b))
        assertDongBo(m)
    }

    func testSidebarBindingDocMucDangChon() {
        let m = model()
        m.selectSidebar(.extra("K", parent: .b))
        XCTAssertEqual(m.sidebarBinding.wrappedValue, .extra("K", parent: .b))
    }

    func testSidebarBindingChonMucConDoiTab() {
        let m = model()
        m.sidebarBinding.wrappedValue = .extra("K", parent: .c)
        XCTAssertEqual(m.selection, .c)
        assertDongBo(m)
    }

    func testSidebarBindingBoQuaNil() {
        let m = model()
        m.sidebarBinding.wrappedValue = .extra("all", parent: .a)
        m.sidebarBinding.wrappedValue = nil
        XCTAssertEqual(m.sidebarSelection, .extra("all", parent: .a), "sidebar luôn có một mục được chọn")
        assertDongBo(m)
    }

    func testTabCuaMucSidebar() {
        XCTAssertEqual(Item.tab(.c).tab, .c)
        XCTAssertEqual(Item.extra("K", parent: .b).tab, .b)
    }

    /// Một nguồn tiêu đề/icon cho tab bar + sidebar: mọi tab phải có đủ, không rỗng.
    func testMoiTabCoTieuDeVaIcon() {
        for t in FakeTab.allCases {
            XCTAssertFalse(t.title.isEmpty, "\(t)")
            XCTAssertFalse(t.systemImage.isEmpty, "\(t)")
        }
    }

    /// Chạm lại đúng tab/mục đang chọn không được phát `objectWillChange` (vẽ lại cả cây gốc vô ích).
    func testChonLaiDungMucDangChonKhongPhatThayDoi() {
        let m = model()
        m.selectSidebar(.extra("K", parent: .b))
        var count = 0
        let c = m.objectWillChange.sink { count += 1 }
        defer { c.cancel() }
        m.select(.b)
        m.tabBinding.wrappedValue = .b
        m.selectSidebar(.extra("K", parent: .b))
        m.sidebarBinding.wrappedValue = .extra("K", parent: .b)
        XCTAssertEqual(count, 0)
        m.select(.c)
        XCTAssertGreaterThan(count, 0, "đổi tab thật phải phát")
    }

    /// View không nhận kênh nào được truyền `.none`: không có yêu cầu, `take()` luôn nil.
    func testOneShotNoneRong() {
        let r = OneShotRequest<Int>.none
        XCTAssertNil(r.pending)
        XCTAssertNil(r.take())
    }

    // MARK: - SidebarItem.erased (đường `selectSidebarItem`)

    func testErasedDungKieuThiTraMuc() {
        let item = Item.extra("x", parent: .b)
        XCTAssertEqual(Item.erased(AnyHashable(item)), item)
        XCTAssertEqual(Item.erased(AnyHashable(Item.tab(.c))), .tab(.c))
    }

    func testErasedSaiKieuThiNil() {
        XCTAssertNil(Item.erased(AnyHashable("chuoi")))
        XCTAssertNil(Item.erased(AnyHashable(42)))
        // Cùng hình nhưng khác tham số kiểu (Extra = Int) cũng bị bỏ qua.
        XCTAssertNil(Item.erased(AnyHashable(SidebarItem<FakeTab, Int>.extra(1, parent: .a))))
    }
}
