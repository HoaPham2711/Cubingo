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

    static let turnSeconds = 0.9

    init(orientation: simd_quatf, replayFrom: simd_quatf? = nil, token: Int = 0) {
        self.orientation = orientation
        self.replayFrom = replayFrom
        self.token = token
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
