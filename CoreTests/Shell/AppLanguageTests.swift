import XCTest
@testable import AppHost

/// Override ngôn ngữ app — UserDefaults suite riêng, danh sách bản địa hoá truyền tay (không đọc bundle thật).
final class AppLanguageTests: XCTestCase {

    private var suite = ""
    private var d: UserDefaults!

    override func setUp() {
        super.setUp()
        suite = "AppLanguageTests.\(UUID().uuidString)"
        d = UserDefaults(suiteName: suite)!
    }

    override func tearDown() {
        d.removePersistentDomain(forName: suite)
        d = nil
        super.tearDown()
    }

    /// Chỉ có tiếng Anh trong bundle ⇒ picker ẩn; có thêm ngôn ngữ thật thứ hai thì hiện.
    func testChiCoEnThiAnPicker() {
        XCTAssertFalse(AppLanguage.isPickerVisible(localizations: ["en"]))
        XCTAssertEqual(AppLanguage.available(localizations: ["en"]).map(\.code), [nil, "en"])
        XCTAssertTrue(AppLanguage.isPickerVisible(localizations: ["en", "vi"]))
    }

    /// `Base` bị bỏ, mã trùng chỉ giữ một; `.system` luôn đứng đầu.
    func testBaseBiBoVaKhongTrung() {
        let list = AppLanguage.available(localizations: ["Base", "en", "vi", "en"])
        XCTAssertEqual(list.map(\.code), [nil, "en", "vi"])
        XCTAssertEqual(list.first, .system)
    }

    /// Mã có vùng/chữ viết vẫn ra tên hiển thị không rỗng.
    func testMaCoVungCoTenHienThi() {
        XCTAssertFalse(AppLanguage(code: "zh-Hans").title.isEmpty)
        XCTAssertFalse(AppLanguage(code: "pt-BR").title.isEmpty)
        XCTAssertFalse(AppLanguage.system.title.isEmpty)
    }

    /// Chưa từng ghi hoặc giá trị rác ⇒ `.system`.
    func testDocKhoaRongHoacRacLaSystem() {
        XCTAssertEqual(AppLanguage.load(from: d, localizations: ["en", "vi"]), .system)
        d.set("klingon", forKey: AppLanguage.defaultsKey)
        XCTAssertEqual(AppLanguage.load(from: d, localizations: ["en", "vi"]), .system)
    }

    /// Mã đã lưu mà bundle không còn ⇒ `.system`; còn thì giữ.
    func testMaLuuKhongConTrongBundleVeHeThong() {
        d.set("vi", forKey: AppLanguage.defaultsKey)
        XCTAssertEqual(AppLanguage.load(from: d, localizations: ["en", "vi"]), AppLanguage(code: "vi"))
        XCTAssertEqual(AppLanguage.load(from: d, localizations: ["en"]), .system)
    }

    /// Chọn ngôn ngữ cụ thể ghi override `AppleLanguages`; về `.system` thì xoá override.
    func testApplyGhiVaXoaAppleLanguages() {
        let en = AppLanguage(code: "en")
        en.apply(to: d)
        XCTAssertEqual(AppLanguage.load(from: d, localizations: ["en"]), en)
        XCTAssertEqual(d.stringArray(forKey: "AppleLanguages"), ["en"])
        AppLanguage.system.apply(to: d)
        XCTAssertEqual(AppLanguage.load(from: d, localizations: ["en"]), .system)
        XCTAssertNil(d.persistentDomain(forName: suite)?["AppleLanguages"])
    }
}

/// Link công khai dựng từ `AppConfig` dựng tay (không đọc cấu hình thật của template).
final class AppLinksTests: XCTestCase {

    func testLinkTheoHostWeb() {
        let links = AppLinks(config: AppConfig(info: ["WebHost": "example.com"]))
        XCTAssertEqual(links.site?.absoluteString, "https://example.com/")
        XCTAssertEqual(links.privacy?.absoluteString, "https://example.com/privacy/")
        XCTAssertEqual(links.terms?.absoluteString, "https://example.com/terms/")
        XCTAssertEqual(links.support?.absoluteString, "https://example.com/support/")
    }

    func testKhongCoWebThiMoiLinkNil() {
        let links = AppLinks(config: AppConfig(info: [:]))
        XCTAssertNil(links.site); XCTAssertNil(links.privacy); XCTAssertNil(links.terms); XCTAssertNil(links.support)
    }
}
