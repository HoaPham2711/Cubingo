# Cubingo Đợt A — 3×3 trọn vẹn — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Người mới cầm khối 3×3 xáo trộn, mở app, quét (hoặc nhập tay), kiểm tra, rồi giải xong khối thật bằng Teach me (7 chặng, quét kiểm tra sau mỗi chặng) hoặc Just solve it, được chỉ từng bước bằng khối 3D — tiếng Anh, giao diện sáng.

**Architecture:** Logic thuần Swift (mô hình khối, bộ giải, phân nhóm màu, máy trạng thái chỉ bước) tách khỏi View và test ở `-O0`; View SwiftUI + RealityKit (`RealityView`, iOS 18) + AVFoundation chỉ là lớp mỏng gọi logic đó. Bảng tra Kociemba sinh trước bằng tool `-O` và nhúng làm resource. Khung app bỏ tab bar: một `NavigationStack` gốc ở màn chọn khối, Settings mở bằng sheet.

**Tech Stack:** Swift 5 / SwiftUI, RealityKit (`RealityView`, camera `.virtual`), AVFoundation (`AVCaptureVideoDataOutput`), XCTest, XcodeGen, `tools/dev/run_tests.py`, `tools/dev/ui_shots.py`.

**Spec:** `docs/superpowers/specs/2026-11-27-cubingo-design.md` (đọc kèm; bản phác `docs/superpowers/specs/assets/2026-11-27-cubingo/`).

## Global Constraints

- iOS tối thiểu **18.0** (`AppHost/project.yml` `deploymentTarget`). iPhone dọc + iPad mọi hướng; bố cục theo `horizontalSizeClass`/bề rộng, không theo idiom.
- Không chữ **"Rubik"** ở bất kỳ chuỗi UI, tên type hiển thị, ảnh nào. Dùng "cube".
- Không mã GPL/LGPL. Bộ giải Kociemba **tự viết** theo mô tả công khai của thuật toán hai pha; không chép mã nguồn có giấy phép copyleft.
- Chạy offline hoàn toàn: quét, giải, 3D không gọi mạng. Không ARKit/LiDAR — chỉ camera sau thường.
- Bảng màu khối **tự nhận diện**: không có giả định bảng màu chuẩn ở logic giải/chữ; mọi chữ nhắc màu là chuỗi có tham số màu (`String(localized: "Hold: \(top) on top, \(front) facing you")`), không nối chuỗi.
- Giao diện **chỉ sáng** (`colorScheme: .light`), phong cách A: nhấn cam `#FF7A00`, xanh lá "xong", thẻ trắng bo 22–24 pt, chữ SF Rounded đậm, nền gradient kem–hồng nhạt.
- Chuỗi UI tiếng Anh (String Catalog nguồn `en`); qua biến `String` ⇒ bọc `String(localized:)`. Bản `vi` để Đợt B (`[i18n] languages` giữ `["en"]`).
- Cỡ chữ cố định ⇒ `.scaledFont(size:weight:design:)`, không `.font(.system(size:))`. Hộp xác nhận ⇒ `.alert`.
- Mỗi tính năng một thư mục `AppHost/AppHost/Features/<Tên>/`, type mang tiền tố `<Tên>`; test ở `AppHost/AppHostTests/<Tên>/`. Không `public`, không `@EnvironmentObject` cho đối tượng nghiệp vụ; phụ thuộc qua `FlowDependencies` dựng một lần ở `AppHostApp`.
- `#if INTERNAL` chỉ ở `AppHost/AppHost/Internal/AppInternalEntry.swift`; seed preview tên `…PreviewSeed`, trong `#if targetEnvironment(simulator)`.
- Không sửa `Core/` (lớp đồng bộ). Màn lõi nào không đọc được trên nền sáng ⇒ ghi nợ cho template, không vá tại app.
- Thêm/xoá file ⇒ `cd AppHost && xcodegen generate`. Test chỉ ở `Debug` qua `tools/dev/run_tests.py`; rc 3 không phải xanh. Test > 2 s phải ghi lý do trong comment.
- Đợt A KHÔNG làm: 2×2 (thẻ hiện mờ "SOON"), Patterns, tiếng Việt, analytics event mới (chỉ `.trackScreen`), SolveLog, AR, bấm giờ.
- Mọi commit kết thúc bằng trailer theo skill `commit-convention` (`Co-Authored-By: Claude <model đang chạy> <noreply@anthropic.com>`).

## Review Focus

1. **Người dùng cầm khối khác hướng app đang giả định** (sau một bước xoay cả khối `y`, sau lật z2…) — mỗi bước xoay cả khối phải kèm chip "Hold: … on top, … facing you" khớp đúng trạng thái sau xoay. Test: Task 7 `testMoiBuocXoayCaKhoiCoChipHoldDung`.
2. **Đỏ/cam lẫn nhau dưới đèn vàng ấm** — phân nhóm phải giữ đúng 9 ô/màu và tách đỏ–cam sau cân trắng. Test: Task 10 `testDenAmVanTachDoCam`.
3. **Quét mặt trên/dưới bị nghiêng sai hướng** — 16 tổ hợp xoay U/D: tổ hợp hợp lệ duy nhất thì tự sửa, nhiều tổ hợp thì không tự sửa. Test: Task 3 `testSuaHuongQuetMatTrenDuoi`.
4. **Back/Replay vắt qua ranh giới chặng và qua bước xoay cả khối** — trạng thái hiển thị luôn bằng trạng thái đầu áp các bước đã làm. Test: Task 14 `testBackQuaRanhGioiChangGiuTrangThaiNhatQuan`.
5. **Khối quét vào đã giải, hoặc lập lại lời giải sau quét kiểm tra mà vài chặng đã xong** — chặng rỗng bị bỏ qua, không hiện "0 / 0". Test: Task 14 `testChangRongDuocBoQua`, Task 7 `testKhoiDaGiaiChoRaToanChangRong`.

---

## Quy ước chung cho mọi task

- **Chạy test một class:** `tools/dev/run_tests.py <TenClass>` — xanh = rc 0, có dòng `Executed N tests, with 0 failures` và N > 0.
- **Thêm file:** sau khi tạo file mới ⇒ `cd AppHost && xcodegen generate && cd ..`.
- **Commit:** chỉ `git add` file của task; message dạng `feat(<tính năng>): …` tiếng Việt + trailer.
- **Toạ độ khối** (dùng ở Task 2, 3, 10, 13): x sang phải (mặt R = +x), y lên (U = +y), z về phía người nhìn (F = +z). Thứ tự mặt và đánh số ô theo chuẩn Kociemba: chuỗi 54 ký tự `U1..U9 R1..R9 F1..F9 D1..D9 L1..L9 B1..B9`, mỗi mặt đọc theo hàng (r, c ∈ 0…N−1):
  | Mặt | Nhìn từ | Hàng trên cùng là | Toạ độ ô (N=3, toạ độ ∈ {−1,0,1}) |
  |---|---|---|---|
  | U | trên | phía B | (c−1, 1, r−1) |
  | R | phải | phía U, cột 0 sát F | (1, 1−r, 1−c) |
  | F | trước | phía U | (c−1, 1−r, 1) |
  | D | dưới | phía F | (c−1, −1, 1−r) |
  | L | trái | phía U, cột 0 sát B | (−1, 1−r, c−1) |
  | B | sau | phía U, cột 0 sát R | (1−c, 1−r, −1) |
  Tổng quát N: chỉ số i ↦ toạ độ nhân đôi `2i − (N−1)`.
- **Bước xoay** (quarter turn theo chiều kim đồng hồ khi nhìn từ phía mặt đó): R = lớp x>0 quay −90° quanh +x; L = lớp x<0 quay +90° quanh +x; U = y>0, −90° quanh +y; D = y<0, +90° quanh +y; F = z>0, −90° quanh +z; B = z<0, +90° quanh +z. Xoay cả khối: `x` như R, `y` như U, `z` như F (mọi lớp).

---

## Phase 0 — Vỏ app

### Task 1: iOS 18, theme sáng, bỏ onboarding, khung một luồng + màn chọn khối

**Files:**
- Modify: `AppHost/project.yml` (deploymentTarget `18.0`; `info.properties.NSCameraUsageDescription` = "This app uses the camera to read the colors of your cube. Images never leave your device." — không viết tên app: `lint_identity.py` cấm literal định danh)
- Modify: `AppHost/AppHost/AppTheme.swift`, `AppHost/AppHost/AppOnboarding.swift`, `AppHost/AppHost/AppShellView.swift`, `AppHost/AppHost/HomeView.swift`, `AppHost/AppHost/AppHostApp.swift`, `AppHost/AppHost/AppPreview.swift`
- Create: `AppHost/AppHost/Features/Style/StyleBackground.swift`, `StyleThickButton.swift`, `StyleCard.swift`
- Create: `AppHost/AppHost/Features/Prefs/PrefsStore.swift`, `PrefsSection.swift`
- Create: `AppHost/AppHost/Features/Flow/FlowRoute.swift`, `FlowModel.swift`, `FlowDependencies.swift`, `FlowPickerView.swift`, `README.md`
- Test: `AppHost/AppHostTests/SmokeTests.swift` (sửa), `AppHost/AppHostTests/Prefs/PrefsStoreTests.swift`, `AppHost/AppHostTests/Flow/FlowModelTests.swift`

**Interfaces:**
- Produces:
  - `AppTheme.theme: DSTheme` — `colorScheme: .light`, `accent #FF7A00` (qua `.withAccent(hex: 0xFF7A00)` trên một palette sáng khai đủ mọi trường của `DSTheme.Palette`: `pageBackground #FFF6EE`, `cardBackground #FFFFFF`, `sheetBackground #FFFFFF`, `statusGood #2DBE60`, `textPrimary #2B1D14`, `textSecondary` = textPrimary 60 %, `textTertiary` 40 %, hairline/ring/glass là đen độ mờ 0,08–0,15; ba `chartSeries*` giữ của `.standard`).
  - `enum PrefsSpeed: String, CaseIterable { case slow, medium, fast }` với `quarterTurnSeconds: Double` = 0.9 / 0.5 / 0.25.
  - `@MainActor final class PrefsStore: ObservableObject { init(defaults: UserDefaults); @Published var speed: PrefsSpeed; @Published var haptics: Bool; @Published var showNotation: Bool }` — mặc định `.medium`, `true`, `true`; khoá `prefs.speed|haptics|notation`.
  - `enum FlowPuzzle: String, CaseIterable { case cube3, cube2, pyramid, cube4 }` với `isAvailable` (chỉ `cube3` ở Đợt A).
  - `enum FlowRoute: Hashable { case scan, review(manual: Bool), mode, guide(GuideMode), done }` — `GuideMode` khai ở Task 14; ở task này tạm khai `enum GuideMode: Hashable { case teach, quick }` trong `FlowRoute.swift`, Task 14 chuyển nó về `Features/Guide/`.
  - `struct FlowDependencies { let prefs: PrefsStore; let haptic: (FlowHaptic) -> Void }` với `enum FlowHaptic { case capture, success, warning }` (Task 5/11 thêm trường `quickSolver`, `cameraAuth`).
  - `@MainActor final class FlowModel: ObservableObject { @Published var path: [FlowRoute]; @Published var puzzle: FlowPuzzle?; func choose(_ p: FlowPuzzle); func startOver() }` — `choose` chỉ nhận puzzle `isAvailable`, đẩy `.scan`; `startOver` xoá path và mọi trạng thái khối.
  - `AppShellView` không còn dùng `RootShellView`: dựng `HomeView` + `.sheet(isPresented: $showSettings) { SettingsView(...) }`; `tabRouter.requested == .settings` hoặc `AppPreview.current == .settings` ⇒ mở sheet. `SettingsView.appSections` chứa `PrefsSection(prefs:)` (Animation speed · Haptics · Show move notation).
  - `HomeView(updateChecker:openStore:flow:deps:onOpenSettings:)` = `NavigationStack(path: $flow.path)` gốc `FlowPickerView`, giữ banner cập nhật ở đầu; `.navigationDestination(for: FlowRoute.self)` trả `EmptyView()` cho mọi route chưa làm (các task sau thay).
  - `FlowPickerView`: tiêu đề "Which cube do you have?"; thẻ 3×3 "The classic", 2×2 "Pocket cube" (mờ, nhãn SOON ở Đợt A), Pyramid, 4×4 (mờ, SOON; chạm ⇒ `.alert` "Coming in a future update"); dòng "Not sure? Count the squares on one side"; nút tròn Settings góc trên phải (không tab bar, không nút Patterns ở Đợt A). iPhone: lưới 2 cột; regular: 4 cột, `readableContentWidth()`. `.trackScreen("flow_picker")`.
  - `AppOnboarding.flow` trả luồng rỗng (`allPages: []`) ⇒ mở app vào thẳng màn chọn khối.

- [ ] **Step 1: Viết test hỏng**

```swift
// SmokeTests (sửa)
func testThemeSangCamCuaCubingo() {
    XCTAssertEqual(AppTheme.theme.colorScheme, .light)
    XCTAssertEqual(AppTheme.theme.palette.accent, Color(hex: 0xFF7A00))
}
func testMoAppVaoThangManChonKhoi() {
    XCTAssertTrue(AppOnboarding.flow(.firstRun).isEmpty)
}
// PrefsStoreTests
func testMacDinhVaLuuLai() // suite UserDefaults riêng: speed == .medium, haptics, showNotation true; đặt .fast ⇒ store mới cùng suite đọc ra .fast
func testThoiLuongXoayTheoTocDo() // slow 0.9, medium 0.5, fast 0.25
// FlowModelTests
func testChiChonDuocKhoiDangCo() // choose(.cube2) ⇒ path rỗng; choose(.cube3) ⇒ path == [.scan], puzzle == .cube3
func testStartOverXoaHet() // sau choose + append .mode ⇒ startOver ⇒ path rỗng, puzzle nil
```

- [ ] **Step 2:** `tools/dev/run_tests.py SmokeTests` — Expected: FAIL (`colorScheme` đang `.dark`, `PrefsStore` chưa có).
- [ ] **Step 3:** Làm các file trên theo Interfaces; `xcodegen generate`.
- [ ] **Step 4:** `tools/dev/run_tests.py SmokeTests PrefsStoreTests FlowModelTests` — Expected: PASS.
- [ ] **Step 5:** `python3 tools/i18n/lint_localizable.py` sạch; `python3 tools/dev/ui_shots.py home settings whatsNew` iPhone dọc + iPad ngang — xem ảnh: Settings/What's New của lõi đọc được trên nền sáng. Màn nào không đọc được ⇒ ghi dòng nợ vào `docs/ROADMAP.md` mục "Nợ đã biết" (sửa ở template), không vá ở app.
- [ ] **Step 6: Commit** `feat(flow): khung một luồng, theme sáng, màn chọn khối`

---

## Phase 1 — Mô hình khối (logic thuần, `Features/Cube/`)

### Task 2: Mặt, bước, hình học ô, áp bước lên facelet

**Files:**
- Create: `AppHost/AppHost/Features/Cube/CubeFace.swift`, `CubeMove.swift`, `CubeGeometry.swift`, `CubeFacelets.swift`
- Test: `AppHost/AppHostTests/Cube/CubeMoveTests.swift`, `CubeGeometryTests.swift`

**Interfaces:**
- Produces:
  - `enum CubeFace: Int, CaseIterable { case u, r, f, d, l, b }` + `var opposite: CubeFace`, `var letter: Character`.
  - `struct CubeColor: Hashable { let raw: UInt8 }` (0…5, là nhãn nhóm màu, KHÔNG phải màu chuẩn).
  - `struct CubeMove: Hashable { enum Axis { case face(CubeFace), x, y, z }; let axis: Axis; let turns: Int }` (`turns` ∈ {1, 2, 3} = xuôi, kép, ngược) + `inverse`, `isRotation`, `notation: String` ("R", "U'", "F2", "x", "y'"), `static func parse(_ s: String) -> [CubeMove]?` (tách theo khoảng trắng; ký hiệu lạ ⇒ `nil`).
  - `struct CubeGeometry { let n: Int; static func of(n: Int) -> CubeGeometry; func permutation(_ m: CubeMove) -> [Int] }` — `new[i] = old[perm[i]]`; sinh từ toạ độ 3D bảng "Toạ độ khối" + phép quay của "Bước xoay", cache theo (n, move). Hỗ trợ n = 2, 3.
  - `struct CubeFacelets: Hashable { let n: Int; var stickers: [CubeColor] }` + `static func solved(n:)` (ô của mặt k mang `CubeColor(raw: k)`), `func applying(_ m: CubeMove) -> CubeFacelets`, `func applying(_ ms: [CubeMove]) -> CubeFacelets`, `var isSolved: Bool` (mỗi mặt một màu, không đòi đúng nhãn), `func color(_ face: CubeFace, _ index: Int) -> CubeColor`, `func center(_ face: CubeFace) -> CubeColor` (n=3), `init?(kociemba: String)` / `var kociemba: String` (n=3, chữ cái theo mặt của tâm — chỉ dùng cho test và tool).

- [ ] **Step 1: Viết test hỏng**

```swift
func testRTrenKhoiDaGiaiKhopChuoiKociemba() {
    let s = CubeFacelets.solved(n: 3).applying(CubeMove.parse("R")!)
    XCTAssertEqual(s.kociemba, "UUFUUFUUFRRRRRRRRRFFDFFDFFDDDBDDBDDBLLLLLLLLLUBBUBBUBB")
}
func testUTrenKhoiDaGiaiKhopChuoiKociemba() {
    let s = CubeFacelets.solved(n: 3).applying(CubeMove.parse("U")!)
    XCTAssertEqual(s.kociemba, "UUUUUUUUUBBBRRRRRRRRRFFFFFFDDDDDDDDDFFFLLLLLLLLLBBBBBB")
}
func testChuKy() // n = 2 và 3: mỗi bước mặt ^4 = solved; "R U R' U'" ^6 = solved; "R U" ^105 = solved (n=3); x^4, y^4, z^4 = solved
func testBuocVaNghichDaoTrieuTieu() // 200 bước ngẫu nhiên (LCG cục bộ trong file test, seed 1 — CubeRandom chưa có) rồi các nghịch đảo theo thứ tự ngược ⇒ solved
func testXoayCaKhoiBangTichCacLop() // "x" == "R L'" và lớp giữa: kiểm  x ⇒ tâm F sang U: applying(x).center(.u) == solved.center(.f)
func testParseVaNotation() // parse("R U' F2 x y' z2")?.map(\.notation) == ["R","U'","F2","x","y'","z2"]; parse("Q") == nil; parse("") == []
func testKhoiHaiHai() // n=2: solved.applying(R).isSolved == false; R4 == solved; stickers.count == 24
```

- [ ] **Step 2:** `tools/dev/run_tests.py CubeMoveTests CubeGeometryTests` — Expected: FAIL (type chưa có).
- [ ] **Step 3:** Làm bốn file theo Interfaces.
- [ ] **Step 4:** Chạy lại — Expected: PASS.
- [ ] **Step 5: Commit** `feat(cube): mô hình facelet, bước xoay, hình học N×N`

### Task 3: Cubie, trạng thái ngẫu nhiên có seed, kiểm hợp lệ, sửa hướng quét

**Files:**
- Create: `AppHost/AppHost/Features/Cube/CubeCubies.swift`, `CubeRandom.swift`, `CubeValidation.swift`
- Test: `AppHost/AppHostTests/Cube/CubeCubiesTests.swift`, `CubeValidationTests.swift`

**Interfaces:**
- Consumes: `CubeFacelets`, `CubeMove`, `CubeFace` (Task 2).
- Produces:
  - `struct CubeCubies: Hashable { var cp: [Int]; var co: [Int]; var ep: [Int]; var eo: [Int] }` — thứ tự góc `URF UFL ULB UBR DFR DLF DBL DRB`, cạnh `UR UF UL UB DR DF DL DB FR FL BL BR`, bảng `cornerFacelet`/`edgeFacelet` chuẩn Kociemba. `static let solved`; `init(facelets: CubeFacelets) throws(CubePieceError)` — đổi nhãn màu theo 6 tâm (màu của tâm U ⇒ mặt U…); `func facelets(centers: [CubeFace: CubeColor]) -> CubeFacelets`; `func multiplied(_ other: CubeCubies) -> CubeCubies`; `static func move(_ m: CubeMove) -> CubeCubies` (chỉ bước mặt); `var cornerTwistSum: Int`, `var edgeFlipSum: Int`, `var permutationParityMatches: Bool`.
  - `enum CubePieceError: Error, Equatable { case impossiblePiece(stickers: [Int]) }` — bộ màu không là miếng nào (hai màu đối diện, trùng màu, hoặc góc ngược chiều gương); `stickers` là chỉ số facelet của miếng đó.
  - `struct CubeRandom: RandomNumberGenerator { init(seed: UInt64) }` (SplitMix64) + `static func state(using: inout some RandomNumberGenerator) -> CubeCubies` (hoán vị + định hướng đều, ép tổng xoắn ≡ 0 mod 3, tổng lật chẵn, chẵn lẻ khớp).
  - `enum CubeIssue: Equatable { case colorCount(over: CubeColor, under: CubeColor, overCount: Int, underCount: Int, suspects: [Int]); case impossiblePiece(stickers: [Int]); case twistedCorner; case flippedEdge; case swappedPieces }`
  - `enum CubeValidation { static func firstIssue(_ f: CubeFacelets, confidence: [Double]?) -> CubeIssue?; static func repairScanOrientation(_ f: CubeFacelets) -> CubeFacelets? }` — thứ tự kiểm theo spec 5.4 (đếm màu ⇒ miếng không tồn tại ⇒ xoắn góc ⇒ lật cạnh ⇒ đổi chỗ); `suspects` của lỗi đếm = các ô của màu thừa có `confidence` thấp nhất (đủ số ô thừa; không có confidence ⇒ rỗng). `repairScanOrientation`: chỉ gọi khi đếm màu đúng mà còn lỗi; thử 16 tổ hợp xoay mặt U (0…3 × 90°) × mặt D (0…3), trả tổ hợp khác (0,0) nếu nó là tổ hợp hợp lệ DUY NHẤT, ngược lại `nil`.

- [ ] **Step 1: Viết test hỏng**

```swift
func testFaceletCubieHaiChieu() // 200 trạng thái CubeRandom(seed: 7): CubeCubies(facelets: c.facelets(centers: chuẩn)) == c
func testBuocMatTrenCubieKhopFacelet() // với 18 bước mặt: CubeCubies(facelets: solved.applying(m)) == CubeCubies.move(m)
func testDoiNhanTheoTam() // bảng màu hoán vị (raw 0↔2, 1↔5): facelets của trạng thái ngẫu nhiên với tâm hoán vị ⇒ CubeCubies vẫn ra đúng trạng thái
func testTrangThaiNgauNhienLuonHopLe() // 500 seed: firstIssue == nil
func testLoiDemMau() // đổi 1 ô cam (không tâm) thành đỏ ⇒ .colorCount(over: đỏ, under: cam, overCount: 10, underCount: 8, suspects.count == 1); confidence thấp nhất ở đúng ô bị đổi ⇒ suspects == [ô đó]
func testMienKhongTonTai() // cạnh UF đổi thành màu U + màu D (giữ số đếm bằng cách đổi bù ở cạnh khác) ⇒ .impossiblePiece(stickers chứa hai chỉ số của UF)
func testGocXoanCanhLatDoiCho() // xoắn góc URF 1 nấc ⇒ .twistedCorner; lật cạnh UF ⇒ .flippedEdge; đổi chỗ hai cạnh UR,UF ⇒ .swappedPieces
func testSuaHuongQuetMatTrenDuoi() {
    // Với 20 trạng thái ngẫu nhiên và mỗi tổ hợp (u,d) ≠ (0,0) trong 16: xoay sẵn mặt U u nấc, D d nấc (chỉ xoay lưới ô của mặt đó, như người dùng nghiêng sai)
    // ⇒ nếu bản gốc là tổ hợp hợp lệ duy nhất: repairScanOrientation trả đúng bản gốc; nếu không duy nhất: trả nil.
    // Khối đã giải: mọi tổ hợp hợp lệ ⇒ nil (không tự sửa).
}
```

- [ ] **Step 2:** `tools/dev/run_tests.py CubeCubiesTests CubeValidationTests` — Expected: FAIL.
- [ ] **Step 3:** Làm ba file theo Interfaces.
- [ ] **Step 4:** Chạy lại — Expected: PASS. Chứng minh test gác: `python3 tools/factory/mutate.py` đổi điều kiện `% 3` của tổng xoắn ⇒ `testGocXoanCanhLatDoiCho` đỏ.
- [ ] **Step 5: Commit** `feat(cube): cubie, trạng thái ngẫu nhiên, kiểm hợp lệ và sửa hướng quét`

---

## Phase 2 — Bộ giải (`Features/Solver/`)

### Task 4: Toạ độ và bảng tra Kociemba (tool sinh + resource + nạp)

**Files:**
- Create: `AppHost/AppHost/Features/Solver/SolverKociembaCoords.swift` (chỉ `import Foundation`)
- Create: `AppHost/AppHost/Features/Solver/SolverKociembaTables.swift`
- Create: `tools/app/kociemba/main.swift`, `tools/app/kociemba/gen_tables.sh`, `tools/app/kociemba/README.md`
- Create (sinh ra, commit): `AppHost/AppHost/Features/Solver/Resources/kociemba-tables.bin`
- Test: `AppHost/AppHostTests/Solver/SolverKociembaTablesTests.swift`

**Interfaces:**
- Consumes: `CubeCubies` (Task 3) — `SolverKociembaCoords.swift` và `CubeCubies.swift` phải biên dịch được bằng `swiftc` ngoài Xcode (chỉ Foundation) để tool dùng lại.
- Produces:
  - Toạ độ chuẩn Kociemba: `twist` 0…2186, `flip` 0…2047, `sliceSorted` 0…11879 (phase 1 dùng `sliceSorted / 24` 0…494), `corners` 0…40319, `udEdges` 0…40319, `slicePhase2 = sliceSorted % 24`. `enum SolverKociembaCoords` có `static func twist(_ c: CubeCubies) -> Int` … và `static func buildMoveTable(…)`, `static func buildPruneTable(…)`.
  - Bảng: move tables `[UInt16]` — 18 bước: `twistMove` 2187×18, `flipMove` 2048×18, `sliceSortedMove` 11880×18; 10 bước pha 2 (U, U2, U', D, D2, D', R2, L2, F2, B2): `cornersMove` 40320×10, `udEdgesMove` 40320×10 (`udEdges` chỉ xác định dưới nhóm pha 2); prune 4 bit/ô: `twistSlicePrune` 2187×495, `flipSlicePrune` 2048×495, `cornersSlicePrune` 40320×24, `udEdgesSlicePrune` 40320×24.
  - File `kociemba-tables.bin`: header ASCII `KCB1`, `UInt32` số bảng, mỗi bảng = `UInt8` độ dài tên + tên UTF-8 + `UInt8` kiểu (1 = UInt16, 2 = nibble) + `UInt32` số phần tử + dữ liệu little-endian. Kích thước dự kiến ≈ 4,2 MB.
  - `final class SolverKociembaTables: @unchecked Sendable { static func load(bundle: Bundle) throws -> SolverKociembaTables; static func load(data: Data) throws -> SolverKociembaTables }` — bất biến sau khi nạp; lỗi định dạng ⇒ `throw`, không crash.
  - `tools/app/kociemba/gen_tables.sh` = `swiftc -O CubeFace.swift CubeMove.swift CubeCubies.swift SolverKociembaCoords.swift main.swift -o <scratch>` rồi chạy ra đúng đường resource. README ghi: bảng chỉ sinh lại khi đổi toạ độ; nguồn thuật toán là mô tả công khai hai pha, không chép mã copyleft.

- [ ] **Step 1: Viết test hỏng**

```swift
func testNapDuocVaDungKichThuoc() // load(bundle: .main): twistMove.count == 2187*18, cornersMove.count == 40320*10 … udEdgesSlicePrune có 40320*24 phần tử
func testMoveTableKhopTinhLai() // 200 (toạ độ, bước) ngẫu nhiên seed 3 mỗi bảng: bảng == tính trực tiếp bằng CubeCubies.move + toạ độ
func testPruneTableGocBangKhong() // prune(solved) == 0 cả 4 bảng; với 50 trạng thái cách solved đúng 1 bước phase 1: twistSlicePrune ≤ 1
func testFileHongThiNem() // load(data: Data("KCB0".utf8)) throws; data cắt cụt throws
```

- [ ] **Step 2:** `tools/dev/run_tests.py SolverKociembaTablesTests` — Expected: FAIL.
- [ ] **Step 3:** Viết coords + tool; chạy `bash tools/app/kociemba/gen_tables.sh` — Expected: in đường file và kích thước ≈ 4,2 MB. Viết `SolverKociembaTables`; `xcodegen generate` (`.bin` dưới `AppHost/` tự vào resources — kiểm trong `.xcodeproj` sinh ra).
- [ ] **Step 4:** Chạy lại test — Expected: PASS.
- [ ] **Step 5: Commit** `feat(solver): bảng tra Kociemba sinh trước + nạp từ resource` (kèm file `.bin`).

### Task 5: Just solve it — tìm hai pha, huỷ được, có hạn giờ

**Files:**
- Create: `AppHost/AppHost/Features/Solver/SolverKociembaSearch.swift`, `SolverQuick.swift`
- Modify: `AppHost/AppHost/Features/Flow/FlowDependencies.swift` (thêm `let quickSolver: SolverQuick`), `AppHost/AppHost/AppHostApp.swift` (dựng một lần)
- Test: `AppHost/AppHostTests/Solver/SolverQuickTests.swift`

**Interfaces:**
- Consumes: `SolverKociembaTables`, `CubeCubies`, `CubeMove`.
- Produces:
  - `final class SolverQuick: Sendable { init(tables: @escaping @Sendable () throws -> SolverKociembaTables); func solve(_ c: CubeCubies, maxLength: Int = 22, timeout: Duration = .seconds(1)) async throws -> [CubeMove] }` — nạp bảng lười một lần (lần gọi đầu); chạy ngoài main actor; kiểm `Task.isCancelled` định kỳ ⇒ `CancellationError`; hết giờ ⇒ trả lời giải tốt nhất đã có (dài ≤ 30); chưa có lời giải nào ⇒ `throw SolverQuickError.timedOut`. Khối đã giải ⇒ `[]`. Chỉ trả bước mặt (không x/y/z).

- [ ] **Step 1: Viết test hỏng**

```swift
// 30 trạng thái: chạy ở -O0, mỗi lời giải ~0,1–0,5 s ⇒ class này được phép > 2 s (ghi comment lý do).
func testLoiGiaiLuonDungTrenTrangThaiNgauNhien() async throws // CubeRandom(seed: 11), 30 trạng thái: c.multiplied(bước lời giải lần lượt) == .solved; count ≤ 30
func testKhoiDaGiaiVaMotBuoc() async throws // solved ⇒ []; mỗi bước trong 18: lời giải dài ≤ 1 và đúng
func testSuperflip() async throws // trạng thái superflip (mọi cạnh lật) ⇒ lời giải đúng (timeout 5 s trong test)
func testHuyDuoc() async // task.cancel() ngay sau khi bắt đầu ⇒ throws CancellationError
```

- [ ] **Step 2:** `tools/dev/run_tests.py SolverQuickTests` — Expected: FAIL.
- [ ] **Step 3:** Làm IDA* pha 1 (bỏ qua bước cùng mặt/đối diện thứ tự ngược) rồi pha 2 trên 10 bước; tiếp tục tìm lời giải ngắn hơn tới `maxLength` hoặc hết giờ.
- [ ] **Step 4:** Chạy lại — Expected: PASS.
- [ ] **Step 5: Commit** `feat(solver): Just solve it bằng Kociemba hai pha`

### Task 6: Teach me — hướng cầm, kiểu chặng, chặng 1–3

**Files:**
- Create: `AppHost/AppHost/Features/Solver/SolverStage.swift`, `SolverHold.swift`, `SolverAlgorithm.swift`, `SolverBeginnerF2L.swift`
- Test: `AppHost/AppHostTests/Solver/SolverHoldTests.swift`, `SolverBeginnerF2LTests.swift`

**Interfaces:**
- Consumes: `CubeFacelets`, `CubeMove`, `CubeColor`.
- Produces:
  - `enum SolverStageKind: Int, CaseIterable { case cross = 1, corners, middle, topCross, topFace, topCorners, topEdges }`.
  - `enum SolverAlgorithm: CaseIterable { case rightTrigger, rightInsert, leftInsert, crossMaker, sune, cornerCycle, edgeCycle; var moves: [CubeMove] }` với chuỗi chính xác: rightTrigger `R U R' U'`; rightInsert `U R U' R' U' F' U F`; leftInsert `U' L' U L U F U' F'`; crossMaker `F R U R' U' F'`; sune `R U R' U R U2 R'`; cornerCycle `R' F R' B2 R F' R' B2 R2`; edgeCycle `R U' R U R U R U' R' U' R2`.
  - `enum SolverReason: Equatable { case hold(top: CubeColor, front: CubeColor); case makeDaisy(edge: CubeColor); case dropToCross(edge: CubeColor); case liftCorner; case placeCorner(CubeColor, CubeColor); case insertEdge(CubeColor, CubeColor, toRight: Bool); case popEdge; case makeTopCross; case orientTopCorners; case placeTopCorners; case placeTopEdges; case alignTop }` — màu `edge` là màu bên (không phải màu nền) của cạnh.
  - `struct SolverStep: Equatable { let move: CubeMove; let reason: SolverReason?; let algorithm: SolverAlgorithm? }` — `reason` chỉ ở bước đầu một nhóm; mọi bước xoay cả khối mang `reason: .hold(top:front:)` của hướng cầm SAU bước đó.
  - `struct SolverStage: Equatable { let kind: SolverStageKind; let steps: [SolverStep]; let start: CubeFacelets; var end: CubeFacelets { start.applying(steps.map(\.move)) } }`.
  - `enum SolverHold { static func hold(of f: CubeFacelets) -> (top: CubeColor, front: CubeColor); static func rotations(from f: CubeFacelets, top: CubeColor, preferFront: CubeColor?) -> [CubeMove] }` — BFS ≤ 2 bước trong {x, y, z, ', 2}, ưu tiên giữ `preferFront` làm mặt trước, rồi ít bước nhất.
  - `enum SolverBeginnerF2L { static func cross(_ f: CubeFacelets, base: CubeColor) -> SolverStage; static func corners(_ f: CubeFacelets, base: CubeColor) -> SolverStage; static func middle(_ f: CubeFacelets, base: CubeColor) -> SolverStage }`. Quy tắc:
    - **Chặng 1 (daisy):** bước đầu là `SolverHold.rotations(top: màu đối diện base, preferFront: tâm F hiện tại)`. Rồi với mỗi cạnh có màu base chưa thành "cánh hoa" (ô base nằm trên mặt U quanh tâm): tìm sâu dần ≤ 4 bước trong {U, F, R, B, L và ', 2} sao cho số cánh tăng và không mất cánh nào (`reason: .makeDaisy`). Rồi với mỗi cánh: U tới khi màu bên của cánh nằm trên tâm cùng màu, xoay mặt đó 2 lần (`reason: .dropToCross`). Kết thúc: chữ thập base ở D, khớp tâm bên.
    - **Chặng 2:** với mỗi khe góc D chưa đúng: `y`/`y'`/`y2` đưa khe về DFR; góc cần đặt nằm ở D sai chỗ ⇒ xoay đưa khe của nó về DFR, `rightTrigger` một lần (`.liftCorner`), xoay về; U tới khi góc ở UFR; lặp `rightTrigger` tới khi khe đúng (≤ 5 lần) (`.placeCorner`).
    - **Chặng 3:** còn cạnh tầng U không mang màu đỉnh ⇒ xoay `y` để màu mặt-trước của cạnh nằm ở F, U khớp tâm, rồi `rightInsert` nếu màu kia của cạnh = tâm R, `leftInsert` nếu = tâm L. Không còn cạnh như vậy mà tầng giữa chưa xong ⇒ `y` đưa khe sai về FR, `rightInsert` (`.popEdge`).

- [ ] **Step 1: Viết test hỏng**

```swift
func testHoldVaXoay() // solved: hold == (raw 0, raw 2); rotations(top: raw 3, preferFront: raw 2) == [z2]; áp xong hold == (raw 3, raw 2)
func testChang1Den3TrenNamTramTrangThai() {
    // CubeRandom(seed: 21), 500 trạng thái, base = tâm U ban đầu:
    // cross.end: 4 cạnh base ở D, ô bên khớp tâm bên; corners.end: tầng D hoàn chỉnh; middle.end: hai tầng hoàn chỉnh.
    // Mỗi chặng ≤ 60 bước. Chạy xâu chuỗi: corners(cross.end), middle(corners.end).
}
func testThuatToanDungChuoi() // SolverAlgorithm.sune.moves.map(\.notation).joined(separator: " ") == "R U R' U R U2 R'" (và 6 cái còn lại)
func testBangMauKhacChuan() // tô lại bảng màu (hoán vị raw 1↔5, 2↔4) cùng trạng thái ⇒ các chặng vẫn đạt mục tiêu; số bước bằng nhau
```

- [ ] **Step 2:** `tools/dev/run_tests.py SolverHoldTests SolverBeginnerF2LTests` — Expected: FAIL.
- [ ] **Step 3:** Làm theo quy tắc trên.
- [ ] **Step 4:** Chạy lại — Expected: PASS.
- [ ] **Step 5: Commit** `feat(solver): Teach me chặng 1–3 (daisy, góc, tầng giữa)`

### Task 7: Teach me — chặng 4–7 và lời giải trọn

**Files:**
- Create: `AppHost/AppHost/Features/Solver/SolverBeginnerLastLayer.swift`, `SolverBeginner.swift`
- Test: `AppHost/AppHostTests/Solver/SolverBeginnerTests.swift`

**Interfaces:**
- Consumes: Task 6.
- Produces:
  - `enum SolverBeginnerLastLayer { static func topCross(_:) / topFace(_:) / topCorners(_:) / topEdges(_:) -> SolverStage }` (đều nhận `CubeFacelets` có hai tầng dưới xong, base ở D). Quy tắc (mỗi vòng chọn tiền-xoay `U^k`, k 0…3, theo luật; luật không áp được ⇒ thử 4 k, lấy k làm tiến triển nhiều nhất — phép thử vét cạn dưới đây là bằng chứng):
    - **4:** chấm ⇒ `crossMaker`; chữ L ⇒ U để L ở trái-sau rồi `crossMaker`; vạch ⇒ U để vạch ngang rồi `crossMaker`; lặp tới chữ thập.
    - **5:** 1 góc đúng ⇒ đưa về trước-trái; 0 góc ⇒ góc trước-trái có ô màu đỉnh nhìn sang trái; 2 góc ⇒ góc trước-trái có ô màu đỉnh nhìn về trước; rồi `sune`; lặp (≤ 6 lần).
    - **6:** có "đèn pha" (hai góc cùng một mặt bên cùng màu) ⇒ U để đèn pha ở sau rồi `cornerCycle`; không có ⇒ `cornerCycle` một lần rồi lặp; cuối chặng U cho góc khớp tâm (`.alignTop`).
    - **7:** có mặt bên đã xong ⇒ `y` để mặt đó ở sau, `edgeCycle`; không có ⇒ `edgeCycle` một lần; lặp (≤ 3) tới khi giải xong.
  - `enum SolverBeginner { static func solve(_ start: CubeFacelets, base: CubeColor) -> [SolverStage] }` — luôn trả đúng 7 chặng theo thứ tự; chặng đã đạt ⇒ `steps` rỗng (KHÔNG có bước hold thừa). Chọn `base` từ bảng màu là việc của `CubePalette.baseColor` (Task 8); test ở đây truyền `base` thẳng.

- [ ] **Step 1: Viết test hỏng**

```swift
func testVetCanTangCuoi() {
    // Mọi trạng thái tầng cuối hợp lệ có hai tầng dưới xong: định hướng góc (27) × định hướng cạnh (8) × hoán vị góc (24) × hoán vị cạnh (24),
    // lọc chẵn lẻ/tổng ⇒ ≈ 62 208 trạng thái. Với mỗi: chuỗi topCross→topFace→topCorners→topEdges cho .isSolved; mỗi chặng ≤ 40 bước.
    // Chạy -O0 có thể ~10–20 s ⇒ comment lý do (vét cạn là bằng chứng duy nhất cho các luật tầng cuối).
}
func testNamTramTrangThaiGiaiXong() // CubeRandom(seed: 31), 500: start.applying(mọi bước 7 chặng).isSolved; tổng bước ≤ 250
func testKhoiDaGiaiChoRaToanChangRong() // solve(solved) ⇒ 7 chặng, mọi steps rỗng
func testMoiBuocXoayCaKhoiCoChipHoldDung() // 100 trạng thái: mỗi bước isRotation ⇒ reason == .hold(top:front:) bằng SolverHold.hold(of: trạng thái sau bước)
func testChangDauBatDauBangHold() // trạng thái có tâm base ở F: bước đầu chặng 1 là xoay, reason .hold(top: đối diện base, …)
```

- [ ] **Step 2:** `tools/dev/run_tests.py SolverBeginnerTests` — Expected: FAIL.
- [ ] **Step 3:** Làm hai file.
- [ ] **Step 4:** Chạy lại — Expected: PASS. `mutate.py`: đổi một bước trong `edgeCycle` ⇒ `testVetCanTangCuoi` đỏ.
- [ ] **Step 5: Commit** `feat(solver): Teach me chặng 4–7, lời giải người mới trọn vẹn`

---

## Phase 3 — Màu, chữ, quét

### Task 8: Bảng màu đo được, toán màu, tên màu

**Files:**
- Create: `AppHost/AppHost/Features/Cube/CubePalette.swift`, `CubeColorMath.swift`, `CubeColorName.swift`
- Test: `AppHost/AppHostTests/Cube/CubeColorTests.swift`

**Interfaces:**
- Produces:
  - `struct CubeRGB: Hashable { var r, g, b: Double }` (sRGB 0…1).
  - `enum CubeColorMath { static func lab(_ c: CubeRGB) -> SIMD3<Double>; static func deltaE(_ a: CubeRGB, _ b: CubeRGB) -> Double (CIE76); static func chroma(_ c: CubeRGB) -> Double; static func whiteBalanced(_ samples: [CubeRGB], white: CubeRGB) -> [CubeRGB] }` — sRGB → tuyến tính → XYZ D65 → Lab; cân trắng von Kries trên RGB tuyến tính sao cho `white` thành xám cùng độ sáng.
  - `enum CubeColorName: String, CaseIterable { case white, yellow, orange, red, green, blue, purple, pink, black }` + `enum CubeColorShade { case light, dark }` + `static func nearest(_ c: CubeRGB) -> CubeColorName` (C* < 20 ⇒ white nếu L* ≥ 25, black nếu < 25; còn lại theo góc hue h° của Lab: red [345, 25), orange [25, 60), yellow [60, 105), green [105, 190), blue [190, 290), purple [290, 345); red/purple có L* > 70 ⇒ pink) + `func localized(shade: CubeColorShade?) -> String` (`String(localized: "white")`…, có shade ⇒ `String(localized: "light \(name)")` / `"dark \(name)"`).
  - `struct CubePalette: Equatable { let colors: [CubeColor: CubeRGB]; func name(_ c: CubeColor) -> String; func rgb(_ c: CubeColor) -> CubeRGB; var baseColor: CubeColor; static let manualDefault: CubePalette }` — `baseColor` (màu nền chặng 1 của Teach me): màu có chroma thấp nhất trong các màu `L* > 60`; không có ⇒ màu `L*` cao nhất. Hai màu cùng `CubeColorName` ⇒ màu L* cao hơn gắn shade `.light`, thấp hơn `.dark`. `manualDefault`: raw 0…5 (U R F D L B) = white, red, green, yellow, orange, blue với RGB chuẩn (#FFFFFF, #C41E3A, #009E60, #FFD500, #FF5800, #0051BA).

- [ ] **Step 1: Viết test hỏng**

```swift
func testLabVaDeltaE() // lab(trắng) ≈ (100, 0, 0) ±0.5; deltaE(x, x) == 0; deltaE(đỏ #C41E3A, cam #FF5800) > 20
func testTenMauChuan() // sáu RGB của manualDefault ⇒ đúng sáu tên; #8E44AD ⇒ purple; #FF8FC8 ⇒ pink; #202020 ⇒ black
func testCanTrangDuaTamTrangVeXam() // samples ám vàng (×(1.0, 0.9, 0.7)) ⇒ sau whiteBalanced, chroma(tâm trắng) < 3
func testHaiMauCungTenCoShade() // palette có hai xanh lá (#00A050, #7FD08F) ⇒ name trả "dark green" và "light green"
func testMauNen() // manualDefault.baseColor == raw 0 (white); palette không có trắng (thay bằng hồng nhạt #FFC0D0 và vàng) ⇒ màu chroma thấp nhất có L* > 60; mọi màu L* ≤ 60 ⇒ màu sáng nhất
```

- [ ] **Step 2:** `tools/dev/run_tests.py CubeColorTests` — Expected: FAIL.
- [ ] **Step 3:** Làm ba file.
- [ ] **Step 4:** Chạy lại — Expected: PASS.
- [ ] **Step 5: Commit** `feat(cube): bảng màu đo được, Lab/ΔE, tên màu có tham số`

### Task 9: Chữ hướng dẫn (bước, chặng, hướng cầm, lý do)

**Files:**
- Create: `AppHost/AppHost/Features/Guide/GuideText.swift`
- Test: `AppHost/AppHostTests/Guide/GuideTextTests.swift`

**Interfaces:**
- Consumes: `CubeMove`, `SolverStageKind`, `SolverReason`, `SolverAlgorithm`, `CubePalette`.
- Produces: `enum GuideText` với các hàm trả `String` đã localize:
  - `static func sentence(_ m: CubeMove) -> String` — chép đúng bảng dưới (kép = "… twice", ví dụ "Turn the right side twice"):

    | Bước | Câu | Bước | Câu |
    |---|---|---|---|
    | R | Turn the right side up | R' | Turn the right side down |
    | L | Turn the left side down | L' | Turn the left side up |
    | U | Turn the top to the left | U' | Turn the top to the right |
    | D | Turn the bottom to the right | D' | Turn the bottom to the left |
    | F | Turn the front clockwise | F' | Turn the front counterclockwise |
    | B | Turn the back counterclockwise | B' | Turn the back clockwise |
    | x | Roll the whole cube forward so the front goes up | x' | Roll the whole cube back so the front goes down |
    | y | Turn the whole cube to the left | y' | Turn the whole cube to the right |
    | z | Tip the whole cube to the right | z' | Tip the whole cube to the left |
    (B ghi "as seen from the front" trong ngữ cảnh nhìn từ trước — câu trên đã quy về nhìn từ trước.)
  - `static func stageTitle(_ k: SolverStageKind, base: String, top: String) -> String` — "\(base) cross", "\(base) corners", "Middle layer", "\(top) cross", "\(top) face", "\(top) corners", "\(top) edges"; `stageHeader` = "Stage \(n) · \(title)".
  - `static func stageGoal(_ k: SolverStageKind, base:top:) -> String` — một câu mục tiêu mỗi chặng (≤ 70 ký tự, người viết soạn; user duyệt ở Đợt B cùng bản Việt).
  - `static func hold(top: String, front: String) -> String` = "Hold: \(top) on top, \(front) facing you".
  - `static func reason(_ r: SolverReason, palette: CubePalette, base: CubeColor) -> String` — ví dụ `.dropToCross(edge: c)` ⇒ "Line up the \(base)-\(c) edge over its center, then turn that side twice"; `.makeDaisy` ⇒ "Bring the \(base)-\(c) edge up next to the \(top) center"; mỗi case một câu ≤ 90 ký tự.
  - `static func algorithmName(_ a: SolverAlgorithm) -> String` — "Right trigger", "Right insert", "Left insert", "Cross maker", "Sune", "Corner cycle", "Edge cycle".
  - `static func progress(step: Int, of: Int) -> String` = "\(step) / \(of)"; `quickProgress` = "Move \(step) / \(of)".

- [ ] **Step 1: Viết test hỏng**

```swift
func testCauCuaMoiBuoc() // sentence(R) == "Turn the right side up"; sentence(R2) == "Turn the right side twice"; mọi bước của 18 + 9 xoay cả khối có câu khác rỗng
func testChuoiDungBangMauDoDuoc() {
    // palette tráo (base là "blue", top là "green"): stageTitle(.cross) == "blue cross"; hold(...) chứa "green on top"
    // Không chuỗi nào (qua mọi reason × palette tráo) chứa "white" hay "yellow" khi palette không có hai màu đó.
}
func testTenThuatToan() // algorithmName(.sune) == "Sune"
```

- [ ] **Step 2:** `tools/dev/run_tests.py GuideTextTests` — Expected: FAIL.
- [ ] **Step 3:** Làm `GuideText.swift` — mọi literal qua `String(localized:)` với nội suy (không nối chuỗi).
- [ ] **Step 4:** Chạy lại — Expected: PASS; `python3 tools/i18n/lint_localizable.py` sạch.
- [ ] **Step 5: Commit** `feat(guide): chữ hướng dẫn có tham số màu`

### Task 10: Quét — logic thuần (phân nhóm, giao thức, lắp mặt, ổn định, ánh sáng)

**Files:**
- Create: `AppHost/AppHost/Features/Scan/ScanHungarian.swift`, `ScanClusterer.swift`, `ScanProtocol.swift`, `ScanStabilizer.swift`, `ScanLighting.swift`
- Create: `AppHost/AppHostTests/Scan/ScanFixtures.swift` (dữ liệu Swift, không resource)
- Test: `AppHost/AppHostTests/Scan/ScanClustererTests.swift`, `ScanProtocolTests.swift`, `ScanStabilizerTests.swift`

**Interfaces:**
- Consumes: `CubeRGB`, `CubeColorMath`, `CubeFacelets`, `CubePalette`, `CubeColor`, `CubeFace`.
- Produces:
  - `enum ScanHungarian { static func assign(cost: [[Double]]) -> [Int] }` — gán tối thiểu, ma trận vuông.
  - `struct ScanResult: Equatable { let facelets: CubeFacelets; let palette: CubePalette; let confidence: [Double]; let ambiguousCenters: (CubeColor, CubeColor)? }` (Equatable thủ công cho tuple).
  - `enum ScanClusterer { static func cluster(_ samples: [CubeRGB], n: Int) -> ScanResult }` — `samples` 54 ô theo thứ tự Kociemba. Nhóm k = màu của tâm mặt k (`CubeColor(raw: k)`), tâm cố định vào nhóm mình. Cân trắng theo tâm có chroma thấp nhất nếu chroma đó < 25. Gán 48 ô còn lại vào 6 nhóm, mỗi nhóm đúng 8, bằng `ScanHungarian` trên ma trận 48×48 (mỗi nhóm nhân 8 cột), chi phí = ΔE76 tới tâm. `confidence[i]` = ΔE tới nhóm tốt thứ hai − ΔE tới nhóm được gán (tâm = +∞ thay bằng 100). Palette = trung bình RGB (đã cân trắng) của từng nhóm. Hai tâm ΔE < 15 ⇒ `ambiguousCenters`.
  - `enum ScanInstruction { case start, turnLeft, backToFirst, tiltTopToYou, tiltBottomToYou }` + `struct ScanStep { let instruction: ScanInstruction; let face: CubeFace?; }` + `enum ScanProtocol { static let cube3: [ScanStep] }` = `[start→F, turnLeft→R, turnLeft→B, turnLeft→L, backToFirst→nil (chỉ kiểm tâm = tâm F đã chụp), tiltTopToYou→U, tiltBottomToYou→D]`; mọi mặt ghép với xoay 0 (bảng "Toạ độ khối"). `static func assemble(_ grids: [CubeFace: [CubeRGB]]) -> [CubeRGB]` (54 ô).
  - `struct ScanStabilizer { init(window: TimeInterval = 0.6, maxDeltaE: Double = 6); mutating func feed(_ s: [CubeRGB], at t: TimeInterval) -> Bool; mutating func reset() }` — `true` một lần khi mọi ô lệch ≤ `maxDeltaE` so với khung trước suốt ≥ `window`; sau đó cần `reset()`.
  - `enum ScanLightTip { case tooDark, glare }` + `enum ScanLighting { static func tip(_ s: [CubeRGB]) -> ScanLightTip? }` — L* trung bình < 25 ⇒ `.tooDark`; ≥ 3 ô L* > 95 và C* < 5 ⇒ `.glare`.
  - `ScanFixtures`: `static func samples(for f: CubeFacelets, palette: CubePalette, tint: CubeRGB, noise: Double, seed: UInt64) -> [CubeRGB]` + bốn điều kiện: `daylight` (tint 1,1,1; noise 0.03), `warmLamp` (1.0, 0.85, 0.6; 0.04), `coolLED` (0.85, 0.95, 1.05; 0.04), `dim` (×0.35; 0.05). Ghi chú: ảnh thật thu ở cổng device sẽ thêm vào đây sau.

- [ ] **Step 1: Viết test hỏng**

```swift
func testHungarianNhoDungToiUu() // ma trận 4×4 biết trước ⇒ gán đúng, tổng chi phí nhỏ nhất
func testPhanNhomDungMoiDieuKien() // 40 trạng thái × 4 điều kiện, palette manualDefault: cluster(...).facelets == trạng thái gốc; mỗi màu đúng 9 ô
func testDenAmVanTachDoCam() // warmLamp, noise 0.06, 40 trạng thái: không ô đỏ nào gán vào nhóm cam và ngược lại
func testBangMauLa() // palette tím/hồng/đen thay đỏ/cam/xanh dương ⇒ vẫn đúng; tên màu trả "purple"/"pink"/"black"
func testHaiTamQuaGiong() // tâm R và tâm L cùng RGB ±0.01 ⇒ ambiguousCenters != nil
func testGiaoThucVaLapMat() { // ScanProtocol.cube3.count == 7; bước 5 face == nil
    // Lấy một trạng thái, cắt lưới 9 ô theo từng mặt (đúng thứ tự Kociemba của mặt đó), assemble ⇒ đúng 54 ô gốc
}
func testOnDinhSauNuaGiay() // 7 khung giống nhau cách 0.1 s ⇒ feed trả true đúng ở khung có t ≥ 0.6, đúng một lần; một khung lệch ΔE 20 ở giữa ⇒ đếm lại từ đó
func testMeoAnhSang() // dim ⇒ .tooDark; 4 ô (1,1,1) ⇒ .glare; daylight ⇒ nil
```

- [ ] **Step 2:** `tools/dev/run_tests.py ScanClustererTests ScanProtocolTests ScanStabilizerTests` — Expected: FAIL.
- [ ] **Step 3:** Làm các file.
- [ ] **Step 4:** Chạy lại — Expected: PASS.
- [ ] **Step 5: Commit** `feat(scan): phân nhóm màu có ràng buộc, giao thức quét, ổn định khung hình`

### Task 11: Quét — camera, xin quyền, màn quét

**Files:**
- Create: `AppHost/AppHost/Features/Scan/ScanCameraAuth.swift`, `ScanSampler.swift`, `ScanCamera.swift`, `ScanPreviewLayer.swift`, `ScanView.swift`, `ScanPermissionView.swift`, `ScanPreviewSeed.swift`, `README.md`
- Modify: `FlowDependencies.swift` (thêm `cameraAuth: ScanCameraAuth`), `FlowModel.swift` (thêm `scan: ScanResult?`, `func didScan(_ r: ScanResult)` ⇒ push `.review(manual: false)`), `HomeView.swift` (đích `.scan`)
- Test: `AppHost/AppHostTests/Scan/ScanSamplerTests.swift`, `ScanCameraAuthTests.swift`

**Interfaces:**
- Consumes: Task 10, `FlowModel`, `FlowDependencies`, `PrefsStore`.
- Produces:
  - `enum ScanCameraStatus { case notDetermined, authorized, denied }` + `struct ScanCameraAuth { var status: () -> ScanCameraStatus; var request: () async -> Bool }` với `static let live` (AVCaptureDevice `.video`; `restricted` ⇒ `denied`).
  - `enum ScanSampler { static func cellRects(n: Int, in size: CGSize) -> [CGRect]; static func sample(_ buffer: CVPixelBuffer, n: Int) -> [CubeRGB] }` — khung = hình vuông giữa ảnh, cạnh 60 % cạnh ngắn; mỗi ô lấy trung bình vùng giữa 40 % của ô; BGRA 8 bit. Overlay của `ScanView` vẽ đúng hình vuông này qua `AVCaptureVideoPreviewLayer.layerRectConverted(fromMetadataOutputRect:)`.
  - `@MainActor final class ScanCamera: ObservableObject { @Published private(set) var samples: [CubeRGB]; func start(); func stop() }` — camera sau, `AVCaptureVideoDataOutput` BGRA, xử lý trên queue riêng, phát `samples` ≤ 15 lần/giây.
  - `struct ScanView: View { init(flow: FlowModel, deps: FlowDependencies) }` — chạy `ScanProtocol.cube3`: chữ hướng dẫn theo bước ("Point the camera at any side", "Turn the cube left — the next center should face you", "Turn left once more — the first side faces you again", "Tilt the top toward you", "Tilt the other way to show the bottom"), minh hoạ hướng xoay bằng `Image(systemName:)` mũi tên (khối 3D nhỏ để Đợt B); màu sống trong 9 ô; tự chụp khi `ScanStabilizer` báo + `deps.haptic(.capture)` (nếu `prefs.haptics`); nút chụp tay; bước `backToFirst` chỉ qua khi tâm khớp tâm F (ΔE < 15), không thì chữ "That's not the first side yet"; bước chụp mặt mới mà tâm trùng một tâm đã chụp (ΔE < 10) ⇒ "This side was already scanned — turn once more"; 6 chấm tiến độ; mẹo ánh sáng "Face a window or a lamp" (tooDark) / "Too much glare — tilt the cube slightly" (glare); nút "Enter colors manually" luôn có ⇒ `.review(manual: true)`. Xong mặt 6 ⇒ `ScanClusterer.cluster` ⇒ `flow.didScan`. `.keepScreenAwake` không cần. `.trackScreen("scan_camera")`.
  - `ScanPermissionView`: trước lần quét đầu (status `.notDetermined`) một màn ngắn "We use the camera to read your cube's colors. Nothing leaves your phone." + nút "Allow camera"; `denied` ⇒ "Camera is off for Cubingo" (tên app qua `AppConfig.displayName`) + "Open Settings" (`UIApplication.openSettingsURLString`) + "Enter colors manually".
  - `ScanPreviewSeed` (`#if targetEnvironment(simulator)`): không camera ⇒ `ScanView` nhận lần lượt 6 lưới từ một trạng thái mẫu cố định (`CubeRandom(seed: 2026)`, palette `manualDefault`, điều kiện `daylight`) mỗi 0,8 s để chụp UI và đi hết luồng trên Simulator.

- [ ] **Step 1: Viết test hỏng**

```swift
func testCellRectsNamTrongKhungVuongGiua() // size 1080×1920, n 3: 9 rect, rect[4].midX == 540, cạnh khung = 648, mỗi ô 216 và vùng lấy mẫu 86.4
func testLayMauTuPixelBufferTongHop() // dựng CVPixelBuffer BGRA 300×300 tô 9 ô màu biết trước ⇒ sample == 9 màu đó (±1/255)
func testTrangThaiQuyen() // ScanCameraAuth giả: status denied ⇒ ScanPermissionModel.screen(for:) == .denied; notDetermined ⇒ .explain; authorized ⇒ .camera
```
  (thêm `enum ScanPermissionModel { enum Screen { case explain, denied, camera }; static func screen(for: ScanCameraStatus) -> Screen }` trong `ScanPermissionView.swift`.)

- [ ] **Step 2:** `tools/dev/run_tests.py ScanSamplerTests ScanCameraAuthTests` — Expected: FAIL.
- [ ] **Step 3:** Làm các file (`NSCameraUsageDescription` đã khai ở Task 1).
- [ ] **Step 4:** Chạy lại — Expected: PASS. Thêm route `AppPreview.scan` ⇒ `ui_shots.py scan` iPhone + iPad, xem ảnh.
- [ ] **Step 5: Commit** `feat(scan): camera, xin quyền, màn quét tự chụp`

### Task 12: Kiểm tra màu và nhập tay

**Files:**
- Create: `AppHost/AppHost/Features/Scan/ScanReviewModel.swift`, `ScanNetView.swift`, `ScanReviewView.swift`
- Modify: `FlowModel.swift` (`cube: CubeFacelets?`, `palette: CubePalette?`, `func didReview(_ f: CubeFacelets, palette: CubePalette)` ⇒ push `.mode`), `HomeView.swift` (đích `.review`)
- Test: `AppHost/AppHostTests/Scan/ScanReviewModelTests.swift`

**Interfaces:**
- Consumes: `ScanResult`, `CubeValidation`, `CubeIssue`, `CubePalette`, `FlowModel`.
- Produces:
  - `@MainActor final class ScanReviewModel: ObservableObject { init(scan: ScanResult); init(manualCenters: [CubeFace: CubeColorName]); @Published private(set) var facelets: [CubeColor?]; @Published private(set) var palette: CubePalette; @Published private(set) var issue: CubeIssue?; @Published private(set) var suspects: Set<Int>; func set(_ index: Int, to c: CubeColor); func setCenter(_ face: CubeFace, to name: CubeColorName); func validate() -> ScanReviewOutcome }`.
  - `enum ScanReviewOutcome: Equatable { case ok(CubeFacelets), autoFixed(CubeFacelets), issue(CubeIssue), incomplete(missing: Int), ambiguousCenters }` — nhập tay còn ô trống ⇒ `.incomplete`; quét có `ambiguousCenters` ⇒ `.ambiguousCenters` cho tới khi người dùng chạm sửa một ô của hai mặt đó; đếm màu đúng mà còn lỗi và đi từ quét ⇒ thử `repairScanOrientation` ⇒ `.autoFixed` (không hỏi); nhập tay không tự sửa. `suspects` theo spec 5.4 (đếm màu ⇒ `CubeIssue.suspects`; miếng không tồn tại ⇒ các ô của miếng; xoắn/lật/đổi chỗ ⇒ rỗng).
  - Nhập tay: tâm tô sẵn `manualDefault` (U white, F green…); chạm tâm ⇒ chọn trong `CubeColorName` (trừ black), không trùng tâm khác; RGB lấy từ bảng chuẩn của tên.
  - `ScanNetView(facelets:palette:suspects:onTap:)` — sơ đồ chữ thập (U trên, L F R B giữa, D dưới), ô nghi viền cam nhấp nháy; iPhone vừa bề ngang, iPad tối đa 560 pt.
  - `ScanReviewView`: chạm ô ⇒ bảng 6 màu của palette; một thông báo lỗi mỗi lần, chép đúng:
    - đếm: "You have \(over) \(overName) and \(under) \(underName). One square is probably wrong." (tổng quát: "\(overCount) \(overName) and \(underCount) \(underName)")
    - miếng: "These squares can't be on the same piece. Check their colors."
    - xoắn: "One corner is twisted — this happens when a cube was taken apart and put back. Twist that corner to fix it."
    - lật: "One edge is flipped — this happens when a cube was taken apart and put back. Flip that edge to fix it."
    - đổi chỗ: "Two pieces are swapped — this happens when a cube was taken apart and put back."
    - tâm giống nhau: "Two centers look the same color. Tap the squares to fix them."
    - nhập tay thiếu: "\(missing) squares left to fill."
    - hợp lệ: "Looks right — let's go!" + nút "Continue" ⇒ `flow.didReview`.
    Nút "Scan again" (từ quét). `.trackScreen("scan_review")`.

- [ ] **Step 1: Viết test hỏng**

```swift
func testQuetDungThiOk() // ScanResult từ trạng thái hợp lệ ⇒ validate() == .ok(trạng thái)
func testDemMauVaSuaMotO() // đổi một ô ⇒ .issue(.colorCount…), suspects chứa ô đó; set(ô, màu đúng) ⇒ .ok
func testTuSuaHuongMatTren() // xoay lưới U 1 nấc (trạng thái ngẫu nhiên có tổ hợp duy nhất) ⇒ .autoFixed(bản gốc)
func testNhapTayThieuOVaKhongTuSua() // manual: 48 ô trống ⇒ .incomplete(missing: 48); điền đủ một trạng thái có U xoay ⇒ .issue (không autoFixed)
func testDoiTamNhapTayKhongTrung() // setCenter(.f, to: .white) khi U đang white ⇒ bị từ chối (palette không đổi)
func testTamGiongNhauChanChoToiKhiSua() // ScanResult có ambiguousCenters ⇒ .ambiguousCenters; set một ô ⇒ không còn .ambiguousCenters
```

- [ ] **Step 2:** `tools/dev/run_tests.py ScanReviewModelTests` — Expected: FAIL.
- [ ] **Step 3:** Làm ba file; route `AppPreview.review` (seed trạng thái có một ô sai để ảnh có thông báo).
- [ ] **Step 4:** Chạy lại — Expected: PASS; `ui_shots.py review` iPhone + iPad, xem ảnh; `ui_shots.py review --content-size accessibility-extra-large`.
- [ ] **Step 5: Commit** `feat(scan): màn kiểm tra màu và nhập tay`

---

## Phase 4 — Khối 3D

### Task 13: Mô hình cảnh 3D thuần + `Cube3DView` RealityKit

**Files:**
- Create: `AppHost/AppHost/Features/Cube3D/Cube3DScene.swift` (thuần, `import simd`), `Cube3DView.swift`, `Cube3DArrow.swift`, `README.md`
- Test: `AppHost/AppHostTests/Cube3D/Cube3DSceneTests.swift`

**Interfaces:**
- Consumes: `CubeFacelets`, `CubeMove`, `CubePalette`, `PrefsSpeed`.
- Produces:
  - `struct Cube3DCubie: Equatable { let id: Int; var position: SIMD3<Int>; var orientation: simd_quatf; let stickers: [SIMD3<Int>: CubeColor] }` (pháp tuyến ban đầu ⇒ màu).
  - `struct Cube3DScene: Equatable { let n: Int; private(set) var cubies: [Cube3DCubie]; init(_ f: CubeFacelets); func members(_ m: CubeMove) -> [Int]; static func axisAngle(_ m: CubeMove) -> (axis: SIMD3<Float>, radians: Float); mutating func apply(_ m: CubeMove); func facelets() -> CubeFacelets }` — 26 khối con (3×3; bỏ lõi), toạ độ nhân đôi như Task 2; `apply` quay vị trí + nhân quaternion, làm tròn vị trí về số nguyên.
  - `struct Cube3DAnimation: Equatable { let move: CubeMove; let reverse: Bool; let token: Int }`.
  - `struct Cube3DView: View { init(state: CubeFacelets, palette: CubePalette, animation: Cube3DAnimation?, speed: PrefsSpeed, highlight: CubeMove?, onAnimationEnd: @escaping () -> Void) }` — `RealityView` với `content.camera = .virtual`; khối con = `MeshResource.generateBox(size: 0.95, cornerRadius: 0.12)` vật liệu đen nhám + nhãn màu là hộp mỏng 0.8×0.8×0.02 bo 0.1 màu `palette.rgb`; góc nhìn chuẩn: lệch phương vị 35° sang R, nâng 30° (thấy U, F, R). Hoạt ảnh: gom `members(move)` vào entity cha tạm, `move(to:relativeTo:duration:timingFunction: .easeInOut)` với thời lượng `speed.quarterTurnSeconds` (×1.5 cho bước kép; `reverse` quay ngược), xong thì gỡ cha, chốt transform theo `Cube3DScene.apply`, gọi `onAnimationEnd`. `token` đổi ⇒ chạy lại (Replay). `highlight` ⇒ nhãn của lớp đó sáng lên (thêm emissive) + `Cube3DArrow` (cung 8 trụ nhỏ + đầu nón `MeshResource.generateCone`) quanh trục lớp theo chiều bước. Kéo ⇒ xoay entity gốc (giới hạn nâng ±80°); thả ⇒ trở về góc nhìn chuẩn trong 0,4 s.

- [ ] **Step 1: Viết test hỏng**

```swift
func testCanhKhopFaceletSauMoiBuoc() {
    // 300 bước ngẫu nhiên (cả x/y/z): scene.apply(m) và f = f.applying(m) ⇒ scene.facelets() == f sau mỗi bước
}
func testThanhVienLop() // members(R).count == 9; members(x).count == 26; members(U) ∩ members(D) rỗng
func testGocQuay() // axisAngle(R) == (+x, -π/2); axisAngle(U2) == (+y, -π); axisAngle(L) == (+x, +π/2)
func testDungTuFaceletBatKy() // Cube3DScene(trạng thái ngẫu nhiên).facelets() == trạng thái đó
```

- [ ] **Step 2:** `tools/dev/run_tests.py Cube3DSceneTests` — Expected: FAIL.
- [ ] **Step 3:** Làm `Cube3DScene` (test xanh), rồi `Cube3DView` + `Cube3DArrow`.
- [ ] **Step 4:** Chạy lại — Expected: PASS. Kiểm bằng mắt ở Task 15 (route `guide`).
- [ ] **Step 5: Commit** `feat(cube3d): cảnh 3D thuần + RealityView có hoạt ảnh xoay lớp`

---

## Phase 5 — Chỉ từng bước

### Task 14: `GuideSession` — máy trạng thái chỉ bước

**Files:**
- Create: `AppHost/AppHost/Features/Guide/GuideMode.swift` (chuyển `GuideMode` từ `FlowRoute.swift`), `GuideSession.swift`, `GuideCheck.swift`
- Modify: `AppHost/AppHost/Features/Flow/FlowRoute.swift`
- Test: `AppHost/AppHostTests/Guide/GuideSessionTests.swift`, `GuideCheckTests.swift`

**Interfaces:**
- Consumes: `SolverStage`, `SolverStep`, `CubeFacelets`, `CubeMove`, `Cube3DAnimation`.
- Produces:
  - `enum GuideMode: Hashable { case teach, quick }`.
  - `@MainActor final class GuideSession: ObservableObject { init(mode: GuideMode, stages: [SolverStage], clock: @escaping () -> Date = Date.init) }` — chế độ quick truyền MỘT chặng gói lời giải Kociemba (kind bất kỳ, View không hiện tên chặng khi `mode == .quick`); chip hold của quick lấy từ `SolverHold.hold(of: state)` ở bước đầu, không chèn bước giả.
    - `@Published private(set) var stageIndex: Int`, `stepIndex: Int` (bước đang hiện, chưa làm), `state: CubeFacelets` (= trạng thái TRƯỚC bước đang hiện), `animation: Cube3DAnimation?`, `phase: GuidePhase` (`.step`, `.stageDone(SolverStageKind)`, `.finished`).
    - `var currentStep: SolverStep?`, `var stepCount: Int` (của chặng hiện tại), `var hold: (top: CubeColor, front: CubeColor)` = `SolverHold.hold(of: state)`, `var base: CubeColor` (= màu nền truyền lúc dựng lời giải; giữ qua `replan`).
    - `func next()` — đang `.step`: phát hoạt ảnh bước hiện tại tiến (`animation` token mới), `state` áp bước, tăng `stepIndex`; hết bước chặng ⇒ `phase = .stageDone` (teach) hoặc `.finished` (quick / chặng 7). `func back()` — lùi một bước (kể cả vắt về bước cuối chặng trước; ở `.stageDone` thì về bước cuối chặng đó), phát hoạt ảnh `reverse`. `func replay()` — phát lại bước vừa làm (không đổi state). `func continueAfterStage()` — sang chặng kế tiếp KHÔNG rỗng (chặng rỗng bị bỏ). `func replan(_ stages: [SolverStage])` — thay lời giải từ trạng thái mới, vào chặng đầu không rỗng.
    - `var elapsed: TimeInterval`, `var movesDone: Int` (không đếm bước xoay cả khối).
  - `struct GuideCheckSpec: Equatable { let face: CubeFace; let indices: [Int]; let anyRotation: Bool }` + `enum GuideCheck { static func spec(_ k: SolverStageKind) -> GuideCheckSpec; static func matches(_ grid: [CubeColor], expected: CubeFacelets, spec: GuideCheckSpec) -> Bool }` — bảng: cross ⇒ (D, [1,3,5,7], xoay tự do); corners ⇒ (D, 0…8, tự do); middle ⇒ (F, 3…8, cố định); topCross ⇒ (U, [1,3,5,7], tự do); topFace ⇒ (U, 0…8, tự do); topCorners ⇒ (F, [0,2], cố định); topEdges ⇒ (F, 0…8, cố định). Màu mong đợi lấy từ `expected` (trạng thái cuối chặng, cùng hướng cầm).

- [ ] **Step 1: Viết test hỏng**

```swift
func testTienHetMotChangVaStageDone() // stages của một trạng thái ngẫu nhiên: next() × steps.count ⇒ phase == .stageDone(.cross); state == stages[0].end
func testBackQuaRanhGioiChangGiuTrangThaiNhatQuan() {
    // Đi tới bước 0 của chặng 2 (qua continueAfterStage), back() ⇒ stageIndex chặng trước, stepIndex = bước cuối,
    // và sau MỌI next/back/replay ngẫu nhiên (seed 5, 400 thao tác): state == start.applying(các bước đã làm)
}
func testChangRongDuocBoQua() // stages có chặng 2 và 3 rỗng: continueAfterStage() từ chặng 1 ⇒ vào chặng 4; tiến độ không bao giờ "0 / 0"
func testQuickKetThucLaFinished() // mode .quick, một chặng 20 bước ⇒ sau 20 next(): phase == .finished; movesDone == 20
func testReplanTuTrangThaiMoi() // replan(SolverBeginner.solve(trạng thái giữa chừng)) ⇒ stageIndex trỏ chặng không rỗng đầu tiên, stepIndex 0
func testDemBuocKhongTinhXoayCaKhoi() // chặng có 2 bước y + 8 bước mặt ⇒ movesDone == 8 sau khi xong
// GuideCheckTests
func testKiemChangKhopVaLech() // cross: lưới D đúng xoay 90° vẫn khớp; middle: lưới F lệch một ô hàng giữa ⇒ không khớp
```

- [ ] **Step 2:** `tools/dev/run_tests.py GuideSessionTests GuideCheckTests` — Expected: FAIL.
- [ ] **Step 3:** Làm các file.
- [ ] **Step 4:** Chạy lại — Expected: PASS.
- [ ] **Step 5: Commit** `feat(guide): máy trạng thái chỉ bước và kiểm chặng`

### Task 15: Màn chọn cách giải, màn chỉ từng bước, màn xong

**Files:**
- Create: `AppHost/AppHost/Features/Flow/FlowModeView.swift`
- Create: `AppHost/AppHost/Features/Guide/GuideView.swift`, `GuideStepCard.swift`, `GuideHoldChip.swift`, `GuideNotationSheet.swift`, `GuideStageDoneView.swift`, `GuideDoneView.swift`, `README.md`
- Modify: `FlowModel.swift` (`session: GuideSession?`, `func startGuide(_ m: GuideMode) async`), `HomeView.swift` (đích `.mode`, `.guide`, `.done`)
- Test: `AppHost/AppHostTests/Flow/FlowModeTests.swift`

**Interfaces:**
- Consumes: Task 5, 7, 9, 13, 14, `PrefsStore`.
- Produces:
  - `FlowModel.startGuide(.teach)` ⇒ `SolverBeginner.solve(cube, base: palette.baseColor)` ⇒ `GuideSession(mode: .teach, …)` ⇒ push `.guide(.teach)`. `startGuide(.quick)` ⇒ `deps.quickSolver.solve(CubeCubies(facelets: cube))` (hiện tiến trình "Finding the shortest way…"; lỗi/hết giờ ⇒ đặt `@Published var alert: FlowAlert?` (`enum FlowAlert { case solverFailed }`) ⇒ `.alert` "Couldn't find a solution. Try Teach me instead.") ⇒ một chặng ⇒ push `.guide(.quick)`.
  - `enum FlowMode { static func estimate(teach stages: [SolverStage]) -> Int }` (tổng bước mặt, không tính xoay cả khối).
  - `FlowModeView`: `Cube3DView` của khối vừa quét (không hoạt ảnh) + hai thẻ: **Teach me** (mặc định, viền cam) "Learn the beginner method in 7 stages" + "About \(n) moves"; **Just solve it** "Shortest way, about 20 moves". Khối đã giải ⇒ thay hai thẻ bằng "Already solved! Nice." + nút "Scan another cube" (Patterns để Đợt B). `.trackScreen("flow_mode")`.
  - `GuideView(session:palette:prefs:onFinish:)`: trên — `stageHeader` + `progress` + thanh tiến độ (teach) hoặc `quickProgress` (quick); giữa — `Cube3DView(state: session.state, animation: session.animation, speed: prefs.speed, highlight: currentStep?.move)`; `GuideHoldChip` hiện ở bước đầu mỗi chặng, ở mọi bước có `reason == .hold`, và luôn ở bước đầu quick; `GuideStepCard`: ký hiệu to (ẩn khi `!prefs.showNotation`) + `GuideText.sentence` + (teach) dòng `reason` + tên thuật toán nếu có; nút Back · Replay · **Next** (to nhất, `StyleThickButton`); nút "?" ⇒ `GuideNotationSheet` (bảng 18 bước + 9 xoay cả khối với câu của `GuideText`); nút chuyển tốc độ chậm/vừa/nhanh ghi `prefs.speed`. Regular size class: hai cột (3D trái, thẻ bước + danh sách bước của chặng phải); compact: một cột. `.trackScreen("guide_steps")`.
  - `GuideStageDoneView`: "Stage complete!" + `stageTitle` + nút "Check my cube" (⇒ Task 16) + "Skip check" (⇒ `continueAfterStage()`).
  - `GuideDoneView`: hoạt hình ăn mừng (hạt confetti SwiftUI `Canvas` 1,5 s) + `deps.haptic(.success)` + "Solved!" + "\(moves) moves · \(mm:ss)" + nút "Solve another cube" (⇒ `flow.startOver()`). `.trackScreen("guide_done")`.

- [ ] **Step 1: Viết test hỏng**

```swift
func testUocLuongKhongTinhXoayCaKhoi() // stages có 3 bước xoay + 40 bước mặt ⇒ estimate == 40
@MainActor func testStartGuideTeachDayRoute() async // FlowModel có cube hợp lệ ⇒ startGuide(.teach) ⇒ path.last == .guide(.teach), session.mode == .teach
@MainActor func testStartGuideQuickLoiThiKhongDayRoute() async // quickSolver giả ném timedOut ⇒ path không đổi, flow.alert != nil
```
  (`SolverQuick` nhận closure nạp bảng — test truyền closure ném lỗi để giả.)

- [ ] **Step 2:** `tools/dev/run_tests.py FlowModeTests` — Expected: FAIL.
- [ ] **Step 3:** Làm các file; route `AppPreview.mode`, `.guide`, `.guideStageDone`, `.done` (seed `GuidePreviewSeed` dựng phiên từ `CubeRandom(seed: 2026)` tới giữa chặng 3).
- [ ] **Step 4:** Chạy lại — Expected: PASS. `ui_shots.py mode guide guideStageDone done` iPhone dọc + iPad ngang, và `--content-size accessibility-extra-large` cho `guide`; xem ảnh: 3D hiện đúng màu, chip hold đọc được, iPad hai cột.
- [ ] **Step 5: Commit** `feat(guide): màn chọn cách giải, màn chỉ từng bước 3D, màn xong`

### Task 16: Quét kiểm tra sau mỗi chặng + lập lại lời giải

**Files:**
- Modify: `AppHost/AppHost/Features/Scan/ScanView.swift` (thêm chế độ `ScanMode.checkFace(GuideCheckSpec, expected: CubeFacelets)`), `FlowModel.swift`, `GuideStageDoneView.swift`
- Create: `AppHost/AppHost/Features/Guide/GuideCheckFlow.swift`
- Test: `AppHost/AppHostTests/Guide/GuideCheckFlowTests.swift`

**Interfaces:**
- Consumes: `GuideCheck`, `GuideSession`, `ScanStabilizer`, `CubePalette`, `ScanView`.
- Produces:
  - `enum ScanMode: Equatable { case full, checkFace(GuideCheckSpec, expected: CubeFacelets) }`; `ScanView(flow:deps:mode:)`. Chế độ check chụp MỘT mặt với chữ theo `spec.face`: D ⇒ "Show us the bottom side", U ⇒ "Show us the top side", F ⇒ "Show us the front side"; có nút "Skip".
  - `enum GuideCheckFlow { static func classify(_ samples: [CubeRGB], palette: CubePalette) -> [CubeColor]; static func outcome(samples: [CubeRGB], palette: CubePalette, spec: GuideCheckSpec, expected: CubeFacelets) -> GuideCheckOutcome }` — mỗi ô gán màu palette gần nhất (ΔE76); `enum GuideCheckOutcome { case match, mismatch }`.
  - Khớp ⇒ `session.continueAfterStage()` + haptic `.success`. Lệch ⇒ màn "Looks different from what we expected — no worries" + nút "Scan the whole cube" ⇒ `ScanView(mode: .full)` ⇒ review ⇒ `session.replan(SolverBeginner.solve(new, base: base cũ))` (giữ base của phiên) ⇒ quay lại `.guide(.teach)` (pop route quét/kiểm tra, không push phiên mới). `.trackScreen("guide_check")`.

- [ ] **Step 1: Viết test hỏng**

```swift
func testPhanLoaiMauGanNhat() // samples = palette ± noise 0.04 ⇒ classify đúng 9 màu
func testKhopVaLechTheoSpec() // chặng middle: samples mặt F của expected ⇒ .match; đổi ô 4 ⇒ .mismatch; cross: lưới D xoay 270° ⇒ .match
@MainActor func testLechThiReplanGiuBase() // FlowModel: sau mismatch + didReview(trạng thái mới) ⇒ session.stageIndex trỏ chặng không rỗng đầu tiên của lời giải mới; base không đổi; path kết thúc bằng .guide(.teach) đúng một lần
```

- [ ] **Step 2:** `tools/dev/run_tests.py GuideCheckFlowTests` — Expected: FAIL.
- [ ] **Step 3:** Làm các thay đổi.
- [ ] **Step 4:** Chạy lại — Expected: PASS.
- [ ] **Step 5: Commit** `feat(guide): quét kiểm tra sau chặng và lập lại lời giải`

---

## Phase 6 — Tích hợp và cổng

### Task 17: Ghép luồng, route preview, công cụ nội bộ, L2, ghi trạng thái

**Files:**
- Modify: `AppHost/AppHost/AppPreview.swift` (route `scan`, `review`, `mode`, `guide`, `guideStageDone`, `done` — đã thêm dần từ Task 11–15; kiểm đủ), `AppHost/AppHostTests/SmokeTests.swift` (`testRoutePreviewCuaApp`: sáu route khung + route tính năng theo thứ tự khai), `AppHost/AppHostUITests/UIShotsTests.swift` (`scrollRoutes` nếu màn dài), `AppHost/AppHost/Internal/AppInternalEntry.swift` (mục "Random scrambled cube" ⇒ `flow.didReview(CubeRandom ngẫu nhiên, palette: .manualDefault)` để thử Teach me/Just solve it trên device không cần quét; type mới ghi vào `[binary]` của `AppHost/Config/debug_symbols.app.txt`), `docs/ROADMAP.md`, `AppHost/AppHost/Features/*/README.md` (mỗi route một dòng)
- Create: `docs/superpowers/plans/2026-11-27-cubingo-dot-a-device-checklist.md`

**Interfaces:**
- Consumes: mọi task trước.
- Produces: luồng chạy được từ đầu tới cuối trên Simulator (bằng `ScanPreviewSeed`) và device; checklist device cho user.

- [ ] **Step 1:** Đi hết luồng trên Simulator bằng tay qua skill `build-and-run`/`ui-preview-sim`: picker → scan (seed) → review → mode → Teach me tới chặng 2 → Skip check → Back qua ranh giới chặng → … → Just solve it tới xong. Ghi lỗi gặp được, sửa trong task này (vòng sửa L1).
- [ ] **Step 2: L2** — `tools/dev/run_tests.py --full` (rc 0, không `[false-green]`); `python3 tools/i18n/lint_localizable.py`; `python3 tools/release/lint_debug_symbols.py`; `python3 tools/common/lint_identity.py`; `python3 tools/release/lint_preview_code.py`; `python3 tools/dev/ui_shots.py all` iPhone dọc + iPad ngang — xem từng ảnh; thêm `--content-size accessibility-extra-large` cho `flow_picker`, `review`, `guide`.
- [ ] **Step 3:** Grep chặn chữ cấm: `grep -rni "rubik" AppHost/AppHost store web/site/public` — Expected: không dòng nào.
- [ ] **Step 4:** Viết checklist device (user làm): build Internal lên iPhone đời thấp nhất có (lý tưởng XS/XR) và một iPad; quét ≥ 3 khối khác hãng ở ≥ 3 điều kiện sáng (ghi số ô phải sửa tay mỗi lần); Just solve it: thời gian từ bấm tới khi hiện bước đầu < 1 s (lần đầu có nạp bảng: ghi lại); giải xong khối thật bằng Teach me (có quét kiểm tra ít nhất 3 chặng, cố ý làm sai một lần để thử lập lại lời giải) và bằng Just solve it; từ chối quyền camera ⇒ nhập tay chạy; mục "Random scrambled cube" trong công cụ nội bộ chạy. Gom mẫu RGB của các lần quét thật (công cụ nội bộ in 54 mẫu ra log) để Đợt B thêm vào `ScanFixtures`.
- [ ] **Step 5:** Cập nhật `docs/ROADMAP.md`: mục Đợt A (≤ 12 dòng: nhánh, trạng thái, chờ thử device), sửa dòng nợ cũ "Remote chưa tạo/push" (remote đã có từ 2026-11-27), nợ mới nếu Task 1 thấy màn lõi khó đọc trên nền sáng.
- [ ] **Step 6: Commit** `feat: ghép luồng Đợt A, route preview, công cụ nội bộ; ROADMAP` — rồi báo user: L2 xanh + ảnh + checklist device (cổng user).

---

## Ngoài plan này (các đợt sau, theo spec mục 12)

- **Đợt B:** 2×2 (cả hai chế độ, giao thức quét 2×2), Patterns, bản tiếng Việt (user duyệt), iPad hoàn thiện, analytics (spec mục 9), SolveLog, minh hoạ hướng xoay bằng khối 3D nhỏ ở màn quét, fixture ảnh thật.
- **Đợt C:** store/ASO, web khi có tên miền, notes Apple Review, ra bản 1.0.
