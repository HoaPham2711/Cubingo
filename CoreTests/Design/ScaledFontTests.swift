import SwiftUI
import XCTest
@testable import AppHost

final class ScaledFontTests: XCTestCase {

    func testCoDungBangStyleChonDungStyleDo() {
        XCTAssertEqual(ScaledFontStyle.textStyle(forPointSize: 17), .body)
        XCTAssertEqual(ScaledFontStyle.textStyle(forPointSize: 15), .subheadline)
        XCTAssertEqual(ScaledFontStyle.textStyle(forPointSize: 13), .footnote)
        XCTAssertEqual(ScaledFontStyle.textStyle(forPointSize: 22), .title2)
        XCTAssertEqual(ScaledFontStyle.textStyle(forPointSize: 28), .title)
        XCTAssertEqual(ScaledFontStyle.textStyle(forPointSize: 11), .caption2)
    }

    func testCoGiuaHaiStyleChonStyleNhoHonGanNhat() {
        XCTAssertEqual(ScaledFontStyle.textStyle(forPointSize: 14), .footnote)
        XCTAssertEqual(ScaledFontStyle.textStyle(forPointSize: 26), .title2)
        XCTAssertEqual(ScaledFontStyle.textStyle(forPointSize: 18), .body)
    }

    func testCoNgoaiBangKepVeHaiDau() {
        XCTAssertEqual(ScaledFontStyle.textStyle(forPointSize: 72), .largeTitle)
        XCTAssertEqual(ScaledFontStyle.textStyle(forPointSize: 9), .caption2)
    }

    func testBangCoMacDinhGiamDan() {
        let sizes = ScaledFontStyle.defaultSizes.map(\.size)
        XCTAssertEqual(sizes, sizes.sorted(by: >))
    }
}

final class ReadableColumnTitleTests: XCTestCase {

    func testRegularDatTieuDeTrongCot() {
        let p = ReadableColumnTitlePlacement(sizeClass: .regular)
        XCTAssertEqual(p, .inColumn)
        XCTAssertEqual(p.titleDisplayMode, .inline)
        XCTAssertEqual(p.topScrollMargin, 0)
    }

    func testCompactGiuTieuDeLonCuaThanh() {
        let p = ReadableColumnTitlePlacement(sizeClass: .compact)
        XCTAssertEqual(p, .navigationBar)
        XCTAssertEqual(p.titleDisplayMode, .large)
        XCTAssertNil(p.topScrollMargin)
    }

    /// Chưa biết size class (lúc dựng đầu) ⇒ như iPhone — không được vẽ tiêu đề đôi.
    func testChuaBietSizeClassNhuCompact() {
        XCTAssertEqual(ReadableColumnTitlePlacement(sizeClass: nil), .navigationBar)
    }
}
