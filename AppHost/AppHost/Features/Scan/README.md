# Scan

Quét khối bằng camera sau (không ARKit): lấy mẫu 9 ô trong khung vuông giữa ảnh (`ScanSampler`). Màn quét
(`ScanView`) hiện camera ở trên và khối 3D ở dưới. Mặt đang quét nhận màu camera sống (`ScanCaptureModel`, làm mượt);
người dùng bấm ✓ để chụp. Chụp xong, mũi tên cong (`ScanTurnArrow`) và khối xoay mẫu chỉ động tác tới mặt kế tiếp.
Giao thức 6 bước (`ScanProtocol`); hướng lưới mỗi mặt tính từ hướng khối (`ScanOrientation`). Đủ 6 mặt thì phân nhóm màu
toàn khối có ràng buộc 9 ô/màu (`ScanClusterer` + `ScanHungarian`). Simulator không có camera ⇒ `ScanPreviewSeed` phát lưới của một
trạng thái mẫu cố định.

| Route preview | Màn |
|---|---|
| `scan` | Màn quét: đã chụp 2 mặt, đang nhận màu mặt 3 |
| `scanTurn` | Màn quét: đã chụp 3 mặt, đang hiện mũi tên chờ xoay |
| `review` | Màn kiểm tra màu, một ô bị đọc sai (có thông báo lỗi) |
