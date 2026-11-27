# Cubingo — thiết kế bản 1 (Plan 7: app thật đầu tiên từ template)

Ngày: 2026-11-27 · Trạng thái: **user DUYỆT 2026-11-27** · Template: `ios-app-factory` v0.6.0 + vá lint định danh (`20b1621`, sẽ là v0.6.1)

> Ghi chú: chữ hiển thị trong app viết tiếng Anh ở doc này (nguồn String Catalog là `en`); bản tiếng Việt dịch sau.
> "Đã chốt" = user quyết trong buổi phỏng vấn 2026-11-27. "Đề xuất của Claude" = quyết định của Claude, user sửa được.

## 1. Ý định và lý do

Cubingo là app iOS (iPhone + iPad) **kiếm tiền trên App Store**, giúp **người mới chơi** giải khối Rubik: quét khối bằng
camera, rồi được chỉ từng bước bằng khối 3D có animation. Khác ứng dụng dẫn đầu thị trường ASolver (Android/Windows,
10M+ lượt tải, KHÔNG có trên iOS — chỉ giải hộ), Cubingo **dạy cách giải** theo phương pháp cho người mới, ngoài chế độ
giải nhanh. Đây cũng là app thật đầu tiên chạy hết vòng đời template (tạo app → build → store/ASO → web → ra bản).

Đã chốt:
- Đối tượng: người mới chơi (teen, người lớn). **Không** nhắm tới trẻ em, **không** vào mục Kids (giữ analytics/crash).
- **Bản 1 miễn phí hoàn toàn, không quảng cáo.** Thu phí bật sau, bằng tính năng MỚI (không rút cái đã cho miễn phí).
- Loại khối bản 1: **3×3 và 2×2**.
- Lõi: hai chế độ — **Teach me** (phương pháp người mới, theo chặng, có giải thích) và **Just solve it** (ngắn nhất).
- Hiển thị: **khối 3D ảo trên màn hình** + kiểm tra bằng camera sau mỗi chặng; AR đè lên khối thật để bản sau.
- Quét: camera chạy liên tục, tự chụp khi đứng yên, hướng dẫn xoay mặt; màn sửa tay từng ô.
- Phong cách giao diện **A — vui tươi, thân thiện** (bo tròn to, màu ấm cam–hồng, nút "dày" có bóng dưới).
- Mở app **vào thẳng màn chọn loại khối**; chọn cách giải **sau khi quét**; thẻ mờ "Coming soon" cho Pyramid/4×4.
- Thêm **khoảng 10 hoa văn đẹp** (patterns) ở bản 1.
- **Bảng màu khối tự nhận diện** từ chính khối quét được (không cài đặt màu) — 5.11. iOS tối thiểu **18**.
- Định danh `com.vimindtech.cubingo`, email hỗ trợ bongao.developer@gmail.com, tên miền mua sau, không có hạn chót (mục 7, 12).
- Ngôn ngữ giao diện: **tiếng Anh + tiếng Việt**; metadata App Store thêm 5–7 ngôn ngữ lớn.
- Tên: **Cubingo**. Hướng dài hạn: thi đấu, xếp hạng theo thời gian (bấm giờ bằng camera), tìm trận 1:1 và nhiều người.

### Thế nào là thành công (đề xuất của Claude)
- Người mới cầm khối xáo trộn, mở app, quét và **giải xong khối thật** mà không cần trợ giúp ngoài app.
- Tỉ lệ "quét bắt đầu → khối đã giải" và "Teach me bắt đầu → xong chặng 7" đo được bằng analytics (mục 9).
- Đánh giá App Store ≥ 4,5★; không có đánh giá 1★ vì "lời giải sai làm hỏng khối".

## 2. Mục tiêu · không làm · phản mục tiêu

**Mục tiêu bản 1:** chọn khối → quét (hoặc nhập tay) → kiểm tra → Teach me / Just solve it → chỉ bước 3D → giải xong;
hoa văn; cài đặt cơ bản; Anh + Việt; iPhone + iPad; chạy hoàn toàn trên máy.

**Không làm ở bản 1:** paywall/thu phí; quảng cáo; tài khoản; mạng (ngoài analytics/crash của template); AR; bấm giờ;
thi đấu/xếp hạng/đấu trận; 4×4, Pyraminx và khối khác; luyện công thức; nhận màu bằng học máy; mục Kids; hướng dẫn
tháo-lắp sửa khối bị lắp sai (chỉ phát hiện và giải thích).

**Phản mục tiêu (dù chạy được vẫn là thất bại):**
- Lời giải SAI hoặc lệch hướng cầm khối ⇒ người dùng làm hỏng khối. Đúng đắn của bộ giải và của chỉ dẫn hướng cầm là
  ưu tiên số một.
- Người dùng bị kẹt ở bước quét không có lối thoát (luôn có nhập tay).
- Màn hình dày chữ như sách giáo khoa; người mới thấy "khó".
- Bất kỳ dấu hiệu "app đòi tiền" ở bản 1.

## 3. Ràng buộc

- Template v0.6.0 (`new_app.py`): định danh chỉ ở `app.config.toml`; quy ước, cổng và thang kiểm chứng của template áp
  dụng nguyên (L1/L2/L3, `verify_release_clean.sh`, i18n lint, `#if INTERNAL` cho code debug).
- **Không dùng chữ "Rubik"** (thương hiệu đã đăng ký) trong tên, phụ đề, từ khoá, ảnh store. Dùng "cube", "puzzle
  cube", "magic cube", "speed cube". Không dùng hình/logo khối mang thương hiệu.
- Mã bộ giải lấy từ nguồn mở chỉ khi giấy phép cho phép bán app đóng (MIT/BSD/Apache…); **không GPL/LGPL**.
- Chạy offline: quét, giải, animation không cần mạng.
- ARKit/LiDAR KHÔNG cần — chỉ camera thường (mọi iPhone/iPad hỗ trợ iOS tối thiểu).
- Thiết bị tối thiểu: **iOS 18** (đã chốt) — để dùng `RealityView` (RealityKit cho SwiftUI chỉ có từ iOS 18 trên
  iPhone/iPad). Template mặc định iOS 17 ⇒ app nâng `deploymentTarget` trong `AppHost/project.yml` (lớp gieo, app sở hữu).
  Mục tiêu hiệu năng đo trên máy iOS 18 đời thấp nhất (iPhone XS/XR).

## 4. Approaches (cách dựng — đã chốt)

Tổng thể chỉ một hướng hợp lý: repo **Cubingo** sinh bằng `new_app` từ template, Swift/SwiftUI thuần, mọi thứ trên máy.
Ba chỗ chọn kỹ thuật (user đồng ý cả ba lựa chọn của Claude):

| Chỗ | Đã chọn | Phương án khác và vì sao không |
|---|---|---|
| Hiển thị 3D + animation | **RealityKit** — dùng chung cho AR/bấm giờ bằng camera sau này | SceneKit: dễ hơn chút nhưng Apple ngừng phát triển, lên AR phải viết lại · Metal tự vẽ: tốn công gấp nhiều lần |
| Nhận màu | **Xử lý ảnh cổ điển** — lấy mẫu 9 vùng trong khung, phân nhóm 6 màu trên CẢ 54 ô cùng lúc (mỗi nhóm đúng 9) | Core ML: tốt hơn khi khối nghiêng/chuyển động (hợp bấm giờ realtime bản sau) nhưng cần dữ liệu ảnh gán nhãn, chậm bản 1 |
| Bộ giải | **Kociemba hai pha** (3×3, ~20 bước) + **tìm tối ưu** (2×2) cho Just solve it; **bộ giải theo luật 7 chặng tự viết** cho Teach me | Chỉ dùng một bộ giải ngắn nhất cho cả hai chế độ: không dạy được (bước không theo chặng, không giải thích được) |

## 5. Trải nghiệm (đã chốt, chi tiết là đề xuất của Claude)

### 5.1 Luồng chính
```
Mở app ─► Chọn loại khối ─► Quét 6 mặt ─► Kiểm tra màu/hợp lệ ─► Chọn cách giải ─► Màn chỉ từng bước ─► Đã giải 🎉
              │                  └─(camera chịu thua)─► Nhập tay ─┘        │
              ├─► Patterns (hoa văn)                                         └─(Teach me: hết mỗi chặng)─► Quét kiểm tra
              └─► Settings
```

### 5.2 Màn chọn loại khối (màn mở đầu)
Tiêu đề "Which cube do you have?"; thẻ to có hình khối: **3×3** ("The classic"), **2×2** ("Pocket cube"); thẻ mờ nhãn
SOON: **Pyramid**, **4×4** (không bấm được, hoặc bấm ra một lời nhắn "Coming in a future update"). Dòng gợi ý dưới:
"Not sure? Count the squares on one side". Cùng màn có lối vào **Patterns** và **Settings** (đề xuất: hai nút tròn ở
góc trên, không dùng tab bar — app một luồng, tab bar thừa; iPad cũng một cột ở giữa với `readableContentWidth`).

### 5.3 Quét
- Xin quyền camera **ngay trước lần quét đầu**, có màn giải thích ngắn; từ chối ⇒ mời nhập tay + nút mở Settings.
- Camera toàn màn hình; khung 3×3 (2×2 cho khối 2×2) cố định ở giữa; màu nhận được hiện trực tiếp trong từng ô.
- **Giao thức quét cố định theo HƯỚNG XOAY, không theo màu** (cần để dựng đúng trạng thái; bảng màu tự nhận — 5.11):
  mặt 1 là mặt đang hướng về người dùng; xoay cả khối sang trái để lần lượt lấy 4 mặt bên (giữ nguyên mặt trên); rồi
  nghiêng lấy mặt trên, nghiêng ngược lấy mặt dưới. Mỗi bước có hình minh hoạ hướng xoay (animation khối 3D nhỏ). 2×2
  không có tâm ⇒ cùng giao thức, mốc là hướng cầm (chi tiết để người dựng, mục 12).
- **Tự chụp** khi khung ổn định ~0,6 s (màu 9 ô giống nhau qua nhiều khung hình liên tiếp) + rung nhẹ; có nút chụp tay.
- Dải 6 chấm tiến độ; sau mặt 6 sang Kiểm tra. Nút "Enter colors manually" luôn có.
- Mẹo ánh sáng khi độ sáng thấp/chói ("Face a window or a lamp").

### 5.4 Kiểm tra màu (và nhập tay)
- Sơ đồ trải phẳng 6 mặt; chạm ô → chọn màu ở bảng 6 màu. Nhập tay = cùng màn, bắt đầu từ sơ đồ trống (chỉ tô sẵn tâm).
- Kiểm theo thứ tự, báo **một** lỗi dễ hiểu nhất mỗi lần, đánh dấu ô nghi ngờ:
  1. Đếm màu: mỗi màu đúng 9 ô (2×2: 4) — "You have 10 orange and 8 red. One square is probably wrong."
  2. Miếng không tồn tại (vd một cạnh trắng–vàng) ⇒ ô nghi sai.
  3. **Khối không giải được** (lắp sai): góc bị xoay (tổng xoắn góc ≠ 0 mod 3), cạnh bị lật (tổng lật cạnh lẻ), hai
     miếng bị đổi chỗ (chẵn lẻ hoán vị lệch). Giải thích bằng hình: "One corner is twisted — this happens when a cube was
     taken apart and put back. Twist that corner to fix it." (hướng dẫn tháo-lắp đầy đủ để bản sau). Trước khi báo lỗi
     này, app thử lại các hướng xoay của mặt trên/dưới (16 tổ hợp) vì người dùng hay nghiêng sai hướng khi quét — tổ hợp
     duy nhất hợp lệ thì tự sửa không hỏi.
- Hợp lệ ⇒ "Looks right — let's go!" → Chọn cách giải.

### 5.5 Chọn cách giải
Khối 3D của chính khối vừa quét + hai thẻ: **Teach me** (mặc định, viền cam): "Learn the beginner method in 7 stages" +
ước lượng số bước; **Just solve it**: "Shortest way, about 20 moves". Khối đã giải sẵn ⇒ chúc mừng, mời Patterns.

### 5.6 Màn chỉ từng bước (dùng chung cho Teach me, Just solve it, Patterns)
- Trên: tên chặng ("Stage 3 · Middle layer") + đếm bước "3 / 8", thanh tiến độ. Just solve it: chỉ "Move 7 / 21".
- Giữa: khối 3D trạng thái hiện tại; lớp sắp xoay sáng lên, **mũi tên** chỉ chiều, rồi animation xoay. Kéo để xoay
  nhìn quanh, thả ra khối tự về góc nhìn chuẩn.
- **Hướng cầm luôn hiện rõ**: chip "Hold: white on top, green facing you" ở đầu chặng và mỗi khi lời giải đòi đổi hướng
  cầm (xoay cả khối x/y/z cũng là một bước có animation riêng). Đây là chỗ người mới sai nhiều nhất.
- Thẻ bước: ký hiệu to (R, U', F2) + câu thường ("Turn the right side up"); Teach me thêm câu "vì sao" ngắn ở đầu mỗi
  chặng/nhóm bước ("We're moving the white-red edge up to the top").
- Nút: Back, Replay, Next (to nhất); tốc độ animation (chậm/vừa/nhanh); bật/tắt danh sách ký hiệu; nút "?" giải nghĩa
  ký hiệu.
- Teach me, hết mỗi chặng: màn "Stage complete!" + **quét kiểm tra** (chỉ các mặt cần cho chặng đó, đề xuất 1–2 mặt;
  bỏ qua được). Khớp ⇒ chặng sau. Lệch ⇒ "Looks different from what we expected — no worries" → quét lại cả khối và
  **lập lại lời giải từ trạng thái mới** (không bắt làm lại từ đầu).
- Xong: màn ăn mừng (hoạt hình + rung), số bước, thời gian; lối ra: giải khối khác / thử hoa văn.

### 5.7 Teach me — 7 chặng (3×3) và chặng của 2×2
3×3, phương pháp người mới phổ biến (tên chặng viết theo bảng màu chuẩn ở đây; trong app là chuỗi có tham số màu —
5.11): 1 White cross · 2 White corners · 3 Middle layer · 4 Yellow cross · 5 Yellow face ·
6 Yellow corners (đặt đúng chỗ) · 7 Yellow edges (đặt đúng chỗ). Mỗi chặng: một câu mục tiêu + ảnh "trông thế nào khi
xong" + các bước sinh từ trạng thái thật. Các công thức chuẩn của phương pháp (vd "Sune", "right trigger") được đặt tên
và lặp lại nhất quán để người dùng học thuộc dần.
2×2 (đề xuất): 1 White face (tầng 1) · 2 Yellow face · 3 Last layer — dùng lại công thức của 3×3 để kiến thức chuyển được.

### 5.8 Patterns (hoa văn)
~10 mẫu kinh điển (checkerboard, cube in cube, superflip, cross, stripes, …) cho 3×3; 2×2 vài mẫu nếu có ý nghĩa.
Thẻ có ảnh kết quả; bắt đầu yêu cầu khối **đã giải** (nhắc rõ; có lối "Solve my cube first"); chạy bằng màn chỉ từng
bước; có "Undo pattern" (chuỗi ngược). Chuỗi bước hoa văn là kiến thức phổ biến, tự gõ vào dữ liệu app.

### 5.9 Settings
Language (theo template `AppLanguage`: System/English/Tiếng Việt) · Animation speed · Haptics · Show move notation ·
About/What's New/Feedback/Rate (có sẵn ở template). Không có cài đặt bảng màu — xem 5.11.

### 5.11 Bảng màu khối: TỰ NHẬN DIỆN (đã chốt)
App không giả định bảng màu chuẩn và không có màn cài đặt màu. Sáu ô tâm (3×3) — hoặc tám góc (2×2) — quét được xác định
bảng màu của CHÍNH khối đó: mỗi tâm là một nhóm màu, mặt đối diện suy ra từ cấu trúc khối. Hệ quả cho người dựng:
- Khối 3D ảo vẽ bằng màu đo được (đã chuẩn hoá) của khối người dùng, không phải bảng màu chuẩn.
- Mọi chữ nhắc tới mặt/màu ("white on top", "the white-red edge", tên chặng "White cross", "Yellow face") là **chuỗi có
  tham số màu**, sinh từ bảng màu đã nhận: chặng 1 bắt đầu từ màu của một tâm do app chọn (ưu tiên tâm gần trắng nhất;
  không có thì tâm sáng nhất), các chặng tầng cuối dùng màu tâm đối diện. Tên màu hiển thị = tên chuẩn gần nhất theo sắc
  độ (white/yellow/red/orange/blue/green/purple/pink…), có trong String Catalog cả en lẫn vi (chuỗi ghép phải localize đúng
  cách theo quy ước i18n của template — không nối chuỗi).
- Giao thức quét gọi mặt theo vị trí + màu tâm vừa thấy ("Turn the cube left — the next center should face you"), không
  đòi "tâm xanh lá trước": mặt đầu tiên là mặt bất kỳ người dùng đang cầm; app ghi hướng theo lần xoay đã hướng dẫn.
- Hai tâm màu quá giống nhau (không phân biệt được) ⇒ báo và mời người dùng chạm chọn ở màn kiểm tra.
- Test: mọi giáo trình/chuỗi chạy với ít nhất một bảng màu KHÁC chuẩn (vd đổi chỗ xanh dương–đỏ) để bắt chỗ ngầm giả
  định màu chuẩn.

### 5.10 Phong cách A và iPad
**Giao diện SÁNG, bản 1 chỉ sáng** (đề xuất của Claude; dark mode để sau). Template mặc định tối, nhưng khe theme
`DSTheme` (palette + `colorScheme`) do app khai ở `AppHost/AppHost/AppTheme.swift` (lớp gieo, app sở hữu) ⇒ Cubingo khai
palette sáng + `colorScheme: .light`, KHÔNG sửa `Core/`. Màn lõi của template (Settings, What's New, Feedback,
onboarding) đi theo palette đó; người dựng kiểm chúng đọc được trên nền sáng — màn nào của lõi còn giả định nền tối thì
sửa ở TEMPLATE (bản vá, tag, `sync_core`), không sửa tại app. Thành phần riêng kiểu A ("nút dày", thẻ bo to, chữ SF
Rounded) nằm ở `Features/` của app.
Token: nền gradient kem–hồng nhạt, nhấn cam `#FF7A00`, xanh lá cho "xong", thẻ trắng bo 22–24 pt, chữ SF Rounded đậm.
Bản phác đã duyệt (mở bằng trình duyệt): `docs/superpowers/specs/assets/2026-11-27-cubingo/` — `visual-style.html`
(user chọn A), `main-flow.html` (màn quét + màn kiểm màu; màn "lộ trình" trong file này đã BỎ), `picker-flow-v2.html`
(màn chọn khối + chọn cách giải).
iPad (size class regular): màn chỉ bước chia hai cột — khối 3D trái, thẻ bước + danh sách bước phải; màn chọn khối lưới
4 cột; màn quét giữ khung ở giữa. Theo quy ước template: bố cục theo size class/bề rộng thật, không theo idiom.

## 6. Kiến trúc (đề xuất của Claude — người dựng chi tiết hoá)

Mỗi tính năng một thư mục `AppHost/AppHost/Features/<Tên>/`; logic thuần Swift tách khỏi View để test được ở `-O0`.

- **CubeModel** — kiểu trạng thái cho N×N (bản 1: 2, 3) theo mô hình miếng (cubie: hoán vị + định hướng) và mô hình
  ô (facelet: 6×N² màu); chuyển đổi hai chiều; ký hiệu bước (Singmaster: R U F L D B, ', 2, xoay cả khối x y z); áp
  bước; kiểm hợp lệ (mục 5.4). Thiết kế giao thức `PuzzleKind` (hình học, số ô, giao thức quét, bộ giải, giáo trình) để
  Pyraminx/4×4 sau này là một kiểu mới, không sửa luồng.
- **Solver** — `QuickSolver` (Kociemba hai pha cho 3×3: bảng tra dựng trước, nhúng vào app dạng resource hoặc dựng lần
  đầu rồi cache; mục tiêu < 1 s trên iPhone đời thấp nhất hỗ trợ; 2×2: IDA*/BFS tối ưu) và `BeginnerSolver` (theo luật
  7 chặng, trả về `[Stage]`, mỗi stage là `[Step]` với bước + câu giải thích + hướng cầm). Chạy nền, huỷ được.
  **Kiểm đúng bằng test:** áp lời giải lên hàng nghìn trạng thái xáo trộn ngẫu nhiên có seed ⇒ luôn ra khối đã giải;
  thêm test cố định cho ca biên (khối đã giải, một bước, superflip, mọi ca của từng chặng).
- **Scanner** — AVFoundation capture; lấy mẫu vùng trong khung; ổn định theo khung hình; phân nhóm màu toàn khối (gán
  có ràng buộc 9 ô/màu, tâm làm mốc, cân trắng theo tâm trắng); lắp 6 mặt theo giao thức + thử hướng mặt trên/dưới.
  Logic phân nhóm/lắp mặt là hàm thuần, test bằng bộ ảnh/mẫu màu chụp thật ở nhiều điều kiện sáng (fixture nhỏ).
- **Cube3D** — RealityKit: 26 (3×3) / 8 (2×2) khối con có bo góc, nhãn màu; animation xoay lớp theo bước; mũi tên;
  điều khiển xoay nhìn; tốc độ. Không phụ thuộc Scanner.
- **Guide** — máy trạng thái của màn chỉ bước (bước hiện tại, lùi/tới, kiểm tra chặng, lập lại lời giải).
- **Patterns** — dữ liệu mẫu (tên, chuỗi bước, ảnh) + dùng Guide.
- **SolveLog** — ghi mỗi lần giải cục bộ (loại khối, chế độ, ngày, số bước, thời lượng, đã xong chưa). Bản 1 chỉ để
  analytics + nền cho xếp hạng/bấm giờ sau này; không đồng bộ, không UI lịch sử (đề xuất).
- Chừa chỗ Pro: tính năng mới sau này gắn qua `ProFeature` của template; bản 1 không có `ProFeature` nào bật.

## 7. Cấu hình template cho Cubingo

Định danh (đã chốt): bundle Store **`com.vimindtech.cubingo`** (Internal `com.vimindtech.cubingo.internal`), cùng tài
khoản Apple Developer với các app `com.vimindtech.*` hiện có (team id lấy từ tài khoản đó lúc tạo repo); email hỗ trợ
**bongao.developer@gmail.com**; Cloudflare + Firebase dùng tài khoản `@vimindtech.com` đã đăng nhập trên máy (tạo project
Firebase MỚI cho Cubingo — cổng user). Repo: chính repo này (tạo bằng `new_app` 2026-11-27, `--no-sample --no-paywall --no-web-api --no-apple-ads --locales en-US,vi`).
Tên miền: user mua sau. Kiểm 2026-11-27 (whois/RDAP, chưa phải báo giá): `cubingo.app` và `cubingo.com` ĐÃ có người
đăng ký; `cubingo.io`, `cubingo.co`, `getcubingo.com`, `cubingoapp.com` chưa thấy đăng ký. Tới lúc có tên miền, plan
tạo repo với host giữ chỗ rồi đổi `[web] host_prod/host_dev` + chạy `appconfig.py render` (lint store chặn host giữ chỗ
trước khi đẩy lên ASC ⇒ không lọt).

`new_app.py --name Cubingo --no-sample --no-paywall --no-web-api --no-apple-ads --locales en-US,vi,…` với (đề xuất của
Claude):
- `paywall = false` (bản 1 miễn phí); `web_api = false` (không có máy chủ ⇒ phản hồi qua "Send via Mail" của template;
  bật khi cần App Store Server Notifications lúc có thu phí); `apple_ads = false` (chưa chạy quảng cáo).
- Web: có site tĩnh (trang chủ, privacy, terms, support, changelog — bắt buộc cho App Store: URL privacy/support) trên
  Cloudflare theo P6; `app_paths = []` (bản 1 chưa có link mở app).
- `[i18n] languages = ["en", "vi"]` ⇒ cổng bản dịch của template TỰ BẬT (`verify_catalog.py`): thiếu bản dịch `vi` là
  chặn ship. Chuỗi gốc tiếng Anh; người dựng dịch, user duyệt bản Việt.
- `[store] locales`: en-US, vi + 5–7 ngôn ngữ metadata (đề xuất: es-MX, pt-BR, fr-FR, de-DE, ja, ko, zh-Hans — chọn
  theo thị trường cube lớn; growth-marketer đề xuất danh sách cuối kèm lý do).
- Firebase Analytics + Crashlytics giữ theo template; privacy manifest theo công tắc.

## 8. Đường lên thi đấu (không làm ở bản 1 — chỉ để không đập đi làm lại)

- Bấm giờ + xác nhận giải thật bằng **theo dõi khối realtime qua camera** — cùng nền với AR, dùng chung `CubeModel` và
  `Cube3D` (RealityKit); có thể cần Core ML ở bước đó.
- Xếp hạng, tìm trận 1:1/nhiều người, đấu thời gian thực: nghiêng về **Game Center/GameKit** (không phải tự làm tài
  khoản và máy chủ đấu trận). Trận công bằng cần **cùng một trạng thái xáo trộn** cho mọi người ⇒ `CubeModel` sinh xáo
  trộn từ seed, và Guide chỉ được "xáo theo chuỗi bước" (ngược của Patterns) — có sẵn từ bản 1.
- `SolveLog` là nguồn dữ liệu cho bảng thành tích cá nhân.

## 9. Đo lường (đề xuất của Claude)

Sự kiện analytics (không dữ liệu cá nhân, theo quy ước telemetry của template): `puzzle_selected(kind)`,
`scan_started/scan_completed(duration, manual_fixes)`, `manual_entry_used`, `cube_invalid(reason)`,
`solve_mode_selected(mode)`, `stage_completed(stage)`, `stage_check(result)`, `solve_completed(mode, moves, duration)`,
`solve_abandoned(step)`, `pattern_started/pattern_completed(id)`. Phễu chính: scan_started → solve_completed theo chế độ.

## 10. Kiểm chứng

- Thang L1/L2/L3 của template. Bộ giải: test thuộc tính có seed (mục 6) — nhỏ, nhanh ở `-O0`.
- Quét: không chạy được trên Simulator (không camera) ⇒ logic quét test bằng fixture; luồng quét thật = cổng device.
  Simulator dùng bypass `#if targetEnvironment(simulator)` nạp trạng thái mẫu để chụp UI (skill `ui-preview-sim`).
- Ảnh UI iPhone dọc + iPad ngang cho mọi màn đổi (cổng L2 UI của template).
- Device (user): quét ≥ 3 khối khác hãng/màu ở ≥ 3 điều kiện sáng; giải xong khối thật bằng cả hai chế độ, 3×3 và 2×2.
- Mức "đủ" của quét (đề xuất của Claude): KHÔNG đặt ngưỡng chính xác cứng cho 1.0 — màn sửa tay chạy tốt là đủ ship.
  Mục tiêu mềm: ánh sáng trong nhà bình thường ≤ 2 ô phải sửa tay mỗi lần quét 3×3; đo bằng `scan_completed.manual_fixes`
  sau khi ra bản để quyết có cần vòng tinh chỉnh/Core ML. Bộ fixture ảnh thật nhỏ (vài chục mẫu) dùng cho test hồi quy.
- Tiếng Việt: bản 1.0 có đủ `vi` (cổng `verify_catalog` bật). Người dựng dịch; **user duyệt bản Việt** trước khi đóng
  băng chuỗi — đặt thành một mốc riêng trong plan, trước cổng L2 cuối.

## 11. Ngoài phạm vi kỹ thuật nhưng thuộc Plan 7

Store/ASO (tên "Cubingo: Cube Solver & Tutor" hoặc tương đương ≤ 30 ký tự, không "Rubik"), ảnh/video App Store, web
deploy thật + Universal Link nếu có, notes Apple Review, ra bản 1.0 — theo luồng `release-aso` và `docs/RELEASE.md`;
mỗi bước đẩy/upload/deploy prod là cổng user.

## 12. Để lại cho người dựng / còn mở

Không còn câu hỏi mở cho user. Không có hạn chót (đã chốt).

Phạm vi Plan 7 (đề xuất của Claude): tới lúc **nộp App Store**, chia ba đợt, mỗi đợt kết thúc bằng một lần thử thiết bị:
- **Đợt A** — tạo repo, theme sáng, 3×3 trọn vẹn: chọn khối → quét/nhập tay → kiểm tra → Teach me + Just solve it →
  chỉ bước 3D → quét kiểm tra chặng; bảng màu tự nhận; tiếng Anh.
- **Đợt B** — 2×2 (cả hai chế độ), Patterns, bản tiếng Việt (user duyệt), iPad hoàn thiện, đo lường.
- **Đợt C** — store/ASO (metadata nhiều ngôn ngữ, ảnh, video), web (site + privacy/support) khi có tên miền, notes
  Apple Review, ra bản 1.0.

Để người dựng quyết (không đổi cái được dựng): giao thức quét chi tiết cho 2×2; thuật toán gán màu cụ thể; nhúng hay
dựng-lần-đầu bảng tra Kociemba (cân dung lượng app vs thời gian lần đầu); chọn thư viện nguồn mở nào (theo giấy phép)
hay tự viết; danh sách 10 hoa văn cụ thể; nội dung chữ từng chặng (user duyệt bản cuối); hình ăn mừng.
