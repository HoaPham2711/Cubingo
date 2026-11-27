# Roadmap & trạng thái

Đây là doc trạng thái của Cubingo: mỗi việc lớn một mục, mới nhất ở trên, ≤ 12 dòng; chi tiết để ở spec/plan
trong `docs/superpowers/`. Mẫu tiêu đề: `## <ngày> — <tiêu đề> (<nhánh>, <merged?>, <device?>)`. Nợ còn mở đọc nhanh
bằng `python3 tools/factory/roadmap.py debt`. App sinh từ template tag `v0.6.0-1-g20b1621` ngày 2026-11-27; việc tay trước bản
đầu tiên ở `docs/NEW_APP_CHECKLIST.md`.

## 2026-11-27 — Đợt A: 3×3 trọn vẹn đã code xong, chờ thử device (claude/plan-dot-a, chưa merge, chưa device)

Luồng chọn khối → quét (camera, tự chụp, phân nhóm Hungarian) / nhập tay → kiểm tra → Teach me (7 chặng, daisy, quét
kiểm tra + lập lại lời giải) / Just solve it (Kociemba hai pha tự viết, bảng 4,2 MB nhúng) → chỉ bước bằng khối 3D
RealityKit → màn xong. Plan `docs/superpowers/plans/2026-11-27-cubingo-dot-a.md`; quyết định khi làm ở mục "Rulings"
của báo cáo nhánh. Kiểm: L2 + ảnh iPhone/iPad; vét cạn 62 208 ca tầng cuối. Kế tiếp: user chạy
`docs/superpowers/plans/2026-11-27-cubingo-dot-a-device-checklist.md`, rồi Đợt B (2×2, Patterns, vi, đo lường, mẫu màu
thật), Đợt C (store/ASO, web, 1.0). Spec: `docs/superpowers/specs/2026-11-27-cubingo-design.md`.
Lõi template `v0.6.1`. Remote GitHub `HoaPham2711/Cubingo` (main + develop, 2026-11-27).
Nợ: tên miền chưa mua (`cubingo.io`/`.co`/`getcubingo.com` còn trống 2026-11-27) ⇒ `web.host_prod` còn giữ chỗ.
Project Firebase chưa tạo. Chặng 2 Teach me có ca ~100 bước (lặp right trigger) — xem lại sau thử device.

## Nợ đã biết
