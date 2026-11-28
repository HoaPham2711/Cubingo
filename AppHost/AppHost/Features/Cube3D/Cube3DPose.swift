import simd

/// Màu RGB thô cho từng ô (khoá = chỉ số facelet Kociemba). Ô không có trong `colors` hiện màu thân khối (mặt chưa
/// quét). Có `paint` thì khối bỏ qua bảng màu.
struct Cube3DPaint: Equatable {
    var colors: [Int: CubeRGB]
}

/// Tư thế cả khối (khung khối → thế giới), áp TRƯỚC góc nhìn chuẩn. `orientation` đổi ⇒ quay mượt tới đó; `token` đổi
/// và có `replayFrom` ⇒ về tức thì `replayFrom` rồi quay lại tới `orientation` (diễn lại động tác).
struct Cube3DPose: Equatable {
    var orientation: simd_quatf
    var replayFrom: simd_quatf?
    var token: Int
    /// Góc nhìn lệch sang TRÁI thay vì phải (màn quét: mặt vừa quét — đã sang trái sau khi xoay — vẫn thấy được).
    var viewFromLeft: Bool
    /// Tư thế giữa cho bước quay lớn hơn 90° (lật 180°): nội suy "đường ngắn nhất" của quaternion không xác định chiều
    /// ở 180° ⇒ đi qua `via` để chắc chắn quay đúng chiều động tác.
    var via: simd_quatf?

    static let turnSeconds = 0.9

    init(orientation: simd_quatf, replayFrom: simd_quatf? = nil, token: Int = 0, viewFromLeft: Bool = false,
         via: simd_quatf? = nil) {
        self.orientation = orientation
        self.replayFrom = replayFrom
        self.token = token
        self.viewFromLeft = viewFromLeft
        self.via = via
    }

    /// Góc quay (radian, 0…π) giữa hai hướng.
    static func angle(_ a: simd_quatf, _ b: simd_quatf) -> Float {
        2 * acos(min(1, abs(simd_dot(a.vector, b.vector))))
    }

    /// Các tư thế phải đi qua từ `from` tới `to`: quay hơn ~100° và có `via` ⇒ qua `via` trước.
    static func waypoints(from: simd_quatf, to: simd_quatf, via: simd_quatf?) -> [simd_quatf] {
        if let via, angle(from, to) > .pi * 100 / 180 { return [via, to] }
        return [to]
    }
}

/// Hiệu ứng một lần: lắc cả khối, hoặc nháy đỏ các ô (chỉ số facelet). `token` đổi ⇒ chạy lại.
struct Cube3DEffect: Equatable {
    enum Kind: Equatable {
        case shake
        case flash([Int])
    }

    let kind: Kind
    let token: Int
}
