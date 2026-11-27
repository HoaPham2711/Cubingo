---
name: compile-check
description: Compile-check Swift và chạy test theo phạm vi qua iOS Simulator, không cần device. Dùng để verify build/test sau khi sửa code.
---

## Compile-check + test qua iOS Simulator

### Đường chính: `tools/dev/run_tests.py`

```bash
tools/dev/run_tests.py            # L1: test liên quan tới file đã đổi (so với develop) — mặc định
tools/dev/run_tests.py --list     # xem sẽ chạy class nào, không chạy
tools/dev/run_tests.py FooTests FooTests/test_bar    # chỉ định tay
tools/dev/run_tests.py --no-build FooTests          # chạy lại, không build (test-without-building)
tools/dev/run_tests.py --full     # L2: toàn bộ suite, chạy song song nhiều clone sim
tools/dev/run_tests.py --full --parallel 1   # L2 nối tiếp — khi nghi lỗi chỉ do chạy song song
tools/dev/run_tests.py --base main           # đổi mốc so sánh của L1
```

Luôn chạy ở config `Debug`, scheme `AppHost`, target test `AppHostTests` — không bao giờ Release/`AppHost-Store`
(hook `.claude/hooks/guard_test_config.py` chặn; lý do ở `docs/lessons-learned/test-o-release-treo-vi-storekit.md`).

Script dùng **simulator riêng của worktree** (`factory-<worktree>-<băm>`, tạo + boot lần đầu, sau đó dùng lại;
`tools/dev/sim_pool.py`), không dùng chung sim với phiên khác (`--shared-sim` để quay lại kiểu cũ, `--udid` để chỉ
định). Ở `--full`, test đỏ được **chạy lại nối tiếp** trên sim gốc — vẫn đỏ = lỗi thật, xanh = `[flaky-song-song]`.
Script tự leo thang lên full khi đụng `project.yml`/`.xcstrings`/plist/`.metal`/`.cpp`…, và in rõ file nguồn nào
**không có test nào nhắc tới** (chỉ được compile-check). Log đầy đủ ở `.temp/test-logs/`. Khi nào chạy mức nào:
"Thang kiểm chứng" trong `.claude/rules/conventions.core.md`.

**rc=3 + `[false-green]` KHÔNG phải xanh** — xcodebuild báo thành công nhưng kết quả không đáng tin (0 test, test
chỉ định không chạy, tên test lệch nguồn, file test sửa mà chưa biên dịch). Xem
`docs/lessons-learned/test-chay-binary-cu-va-rc3.md`.

Trước khi chạy, script kiểm `Identity.xcconfig` khớp `app.config.toml` — lệch ⇒
`python3 tools/common/appconfig.py render`.

### Lệnh thô (khi cần cờ đặc biệt)

```bash
cd AppHost && xcodegen generate   # chỉ khi thêm/xoá file hoặc sửa project.yml
UDID=$(python3 tools/dev/sim_pool.py ensure)   # chạy từ gốc repo
xcodebuild -project AppHost/AppHost.xcodeproj -scheme AppHost \
  -destination "id=$UDID" -configuration Debug build CODE_SIGNING_ALLOWED=NO
```

- Dùng `-destination 'id=<udid>'` (destination kiểu `platform=iOS Simulator,name=...` hay không resolve).
- Scheme khai sẵn trong `AppHost/project.yml`, có ngay sau `xcodegen generate`.

### Bẫy stale-bundle

Mở project trong Xcode IDE song song với CLI có thể làm `build-for-testing` báo SUCCEEDED **mà không recompile**
file test đã đổi. Cổng rc=3 bắt phần lớn ca; nghi ngờ thì `xcodegen generate` + `xcodebuild clean`, rebuild, xác
nhận dòng `Test Case '...' started` cho đúng test.

### Ghi chú

- Debug = `-O0`: test mới phải nhanh (fixture nhỏ). Test > 2 s cần lý do — một test chậm là thuế trả ở MỌI lần
  chạy full suite.
- Test Python của tooling: `python3 -m unittest discover -s tools/<thư mục> -p 'test_*.py'`.
