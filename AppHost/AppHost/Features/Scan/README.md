# Scan

Quét khối bằng camera sau (không ARKit): lấy mẫu 9 ô trong khung vuông giữa ảnh (`ScanSampler`), tự chụp khi khung
hình đứng yên 0,6 s (`ScanStabilizer`), đi theo giao thức 7 bước (`ScanProtocol`), rồi phân nhóm màu toàn khối có ràng
buộc 9 ô/màu (`ScanClusterer` + `ScanHungarian`). Simulator không có camera ⇒ `ScanPreviewSeed` phát lưới của một
trạng thái mẫu cố định.

| Route preview | Màn |
|---|---|
| `scan` | Màn quét (Simulator: nguồn giả tự chụp hết 6 mặt) |
