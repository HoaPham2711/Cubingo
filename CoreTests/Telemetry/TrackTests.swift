@testable import AppHost
import XCTest

/// Facade `Track`: mặc định an toàn, thứ tự observer → sink, và bẫy `reset()` không được gỡ observer.
final class TrackTests: XCTestCase {

    override func tearDown() {
        Track.reset()
        Track.removeUsageObserver()
        super.tearDown()
    }

    /// Mặc định là NoOp ⇒ test không biết gì về telemetry vẫn tự an toàn (không mạng, không SDK).
    func testResetVeNoOpSink() {
        Track.install(RecordingSink())
        XCTAssertFalse(Track.isUsingNoOpSink)
        Track.reset()
        XCTAssertTrue(Track.isUsingNoOpSink)
    }

    /// Tắt "chia sẻ dữ liệu sử dụng" gỡ SINK, nhưng ghi nhận "đã dùng tính năng" trên máy vẫn phải chạy tiếp.
    func testResetKhongGoUsageObserver() {
        let o = GhiObserver()
        Track.installUsageObserver(o)
        Track.install(RecordingSink())
        Track.reset()
        Track.log(.paywallView(source: "settings"))
        XCTAssertEqual(o.names, ["paywall_view"], "reset() chỉ được gỡ sink, không gỡ usage observer")
    }

    func testRemoveUsageObserverThiThoiNghe() {
        let o = GhiObserver()
        Track.installUsageObserver(o)
        Track.removeUsageObserver()
        Track.log(.reviewPrompt)
        XCTAssertEqual(o.names, [])
    }

    /// Observer TRƯỚC sink: sink thật có thể chậm/throw ở tầng dưới, ghi nhận trên máy không được phụ thuộc nó.
    func testObserverDuocGoiTruocSink() {
        let thuTu = ThuTu()
        Track.installUsageObserver(ThuTuObserver(thuTu))
        Track.install(ThuTuSink(thuTu))
        Track.log(.tourReplay(source: "settings"))
        XCTAssertEqual(thuTu.log, ["observer", "sink"])
    }

    func testMoiLoaiTinDiQuaSink() {
        let sink = RecordingSink()
        Track.install(sink)
        Track.set(.storeEnv("xcode"))
        Track.diagnostic(.stage, "idle")
        Track.nonFatal(.attribution, code: "parse", detail: "x")
        Track.breadcrumb(Breadcrumb(text: "app.launch"))
        XCTAssertEqual(sink.properties, [.storeEnv("xcode")])
        XCTAssertEqual(sink.diagnostics, [.stage: "idle"])
        XCTAssertEqual(sink.nonFatals, [NonFatal(domain: .attribution, code: "parse", detail: "x")])
        XCTAssertEqual(sink.breadcrumbs, [Breadcrumb(text: "app.launch")])
        sink.clear()
        XCTAssertTrue(sink.events.isEmpty && sink.properties.isEmpty && sink.breadcrumbs.isEmpty)
    }

    func testKhoaChungGiuNguyenTen() {
        XCTAssertEqual(DiagnosticKey.stage.rawValue, "stage")
        XCTAssertEqual(NonFatal.Domain.attribution.rawValue, "attribution")
    }
}

private final class GhiObserver: UsageObserver {
    private(set) var names: [String] = []
    func note(_ event: AppEvent) { names.append(event.name) }
}

private final class ThuTu { var log: [String] = [] }

private final class ThuTuObserver: UsageObserver {
    let t: ThuTu
    init(_ t: ThuTu) { self.t = t }
    func note(_ event: AppEvent) { t.log.append("observer") }
}

private final class ThuTuSink: AnalyticsSink {
    let t: ThuTu
    init(_ t: ThuTu) { self.t = t }
    func log(_ event: AppEvent) { t.log.append("sink") }
    func set(_ property: UserProperty) {}
    func diagnostic(_ key: DiagnosticKey, _ value: String) {}
    func nonFatal(_ error: NonFatal) {}
    func breadcrumb(_ crumb: Breadcrumb) {}
}
