# Test xanh của binary cũ — và vì sao rc 3 không phải xanh

Nguồn: app gốc của template (2026-10), viết lại cho template.

## Chuyện đã xảy ra
Bốn lần "xanh" sau khi chỉ sửa file test: test vừa thêm báo pass gần như tức thì, có lần chạy cả test đã gỡ, có lần
"Executed 0 tests" dù log có biên dịch.

## Hai cơ chế khác nhau
1. **Đã chứng minh — sim chạy bản cũ dù build đúng.** Cài đè app thì simulator có lúc khởi động bản cũ từ
   `data/Library/Caches/com.apple.containermanagerd/Dead/`. Đo cùng điều kiện: không gỡ app trước 4/15 lần sai,
   gỡ trước 0/15.
2. **Chưa rõ hẳn — build báo SUCCEEDED mà không biên dịch file test vừa sửa**, hay gặp khi Xcode IDE mở cùng project
   trong lúc CLI build.

## Đã áp ở template (`tools/dev/run_tests.py`)
- Gỡ app internal khỏi sim trước mỗi lần chạy test (dữ liệu app trên sim đó mất).
- Cổng chống xanh giả: xcodebuild rc 0 nhưng kết quả không đáng tin ⇒ script trả **rc 3** + `[false-green]`: không
  chạy test nào; test/class chỉ định không chạy; tên test đã chạy lệch nguồn; file test sửa trước lệnh mà chưa
  được biên dịch.
- Mỗi worktree một simulator riêng (`tools/dev/sim_pool.py`) — hai phiên không cài đè app của nhau.

## Bài học
- rc 3 là KHÔNG xanh. Đừng đọc chữ "TEST SUCCEEDED".
- Cổng không bắt được binary cũ khi tên test khớp ⇒ test mới bảo vệ bất biến vẫn phải qua "phá code → test đỏ"
  (`tools/factory/mutate.py`).
- Nghi stale build: `xcodegen generate` + `xcodebuild clean`, rebuild, tìm dòng `Test Case '...' started` cho đúng
  test.
- Sửa chính cổng: so mtime với binary là sai (sửa comment không relink) — so với file `.d` của nguồn; stdout app ghi
  xen giữa dòng `Test Case` nên đừng neo regex bằng `^`.
