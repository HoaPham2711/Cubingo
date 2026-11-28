# Cubingo Đợt A — checklist thử trên máy thật (cổng user)

Simulator không có camera và không đo được tốc độ thật, nên các mục dưới đây phải thử trên máy. Build `Internal` (scheme
`AppHost`, Run). Firebase chưa có project ⇒ build cần plist giả:
`python3 tools/common/appconfig.py fixture-plist --out <thư mục>` rồi `FIREBASE_PLIST_DIR=<thư mục>` (CLAUDE.md §Build).

Ghi kết quả ngay dưới từng mục (✅ / ❌ + một dòng ghi chú).

## Máy

- [ ] iPhone đời thấp nhất đang có (lý tưởng XS/XR) — ghi model: ____
- [ ] Một iPad (dọc và ngang) — ghi model: ____

## Quét

- [ ] Lần đầu bấm 3×3: màn giải thích camera hiện trước hộp xin quyền; "Allow camera" ⇒ hộp hệ thống ⇒ màn quét.
- [ ] Quét ≥ 3 khối khác hãng × ≥ 3 điều kiện sáng (cửa sổ ban ngày, đèn vàng ấm, đèn LED trắng/tối). Mỗi lần ghi
      số ô phải sửa tay ở màn kiểm tra:

  | Khối (hãng/màu nhãn) | Ánh sáng | Số ô sửa tay | Ghi chú |
  |---|---|---|---|
  | | | | |

- [ ] Màn quét mới (spec `2026-11-28-cubingo-scan-redesign-design.md`): camera ở trên, khối 3D ở dưới; mặt viền cam nhận
      màu camera liên tục, màu đổi mượt (không giật) và giống khối thật.
- [ ] Bấm ✓ ⇒ rung nhẹ, mặt khoá màu, mũi tên cong hiện trên camera và khối ảo diễn đúng động tác; làm theo được mà
      không cần đọc chữ. Chưa xoay thì mũi tên + động tác nhắc lại khoảng 2,5 s một lần; xoay xong mũi tên tắt.
- [ ] Thứ tự 6 lần bấm: xoay trái ×3, lật mặt trên về phía mình, lật thêm 180° ⇒ đi thẳng sang màn chọn cách giải
      (khi không có lỗi) — khối ở màn chọn cách giải khớp khối thật.
- [ ] Bấm ✓ khi vẫn đang hướng vào mặt vừa quét ⇒ khối lắc, mặt đó nháy đỏ, không nhận.
- [ ] Hoàn tác ⇒ khối quay ngược về mặt trước, mặt đó nhận màu lại. Nút quay lại ở màn chọn cách giải ⇒ quét lại từ đầu.
- [ ] Cố ý lật lệch một góc khi quét mặt trên ⇒ vẫn ra khối đúng (tự sửa) nếu chỉ có một cách đúng.
- [ ] Phòng tối ⇒ biểu tượng bóng đèn nhấp nháy ở góc camera; chói ⇒ biểu tượng mặt trời.
- [ ] Từ chối quyền camera (Settings iOS) ⇒ "Camera is off…" + "Open Settings" + "Enter colors manually"; nhập tay đủ
      54 ô chạy tới màn chọn cách giải.

## Giải

- [ ] Just solve it: thời gian từ lúc bấm tới khi hiện bước đầu < 1 s. Lần đầu sau khi mở app có nạp bảng ~4 MB — ghi
      thời gian lần đầu: ____ s, lần sau: ____ s.
- [ ] Giải xong khối THẬT bằng Just solve it.
- [ ] Giải xong khối THẬT bằng Teach me; quét kiểm tra ít nhất 3 chặng ("Check my cube" ⇒ camera hiện ngay trong màn
      giải, khối quay mặt cần kiểm ra trước, mũi tên chỉ cách đưa mặt đó vào camera). Đưa sai mặt rồi bấm ✓ ⇒ khối lắc.
- [ ] Cố ý làm sai một bước rồi quét kiểm tra ⇒ ô lệch nháy đỏ + "That side doesn't match" ⇒ "Scan whole cube" ⇒ lời
      giải mới bắt đầu từ
      trạng thái mới, màu nền vẫn như cũ.
- [ ] Back / Replay / Next qua ranh giới chặng và qua bước xoay cả khối: khối 3D luôn khớp khối trên tay; chip
      "Hold: … on top, … facing you" đúng sau mỗi bước xoay cả khối.
- [ ] Mũi tên + lớp sáng của bước sắp làm dễ nhìn; đổi tốc độ (nút đồng hồ) có hiệu lực ngay.
- [ ] Màn "Solved!": confetti + rung, số bước và thời gian hợp lý.

## Công cụ nội bộ

- [ ] Nhấn giữ 1,5 s màn chọn khối (hoặc Settings › Internal) ⇒ "Random scrambled cube" ⇒ vào thẳng màn chọn cách giải.
- [ ] Sau mỗi lần quét thật, "Xem log" có dòng `scan-samples …` (54 mẫu RGB). Gửi lại các dòng này để Đợt B thêm vào
      `ScanFixtures` (mẫu thật).

## Ghi chú cho Đợt B

- Chặng 2 (góc tầng 1) lặp right trigger 1–5 lần mỗi góc, có ca tới ~100 bước. Nếu thấy quá dài khi thử, cân nhắc thêm
  "trigger ngược" (U R U' R') cho ca cần 5 lần.
