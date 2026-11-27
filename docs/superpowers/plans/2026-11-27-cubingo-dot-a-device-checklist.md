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

- [ ] Tự chụp khi giữ yên khoảng 0,5 s; nút chụp tay cũng chạy; rung nhẹ khi chụp (Settings › Haptics bật).
- [ ] Bước "Turn left once more": giơ mặt khác ⇒ "That's not the first side yet"; giơ lại mặt đầu ⇒ đi tiếp.
- [ ] Giơ lại một mặt đã quét ⇒ "This side was already scanned — turn once more".
- [ ] Cố ý nghiêng mặt trên 90° khi quét ⇒ màn kiểm tra tự sửa (không báo lỗi) nếu chỉ có một cách đúng.
- [ ] Phòng tối ⇒ "Face a window or a lamp".
- [ ] Từ chối quyền camera (Settings iOS) ⇒ "Camera is off…" + "Open Settings" + "Enter colors manually"; nhập tay đủ
      54 ô chạy tới màn chọn cách giải.

## Giải

- [ ] Just solve it: thời gian từ lúc bấm tới khi hiện bước đầu < 1 s. Lần đầu sau khi mở app có nạp bảng ~4 MB — ghi
      thời gian lần đầu: ____ s, lần sau: ____ s.
- [ ] Giải xong khối THẬT bằng Just solve it.
- [ ] Giải xong khối THẬT bằng Teach me; quét kiểm tra ít nhất 3 chặng ("Check my cube").
- [ ] Cố ý làm sai một bước rồi quét kiểm tra ⇒ "Looks different…" ⇒ "Scan the whole cube" ⇒ lời giải mới bắt đầu từ
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
