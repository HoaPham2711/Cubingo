import Foundation

/// Cổng cấu trúc cho một danh mục event — thay phần trình biên dịch từng ép khi `AppEvent` còn là `enum`.
/// Không phải kiểm hành vi: nó chặn những lỗi GA4 không cho sửa hồi tố (tên sai chuẩn, quá nhiều param, PII).
///
/// Cách dùng (lõi và mỗi app, trong test): `XCTAssertEqual(TelemetryTaxonomy.violations(MyEventName.self,
/// samples: AppEvent.mySamples), [])`.
enum TelemetryTaxonomy {

    /// Trần của GA4.
    static let maxNameLength = 40
    static let maxParameters = 25
    static let maxStringLength = 100

    /// Từ khoá cấm trong khoá param (khớp chuỗi con, không phân biệt hoa thường): id/name/path là ba đường PII
    /// lọt vào nhiều nhất — một UUID làm vỡ cardinality GA4, tên do user đặt và đường dẫn file là dữ liệu người
    /// dùng. Khớp chuỗi con nên cả từ vô hại như "hidden" cũng bị chặn: chọn khoá khác, ĐỪNG nới cổng.
    static let forbiddenKeyFragments = ["id", "name", "path"]

    /// Mảnh chuỗi báo hiệu khoá param mang dữ liệu vị trí (khớp chuỗi con, không phân biệt hoa thường — cùng
    /// luật với `forbiddenKeyFragments`): toạ độ trên máy mà lọt vào analytics là đổi hẳn nhãn quyền riêng tư.
    static let locationKeyFragments = ["lat", "lon", "coord", "gps", "location"]

    /// Kiểm chéo giữa nhiều catalog (lõi + app) — `violations` chỉ nhìn từng catalog một nên không thấy:
    /// - tên trùng giữa hai catalog, hoặc trùng ngay trong một catalog (GA4 gộp hai event làm một);
    /// - mẫu có tên không thuộc catalog nào (mẫu mồ côi: event gửi đi mà không ai khai tên);
    /// - khoá param của mẫu chứa mảnh vị trí (`locationKeyFragments`).
    /// Nhận danh sách tên thuần để nơi gọi truyền `Catalog.allCases.map(\.rawValue)`. Rỗng = đạt.
    static func crossCatalogViolations(catalogs: [[String]], samples: [AppEvent]) -> [String] {
        var out: [String] = []

        // Đếm số lần mỗi tên xuất hiện trên MỌI catalog (kể cả lặp trong cùng một catalog).
        var dem: [String: Int] = [:]
        for catalog in catalogs {
            for ten in catalog { dem[ten, default: 0] += 1 }
        }
        for (ten, so) in dem.sorted(by: { $0.key < $1.key }) where so > 1 {
            out.append("tên event '\(ten)' khai \(so) lần trong các catalog — đổi tên một bên")
        }

        let daKhai = Set(dem.keys)
        for e in samples where !daKhai.contains(e.name) {
            out.append("mẫu '\(e.name)' không thuộc catalog nào — khai tên trong EventNameCatalog hoặc bỏ mẫu")
        }

        for e in samples {
            for key in e.parameters.keys.sorted() {
                for manh in locationKeyFragments where key.lowercased().contains(manh) {
                    out.append("param '\(key)' của \(e.name) trông như dữ liệu vị trí (chứa '\(manh)')")
                }
            }
        }
        return out
    }

    /// Danh sách vi phạm (rỗng = đạt):
    /// - mỗi tên trong `names` phải có ít nhất một mẫu — đây là điều kiện cần của mọi kiểm param bên dưới: các
    ///   kiểm đó chỉ duyệt mẫu, nên một tên KHÔNG có mẫu là một tên chúng hoàn toàn mù;
    /// - tên đúng chuẩn GA4: ≤ 40 ký tự, snake_case thường, chỉ [a-z0-9_];
    /// - mỗi mẫu ≤ 25 param, giá trị chuỗi ≤ 100 ký tự, khoá không chứa id|name|path.
    static func violations<N: EventNameCatalog>(_ names: N.Type, samples: [AppEvent]) -> [String] {
        var out: [String] = []
        let coMau = Set(samples.map(\.name))
        let hopLe = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyz0123456789_")

        for ten in N.allCases {
            let n = ten.rawValue
            if !coMau.contains(n) {
                out.append("tên '\(n)' chưa có mẫu")
            }
            if n.count > maxNameLength {
                out.append("tên event '\(n)' vượt \(maxNameLength) ký tự")
            }
            if n != n.lowercased() {
                out.append("tên event '\(n)' phải snake_case thường")
            }
            if n.rangeOfCharacter(from: hopLe.inverted) != nil {
                out.append("tên event '\(n)' chứa ký tự ngoài [a-z0-9_]")
            }
        }

        for e in samples {
            if e.parameters.count > maxParameters {
                out.append("event \(e.name) có \(e.parameters.count) param, GA4 tối đa \(maxParameters)")
            }
            for (key, value) in e.parameters.sorted(by: { $0.key < $1.key }) {
                for cam in forbiddenKeyFragments where key.lowercased().contains(cam) {
                    out.append("param '\(key)' của \(e.name) chứa từ khoá cấm '\(cam)'")
                }
                if case .string(let s) = value, s.count > maxStringLength {
                    out.append("param '\(key)' của \(e.name) dài \(s.count) ký tự, GA4 tối đa \(maxStringLength)")
                }
            }
        }
        return out
    }
}
