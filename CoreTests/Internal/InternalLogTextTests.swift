#if INTERNAL
import XCTest
@testable import AppHost

/// `LogFileView` (Core/Internal/LogFileView.swift): tách dòng, giải mã lỏng, tìm dòng khớp, cắt dòng dài, tô khớp.
final class InternalLogTextTests: XCTestCase {

    func testLinesCRLFTrailingNewlineAndEmpty() {
        XCTAssertEqual(InternalLogText.lines(of: Data("a\r\nb\n\nc\n".utf8)), ["a", "b", "", "c"])
        XCTAssertEqual(InternalLogText.lines(of: Data("a\nb".utf8)), ["a", "b"])
        XCTAssertEqual(InternalLogText.lines(of: Data()), [])
        XCTAssertEqual(InternalLogText.lines(of: Data("\n".utf8)), [])         // chỉ một "\n" ⇒ rỗng
    }

    /// Log bị cắt giữa ký tự UTF-8 (app chết lúc đang ghi) — vẫn đọc được, không rơi về rỗng.
    func testLinesTruncatedUTF8() {
        var d = Data("dòng 1\nđang ghi ".utf8)
        d.append(contentsOf: Array("ế".utf8).prefix(1))
        let l = InternalLogText.lines(of: d)
        XCTAssertEqual(l.count, 2)
        XCTAssertEqual(l[0], "dòng 1")
        XCTAssertTrue(l[1].hasPrefix("đang ghi "))
    }

    /// Tìm không phân biệt hoa thường; chỉ số 0-based; query rỗng ⇒ không khớp gì.
    func testMatchesKhongPhanBietHoaThuong() {
        let lines = ["Alpha 1", "noise", "alpha 2", "ALPHA 3"]
        XCTAssertEqual(InternalLogText.matches(lines, query: "alpha"), [0, 2, 3])
        XCTAssertEqual(InternalLogText.matches(lines, query: "AlPhA 2"), [2])
        XCTAssertEqual(InternalLogText.matches(lines, query: ""), [])
        XCTAssertEqual(InternalLogText.matches(lines, query: "không có"), [])
    }

    func testMatchIndex() {
        let m = [0, 2, 3]
        XCTAssertEqual(InternalLogText.matchIndex(near: 2, in: m), 1)
        XCTAssertEqual(InternalLogText.matchIndex(near: 1, in: m), 1)   // lần khớp kế tiếp
        XCTAssertEqual(InternalLogText.matchIndex(near: 9, in: m), 0)   // quá cuối ⇒ về đầu
        XCTAssertEqual(InternalLogText.matchIndex(near: nil, in: m), 0)
        XCTAssertEqual(InternalLogText.matchIndex(near: 1, in: []), 0)
    }

    func testDisplayTextCapsLongLines() {
        let long = String(repeating: "a", count: InternalLogText.maxDisplayChars + 10)
        XCTAssertTrue(InternalLogText.displayText(long).hasSuffix("(+10 ký tự)"))
        XCTAssertEqual(InternalLogText.displayText("short"), "short")
    }

    /// Tô MỌI lần khớp (không phân biệt hoa thường), chữ giữ nguyên.
    func testHighlightedToMoiLanKhop() {
        let a = InternalLogText.highlighted("Beta beta BETA x", query: "beta")
        XCTAssertEqual(String(a.characters), "Beta beta BETA x")
        let tomau = a.runs.filter { $0.backgroundColor != nil }.map { String(a[$0.range].characters) }
        XCTAssertEqual(tomau, ["Beta", "beta", "BETA"])
        XCTAssertTrue(InternalLogText.highlighted("abc", query: "").runs.allSatisfy { $0.backgroundColor == nil })
    }
}
#endif
