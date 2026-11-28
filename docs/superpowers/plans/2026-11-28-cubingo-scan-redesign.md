# Thiết kế lại màn quét — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Màn quét "không cần đọc chữ": camera ở trên, khối 3D RealityKit ở dưới nhận màu camera sống, nút ✓ chụp từng
mặt, mũi tên cộng khối xoay mẫu chỉ mặt tiếp theo. Quét kiểm tra sau chặng làm ngay trong màn giải.

**Architecture:** Toán hướng khối là hàm thuần (`ScanOrientation`): quaternion của khối ở mỗi bước → 9 chỉ số facelet
camera thấy. Mô hình quét (`ScanCaptureModel`) thuần, có test: nhận mẫu, làm mượt, chụp, từ chối mặt trùng, hoàn tác, xuất
`Cube3DPaint`. `Cube3DView` mở rộng thêm tư thế cả khối, tô RGB thô, viền phát sáng, hiệu ứng. `FlowModel` thay `path`
thay vì chồng màn, để luôn giữ được bất biến một `RealityView` mỗi chồng.

**Tech Stack:** Swift 5 / SwiftUI / RealityKit (iOS 18), XCTest, XcodeGen.

**Spec:** `docs/superpowers/specs/2026-11-28-cubingo-scan-redesign-design.md`. Tài liệu nền:
`docs/superpowers/specs/2026-11-27-cubingo-design.md`.

## Global Constraints

- iOS 18. Thêm hoặc xoá file ⇒ `cd AppHost && xcodegen generate` (không sửa `.xcodeproj`).
- Chuỗi UI tiếng Anh. Chuỗi đi qua biến `String` phải bọc `String(localized:)`. `python3 tools/i18n/lint_localizable.py`
  phải sạch.
- `.scaledFont(size:weight:design:)`, không dùng `.font(.system(size:))`. Màu lấy từ token `DSColor`. Màu nhấn `#FF7A00`
  (`DSColor.accent`).
- Bố cục theo size class hoặc bề rộng thật (`horizontalSizeClass` / `GeometryReader`), không theo `userInterfaceIdiom`.
- Xác nhận dùng `.alert`, không dùng `.confirmationDialog`.
- **Một `RealityView` mỗi chồng điều hướng.** `.scan` và `.guide` là hai route có `RealityView`.
- Seed và nguồn giả chỉ để chụp ảnh UI: tên kết thúc bằng `PreviewSeed`, đặt trong `#if targetEnvironment(simulator)`.
- `#if INTERNAL` chỉ ở `AppHost/AppHost/Internal/AppInternalEntry.swift`.
- Không `public`, không `@EnvironmentObject` cho đối tượng nghiệp vụ.
- Test chỉ chạy ở Debug (`tools/dev/run_tests.py`). L1 mỗi task, L2 (`--full`) ở task cuối. rc 3 / `[false-green]` không
  phải xanh.
- Commit có trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Message ghi ra file rồi `git commit -F`
  (hook chặn heredoc có chữ `asc`).

## Review Focus

1. **Hướng lưới U/D:** người dùng làm đúng động tác thì khối ghép ra đúng. Nếu sai chiều xoay, lỗi chỉ lộ ra trên máy thật.
   Đã ghim bằng hai cách độc lập: bảng tay ở Task 1, và mô phỏng camera đi qua `ScanOrientation` ở Task 2.
2. **Quay lại từ màn kiểm tra màu:** về màn quét ở 6/6, còn hoàn tác được, bấm ✓ thì gửi lại kết quả. Không được treo
   (`onChange` không bắn khi giá trị không đổi). Ghim ở Task 2 (`testFinishAgainSauKhiDu6`).
3. **Đường điều hướng tạo hai `RealityView`:** quét → chọn cách giải → giải → quét lại → bỏ dở. Ghim ở Task 6 và Task 7
   (`assertOneRealityView` sau mỗi bước).
4. **Bấm ✓ khi camera đang hướng vào bàn hoặc trần** (9 ô cùng màu): vẫn phải nhận, vì mặt đã giải thật cũng đều màu, chỉ
   từ chối khi tâm trùng mặt đã quét. Ghim ở Task 2 (`testChupMatDeuMauVanNhan`).
5. **Mẫu camera nhảy (nhiễu, khung hỏng ít hơn 9 mẫu):** màu sống không được nhấp nháy, nút ✓ không làm sập app. Ghim ở
   Task 2 (`testLamMuotVaBoKhungThieu`).

---

## File Structure

- Create:
  - `AppHost/AppHost/Features/Scan/ScanOrientation.swift`: quaternion các động tác, hàm `imageIndices`.
  - `AppHost/AppHost/Features/Scan/ScanCaptureModel.swift`: mô hình quét, tách khỏi `ScanView.swift`.
  - `AppHost/AppHost/Features/Scan/ScanTurnArrow.swift`: mũi tên cong vẽ đè lên camera.
  - `AppHost/AppHost/Features/Cube3D/Cube3DPose.swift`: `Cube3DPose`, `Cube3DPaint`, `Cube3DEffect`.
  - `AppHost/AppHost/Features/Guide/GuideCheckPanel.swift`: camera, khối và ✓ trong màn giải, cùng lớp phủ khi lệch.
- Modify:
  - `ScanProtocol.swift`: bước mới, có `turn` và `image`.
  - `ScanView.swift`: bố cục mới.
  - `ScanCamera.swift`: `expect(step)`.
  - `ScanPreviewSeed.swift`.
  - `ScanPermissionView.swift`: `ScanEntryView` truyền tham số mới.
  - `Cube3DView.swift`, `Cube3DScene.swift`.
  - `GuideView.swift`, `GuideCheckFlow.swift`.
  - `FlowModel.swift`, `FlowRoute.swift`, `FlowModeView.swift`.
  - `AppHost/AppHost/HomeView.swift`, `AppHost/AppHost/AppPreview.swift`.
  - README của các thư mục Scan, Cube3D, Guide.
- Delete:
  - `ScanStabilizer.swift`: không còn tự chụp.
  - Struct `GuideCheckView` trong `GuideCheckFlow.swift`: được thay bằng `GuideCheckPanel`.
- Tests:
  - `AppHostTests/Scan/ScanOrientationTests.swift` (mới).
  - `AppHostTests/Scan/ScanCaptureModelTests.swift` (mới; chuyển `ScanCaptureModelTests` ra khỏi
    `ScanCameraAuthTests.swift`).
  - `ScanProtocolTests.swift` (bỏ `ScanStabilizerTests`).
  - `AppHostTests/Cube3D/Cube3DPoseTests.swift` (mới).
  - `AppHostTests/Flow/FlowModelTests.swift`, `FlowEndToEndTests.swift`, `ReviewFixTests.swift`.
  - `AppHostTests/Guide/GuideCheckFlowTests.swift`.

---

### Task 1: Hướng khối và chỉ số ảnh (`ScanOrientation`, `ScanProtocol`)

**Files:**
- Create: `AppHost/AppHost/Features/Scan/ScanOrientation.swift`
- Modify: `AppHost/AppHost/Features/Scan/ScanProtocol.swift`
- Test: `AppHost/AppHostTests/Scan/ScanOrientationTests.swift`, `AppHost/AppHostTests/Scan/ScanProtocolTests.swift`

**Interfaces:**
- Produces:
  - `enum ScanTurn: Equatable { case none, left, tiltTowardYou, flipTowardYou }`. `flipTowardYou` nghĩa là lật 180°
    cùng chiều tilt.
  - `enum ScanOrientation`:
    - `static func rotation(_ t: ScanTurn) -> simd_quatf`. Quy ước: `.left` = Ry(−90°) đưa +x về +z; `.tiltTowardYou`
      = Rx(+90°) đưa +y về +z; `.flipTowardYou` = Rx(+180°); `.none` = đơn vị.
    - `static func imageIndices(_ q: simd_quatf, n: Int = 3) -> [Int]`: 9 chỉ số facelet (thứ tự Kociemba U R F D L B,
      `CubeGeometry.of(n:)`) mà camera thấy khi khối quay theo `q` (khung khối → thế giới). Camera nhìn từ +z về −z, ảnh
      đọc theo hàng (hàng 0 là trên, tức +y lớn nhất; cột 0 là trái, tức x nhỏ nhất).
    - `static func frontFace(_ q: simd_quatf) -> CubeFace`.
  - `struct ScanStep: Equatable { let face: CubeFace; let turn: ScanTurn; let orientation: simd_quatf; let image: [Int] }`.
    `turn` là động tác phải làm TRƯỚC khi chụp bước này. `image[k]` là chỉ số facelet của ô ảnh `k`.
  - `ScanProtocol.cube3: [ScanStep]` gồm 6 bước:
    - F `.none`, R `.left`, B `.left`, L `.left`, U `.tiltTowardYou`, D `.flipTowardYou`;
    - `orientation` bước i = `rotation(turn_i) * orientation_{i−1}` (động tác sau nhân bên trái);
    - `image = imageIndices(orientation)`.
  - `ScanProtocol.assemble(_ images: [[CubeRGB]]) -> [CubeRGB]`: 6 ảnh theo thứ tự bước → 54 mẫu thứ tự Kociemba.

- [ ] **Step 1: Viết test đỏ** trong `ScanOrientationTests`:
  ```swift
  func testChiSoAnhTheoBangTay() {
      let s = ScanProtocol.cube3
      XCTAssertEqual(s.map(\.face), [.f, .r, .b, .l, .u, .d])
      XCTAssertEqual(s.map(\.turn), [.none, .left, .left, .left, .tiltTowardYou, .flipTowardYou])
      XCTAssertEqual(s[0].image, Array(18...26))   // F đọc thẳng
      XCTAssertEqual(s[1].image, Array(9...17))    // R
      XCTAssertEqual(s[2].image, Array(45...53))   // B
      XCTAssertEqual(s[3].image, Array(36...44))   // L
      // Từ L nghiêng mặt trên về phía mình: L ở dưới ảnh, B bên trái.
      XCTAssertEqual(s[4].image, [2, 5, 8, 1, 4, 7, 0, 3, 6])
      // Lật thêm 180°: R ở dưới, L ở trên, B bên trái.
      XCTAssertEqual(s[5].image, [33, 30, 27, 34, 31, 28, 35, 32, 29])
      for st in s { XCTAssertEqual(ScanOrientation.frontFace(st.orientation), st.face) }
  }
  func testKiemTraTrongManGiai() {
      XCTAssertEqual(ScanOrientation.imageIndices(ScanOrientation.rotation(.none)), Array(18...26))
      XCTAssertEqual(ScanOrientation.frontFace(ScanOrientation.rotation(.tiltTowardYou)), .u)
      XCTAssertEqual(ScanOrientation.frontFace(ScanOrientation.rotation(.tiltTowardYou).inverse), .d)
  }
  func testGhepAnhRaDungKhoi() {
      var rng = CubeRandom(seed: 9)
      let f = CubeRandom.state(using: &rng).facelets(centers: cubeStandardCenters)
      let samples = ScanFixtures.samples(for: f, palette: .manualDefault, .daylight, seed: 3)
      let images = ScanProtocol.cube3.map { st in st.image.map { samples[$0] } }
      XCTAssertEqual(ScanProtocol.assemble(images), samples)
  }
  ```
  Sửa `ScanProtocolTests.testGiaoThucVaLapMat` theo API mới, hoặc xoá vì `testGhepAnhRaDungKhoi` đã thay nó. Bỏ
  `ScanStabilizerTests`.
- [ ] **Step 2:** `tools/dev/run_tests.py ScanOrientationTests`. Kỳ vọng: FAIL khi biên dịch (chưa có
  `ScanOrientation`).
- [ ] **Step 3:** Viết `ScanOrientation`, `ScanTurn`, `ScanStep` mới và `assemble`.
  - `imageIndices`: lọc facelet có `q.act(normal)` làm tròn bằng (0, 0, 1), rồi sắp theo (−y, x) của `q.act(position)`.
  - Xoá `ScanInstruction` và `ScanStabilizer.swift`.
  - Sửa mọi chỗ gọi cho biên dịch được: `ScanView` tạm thời gọi `model.step.face`; Task 2 và 5 sẽ viết lại.
  - `xcodegen generate`.
- [ ] **Step 4:** `tools/dev/run_tests.py ScanOrientationTests ScanProtocolTests`. Kỳ vọng: PASS.
- [ ] **Step 5:** Chạy `tools/factory/mutate.py` đổi dấu góc của `.tiltTowardYou`. Kỳ vọng: `testChiSoAnhTheoBangTay` đỏ.
  Commit `feat(scan): giao thức 6 bước, hướng khối và chỉ số ảnh`.

### Task 2: Mô hình quét (`ScanCaptureModel`)

**Files:**
- Create: `AppHost/AppHost/Features/Scan/ScanCaptureModel.swift` (chuyển từ `ScanView.swift` rồi viết lại)
- Test: `AppHost/AppHostTests/Scan/ScanCaptureModelTests.swift`. Chuyển `ScanCaptureModelTests` từ
  `ScanCameraAuthTests.swift` sang đây và viết lại. Sửa `Flow/FlowEndToEndTests.swift`, `Flow/ReviewFixTests.swift` theo
  API mới.

**Interfaces:**
- Consumes:
  - `ScanProtocol.cube3`, `ScanStep.image`, `ScanProtocol.assemble` (Task 1);
  - `Cube3DPaint` (Task 3). Task 2 khai báo tạm `struct Cube3DPaint: Equatable { var colors: [Int: CubeRGB] }` trong
    `Cube3D/Cube3DPose.swift` nếu Task 3 chưa có.
- Produces:
  - `enum ScanCaptureOutcome: Equatable { case notReady, accepted, duplicate(CubeFace), finished(ScanResult) }`
  - `@MainActor final class ScanCaptureModel: ObservableObject` gồm:
    - `@Published private(set) var stepIndex: Int`, `live: [CubeRGB]` (đã làm mượt, rỗng khi chưa có),
      `awaitingTurn: Bool`, `result: ScanResult?`;
    - `var step: ScanStep`, `var capturedCount: Int`, `var canUndo: Bool`;
    - `func observe(_ s: [CubeRGB])`:
      - bỏ khung có `count != 9`;
      - làm mượt `live = live + α·(s − live)` với `static let smoothing = 0.35` (mẫu ≤ 15 Hz, thời hằng khoảng 0,2 s);
      - khi `awaitingTurn` và ΔE(s[4], tâm vừa chụp) ≥ `sameCenterDeltaE` (10): `awaitingTurn = false` và `live = s`
        (đặt lại, không pha màu mặt cũ);
    - `@discardableResult func capture() -> ScanCaptureOutcome`:
      - `live` chưa đủ 9 ⇒ `.notReady`;
      - đã đủ 6 mặt (quay lại từ màn kiểm tra) ⇒ phân nhóm lại và trả `.finished` (`finishAgain`);
      - tâm trùng một mặt đã chụp (ΔE < 10) ⇒ `.duplicate(mặt đó)`, KHÔNG kiểm "mặt đều màu";
      - ngược lại lưu ảnh, `stepIndex += 1`, `awaitingTurn = true`;
      - đủ 6 ⇒ `AppInternalScanLog.record(samples)`, `ScanClusterer.cluster(samples, n: 3)` ⇒ `.finished(result)`.
    - `func undoLast()`: bỏ ảnh gần nhất, `stepIndex -= 1`, `awaitingTurn = false`, `result = nil`, `live = []`.
    - `func reset()`.
    - `var paint: Cube3DPaint`: ảnh đã chụp map qua `step.image`, cộng `live` lên mặt bước hiện tại khi `!awaitingTurn`
      và `stepIndex < 6`.
    - `var glowFace: CubeFace?`: mặt bước hiện tại khi `stepIndex < 6`, ngược lại `nil`.
    - `var pose: simd_quatf`: `orientation` của bước hiện tại (đủ 6 thì giữ bước cuối).

- [ ] **Step 1: Viết test đỏ** (fixture `ScanFixtures`, ảnh từng bước = `step.image.map { samples[$0] }`):
  - `testQuetDu6MatRaKetQua`: observe + capture lần lượt 6 ảnh. Kỳ vọng:
    - 5 lần đầu `.accepted`, lần 6 `.finished(r)`;
    - `r.facelets == f` (khối gốc, palette `.manualDefault`, `.daylight`).
  - `testMatTrungBiTuChoi`: chụp F, rồi observe lại ảnh F và capture. Kỳ vọng: `.duplicate(.f)` và `stepIndex == 1`.
  - `testChoXoayRoiMoiNhanMauMoi`:
    - sau capture, `awaitingTurn == true` và `paint` không chứa chỉ số của mặt R;
    - observe ảnh R ⇒ `awaitingTurn == false`, `paint.colors[9] != nil`.
  - `testHoanTac`:
    - chụp 2 mặt rồi `undoLast()` ⇒ `stepIndex == 1`, `paint` không còn chỉ số 9…17, `glowFace == .r`;
    - chụp đủ 6 rồi `undoLast()` ⇒ `result == nil`, `stepIndex == 5`.
  - `testFinishAgainSauKhiDu6`: đủ 6 xong gọi `capture()` lần nữa. Kỳ vọng: `.finished` với cùng `facelets`.
  - `testChupMatDeuMauVanNhan`: mặt F của khối đã giải (9 ô cùng màu). Kỳ vọng: `.accepted`.
  - `testLamMuotVaBoKhungThieu`:
    - observe khung 9 mẫu A, rồi khung 3 mẫu (bỏ qua), rồi khung B ⇒ `live[0]` nằm giữa A và B (không bằng B);
    - `capture()` khi `live` rỗng ⇒ `.notReady`.
  - `testPoseVaGlow`: sau 4 lần chụp, `glowFace == .u` và `ScanOrientation.frontFace(pose) == .u`.
- [ ] **Step 2:** `tools/dev/run_tests.py ScanCaptureModelTests`. Kỳ vọng: FAIL.
- [ ] **Step 3:** Viết `ScanCaptureModel` theo Interfaces. Sửa `FlowEndToEndTests`, `ReviewFixTests` sang
  `observe` + `capture()`. `xcodegen generate`.
- [ ] **Step 4:** `tools/dev/run_tests.py ScanCaptureModelTests FlowEndToEndTests ReviewFixTests`. Kỳ vọng: PASS.
- [ ] **Step 5:** Chạy `mutate.py`: bỏ nhánh `.duplicate` ⇒ `testMatTrungBiTuChoi` đỏ. Commit
  `feat(scan): mô hình quét chụp tay, màu sống làm mượt`.

### Task 3: Khối 3D có tư thế, tô RGB, viền sáng, hiệu ứng

**Files:**
- Create: `AppHost/AppHost/Features/Cube3D/Cube3DPose.swift`
- Modify: `Cube3DView.swift` (gồm `Cube3DView` và `Cube3DController`), `Cube3DScene.swift`
- Test: `AppHost/AppHostTests/Cube3D/Cube3DPoseTests.swift`

**Interfaces:**
- Produces:
  - `struct Cube3DPaint: Equatable { var colors: [Int: CubeRGB] }`. Khoá là chỉ số facelet Kociemba. Ô không có trong
    `colors` hiện màu thân khối, như mặt chưa quét.
  - `struct Cube3DPose: Equatable { var orientation: simd_quatf; var replayFrom: simd_quatf?; var token: Int }`
    - `orientation` (khung khối → thế giới) áp TRƯỚC góc nhìn chuẩn: `cubeRoot = restOrientation * orientation`.
    - `orientation` đổi ⇒ quay mượt tới hướng mới trong `Cube3DPose.turnSeconds = 0.9`, easeInOut.
    - `token` đổi và `replayFrom != nil` ⇒ đặt tức thì về `replayFrom` rồi quay lại tới `orientation`.
  - `struct Cube3DEffect: Equatable { enum Kind: Equatable { case shake, flash([Int]) }; let kind: Kind; let token: Int }`
    - `shake`: lắc ngang cả khối ±0,12 rad, 3 nhịp, khoảng 0,35 s.
    - `flash`: các ô được liệt kê nháy đỏ `#E5484D` hai lần, khoảng 0,6 s, rồi về màu cũ.
  - `Cube3DScene.faceletIndex(cubie: Int, local: SIMD3<Int>) -> Int` (internal; dùng `stickerIndex` sẵn có).
  - `Cube3DView` thêm tham số có mặc định: `pose: Cube3DPose? = nil`, `paint: Cube3DPaint? = nil`,
    `glow: CubeFace? = nil`, `effect: Cube3DEffect? = nil`.
    - `paint != nil` ⇒ mọi ô lấy màu từ `paint`, bỏ qua palette. Màn quét truyền `state: .solved(n: 3)`,
      `palette: .manualDefault`.
    - `glow`: khung phát sáng màu `DSColor.accent` quanh mặt đó (trong khung khối), nhịp sáng 1,2 s. Mặt tính theo hướng
      hiện tại của khối con (`facelets()`).
  - `Cube3DController.displayedStickerRGB(_ index: Int) -> CubeRGB?` (test).
  - Kéo xoay: `setDrag` / `resetView` cộng dồn trên `restOrientation * pose.orientation`.

- [ ] **Step 1: Viết test đỏ** (`@MainActor`, dựng `Cube3DController` không cần `RealityView`, chỉ gọi `update`):
  - `testPaintToMauVaO_trong`:
    - update với `paint = [18: đỏ thô]`;
    - kỳ vọng: `displayedStickerRGB(18) == đỏ thô` và `displayedStickerRGB(0) == Cube3DController.blankRGB`.
  - `testFaceletIndexKhopFacelets`: với mọi khối con và pháp tuyến của `Cube3DScene(.solved(n: 3))`,
    `faceletIndex(...)` khớp chỉ số mà `facelets()` dùng (mỗi chỉ số 0…53 xuất hiện đúng một lần).
  - `testPoseDichDen`:
    - update với `pose.orientation = ScanProtocol.cube3[1].orientation`;
    - kỳ vọng: `controller.targetOrientation == restOrientation * orientation` (sai số 1e-4).
- [ ] **Step 2:** `tools/dev/run_tests.py Cube3DPoseTests Cube3DSceneTests`. Kỳ vọng: FAIL.
- [ ] **Step 3:** Viết theo Interfaces.
  - Thêm `static let blankRGB = CubeRGB(r: 0.16, g: 0.16, b: 0.17)`.
  - Cập nhật màu ô bằng cách thay material, không dựng lại entity.
  - Mỗi hoạt ảnh (tư thế, lắc, nháy) dùng `Task` riêng có huỷ và token, theo mẫu `animationTask` hiện có.
  - Hoạt ảnh lớp của màn giải không được đổi hành vi: `Cube3DSceneTests` phải giữ xanh.
- [ ] **Step 4:** `tools/dev/run_tests.py Cube3DPoseTests Cube3DSceneTests GuideSessionTests`. Kỳ vọng: PASS.
- [ ] **Step 5:** Commit `feat(cube3d): tư thế cả khối, tô màu thô, viền sáng, lắc và nháy`.

### Task 4: Mũi tên cong (`ScanTurnArrow`)

**Files:**
- Create: `AppHost/AppHost/Features/Scan/ScanTurnArrow.swift`
- Test: thêm vào `AppHost/AppHostTests/Scan/ScanOrientationTests.swift`

**Interfaces:**
- Produces:
  - `struct ScanTurnArrow: View { let turn: ScanTurn; let token: Int }`. Vẽ dần (`trim` 0→1 trong khoảng 0,9 s) một cung
    nét 9 pt màu `DSColor.accent`, có đầu mũi tên và bóng tối nhẹ để nổi trên ảnh camera. `token` đổi ⇒ vẽ lại.
    - `.left`: cung phía trên khung, phải → trái.
    - `.tiltTowardYou`: cung bên phải khung, trên → dưới.
    - `.flipTowardYou`: cung như tilt nhưng dài gấp đôi, cộng ký hiệu "×2" vẽ bằng `Text(verbatim: "×2")`.
    - `.none`: không vẽ gì.
  - `static func path(_ turn: ScanTurn, in rect: CGRect) -> Path`. Hàm thuần, để test.
- [ ] **Step 1: Test đỏ** `testMuiTenTheoDongTac`:
  - `.none` ⇒ path rỗng;
  - `.left` ⇒ path không rỗng, điểm cuối có x nhỏ hơn điểm đầu;
  - `.tiltTowardYou` ⇒ điểm cuối có y lớn hơn điểm đầu;
  - bounding box nằm trong `rect`.
- [ ] **Step 2:** `tools/dev/run_tests.py ScanOrientationTests`. Kỳ vọng: FAIL.
- [ ] **Step 3:** Viết view và `path`. Lưu điểm đầu và điểm cuối qua hàm phụ thuần
  `static func endpoints(_:in:) -> (CGPoint, CGPoint)?`.
- [ ] **Step 4:** Chạy lại. Kỳ vọng: PASS.
- [ ] **Step 5:** Commit `feat(scan): mũi tên cong chỉ động tác`.

### Task 5: Màn quét mới (`ScanView`)

**Files:**
- Modify: `ScanView.swift` (viết lại phần view), `ScanCamera.swift`, `ScanPermissionView.swift`, `ScanPreviewSeed.swift`,
  `AppHost/AppHost/AppPreview.swift`, `AppHost/AppHost/Features/Scan/README.md`
- Test: `AppHost/AppHostTests/Scan/ScanCaptureModelTests.swift` (thêm `testA11yMoTaBuoc`)

**Interfaces:**
- Consumes: `ScanCaptureModel` (Task 2), `Cube3DView(pose:paint:glow:effect:)` (Task 3), `ScanTurnArrow` (Task 4),
  `ScanLighting.tip`.
- Produces:
  - `ScanCamera.expect(_ step: ScanStep)`: seed simulator phát `step.image.map { ScanPreviewSeed.samples54[$0] }`.
    `ScanPreviewSeed` thêm `static var samples54: [CubeRGB]`.
  - `ScanView(flow:deps:)`: chỉ còn chế độ quét cả khối. Chế độ kiểm tra chuyển sang Task 7.
  - `ScanText.accessibility(step: ScanStep, captured: Int, awaitingTurn: Bool) -> String`: ví dụ "3 of 6 sides
    scanned. Next: turn the whole cube left". Mỗi `ScanTurn` một câu, bọc `String(localized:)`.
  - Preview: `ScanPreviewSeed.preset: ScanPreviewPreset?`, gồm `.midScan` (đã chụp 2 mặt, đang nhận màu mặt 3) và
    `.turning` (đã chụp 3, đang chờ xoay). `ScanView.onAppear` áp preset ở simulator. `AppPreview` có thêm case
    `scanTurn` và đặt preset cho cả `scan` lẫn `scanTurn`.

Bố cục, theo spec mục "Bố cục" (sơ đồ ở đó):
- `GeometryReader`: rộng hơn cao và `horizontalSizeClass == .regular` ⇒ `HStack` (camera 58%); còn lại ⇒ `VStack`
  (camera 55%).
- Camera: góc bo 24, khung 3×3 viền `DSColor.accent` 2 pt, KHÔNG có chấm màu trong khung.
  - `ScanTurnArrow(turn: model.step.turn, token: arrowToken)` hiện khi `model.awaitingTurn`.
  - `arrowToken` tăng mỗi 2,5 s (`TimelineView` hoặc `Task`) khi còn `awaitingTurn`, đồng thời tăng `pose.token` với
    `replayFrom` = hướng bước trước để khối diễn lại động tác.
- Ba nút tròn 36 pt nền `Color.black.opacity(0.45)`, biểu tượng SF:
  - `chevron.left`: quay lại, gọi `flow.scanBack()` (Task 6);
  - `square.grid.3x3`: nhập tay;
  - `arrow.uturn.backward`: hoàn tác, chỉ hiện khi `canUndo`.

  Ẩn nút back hệ thống: `.navigationBarBackButtonHidden(true)`.
- Biểu tượng ánh sáng: `lightbulb.fill` (quá tối) hoặc `sun.max.fill` (chói), góc dưới trái camera, nhấp nháy, không có
  chữ.
- Vùng khối: `Cube3DView(state: .solved(n: 3), palette: .manualDefault, animation: nil, speed: deps.prefs.speed,
  highlight: nil, pose:, paint: model.paint, glow: model.glowFace, effect:)`.
- Nút ✓: tròn 64 pt nền `DSColor.accent`, `checkmark` trắng, giữa đáy. Mờ 40% khi `model.live.count != 9`.
  Bấm ⇒ `model.capture()`:
  - `.accepted` ⇒ `deps.haptic(.capture)`, tăng `arrowToken`;
  - `.duplicate(face)` ⇒ `deps.haptic(.warning)`, `effect = .shake` rồi `.flash` (các chỉ số ảnh của bước chụp mặt đó);
  - `.finished(r)` ⇒ `deps.haptic(.success)`, `flow.didScan(r)`.
- Bộ đếm `Text(verbatim: "\(captured)/6")`, `.scaledFont(size: 15, weight: .bold, design: .rounded)`,
  `DSColor.textSecondary`, góc dưới phải vùng khối.
- `.onReceive(camera.$samples) { model.observe($0); tip = ScanLighting.tip($0) }`.
  `.onChange(of: model.stepIndex) { camera.expect(model.step) }`.
- Nhãn VoiceOver:
  - khối: `ScanText.accessibility(...)`;
  - ✓: "Capture this side";
  - hoàn tác: "Undo last side";
  - nhập tay: "Enter colors manually";
  - quay lại: "Back".
- Không còn câu hướng dẫn, chấm tiến độ hay thẻ thông báo.

- [ ] **Step 1: Test đỏ** `testA11yMoTaBuoc`:
  - `ScanText.accessibility(step: cube3[1], captured: 1, awaitingTurn: true)` chứa "1 of 6" và "turn the whole cube
    left";
  - câu cho 4 giá trị `ScanTurn` khác nhau từng đôi.
- [ ] **Step 2:** Chạy. Kỳ vọng: FAIL.
- [ ] **Step 3:** Viết view, camera, seed, preset, route `scanTurn` và README (thêm dòng `scanTurn`). `xcodegen generate`.
- [ ] **Step 4:** Chạy `tools/dev/run_tests.py ScanCaptureModelTests` (kỳ vọng PASS). Rồi chụp
  `python3 tools/dev/ui_shots.py --label scan-t5 scan scanTurn`, và cả iPad (`--udid <iPad sim>`). Xem ảnh:
  - camera khoảng 55%;
  - khối có mặt viền cam;
  - mũi tên hiện ở `scanTurn`;
  - không còn câu chữ.
- [ ] **Step 5:** `python3 tools/i18n/lint_localizable.py` sạch. Commit `feat(scan): màn quét mới — camera, khối 3D sống,
  nút chụp, mũi tên`.

### Task 6: Điều hướng giữ một `RealityView` (`FlowModel`)

**Files:**
- Modify: `FlowModel.swift`, `FlowRoute.swift`, `FlowModeView.swift`, `ScanReviewView.swift`, `AppHost/AppHost/HomeView.swift`
- Test: `AppHost/AppHostTests/Flow/FlowModelTests.swift`

**Interfaces:**
- Consumes: `ScanReviewModel(scan:).validate()`, `.palette`, `.whiteReference`.
- Produces:
  - `FlowRoute.hasRealityView: Bool`: `true` cho `.scan` và `.guide`.
  - `FlowModel.didScan(_ r: ScanResult)`:
    - `ScanReviewModel(scan: r).validate()` là `.ok(f)` hoặc `.autoFixed(f)` ⇒ `finishScan(f, palette:, white:)`;
    - ngược lại ⇒ `scan = r`, `path.append(.review(manual: false))`.
  - `FlowModel.didReview(_:palette:white:)`: gọi `finishScan`.
  - `private func finishScan(...)`:
    - `isRechecking` ⇒ `replan`, rồi `path = [.guide(.teach)]`;
    - ngược lại ⇒ lưu `cube`, `palette`, `white`, rồi `path = [.mode]`.
  - `FlowModel.scanBack()`:
    - `isRechecking` ⇒ `isRechecking = false`, `path = [.guide(.teach)]` (phiên giữ nguyên);
    - ngược lại ⇒ `path = []`.
  - `FlowModel.rescanFromMode()`: `scan = nil`, `cube = nil`, `path = [.scan]`.
  - `FlowModel.startRescan()`: `isRechecking = true`, `path = [.scan]`.
  - `FlowModeView`: ẩn back hệ thống, nút back tròn (kiểu hiện tại) gọi `flow.rescanFromMode()`.

- [ ] **Step 1: Test đỏ.** Helper trong test:
  `func assertOneRealityView(_ f: FlowModel) { XCTAssertLessThanOrEqual(f.path.filter(\.hasRealityView).count, 1) }`,
  gọi sau mọi bước của mọi test dưới đây.
  - `testQuetHopLeDiThangSangMode`: `choose(.cube3)` rồi `didScan(ScanPreviewSeed.scanResult)`. Kỳ vọng:
    `path == [.mode]` và `cube != nil`.
  - `testQuetLoiMoReviewRoiThayPath`:
    - `didScan(scanResultWithMistake)` ⇒ `path == [.scan, .review(manual: false)]`;
    - `didReview(f, ...)` ⇒ `path == [.mode]`.
  - `testQuayLaiTuModeQuetLai`: `rescanFromMode()` ⇒ `path == [.scan]` và `cube == nil`.
  - `testQuetLaiKhiLechVaBoDo`:
    - `begin(session)` ⇒ `path` chứa `.guide`;
    - `startRescan()` ⇒ `path == [.scan]`;
    - `scanBack()` ⇒ `path == [.guide(.teach)]`, `isRechecking == false`, `session` vẫn là đối tượng cũ;
    - `startRescan()` lần nữa, rồi `didScan(r)` ⇒ `path == [.guide(.teach)]`.
- [ ] **Step 2:** `tools/dev/run_tests.py FlowModelTests`. Kỳ vọng: FAIL.
- [ ] **Step 3:** Viết theo Interfaces.
  - `ScanReviewView.continueTapped` vẫn gọi `didReview`.
  - Nhập tay mở từ màn quét: `[.scan, .review(manual: true)]` ⇒ Continue ⇒ `[.mode]`.
- [ ] **Step 4:** `tools/dev/run_tests.py FlowModelTests FlowEndToEndTests ReviewFixTests`. Kỳ vọng: PASS.
- [ ] **Step 5:** Chạy `mutate.py` đổi `path = [.scan]` trong `startRescan` thành `path.append(.scan)`. Kỳ vọng:
  `assertOneRealityView` đỏ. Commit `feat(flow): thay path thay vì chồng — một RealityView mỗi chồng`.

### Task 7: Quét kiểm tra trong màn giải (`GuideCheckPanel`)

**Files:**
- Create: `AppHost/AppHost/Features/Guide/GuideCheckPanel.swift`
- Modify:
  - `GuideCheckFlow.swift`: thêm hàm thuần, xoá `GuideCheckView`.
  - `GuideView.swift`, `FlowRoute.swift` (xoá `.check`), `FlowModel.swift` (xoá `startCheck`), `HomeView.swift`.
  - `GuidePreviewSeed.swift`, `AppPreview.swift` (route `guideCheck`), `Guide/README.md`.
- Test: `AppHost/AppHostTests/Guide/GuideCheckFlowTests.swift`, `AppHost/AppHostTests/Flow/FlowModelTests.swift`

**Interfaces:**
- Consumes: `ScanOrientation`, `ScanTurnArrow`, `Cube3DPose/Paint/Effect` (Task 1, 3, 4), `ScanCamera`.
- Produces:
  - `enum GuideCheckPress: Equatable { case wrongSide, match, mismatch([Int]) }`. `[Int]` là chỉ số facelet lệch, để
    nháy đỏ.
  - `GuideCheckFlow.checkTurn(_ face: CubeFace) -> ScanTurn`: `.u` ⇒ `.tiltTowardYou`, `.f` ⇒ `.none`, `.d` ⇒ tilt
    ngược. Thêm `case tiltAwayFromYou` vào `ScanTurn` = Rx(−90°), có mũi tên dưới → trên ở `ScanTurnArrow`.
  - `GuideCheckFlow.orientation(_ face: CubeFace) -> simd_quatf` = `ScanOrientation.rotation(checkTurn(face))`.
  - `GuideCheckFlow.press(image: [CubeRGB], palette:, white:, spec:, expected:) -> GuideCheckPress`:
    - ảnh → lưới mặt bằng `ScanOrientation.imageIndices(orientation(spec.face))` (đổi chỉ số tuyệt đối sang 0…8 trong
      mặt);
    - tâm sai ⇒ `.wrongSide`;
    - `GuideCheck.matches` ⇒ `.match`;
    - ngược lại ⇒ `.mismatch(...)`, liệt kê ô thuộc `spec.indices` không khớp ở phép xoay gần đúng nhất.
  - `GuideCheckFlow.paint(state:palette:face:live:) -> Cube3DPaint`: mọi ô theo `palette.rgb(state)`, riêng mặt `face`
    lấy `live` qua `imageIndices` (khi `live.count == 9`).
  - `GuideView` thêm tham số `deps: FlowDependencies`, `white: CubeRGB?`, `onCheckMatched`, `onCheckSkipped`, `onRescan`.
    Bỏ `onCheck` đẩy route.
    - Nút "Check" ở màn xong chặng ⇒ `@State checking = true`.
    - Khi `checking`: ẩn thẻ bước, chip cách cầm và các nút Back / Replay / Next. Bố cục camera + khối giống màn quét
      (dọc 55/45, ngang 58/42). Khối là `Cube3DView` sẵn có của màn giải, nhận `pose`, `paint`, `glow`, `effect`.
    - Kết quả nút ✓:
      - `.wrongSide` ⇒ lắc + rung warning;
      - `.match` ⇒ rung success, `checking = false`, `onCheckMatched()`;
      - `.mismatch(ix)` ⇒ nháy đỏ `ix` + rung warning + lớp phủ `GuideCheckMismatchOverlay`.
    - Lớp phủ: tiêu đề "That side doesn't match", hai nút có biểu tượng "Scan whole cube" (`onRescan`) và "Skip"
      (`onCheckSkipped`).
    - Nút bỏ qua trên camera (`forward.end.fill`, nhãn "Skip check").
    - Thiếu quyền camera ⇒ `onCheckSkipped()` ngay.
  - `HomeView` truyền `flow.checkMatched()`, `flow.checkSkipped()`, `flow.startRescan()` vào `GuideView`.
  - Preview: `GuidePreviewSeed.openCheck` mở thẳng chế độ kiểm tra cho route `guideCheck`.

- [ ] **Step 1: Test đỏ** trong `GuideCheckFlowTests`:
  - `testPressDungMatKhop`: khối sau chặng cross, ảnh mặt D tạo từ `expected` qua `imageIndices(orientation(.d))`
    và `ScanFixtures`. Kỳ vọng: `.match`.
  - `testPressSaiMat`: đưa ảnh mặt F khi spec là D. Kỳ vọng: `.wrongSide`.
  - `testPressLechTraOLech`: đổi màu ô 1 của mặt D. Kỳ vọng: `.mismatch` chứa chỉ số tuyệt đối `27 + 1`.
  - `testPaintGiuTrangThaiVaMauSong`: `paint(...)` có `colors[0] == palette.rgb(state.stickers[0])`, còn mặt D lấy màu
    `live`.
  - `testCheckTurn`: `frontFace(orientation(.u)) == .u`, `.d` ⇒ `.d`, `.f` ⇒ `.f`.

  Trong `FlowModelTests`: `testKhongConRouteCheck`. Sau `checkMatched()`, `path` vẫn là `[.guide(.teach)]`, rồi
  `assertOneRealityView`.
- [ ] **Step 2:** `tools/dev/run_tests.py GuideCheckFlowTests FlowModelTests`. Kỳ vọng: FAIL.
- [ ] **Step 3:** Viết `GuideCheckFlow` mới, `GuideCheckPanel`, sửa `GuideView`, `HomeView`, `FlowRoute`, `FlowModel`,
  preview, README. `xcodegen generate`.
- [ ] **Step 4:**
  - `tools/dev/run_tests.py GuideCheckFlowTests FlowModelTests GuideSessionTests`. Kỳ vọng: PASS.
  - `ui_shots.py --label check-t7 guideCheck guideStageDone guide` trên iPhone và iPad, rồi xem ảnh.
- [ ] **Step 5:** `lint_localizable.py` sạch. Commit `feat(guide): quét kiểm tra ngay trong màn giải, cùng một khối 3D`.

### Task 8: Tích hợp L2, ảnh, tài liệu, bản cài máy

**Files:**
- Modify: `docs/ROADMAP.md` (mục ngắn "Thiết kế lại màn quét"),
  `docs/superpowers/plans/2026-11-27-cubingo-dot-a-device-checklist.md` (sửa các mục quét theo luồng mới)

- [ ] **Step 1:** `tools/dev/run_tests.py --full`. Kỳ vọng: 0 lỗi, không có `[false-green]`. Chạy thêm:
  - `python3 tools/i18n/lint_localizable.py`
  - `python3 tools/release/lint_debug_symbols.py`
  - `python3 tools/release/lint_preview_code.py`
  - `python3 tools/template/sync_core.py check`
  - `python3 tools/common/lint_identity.py`

  Kỳ vọng: tất cả sạch.
- [ ] **Step 2:** `ui_shots.py all --label redesign-l2` trên iPhone dọc và iPad ngang, cộng
  `--content-size accessibility-extra-large scan scanTurn guideCheck`. Xem từng ảnh:
  - không có chữ bị cắt;
  - nút ✓ không che khối;
  - iPad đặt hai cột cạnh nhau.
- [ ] **Step 3:** Cập nhật ROADMAP và checklist device. Commit `docs: ROADMAP + checklist device cho màn quét mới`.
- [ ] **Step 4:** Build Internal và cài lên BonGao bằng lệnh trong memory `fixture-plist-crashes-on-device` (plist giả có
  `API_KEY` đúng định dạng). Mở app theo dõi khoảng 20 s xem không crash. Đây là cổng người dùng: người dùng tự thử quét
  thật.
