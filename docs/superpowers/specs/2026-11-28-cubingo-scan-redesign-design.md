# Cubingo — thiết kế lại màn quét

Ngày: 2026-11-28. Bổ sung cho spec gốc `docs/superpowers/specs/2026-11-27-cubingo-design.md` (Đợt A). Chỗ nào hai tài
liệu khác nhau về màn quét, tài liệu này thắng.

## Ý định

Màn quét của Đợt A bắt người dùng đọc câu ("Turn the cube left — the next center should face you") và đoán động tác.
Người dùng thử trên máy thật thấy khó hiểu. Mục tiêu mới là **nhìn là làm được, không cần đọc chữ**:

- Người dùng luôn thấy các mặt đã quét có màu gì trên một khối 3D, nên so ngay được với khối thật trong tay.
- Mặt đang quét nhận màu camera liên tục, cho tới khi người dùng bấm xác nhận.
- Động tác xoay tiếp theo được chỉ bằng mũi tên trên khung camera, kèm khối 3D xoay mẫu đúng động tác đó.

Tham khảo: app Asolver (camera nửa trên, khối 3D nửa dưới, mặt đang quét có viền nổi, nút Next). Bản phác đã duyệt:
https://claude.ai/artifact/EBtFM7ncn1r1nVf77r7vPR (hướng A, bản 2). So sánh engine 3D:
https://claude.ai/artifact/TzNBLtzwVqwbNawDYpSCPE.

Nguyên tắc "hình ảnh và chuyển động trước, chữ sau" sẽ áp tiếp cho màn chỉ bước giải ở đợt sau. Đợt này chỉ làm màn quét
(gồm quét kiểm tra sau chặng). Khối 3D và hoạt ảnh xoay cả khối làm ở đợt này phải dùng lại được cho đợt đó.

## Mục tiêu

1. Quét đủ 6 mặt mà không cần đọc một câu chữ nào.
2. Màu trên khối 3D khớp với cái camera đang thấy, đổi theo thời gian thực, không nhấp nháy khó chịu.
3. Mỗi mặt cần đúng một lần bấm ✓. Tổng cộng 6 lần bấm, không có bước "quay về mặt đầu".
4. Diện tích màn hình dành gần hết cho camera và khối 3D.
5. Đúng trên iPhone dọc và iPad ngang.

## Không làm (đợt này)

- Thiết kế lại màn chỉ bước giải. Màn đó chỉ đổi phần quét kiểm tra (mục "Quét kiểm tra sau chặng").
- Tự chụp. Đợt này bỏ tự chụp, chỉ chụp khi bấm ✓.
- Sửa màu bằng cách chạm ô trên khối 3D. Sửa vẫn làm ở màn kiểm tra dạng sơ đồ phẳng hiện có.
- ARKit hay bám theo khối thật trong không gian.
- Đổi khối ở màn chọn cách giải (vẫn là Canvas isometric).

## Anti-goal (dù chạy đúng vẫn coi là hỏng)

- Người dùng phải đọc chữ mới biết làm gì tiếp.
- Thêm thanh, thẻ, banner chiếm chỗ của camera hoặc khối.
- Hai `RealityView` cùng sống trong một chồng điều hướng. Lỗi "khối trắng trơn" của Đợt A là do đúng điều này.
- Màu trên khối giật, nhấp nháy theo từng khung camera.

## Ràng buộc

- iOS 18, SwiftUI, RealityKit `RealityView` với camera ảo (như `Cube3DView` hiện có).
- Quy ước repo: `.claude/rules/conventions.core.md`, `.claude/rules/conventions.app.md`. Đặc biệt:
  - chuỗi UI tiếng Anh, qua `String(localized:)`;
  - `.scaledFont`;
  - bố cục theo size class hoặc bề rộng thật;
  - xác nhận bằng `.alert`;
  - ảnh chụp iPhone dọc và iPad ngang trước khi báo xong.
- **Một `RealityView` mỗi chồng điều hướng** (bất biến, xem `Cube3DView`).
- Bộ lấy mẫu camera giữ nguyên: `ScanCamera`, `ScanSampler` (9 mẫu RGB mỗi khung), `ScanClusterer` + `ScanHungarian`,
  `ScanReviewModel`, `CubeValidation`.

## Cách làm đã chọn

### Các cách đã cân nhắc

| Cách | Ưu | Nhược |
|---|---|---|
| **RealityKit, tổ chức lại chồng màn (đã chọn)** | Khối đẹp nhất: viên bo tròn, có ánh sáng và phối cảnh. Cùng khối với màn giải. Có sẵn bộ hoạt ảnh xoay lớp | Phải tổ chức lại luồng điều hướng để giữ bất biến một-RealityView |
| Canvas tự vẽ (nâng `Cube3DIsoView`) | Không có rủi ro chồng màn, nhẹ | Phẳng, không bo tròn hay bóng. Trong app có hai kiểu khối |
| SceneKit riêng | Né được giới hạn RealityKit | Engine thứ ba. Apple đã ngừng phát triển SceneKit |

Người dùng chọn RealityKit, với lý do UI/UX phải tốt nhất và công sức không phải vấn đề.

## Màn quét (thiết kế đã duyệt)

### Bố cục

```
iPhone dọc                         iPad ngang (regular width)
┌───────────────────────┐          ┌──────────────────┬───────────┐
│ ‹            ▦   ↶    │          │ ‹                │  ▦  ↶     │
│   camera + khung 3×3  │  ~55%    │  camera          │  khối 3D  │
│   (mũi tên cong vẽ    │          │  + khung 3×3     │           │
│    đè lên khi cần)    │          │                  │    (✓)    │
├───────────────────────┤          │                  │      3/6  │
│       khối 3D         │          └──────────────────┴───────────┘
│                  3/6  │
│         (✓)           │
└───────────────────────┘
```

- **Camera:** nửa trên, khoảng 55% chiều cao (iPad ngang thì chiếm phần trái). Có khung 3×3 viền màu nhấn cam
  `#FF7A00`. Bỏ 9 chấm màu sống trong khung, vì màu sống giờ hiện trên khối.
- **Ba nút tròn nhỏ** nền mờ, đặt đè lên góc camera:
  - quay lại (trái trên);
  - nhập màu tay (`.review(manual: true)`);
  - hoàn tác mặt gần nhất (chỉ hiện khi có mặt để hoàn tác).
- **Khối 3D:** phần còn lại, cỡ lớn nhất có thể. Kéo để xoay xem, thả ra tự về (giống màn giải).
- **Nút ✓:** tròn khoảng 64 pt, giữa đáy. Mờ đi khi chưa có lưới 9 mẫu hợp lệ.
- **Bộ đếm "n/6":** chữ nhỏ ở góc dưới phải. Đây là chữ duy nhất trên màn, và là số chứ không phải câu.
- **Không có** chấm tiến độ, câu hướng dẫn hay thẻ thông báo.

### Khối 3D khi quét

- **Mặt chưa quét:** màu thân khối (xám đậm), không có màu ô.
- **Mặt đang quét:** viền cam phát sáng. 9 ô nhận màu RGB thô từ camera mỗi khi có mẫu mới, làm mượt theo thời gian
  (trung bình trượt hàm mũ) để không nhấp nháy. Thời hằng do builder chọn, khoảng 150–250 ms.
- **Mặt đã quét:** giữ đúng màu thô lúc bấm ✓.
- **Hướng khối:** khối luôn quay sao cho mặt đang quét nằm ở vị trí "trước mặt" của góc nhìn, khớp hướng khối thật đang
  hướng vào camera. Góc nhìn vẫn hơi chéo như màn giải, nên vẫn thấy được hai mặt kề bên.
- **Màu hiển thị là màu thô** camera thấy (có thể ám vàng, ám hồng), không phải màu chuẩn sau phân nhóm, để người dùng tự
  so với khối thật. Màu chuẩn chỉ có sau khi đủ 6 mặt.

### Thứ tự quét và động tác

Sáu bước, mỗi bước một lần bấm ✓:

| Bước | Mặt chụp | Động tác trước bước (mũi tên + khối diễn mẫu) |
|---|---|---|
| 1 | F | (không có; đưa một mặt bất kỳ vào khung) |
| 2 | R | xoay cả khối sang trái 90° |
| 3 | B | xoay cả khối sang trái 90° |
| 4 | L | xoay cả khối sang trái 90° |
| 5 | U | lật mặt trên về phía mình 90° (khi L đang hướng vào camera) |
| 6 | D | lật thêm 180° cùng chiều để mặt dưới hướng vào camera |

- Bỏ bước "quay về mặt đầu" của Đợt A. Hướng lưới của U và D khi cầm theo bảng trên là **xác định**: giao thức khai báo
  sẵn số nấc xoay lưới của từng mặt, để `assemble` trả đúng thứ tự đọc Kociemba (U R F D L B).
  `CubeValidation.repairScanOrientation` vẫn giữ làm lưới an toàn khi người dùng cầm lệch.
- Builder phải tính đúng số nấc xoay cho U và D theo bảng trên, và có test chứng minh: quét một khối đã biết theo đúng
  động tác thì ghép ra đúng khối đó.

### Sau khi bấm ✓

1. Mặt hiện tại bị khoá màu. Máy rung kiểu capture (`deps.haptic(.capture)`). Bộ đếm tăng.
2. Mặt sắp quét lên viền cam.
3. **Mũi tên cong** vẽ dần lên khung camera, đè lên khối thật, theo hướng của động tác: cung sang trái cho xoay trái,
   cung từ trên xuống cho lật về phía mình, cung kép hoặc mũi tên vòng cho lật 180°. **Đồng thời** khối 3D quay cả khối
   theo đúng động tác (khoảng 0,8–1 s, easing mượt).
4. Mũi tên và hoạt ảnh **lặp lại** khoảng mỗi 2,5 s, cho tới khi camera thấy một tâm khác hẳn tâm vừa chụp (ΔE ≥
   `ScanCaptureModel.sameCenterDeltaE`), nghĩa là người dùng đã xoay. Khi đó mũi tên tắt, mặt mới bắt đầu nhận màu sống.

   Ở mỗi lần lặp, khối không được nhảy giật: hoặc diễn lại động tác từ tư thế trước, hoặc rung nhẹ theo hướng động tác.
   Builder chọn cách nào miễn mượt.

### Lỗi và tình huống đặc biệt (báo bằng hình, không bằng chữ)

- **Bấm ✓ khi tâm trùng một mặt đã quét:**
  - không nhận lần bấm đó;
  - khối lắc ngang nhẹ, mặt bị trùng nháy đỏ một lần;
  - máy rung kiểu warning (`deps.haptic(.warning)`).
- **Hoàn tác:** mặt gần nhất trở về xám, khối quay ngược về mặt đó (hoạt ảnh), mặt đó nhận màu sống lại.
- **Quá tối / chói** (`ScanLighting.tip`): một biểu tượng nhỏ (bóng đèn / tia chói) nhấp nháy ở góc camera, không có câu.
- **Thiếu quyền camera:** giữ nguyên `ScanPermissionView` hiện có.
- **VoiceOver:** mọi thông tin hình ảnh phải có nhãn tiếng Anh tương đương. Ví dụ:
  - nút ✓: "Capture this side";
  - khối: "3 of 6 sides scanned. Next: turn the whole cube left".

  Chữ chỉ dành cho trợ năng, không hiện trên màn.

### Đủ 6 mặt

- Phân nhóm (`ScanClusterer`), rồi validate như `ScanReviewModel` đang làm.
- Kết quả `.ok` hoặc `.autoFixed`: **đi thẳng sang màn chọn cách giải**, không qua màn kiểm tra.
- Có lỗi: mở màn kiểm tra dạng sơ đồ phẳng (`ScanReviewView`) như hiện nay, có ô nghi ngờ được đánh dấu.
- Khi vào màn chọn cách giải, **màn quét không còn trong chồng**: `path` được thay chứ không chồng thêm.
  - Đi thẳng: `[.scan]` → `[.mode]`.
  - Qua kiểm tra: `[.scan, .review]` → `[.mode]`.

  Màn kiểm tra không có `RealityView` nên được phép tạm nằm trên màn quét.
- Nút quay lại ở màn chọn cách giải đưa về **màn quét mới, quét từ đầu**: `path = [.scan]` và xoá kết quả quét cũ. Không
  về màn chọn khối. Màn nhập tay (`.review(manual: true)`) giữ cách hiện có, nhưng khi bấm Continue cũng thay `path` thành
  `[.mode]`.

## Quét kiểm tra sau chặng (Teach me)

Hiện nay route `.check` đẩy một `ScanView` lên trên màn giải. Màn giải có `RealityView`, nên khi màn quét cũng có
`RealityView` thì bất biến bị phá. Thiết kế mới:

- **Quét kiểm tra một mặt diễn ra ngay trong màn giải.** Không còn route `.check` riêng.
  - Camera trượt vào chiếm nửa trên.
  - **Chính khối của màn giải** thu xuống nửa dưới, quay để mặt cần kiểm (`GuideCheck.spec(kind).face`) hướng ra trước.
  - Mặt đó nhận màu camera sống. Các mặt khác giữ màu trạng thái mong đợi.
  - Nút ✓ để chụp, nút bỏ qua là biểu tượng nhỏ trên camera.
- **Kết quả:**
  - Khớp: rung success, camera trượt ra, sang chặng sau.
  - Lệch: hiện màn mời quét lại cả khối như hiện nay. Mặt lệch được đánh dấu đỏ trên khối nếu làm được.
- **Quét lại cả khối sau khi lệch** (`startRescan`): thay `path` bằng `[.scan]`, giữ `isRechecking` và phiên trong
  `FlowModel`. Quét xong, `replan` như hiện nay, rồi `path = [.guide(.teach)]`. Màn giải dựng lại từ phiên đã lưu.
  Không đẩy `.scan` lên trên `.guide`.
- Nếu thiếu quyền camera thì giữ hành vi hiện tại (bỏ qua kiểm tra).

Các điểm dưới đây do người viết spec tự quyết (sau vòng soát của builder), người dùng có thể sửa:

- **Bố cục màn giải khi đang kiểm tra:** ẩn thẻ bước, chip cách cầm và các nút Back / Replay / Next. Chỉ còn camera,
  khối, nút ✓ và nút bỏ qua.
  - iPad ngang: camera bên trái, khối bên phải, giống màn quét.
  - Khối quay mặt cần kiểm ra trước, kèm mũi tên cong trên camera chỉ động tác đưa mặt đó vào camera. Ví dụ lật cả
    khối để mặt dưới hướng vào camera khi kiểm chữ thập hoặc các góc.
- **Bấm ✓ khi camera đang thấy sai mặt** (tâm không khớp `isRequestedSide`): không chấm điểm, coi như mặt trùng ở màn
  quét. Khối lắc nhẹ, máy rung warning, chờ người dùng đưa đúng mặt vào. Không bao giờ coi đó là "lệch".
- **Màn mời quét lại khi lệch:** thành lớp phủ ngay trong màn giải (không còn là route).
  - Khối hiện các ô lệch nháy đỏ.
  - Hai nút có biểu tượng: quét lại cả khối, bỏ qua.
  - Chữ chỉ một dòng tiêu đề ngắn.
- **Bỏ dở khi đang quét lại cả khối** (quay lại từ màn quét với `isRechecking`): khôi phục `path = [.guide(.teach)]` với
  phiên cũ, vẫn ở trạng thái xong chặng (người dùng có thể kiểm lại hoặc bỏ qua). Đặt `isRechecking = false`.

## Quay lại từ màn kiểm tra

Đây cũng là quyết định của người viết spec.

- Màn quét vẫn sống bên dưới màn kiểm tra nên giữ nguyên trạng thái của nó.
- Quay lại từ màn kiểm tra (có lỗi): trở về màn quét ở 6/6, có thể hoàn tác mặt gần nhất. Bấm ✓ khi đã đủ 6/6 thì phân
  nhóm lại.
- Quay lại từ nhập tay, khi mở giữa chừng: trở về đúng chỗ đang quét dở.
- Trạng thái quét thuộc về view (`ScanCaptureModel`), không chuyển lên `FlowModel`.

## Khối 3D dùng chung (mở rộng `Cube3DView`)

Đây là phần dùng lại cho màn giải ở đợt sau. Builder quyết định API cụ thể. Cần có:

1. **Hướng cả khối điều khiển được:** đặt một hướng đích (mặt nào ra trước), có hoạt ảnh quay cả khối mượt giữa hai
   hướng, dùng chung cơ chế huỷ-task/token như hoạt ảnh lớp hiện có.
2. **Tô màu ô bằng RGB thô** cho một hoặc nhiều mặt (đè lên bảng màu), cập nhật nhiều lần mỗi giây mà không dựng lại
   entity.
3. **Mặt chưa có màu:** hiện màu thân khối.
4. **Viền phát sáng một mặt**, có thể nhấp nháy.
5. **Hiệu ứng:** lắc cả khối; nháy đỏ một mặt.
6. Màn quét chưa có `CubeFacelets` (chưa phân nhóm) nên khối phải chạy được ở chế độ "chỉ có màu thô", không cần
   bảng màu.

## Phần để builder quyết

- Hằng số làm mượt màu, thời lượng và easing hoạt ảnh, hình dáng mũi tên (vẽ bằng SwiftUI `Path` / `Shape` đè lên
  camera).
- API mở rộng của `Cube3DView` / `Cube3DController`, và cách chia file.
- Cách phát hiện "người dùng đã xoay" để tắt mũi tên (gợi ý: ΔE của tâm so với tâm vừa chụp).
- Cỡ khối và tỉ lệ chia màn hình chính xác, miễn camera khoảng 55% trên iPhone dọc và khối lớn nhất có thể.
- Có giữ `ScanStabilizer` hay không. Không còn tự chụp, nhưng có thể dùng để làm mờ nút ✓ khi khung đang rung.
- Route preview / seed để chụp ảnh UI:
  - `scan` (đang quét mặt 3);
  - `scanTurn` (đang hiện mũi tên);
  - `guideCheck` (quét kiểm tra trong màn giải).
- Event telemetry mới nếu cần, đặt tên theo quy ước `scan_*`.

## Tiêu chí xong

- Quét đủ 6 mặt trên Simulator (nguồn giả `ScanPreviewSeed`) đi thẳng sang màn chọn cách giải. Test chứng minh:
  - thứ tự 6 mặt và số nấc xoay ghép ra đúng khối;
  - mặt trùng bị từ chối;
  - hoàn tác trả lại đúng trạng thái;
  - điều hướng thay `path` như mô tả;
  - quay lại từ màn chọn cách giải thì quét lại từ đầu.
- Không lúc nào có hai `RealityView` trong một chồng. Có test hoặc phép kiểm cho mọi đường điều hướng: quét → chọn
  cách giải → giải → kiểm tra → quét lại.
- Ảnh chụp iPhone dọc và iPad ngang của `scan`, `scanTurn`, `guideCheck`, cả cỡ chữ trợ năng.
- `run_tests.py --full` xanh, `lint_localizable.py` sạch.
- Người dùng thử trên BonGao (cổng người dùng).
