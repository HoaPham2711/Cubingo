import Foundation

/// 20 event của vỏ app (onboarding, Pro/mua, phản hồi, đánh giá, cập nhật, nguồn cài, What's New).
/// `rawValue` là tên GA4 — KHÔNG đổi: GA4 không sửa hồi tố, đổi tên là gãy chuỗi số liệu lịch sử.
enum ShellEventName: String, EventNameCatalog {
    case onboardingDone   = "onboarding_done"
    case tourReplay       = "tour_replay"
    case proGateHit       = "pro_gate_hit"
    case paywallView      = "paywall_view"
    case purchaseSuccess  = "purchase_success"
    case purchaseStart    = "purchase_start"
    case purchaseCancel   = "purchase_cancel"
    case purchasePending  = "purchase_pending"
    case purchaseFail     = "purchase_fail"
    case restoreResult    = "restore_result"
    case feedbackSent     = "feedback_sent"
    case reviewPrompt     = "review_prompt"
    case reviewSkip       = "review_skip"
    case reviewAsk        = "review_ask"
    case reviewAnswer     = "review_answer"
    case updatePrompt     = "update_prompt"
    // Nguồn cài Apple Ads, bắn đúng một lần mỗi lượt cài.
    case attributionResolved = "attribution_resolved"
    case whatsNewShown    = "whats_new_shown"
    case whatsNewCta      = "whats_new_cta"
    case whatsNewListOpen = "whats_new_list_open"
}

/// Factory cùng tên case của bản enum cũ ⇒ call site `Track.log(.paywallView(source: "x"))` giữ nguyên.
extension AppEvent {
    /// `skipped_at_page`: 0 = đi hết; ngược lại trang (1-based) đang đứng khi bấm Skip.
    static func onboardingDone(skippedAtPage: Int) -> AppEvent {
        AppEvent(ShellEventName.onboardingDone, ["skipped_at_page": .int(skippedAtPage)])
    }

    static func tourReplay(source: String) -> AppEvent {
        AppEvent(ShellEventName.tourReplay, ["source": .string(source)])
    }

    static func proGateHit(feature: String, detail: String) -> AppEvent {
        AppEvent(ShellEventName.proGateHit, ["feature": .string(feature), "detail": .string(detail)])
    }

    static func paywallView(source: String) -> AppEvent {
        AppEvent(ShellEventName.paywallView, ["source": .string(source)])
    }

    /// `trial`: lượt mua này có đi kèm intro offer (dùng thử) không.
    static func purchaseSuccess(product: String, trial: Bool) -> AppEvent {
        AppEvent(ShellEventName.purchaseSuccess, ["product": .string(product), "trial": .bool(trial)])
    }

    static func purchaseStart(product: String, trial: Bool) -> AppEvent {
        AppEvent(ShellEventName.purchaseStart, ["product": .string(product), "trial": .bool(trial)])
    }

    static func purchaseCancel(product: String) -> AppEvent {
        AppEvent(ShellEventName.purchaseCancel, ["product": .string(product)])
    }

    static func purchasePending(product: String) -> AppEvent {
        AppEvent(ShellEventName.purchasePending, ["product": .string(product)])
    }

    /// `reason`: mã lỗi máy đọc được (`products_unavailable`, `unverified`, `<domain>#<code> <case>`) — để phân
    /// biệt "StoreKit không trả sản phẩm" với "giao dịch lỗi" mà không cần device. Rỗng ⇒ không gửi key.
    static func purchaseFail(product: String, reason: String = "") -> AppEvent {
        var p: [String: ParamValue] = ["product": .string(product)]
        if !reason.isEmpty { p["reason"] = .string(cat(reason)) }
        return AppEvent(ShellEventName.purchaseFail, p)
    }

    /// `outcome`: restored | none | failed.
    static func restoreResult(outcome: String) -> AppEvent {
        AppEvent(ShellEventName.restoreResult, ["outcome": .string(outcome)])
    }

    /// `kind`: bug | feature.
    static func feedbackSent(kind: String) -> AppEvent {
        AppEvent(ShellEventName.feedbackSent, ["kind": .string(kind)])
    }

    /// Gọi `requestReview()` của StoreKit (sau khi user bấm Rate ở hộp hỏi trước).
    static var reviewPrompt: AppEvent { AppEvent(ShellEventName.reviewPrompt) }

    /// `reason` = lý do bỏ qua lượt hỏi đánh giá (mã ngắn cố định).
    static func reviewSkip(reason: String) -> AppEvent {
        AppEvent(ShellEventName.reviewSkip, ["reason": .string(reason)])
    }

    /// Hộp hỏi trước "Rate <app>?" hiện. `source` = khoảnh khắc kích hoạt.
    static func reviewAsk(source: String) -> AppEvent {
        AppEvent(ShellEventName.reviewAsk, ["source": .string(source)])
    }

    /// `outcome`: rate | later.
    static func reviewAnswer(outcome: String) -> AppEvent {
        AppEvent(ShellEventName.reviewAnswer, ["outcome": .string(outcome)])
    }

    /// `action`: shown | open_store.
    static func updatePrompt(action: String) -> AppEvent {
        AppEvent(ShellEventName.updatePrompt, ["action": .string(action)])
    }

    /// Đã chốt nguồn cài (AdServices). Field nil ⇒ vắng param, không gửi chuỗi rỗng.
    /// Tên param KHÔNG chứa "id" (cổng PII) và KHÔNG dùng source/medium/campaign (tên traffic-source GA4).
    static func attributionResolved(source: String, attempts: Int, campaign: String? = nil, adGroup: String? = nil,
                                    keyword: String? = nil, country: String? = nil,
                                    conversion: String? = nil) -> AppEvent {
        var p: [String: ParamValue] = ["acq_source": .string(source), "attempts": .int(attempts)]
        if let v = campaign { p["asa_campaign"] = .string(v) }
        if let v = adGroup { p["ad_group"] = .string(v) }
        if let v = keyword { p["keyword"] = .string(v) }
        if let v = country { p["country"] = .string(v) }
        if let v = conversion { p["conversion"] = .string(v) }
        return AppEvent(ShellEventName.attributionResolved, p)
    }

    /// Sheet What's New hiện (onAppear). `cards` = id thẻ nối `,`; `more` = số thẻ còn lại ngoài sheet;
    /// `fromVersion` = `lastSeen` cũ, `"unknown"` khi khách cũ chưa có mốc; `toVersion` = bản đang cài.
    static func whatsNewShown(cards: String, more: Int, fromVersion: String, toVersion: String) -> AppEvent {
        AppEvent(ShellEventName.whatsNewShown, ["cards": .string(cat(cards)), "more": .int(more),
                                                "from_version": .string(fromVersion),
                                                "to_version": .string(toVersion)])
    }

    /// Bấm nút trên thẻ. `surface`: sheet | list (danh sách đẩy từ sheet) | settings (danh sách mở từ Settings).
    /// `fromVersion` = `from_version` của LẦN HIỆN sheet chứa nút (cùng nghĩa với `whats_new_shown`); `nil` ⇒
    /// không gửi param — danh sách Settings không thuộc lần hiện nào.
    static func whatsNewCta(card: String, fromVersion: String?, toVersion: String, surface: String) -> AppEvent {
        var p: [String: ParamValue] = ["card": .string(card), "to_version": .string(toVersion),
                                       "surface": .string(surface)]
        if let fromVersion { p["from_version"] = .string(fromVersion) }
        return AppEvent(ShellEventName.whatsNewCta, p)
    }

    /// Mở danh sách đầy đủ. `source`: sheet | settings.
    static func whatsNewListOpen(source: String) -> AppEvent {
        AppEvent(ShellEventName.whatsNewListOpen, ["source": .string(source)])
    }

    /// Mẫu cho cổng cấu trúc: mỗi tên trong `ShellEventName` đúng MỘT mẫu, mẫu dùng dạng đầy đủ nhất (mọi param
    /// tuỳ chọn đều có) để cổng PII/độ dài soi được mọi khoá.
    static var shellSamples: [AppEvent] {
        [
            .onboardingDone(skippedAtPage: 0),
            .tourReplay(source: "settings"),
            .proGateHit(feature: "premium_action", detail: "limit_reached"),
            .paywallView(source: "settings"),
            .purchaseSuccess(product: "yearly", trial: true),
            .purchaseStart(product: "yearly", trial: true),
            .purchaseCancel(product: "yearly"),
            .purchasePending(product: "monthly"),
            .purchaseFail(product: "monthly", reason: "products_unavailable"),
            .restoreResult(outcome: "restored"),
            .feedbackSent(kind: "bug"),
            .reviewPrompt,
            .reviewSkip(reason: "dwell_too_short"),
            .reviewAsk(source: "home"),
            .reviewAnswer(outcome: "rate"),
            .updatePrompt(action: "shown"),
            .attributionResolved(source: "apple_ads", attempts: 2, campaign: "1", adGroup: "2", keyword: "3",
                                 country: "US", conversion: "Download"),
            .whatsNewShown(cards: "dark_mode,help_center", more: 2, fromVersion: "1.12.0", toVersion: "1.15.0"),
            .whatsNewCta(card: "help_center", fromVersion: "unknown", toVersion: "1.15.0", surface: "sheet"),
            .whatsNewListOpen(source: "sheet"),
        ]
    }
}
