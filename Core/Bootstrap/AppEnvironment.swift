import Foundation

/// Môi trường app đang chạy: host của unit test, Simulator, route `-uiPreview`.
enum AppEnvironment {
    /// App đang làm host cho unit test (XCTest đặt biến môi trường này trước khi nạp bundle test).
    static let isUnitTestHost: Bool = ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil

    static var isSimulator: Bool {
        #if targetEnvironment(simulator)
        true
        #else
        false
        #endif
    }

    /// Giá trị sau launch argument `-uiPreview` (chụp ảnh/xem màn trên Simulator). Device luôn `nil`.
    static var uiPreviewRoute: String? {
        #if targetEnvironment(simulator)
        value(afterArgument: "-uiPreview", in: CommandLine.arguments)
        #else
        nil
        #endif
    }

    /// Phần tử ngay sau `name` trong `args`; thiếu, hoặc phần tử sau là một cờ khác (bắt đầu bằng `-`) ⇒ `nil`.
    static func value(afterArgument name: String, in args: [String]) -> String? {
        guard let i = args.firstIndex(of: name), args.indices.contains(i + 1) else { return nil }
        let next = args[i + 1]
        return next.hasPrefix("-") ? nil : next
    }
}
