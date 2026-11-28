# Guide

Chỉ từng bước: `GuideSession` (máy trạng thái — Back/Replay/Next, bỏ chặng rỗng, lập lại lời giải), `GuideText` (mọi chữ,
màu là tham số), `GuideCheck` (quét kiểm tra sau chặng; làm ngay trong màn giải bằng `GuideCheckPanel`, không đẩy route — một RealityView mỗi chồng). View: `GuideView` (3D + thẻ bước; iPad hai cột),
`GuideStageDoneView`, `GuideDoneView`, `GuideNotationSheet`.

| Route preview | Màn |
|---|---|
| `mode` | Chọn cách giải (Teach me / Just solve it) — `FlowModeView` |
| `guide` | Teach me giữa chặng 3 |
| `guideStageDone` | Vừa xong chặng 1 ("Stage complete!") |
| `guideCheck` | Quét kiểm tra ngay trong màn giải (camera + khối quay mặt cần kiểm, mũi tên) |
| `done` | Màn ăn mừng sau Just solve it |
