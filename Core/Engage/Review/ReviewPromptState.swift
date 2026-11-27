import Foundation

/// Câu trả lời của user cho hộp hỏi trước của app ("Rate <tên app>?").
enum ReviewAnswer: String, Equatable {
    case rate
    case later
}

/// Bộ đếm BỀN cho chính sách mời đánh giá. Tách khỏi `ReviewPromptPolicy` để policy ở lại thuần
/// và test được bằng bảng, không cần UserDefaults.
struct ReviewPromptState: Equatable {
    static let defaultsPrefix = "review."
    /// Trần số id mục nhớ để nhận ra "mở lại" — đủ cho mọi thư viện thực tế, không phình.
    static let maxRememberedItems = 200

    /// Các lần hộp của app được hiện, chỉ giữ trong 365 ngày cuộn (cắt lúc `save`).
    var askDates: [Date] = []
    var lastAnswer: ReviewAnswer?
    /// Số lần `Not Now` liên tiếp — reset về 0 khi user bấm `Rate`.
    var consecutiveDeclines = 0
    var lastFeedbackSentDate: Date?
    /// Các mục đã từng mở (mới nhất ở cuối) — để biết lần mở này là "mở lại".
    var openedItemIDs: [String] = []

    var lastAskedDate: Date? { askDates.max() }

    static func load(from d: UserDefaults) -> ReviewPromptState {
        ReviewPromptState(
            askDates: d.array(forKey: key("askDates")) as? [Date] ?? [],
            lastAnswer: (d.string(forKey: key("lastAnswer"))).flatMap(ReviewAnswer.init(rawValue:)),
            consecutiveDeclines: d.integer(forKey: key("consecutiveDeclines")),
            lastFeedbackSentDate: d.object(forKey: key("lastFeedbackSentDate")) as? Date,
            openedItemIDs: d.stringArray(forKey: key("openedItemIDs")) ?? [])
    }

    func save(to d: UserDefaults, now: Date = Date()) {
        let namTruoc = now.addingTimeInterval(-365 * 86400)
        d.set(askDates.filter { $0 > namTruoc }, forKey: Self.key("askDates"))
        d.set(lastAnswer?.rawValue, forKey: Self.key("lastAnswer"))
        d.set(consecutiveDeclines, forKey: Self.key("consecutiveDeclines"))
        d.set(lastFeedbackSentDate, forKey: Self.key("lastFeedbackSentDate"))
        d.set(Array(openedItemIDs.suffix(Self.maxRememberedItems)), forKey: Self.key("openedItemIDs"))
    }

    private static func key(_ s: String) -> String { defaultsPrefix + s }
}
