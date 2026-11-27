import Foundation
import Security

/// Kho một số nguyên bền. Protocol để test chạy trên bộ nhớ.
///
/// `read()` ném lỗi thay vì lặng lẽ trả 0: với bộ đếm lượt free, 0 nghĩa là user được thêm lượt, nên bên gọi
/// phải tự quyết (hiển thị thì coi như 0 và ghi log; ghi đè bộ đếm thì KHÔNG — xem `FreeUseLedger.consume`).
/// "Chưa có mục" không phải lỗi: trả 0.
protocol SecureCounterStore {
    func read() throws -> Int
    func write(_ value: Int) throws
}

/// Keychain — sống qua gỡ app cài lại (UserDefaults thì không), nên lượt free không reset được
/// bằng cách xoá app. `AfterFirstUnlock`, KHÔNG đồng bộ iCloud: đếm theo máy.
final class KeychainCounterStore: SecureCounterStore {
    struct KeychainError: LocalizedError {
        let status: OSStatus
        var errorDescription: String? {
            String(localized: "Couldn't save the free-use count (Keychain error \(Int(status))).")
        }
    }

    /// Service Keychain riêng của app: `<bundle id>.<suffix>`. Bundle id khác nhau giữa bản Store và bản
    /// nội bộ ⇒ hai bản cài song song không đọc nhầm bộ đếm của nhau.
    static func appService(_ suffix: String) -> String {
        (Bundle.main.bundleIdentifier ?? "app") + "." + suffix
    }

    private let service: String
    private let account: String

    init(service: String, account: String) {
        self.service = service
        self.account = account
    }

    private var baseQuery: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: account]
    }

    func read() throws -> Int {
        var q = baseQuery
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: CFTypeRef?
        let status = SecItemCopyMatching(q as CFDictionary, &out)
        if status == errSecItemNotFound { return 0 }
        guard status == errSecSuccess else { throw KeychainError(status: status) }
        guard let data = out as? Data,
              let s = String(data: data, encoding: .utf8),
              let v = Int(s) else { return 0 }
        return v
    }

    func write(_ value: Int) throws {
        let data = Data(String(value).utf8)
        let status = SecItemUpdate(baseQuery as CFDictionary,
                                   [kSecValueData as String: data] as CFDictionary)
        if status == errSecItemNotFound {
            var add = baseQuery
            add[kSecValueData as String] = data
            add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
            let s = SecItemAdd(add as CFDictionary, nil)
            guard s == errSecSuccess else { throw KeychainError(status: s) }
        } else if status != errSecSuccess {
            throw KeychainError(status: status)
        }
    }

    #if INTERNAL
    /// Chỉ cho test (Debug có cờ INTERNAL): xoá bộ đếm = trả lại mọi lượt free. Bản App Store không có hàm này.
    // debug-symbol: required
    func deleteForTesting() { SecItemDelete(baseQuery as CFDictionary) }
    #endif
}
