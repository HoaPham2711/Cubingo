@testable import AppHost
import XCTest

/// Cổng cấu trúc cho taxonomy analytics của vỏ app. Đây KHÔNG phải test hành vi — nó chặn những lỗi mà
/// GA4 không cho sửa hồi tố: tên event sai chuẩn, param quá nhiều, và PII lọt vào từ một lần refactor vô
/// tình sau này. Trước kia `enum` + `switch` vét cạn ép mỗi event khai param và mẫu; nay `AppEvent` là
/// struct (để app thêm event riêng) nên `TelemetryTaxonomy.violations` gánh phần đó — test ở đây chứng minh
/// nó gác thật.
final class ShellEventTaxonomyTests: XCTestCase {

    override func tearDown() {
        Track.reset()
        Track.removeUsageObserver()
        super.tearDown()
    }

    // MARK: - Cổng taxonomy

    /// Điều kiện cần của mọi cổng param bên dưới: chúng chỉ duyệt mẫu, nên một tên KHÔNG có mẫu là một tên
    /// chúng hoàn toàn mù. Đừng bao giờ nới cổng "mỗi tên có mẫu" để "cho qua" — nới nó là chọc thủng cả bộ.
    func testMoiTenShellDeuCoMauVaHopLe() {
        XCTAssertEqual(TelemetryTaxonomy.violations(ShellEventName.self, samples: AppEvent.shellSamples), [])
    }

    func testMoiTenShellDungMotMau() {
        XCTAssertEqual(ShellEventName.allCases.count, 20)
        XCTAssertEqual(AppEvent.shellSamples.count, ShellEventName.allCases.count)
        XCTAssertEqual(Set(AppEvent.shellSamples.map(\.name)), Set(ShellEventName.allCases.map(\.rawValue)))
    }

    func testThieuMauBiBat() {
        XCTAssertFalse(TelemetryTaxonomy.violations(ShellEventName.self, samples: []).isEmpty)
        // Thiếu đúng MỘT tên cũng phải bị bắt, và thông báo nêu đúng tên đó.
        let thieu = AppEvent.shellSamples.filter { !$0.isNamed(ShellEventName.reviewPrompt) }
        let v = TelemetryTaxonomy.violations(ShellEventName.self, samples: thieu)
        XCTAssertEqual(v.count, 1)
        XCTAssertTrue(v.first?.contains("review_prompt") == true, "\(v)")
    }

    /// id/name/path là ba đường PII lọt vào nhiều nhất — một UUID làm vỡ cardinality GA4, tên do user đặt và
    /// đường dẫn file là dữ liệu người dùng. Khớp chuỗi con, không phân biệt hoa thường.
    func testBatThamSoGiongDinhDanh() {
        let bad = AppEvent(ShellEventName.paywallView, ["user_id": .string("x")])
        XCTAssertFalse(TelemetryTaxonomy.violations(ShellEventName.self, samples: AppEvent.shellSamples + [bad]).isEmpty)
        for key in ["displayName", "file_path", "ID"] {
            let e = AppEvent(ShellEventName.paywallView, [key: .int(1)])
            XCTAssertFalse(TelemetryTaxonomy.violations(ShellEventName.self, samples: AppEvent.shellSamples + [e]).isEmpty,
                           "khoá '\(key)' phải bị cổng PII chặn")
        }
    }

    func testGiaTriQua100KyTuBiBat() {
        let vua = AppEvent(ShellEventName.paywallView, ["source": .string(String(repeating: "a", count: 100))])
        XCTAssertEqual(TelemetryTaxonomy.violations(ShellEventName.self, samples: AppEvent.shellSamples + [vua]), [])
        let dai = AppEvent(ShellEventName.paywallView, ["source": .string(String(repeating: "a", count: 101))])
        XCTAssertFalse(TelemetryTaxonomy.violations(ShellEventName.self, samples: AppEvent.shellSamples + [dai]).isEmpty)
    }

    func testQua25ThamSoBiBat() {
        func mau(_ n: Int) -> AppEvent {
            AppEvent(ShellEventName.paywallView,
                     Dictionary(uniqueKeysWithValues: (0..<n).map { ("k\($0)", ParamValue.int($0)) }))
        }
        XCTAssertEqual(TelemetryTaxonomy.violations(ShellEventName.self, samples: AppEvent.shellSamples + [mau(25)]), [])
        XCTAssertFalse(TelemetryTaxonomy.violations(ShellEventName.self, samples: AppEvent.shellSamples + [mau(26)]).isEmpty)
    }

    /// Chuẩn GA4: ≤ 40 ký tự, snake_case thường, chỉ [a-z0-9_].
    func testTenSaiChuanGA4BiBat() {
        let v = TelemetryTaxonomy.violations(TenSaiGA4.self, samples: TenSaiGA4.allCases.map { AppEvent($0) })
        for ten in TenSaiGA4.allCases where ten != .vuaKhit40 {
            XCTAssertTrue(v.contains { $0.contains("'\(ten.rawValue)'") }, "tên '\(ten.rawValue)' phải bị bắt: \(v)")
        }
        XCTAssertFalse(v.contains { $0.contains("'\(TenSaiGA4.vuaKhit40.rawValue)'") }, "40 ký tự là hợp lệ: \(v)")
    }

    /// Không có gì trong taxonomy được phép mang toạ độ: dữ liệu vị trí trên máy mà lọt vào analytics là đổi
    /// hẳn nhãn quyền riêng tư của app.
    func testKhongCoParamViTri() {
        let v = TelemetryTaxonomy.crossCatalogViolations(
            catalogs: [ShellEventName.allCases.map(\.rawValue)], samples: AppEvent.shellSamples)
        XCTAssertEqual(v, [])
    }

    // MARK: - Tên và khoá param giữ nguyên (GA4 không sửa hồi tố)

    func testTenVaKhoaThamSoGiuNguyenNguon() {
        let mongDoi: [String: Set<String>] = [
            "onboarding_done": ["skipped_at_page"],
            "tour_replay": ["source"],
            "pro_gate_hit": ["feature", "detail"],
            "paywall_view": ["source"],
            "purchase_success": ["product", "trial"],
            "purchase_start": ["product", "trial"],
            "purchase_cancel": ["product"],
            "purchase_pending": ["product"],
            "purchase_fail": ["product", "reason"],
            "restore_result": ["outcome"],
            "feedback_sent": ["kind"],
            "review_prompt": [],
            "review_skip": ["reason"],
            "review_ask": ["source"],
            "review_answer": ["outcome"],
            "update_prompt": ["action"],
            "attribution_resolved": ["acq_source", "attempts", "asa_campaign", "ad_group", "keyword", "country",
                                     "conversion"],
            "whats_new_shown": ["cards", "more", "from_version", "to_version"],
            "whats_new_cta": ["card", "from_version", "to_version", "surface"],
            "whats_new_list_open": ["source"],
        ]
        let thucTe = Dictionary(uniqueKeysWithValues: AppEvent.shellSamples.map { ($0.name, Set($0.parameters.keys)) })
        XCTAssertEqual(thucTe, mongDoi)
    }

    /// Bước 1 của onboarding: biết trang bị bỏ ngang. Tham số chế độ ưa thích của nguồn KHÔNG đi theo (nó là
    /// lựa chọn nghiệp vụ của app).
    func testOnboardingDoneChiMangTrangSkip() {
        let e = AppEvent.onboardingDone(skippedAtPage: 3)
        XCTAssertEqual(e.name, "onboarding_done")
        XCTAssertEqual(e.parameters, ["skipped_at_page": .int(3)])
    }

    func testTourReplay() {
        let e = AppEvent.tourReplay(source: "settings")
        XCTAssertEqual(e.name, "tour_replay")
        XCTAssertEqual(e.parameters["source"], .string("settings"))
    }

    /// Ba event What's New, chỉ mang id thẻ do app đặt + số bản — không dữ liệu người dùng.
    func testWhatsNewEvents() {
        let s = AppEvent.whatsNewShown(cards: "dark_mode,help_center", more: 2,
                                       fromVersion: "unknown", toVersion: "1.15.0")
        XCTAssertEqual(s.name, "whats_new_shown")
        XCTAssertEqual(s.parameters, ["cards": .string("dark_mode,help_center"), "more": .int(2),
                                      "from_version": .string("unknown"), "to_version": .string("1.15.0")])
        let c = AppEvent.whatsNewCta(card: "dark_mode", fromVersion: "1.12.0", toVersion: "1.15.0", surface: "list")
        XCTAssertEqual(c.name, "whats_new_cta")
        XCTAssertEqual(c.parameters, ["card": .string("dark_mode"), "from_version": .string("1.12.0"),
                                      "to_version": .string("1.15.0"), "surface": .string("list")])
        // Danh sách mở từ Settings không thuộc lần hiện sheet nào ⇒ KHÔNG gửi from_version (khác nghĩa với sheet).
        let st = AppEvent.whatsNewCta(card: "dark_mode", fromVersion: nil, toVersion: "1.15.0", surface: "settings")
        XCTAssertEqual(st.parameters, ["card": .string("dark_mode"), "to_version": .string("1.15.0"),
                                       "surface": .string("settings")])
        let l = AppEvent.whatsNewListOpen(source: "settings")
        XCTAssertEqual(l.name, "whats_new_list_open")
        XCTAssertEqual(l.parameters, ["source": .string("settings")])
    }

    /// Field nil thì vắng param, không gửi chuỗi rỗng; không dùng source/medium/campaign (tên traffic-source GA4).
    func testAttributionResolved() {
        let e = AppEvent.attributionResolved(source: "apple_ads", attempts: 2, campaign: "1", adGroup: "2",
                                             keyword: nil, country: "US", conversion: "Download")
        XCTAssertEqual(e.name, "attribution_resolved")
        XCTAssertEqual(e.parameters["acq_source"], .string("apple_ads"))
        XCTAssertNil(e.parameters["source"], "source/medium/campaign là tên traffic-source của GA4")
        XCTAssertNil(e.parameters["campaign"])
        XCTAssertEqual(e.parameters["attempts"], .int(2))
        XCTAssertEqual(e.parameters["asa_campaign"], .string("1"))
        XCTAssertEqual(e.parameters["ad_group"], .string("2"))
        XCTAssertNil(e.parameters["keyword"])
        XCTAssertEqual(e.parameters["country"], .string("US"))
        XCTAssertEqual(e.parameters["conversion"], .string("Download"))
        XCTAssertEqual(UserProperty.acqSource("organic").name, "acq_source")
        XCTAssertEqual(UserProperty.asaCampaign("7").name, "asa_campaign")
        XCTAssertEqual(UserProperty.asaKeyword("9").name, "asa_keyword")
        XCTAssertEqual(UserProperty.asaKeyword("9").value, "9")
    }

    /// 6 thuộc tính người dùng của lõi: tên giữ nguyên nguồn; GA4 không có bool ⇒ chuỗi "true"/"false".
    func testThuocTinhNguoiDungLoi() {
        XCTAssertEqual(UserProperty.isPro(true), UserProperty(name: "is_pro", value: "true"))
        XCTAssertEqual(UserProperty.isPro(false).value, "false")
        XCTAssertEqual(UserProperty.storeEnv("sandbox"), UserProperty(name: "store_env", value: "sandbox"))
        XCTAssertEqual(UserProperty.internalDevice, UserProperty(name: "internal_device", value: "true"))
        XCTAssertEqual(UserProperty.acqSource("organic").value, "organic")
    }

    /// `reason` có thể đến từ mô tả lỗi dài bất kỳ ⇒ cắt về trần 100 ký tự của GA4; rỗng ⇒ không gửi key.
    func testPurchaseFailCatLyDoVaBoKhiRong() {
        XCTAssertEqual(AppEvent.purchaseFail(product: "monthly").parameters, ["product": .string("monthly")])
        let dai = AppEvent.purchaseFail(product: "monthly", reason: String(repeating: "x", count: 250))
        XCTAssertEqual(dai.string("reason")?.count, 100)
    }

    func testIsNamedVaString() {
        let e = AppEvent.paywallView(source: "settings")
        XCTAssertTrue(e.isNamed(ShellEventName.paywallView))
        XCTAssertFalse(e.isNamed(ShellEventName.purchaseStart))
        XCTAssertEqual(e.string("source"), "settings")
        XCTAssertNil(e.string("khong_co"))
        XCTAssertNil(AppEvent.onboardingDone(skippedAtPage: 1).string("skipped_at_page"), "giá trị int không phải chuỗi")
    }

    // MARK: - Đường mở rộng của app

    /// Một app khai danh mục tên riêng + factory riêng trong extension, KHÔNG sửa gì trong `Core/`: call site
    /// vẫn `Track.log(.tenEvent(...))`, sink nhận đúng, và cổng taxonomy gác được danh mục của app.
    func testAppTuThemEventQuaExtension() {
        let sink = RecordingSink()
        Track.install(sink)
        Track.log(.demoItemAdd(count: 2, source: "home"))
        Track.log(.demoItemRemove)
        Track.log(.paywallView(source: "settings"))
        XCTAssertEqual(sink.names, ["demo_item_add", "demo_item_remove", "paywall_view"])
        XCTAssertTrue(sink.events[0].isNamed(DemoEventName.demoItemAdd))
        XCTAssertEqual(sink.events[0].parameters, ["count": .int(2), "source": .string("home")])

        XCTAssertEqual(TelemetryTaxonomy.violations(DemoEventName.self, samples: AppEvent.demoSamples), [])
        XCTAssertFalse(TelemetryTaxonomy.violations(DemoEventName.self, samples: [.demoItemRemove]).isEmpty,
                       "danh mục của app cũng bị ép 'mỗi tên có mẫu'")
        XCTAssertFalse(TelemetryTaxonomy.violations(
            DemoEventName.self,
            samples: AppEvent.demoSamples + [AppEvent(DemoEventName.demoItemAdd, ["item_path": .string("a")])]).isEmpty,
                       "danh mục của app cũng qua cổng PII")
    }
}

// MARK: - Fixture: danh mục tên của một "app" giả

/// Danh mục tên kiểu app khai — sống trong target test, chứng minh mở rộng được mà không sửa `Core/`.
enum DemoEventName: String, EventNameCatalog {
    case demoItemAdd = "demo_item_add"
    case demoItemRemove = "demo_item_remove"
}

extension AppEvent {
    static func demoItemAdd(count: Int, source: String) -> AppEvent {
        AppEvent(DemoEventName.demoItemAdd, ["count": .int(count), "source": .string(source)])
    }

    static var demoItemRemove: AppEvent { AppEvent(DemoEventName.demoItemRemove) }

    static var demoSamples: [AppEvent] { [.demoItemAdd(count: 1, source: "home"), .demoItemRemove] }
}

/// Tên sai chuẩn GA4 (trừ `vuaKhit40`: đúng 40 ký tự, hợp lệ).
enum TenSaiGA4: String, EventNameCatalog {
    case chuHoa = "Bad_event"
    case gachNgang = "bad-event"
    case dauCach = "bad event"
    case qua40 = "a_very_long_event_title_that_exceeds_forty"
    case vuaKhit40 = "a_very_long_event_title_exactly_40_chars"
}
