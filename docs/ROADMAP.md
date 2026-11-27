# Roadmap & trạng thái

Đây là doc trạng thái của Cubingo: mỗi việc lớn một mục, mới nhất ở trên, ≤ 12 dòng; chi tiết để ở spec/plan
trong `docs/superpowers/`. Mẫu tiêu đề: `## <ngày> — <tiêu đề> (<nhánh>, <merged?>, <device?>)`. Nợ còn mở đọc nhanh
bằng `python3 tools/factory/roadmap.py debt`. App sinh từ template tag `v0.6.0-1-g20b1621` ngày 2026-11-27; việc tay trước bản
đầu tiên ở `docs/NEW_APP_CHECKLIST.md`.

## 2026-11-27 — Bản 1: thiết kế đã duyệt, chưa có plan (develop, chưa merge, chưa device)

App hướng dẫn giải khối 3×3 + 2×2 cho người mới: quét camera (bảng màu tự nhận) → kiểm tra → Teach me (7 chặng) / Just
solve it → chỉ bước bằng khối 3D RealityKit; ~10 hoa văn; en + vi; iOS 18; miễn phí, không quảng cáo. Spec đã duyệt:
`docs/superpowers/specs/2026-11-27-cubingo-design.md` (+ bản phác `specs/assets/2026-11-27-cubingo/`).
Kế tiếp: viết plan **Đợt A** (3×3 trọn vẹn) bằng skill writing-plans, rồi Đợt B (2×2, Patterns, tiếng Việt, iPad),
Đợt C (store/ASO, web khi có tên miền, ra bản 1.0).
Lõi template: `v0.6.1` (đã sync 2026-11-27). Nợ: tên miền chưa mua (`cubingo.io`/`.co`/`getcubingo.com` còn trống
2026-11-27) ⇒ `web.host_prod` còn giữ chỗ. Remote chưa tạo/push (cổng user). Project Firebase chưa tạo.

## Nợ đã biết
