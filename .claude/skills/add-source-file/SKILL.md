---
name: add-source-file
description: Thêm/xóa file nguồn đúng cách (sửa project.yml, không sửa .xcodeproj). Dùng khi thêm .swift/.cpp/.metal/resource vào app.
---

## Quy trình thêm file nguồn

### Nguyên tắc chung

- Luôn sửa `AppHost/project.yml` rồi `cd AppHost && xcodegen generate` — `.xcodeproj` là sản phẩm sinh ra (bị
  `.gitignore`), không sửa tay.
- Target `AppHost` glob cả thư mục `AppHost/AppHost/`, test `AppHostTests` glob `AppHost/AppHostTests/`: thêm file
  `.swift` vào đúng thư mục chỉ cần chạy `xcodegen generate` (không sửa yml).
- Code chỉ cho build debug của APP ⇒ đặt trong `#if INTERNAL` ở `AppHost/AppHost/Internal/AppInternalEntry.swift`
  (chỗ DUY NHẤT trong app viết `#if INTERNAL`; lõi chỉ cấp `dtext`, `internalBadge`, `InternalLongPressSheet`,
  `InternalLaunch` và màn debug chung của nó — không sửa `Core/` cho việc của app) và thêm tên type vào mục `[binary]` của `AppHost/Config/debug_symbols.app.txt` (danh sách của app; `tools/release/debug_symbols.txt` là của lõi, không sửa) (hàm/biến nguy hiểm: marker
  `// debug-symbol: required` + mục `[source-only]`); `python3 tools/release/lint_debug_symbols.py` kiểm.

### File XcodeGen không tự nhận

XcodeGen bỏ qua đuôi nó không biết (ví dụ `.xcprivacy`) — file như vậy phải khai **tường minh** với
`buildPhase: resources`, như `AppHost/AppHost/PrivacyInfo.xcprivacy` đang khai trong `AppHost/project.yml`.
Thiếu là file không lọt vào `.app` mà build vẫn xanh (`docs/lessons-learned/privacy-manifest-phai-khai-tuong-minh.md`).

Key Info.plist mới: khai trong khối `info.properties` của `project.yml`, không sửa thẳng `AppHost/AppHost/Info.plist`
— `xcodegen generate` sinh lại file đó (`docs/lessons-learned/xcodegen-ghi-de-info-plist.md`).

### File `.cpp` perf-critical

Thêm source entry riêng với `compilerFlags: "-O2"` (Debug là `-O0`, code CPU nặng chậm hàng chục lần), và
**loại file đó khỏi glob** `- path: AppHost` bằng `excludes:` — glob đã gồm sẵn file, thiếu `excludes` thì file bị
liệt kê hai lần (cảnh báo build file trùng/symbol trùng, cờ `-O2` có thể không áp):

```yaml
sources:
  - path: AppHost
    excludes: ["Native/NewAlgorithm.cpp"]   # đường dẫn tương đối với path của glob
  - path: AppHost/Native/NewAlgorithm.cpp
    compilerFlags: "-O2"
```

### Xác nhận sau khi thêm

Compile-check bằng skill `compile-check` (`run_tests.py` tự leo thang lên full khi `project.yml` đổi).
