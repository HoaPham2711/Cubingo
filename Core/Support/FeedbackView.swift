import SwiftUI

/// Trạng thái gửi một `FeedbackDraft`. `.failed` mang theo thông báo ĐÃ localize sẵn (xem
/// `FeedbackViewModel.moTa`) — view chỉ hiển thị `verbatim`, không tự dịch lại.
enum SendState: Equatable {
    case idle, sending, sent
    case failed(String)
}

/// Cầu nối `FeedbackDraft`/`FeedbackTransport` (thuần, đã test riêng) với SwiftUI. `onSent` là
/// closure trung tính: app quyết định làm gì khi gửi xong (vd. báo cho bộ mời đánh giá).
@MainActor
final class FeedbackViewModel: ObservableObject {
    @Published var type: FeedbackType
    @Published var message = ""
    @Published var email = ""
    @Published private(set) var state: SendState = .idle

    private let transport: FeedbackTransport
    let diagnostics: DiagnosticsSnapshot
    let support: SupportConfig
    private let onSent: () -> Void

    /// App có hộp thư hỗ trợ ⇒ form có lối thoát "Email us instead" và thông báo lỗi được nhắc tới nó.
    var canEmail: Bool { support.email != nil }

    /// Gửi hỏng (mạng/máy chủ từ chối/validation) VÀ app có hộp thư ⇒ view hiện "Email us instead".
    /// Tách ra đây để luật này test được không cần UI.
    var offersMailFallback: Bool {
        if case .failed = state { return canEmail }
        return false
    }

    init(type: FeedbackType, transport: FeedbackTransport, diagnostics: DiagnosticsSnapshot,
         support: SupportConfig, onSent: @escaping () -> Void = {}) {
        self.type = type
        self.transport = transport
        self.diagnostics = diagnostics
        self.support = support
        self.onSent = onSent
    }

    func send() async {
        state = .sending
        let draft = FeedbackDraft(type: type,
                                   message: message,
                                   email: email.isEmpty ? nil : email,
                                   diagnostics: diagnostics.text)
        do {
            try draft.validate()
            try await transport.send(draft)
            Track.log(.feedbackSent(kind: type.rawValue))
            state = .sent
            onSent()
        } catch {
            // KHÔNG xoá `message` — mất nội dung user vừa gõ là mất luôn phản hồi đó.
            state = .failed(Self.moTa(error, canEmail: canEmail))
        }
    }

    /// Dịch lỗi thành thông báo user đọc được. Từng case validation liệt kê tường minh — RIÊNG
    /// `.diagnosticsTooLong`: chẩn đoán là dữ liệu APP TỰ SINH, user không gõ trường này, nên
    /// thông báo không được bảo họ "rút ngắn" thứ họ chưa từng viết.
    ///
    /// `canEmail == false` (app không có hộp thư hỗ trợ): không có nút gửi mail nên thông báo
    /// cũng không dặn "email us".
    static func moTa(_ error: Error, canEmail: Bool = true) -> String {
        switch error {
        case FeedbackValidationError.messageEmpty:
            return String(localized: "Please describe the issue before sending.")
        case FeedbackValidationError.messageTooLong:
            return String(localized: "Your message is too long. Please shorten it.")
        case FeedbackValidationError.emailInvalid:
            return String(localized: "That email address doesn't look right.")
        case FeedbackValidationError.diagnosticsTooLong:
            return canEmail
                ? String(localized: "Something went wrong preparing this report. Please try again, or email us instead.")
                : String(localized: "Something went wrong preparing this report. Please try again.")
        case FeedbackSendError.offline:
            return String(localized: "Couldn't reach the server. Check your connection and try again.")
        default:
            // FeedbackSendError.rejected(_) (máy chủ từ chối) không có gì riêng để nói thêm với
            // user; email trực tiếp (nếu có) là lối thoát chung cho mọi trường hợp lạ.
            #if INTERNAL
            // Build nội bộ: kèm mã lỗi để chẩn đoán được ngay trên device không cắm Xcode.
            // Chuỗi thô, KHÔNG `String(localized:)` — chuỗi debug không được vào String Catalog.
            if case let FeedbackSendError.rejected(code) = error {
                return "[INTERNAL] Server từ chối HTTP \(code)."
            }
            #endif
            return canEmail
                ? String(localized: "Something went wrong. Please try again, or email us instead.")
                : String(localized: "Something went wrong. Please try again.")
        }
    }
}

private extension FeedbackType {
    /// Nhãn hiển thị cho Picker — đi qua `String` trước khi tới `Text`, nên PHẢI bọc
    /// `String(localized:)` tại điểm viết literal.
    var title: String {
        switch self {
        case .bug: return String(localized: "Bug")
        case .feature: return String(localized: "Feature request")
        case .other: return String(localized: "Other")
        }
    }
}

/// Màn gửi phản hồi — dùng chung cho cả ba loại (`type` ban đầu do nơi mở màn chọn). Chỉ dựng khi
/// app có `FeedbackTransport` thật; app không có thì dùng `SupportContact` thay cho form.
struct FeedbackView: View {
    @StateObject private var viewModel: FeedbackViewModel
    @Environment(\.dismiss) private var dismiss
    /// Phản hồi nhìn thấy được khi "Email us instead" phải fallback sang copy clipboard (máy
    /// không có Mail app) — xem `SupportMailOpener`.
    @State private var showCopiedToast = false

    init(type: FeedbackType, transport: FeedbackTransport, diagnostics: DiagnosticsSnapshot,
         support: SupportConfig, onSent: @escaping () -> Void = {}) {
        _viewModel = StateObject(wrappedValue: FeedbackViewModel(
            type: type, transport: transport, diagnostics: diagnostics, support: support, onSent: onSent))
    }

    private var navigationTitleText: String {
        switch viewModel.type {
        case .bug: return String(localized: "Report a bug")
        case .feature: return String(localized: "Request a feature")
        case .other: return String(localized: "Feedback")
        }
    }

    var body: some View {
        Form {
            Section {
                Picker(String(localized: "Type"), selection: $viewModel.type) {
                    ForEach(FeedbackType.allCases) { t in
                        Text(t.title).tag(t)
                    }
                }
            }
            Section {
                ZStack(alignment: .topLeading) {
                    if viewModel.message.isEmpty {
                        Text("Describe the issue or your idea…")
                            .foregroundColor(DSColor.textTertiary)
                            .padding(.top, 8)
                            .padding(.leading, 5)
                            .allowsHitTesting(false)
                    }
                    TextEditor(text: $viewModel.message)
                        .frame(minHeight: 120)
                }
            } header: {
                Text("Message")
            }
            Section {
                TextField(String(localized: "Email (optional)"), text: $viewModel.email)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .disableAutocorrection(true)
            } footer: {
                Text("We'll only use this to follow up, if needed.")
            }
            Section {
                DisclosureGroup(String(localized: "What gets sent")) {
                    Text(verbatim: viewModel.diagnostics.text)
                        .font(.system(.footnote, design: .monospaced))
                        .foregroundColor(DSColor.textSecondary)
                }
            } footer: {
                // Sinh từ đúng các nhãn đang gửi (lõi + extras) — không viết tay để khỏi nói sai.
                Text(verbatim: viewModel.diagnostics.privacySummary)
            }
            if case .failed(let thongBao) = viewModel.state {
                Section {
                    Text(verbatim: thongBao)
                        .foregroundColor(DSColor.statusDanger)
                    Button("Try again") {
                        Task { await viewModel.send() }
                    }
                    // Chỉ có khi app cấu hình hộp thư hỗ trợ: không có địa chỉ thì không có gì để mở.
                    if viewModel.offersMailFallback {
                        Button("Email us instead") {
                            openMailFallback()
                        }
                    }
                }
            }
            Section {
                Button {
                    Task { await viewModel.send() }
                } label: {
                    HStack {
                        Spacer()
                        if viewModel.state == .sending {
                            ProgressView()
                        } else {
                            Text("Send")
                        }
                        Spacer()
                    }
                }
                .disabled(viewModel.state == .sending)
            }
        }
        .navigationTitle(navigationTitleText)
        .navigationBarTitleDisplayMode(.inline)
        .alert(String(localized: "Thanks!"),
               isPresented: Binding(get: { viewModel.state == .sent }, set: { _ in })) {
            Button("OK") { dismiss() }
        } message: {
            Text("Your feedback was sent.")
        }
        .alert("Copied", isPresented: $showCopiedToast) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(verbatim: SupportContact.copiedAddressMessage)
        }
    }

    /// Máy không có Mail app: đừng để nút bấm vào không làm gì — copy địa chỉ vào clipboard VÀ
    /// báo cho user biết (`showCopiedToast`). Logic mở-mail-rồi-fallback dùng chung với mọi nơi
    /// khác qua `SupportMailOpener` (xem comment ở đó).
    private func openMailFallback() {
        SupportMailOpener.openOrCopyToClipboard(support: viewModel.support,
                                                 diagnostics: viewModel.diagnostics,
                                                 message: viewModel.message) {
            showCopiedToast = true
        }
    }
}
