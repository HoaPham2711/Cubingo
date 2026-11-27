# Cubingo

App iOS (SwiftUI) `cubingo`. Sinh từ template "xưởng app" ở tag `v0.6.0-1-g20b1621` ngày 2026-11-27:
vỏ app + lõi dùng chung (`Core/`) + máy móc build/test/release + harness agent. Mọi định danh (tên, bundle id, team,
version, cờ tính năng, ngôn ngữ) nằm **duy nhất** ở `app.config.toml`.

Việc phải làm tay trước bản đầu tiên: `docs/NEW_APP_CHECKLIST.md`.

## Yêu cầu máy

- macOS + Xcode (có iOS Simulator runtime)
- XcodeGen (`brew install xcodegen`)
- Python 3.12 (chỉ thư viện chuẩn — không cần `pip install`)
- git

## Bắt đầu

```bash
git config core.hooksPath .githooks        # bắt buộc ở mỗi clone — thiếu thì các cổng pre-commit không chạy
python3 tools/common/appconfig.py render   # sinh Identity.xcconfig + Features.generated.yml + PrivacyInfo.xcprivacy từ app.config.toml
cd AppHost && xcodegen generate && cd ..   # sinh AppHost.xcodeproj (không commit .xcodeproj)
python3 tools/dev/run_tests.py --full      # toàn bộ test trên Simulator (Debug)
tools/template/selfcheck.sh --quick        # tự kiểm nhanh: cấu hình, lint, cổng release
```

Ba config build: `Debug` (test, compile-check), `Internal` (dev hằng ngày, có cờ `INTERNAL`, bundle id nội bộ),
`Release` (bản App Store). **Test chỉ chạy ở `Debug`.** Kiến trúc, bố cục repo, invariant: `docs/ARCHITECTURE.md`;
hướng dẫn cho Claude Code: `CLAUDE.md`; trạng thái: `docs/ROADMAP.md`.

## Lõi từ template

`Core/`, `CoreOptional/`, phần lớn `tools/`, `.claude/agents|hooks|skills|workflows/`, `docs/ARCHITECTURE.md`,
`docs/RELEASE.md`, `docs/lessons-learned/` là **lớp đồng bộ**: template sở hữu, giống hệt từng byte ở mọi app, ghi
trong `core.lock` (tag + checksum). Không sửa tại chỗ — pre-commit và cổng release đỏ khi một file đồng bộ lệch
`core.lock`. Lên bản lõi mới: `python3 tools/template/sync_core.py sync --to <tag>` (hướng dẫn đầy đủ:
`.claude/skills/sync-core/SKILL.md`). Lỗi lõi: sửa ở repo template, gắn tag bản vá, rồi đồng bộ về.
