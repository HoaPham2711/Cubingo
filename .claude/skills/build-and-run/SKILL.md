---
name: build-and-run
description: Build & chạy app (target AppHost) trên iPhone/iPad thật hoặc Simulator. Dùng khi user muốn build/run/mở app.
---

## Quy trình build và chạy

Từ thư mục gốc repo:

```bash
python3 tools/common/appconfig.py check   # Identity.xcconfig khớp app.config.toml? lệch ⇒ chạy `render`
cd AppHost
xcodegen generate
open AppHost.xcodeproj
```

### Trong Xcode

- Scheme `AppHost`, chọn device rồi Run. Team ký đọc từ `app.config.toml` (`[apple] team_id`) qua
  `AppHost/Config/Identity.xcconfig`; scheme và signing nằm trong `AppHost/project.yml`, tự áp mỗi lần
  `xcodegen generate` — không chỉnh signing trong Xcode (bị ghi đè, xem
  `docs/lessons-learned/signing-dat-o-project-yml.md`).
- File `.xcodeproj` bị `.gitignore`: scheme chỉ có sau `xcodegen generate`.

### Ba build configuration

| Config | Dùng khi | Tool debug (`INTERNAL`) | Bundle id |
|---|---|---|---|
| `Internal` | **build device hằng ngày** — scheme `AppHost`, Run mặc định | có | `[bundle] internal` (tên hiển thị `display_name_internal`, cài song song bản Store) |
| `Release` | nghiệm thu bản người dùng + Archive lên store — scheme `AppHost-Store` | **không** | `[bundle] store` |
| `Debug` | test suite, compile-check, chụp ảnh UI | có | `[bundle] internal` (test không bao giờ chạy trên id Store) |

`Internal` và `Release` cùng mức tối ưu (`-O`); Debug không tối ưu — đừng đo hiệu năng ở Debug.

### Plist Firebase

`Internal`/`Release` **lỗi build** nếu thiếu plist Firebase (`GoogleService-Info-Dev.plist` /
`GoogleService-Info-Prod.plist` trong thư mục `FIREBASE_PLIST_DIR`, mặc định thư mục Firebase cạnh `project.yml`) — cố ý, để bản
phát hành không ra đời thiếu telemetry. `Debug` chỉ cảnh báo. Template không chứa plist thật; muốn build thử
không có Firebase thật thì làm như `tools/template/selfcheck.sh`:
`python3 tools/common/appconfig.py fixture-plist --out <thư mục>` rồi build với `FIREBASE_PLIST_DIR=<thư mục>`.

### Trước khi upload

`./tools/release/verify_release_clean.sh <app|archive>` trên bản Release — xem `tools/release/README.md` và
`docs/RELEASE.md`.
