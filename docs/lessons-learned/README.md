# Lessons learned

Bài học chung của template — mỗi bài gắn với một cổng/công cụ đang có. Thư mục này thuộc lớp đồng bộ (giống hệt ở mọi
app, không sửa tại app): bài học riêng của một app đặt ở `docs/lessons-learned/app/` (một file + một dòng ở README của
thư mục đó); bài học chung mới thì đưa về repo template.

- [`test-o-release-treo-vi-storekit.md`](test-o-release-treo-vi-storekit.md) — test trên bundle id Store đụng StoreKit sandbox thật, hộp thoại đăng nhập treo suite; test chỉ ở Debug, không bao giờ Release/`AppHost-Store`.
- [`signing-dat-o-project-yml.md`](signing-dat-o-project-yml.md) — signing sửa trong Xcode bị `xcodegen` xoá; `CODE_SIGN_STYLE: Automatic` tường minh, không `CODE_SIGN_IDENTITY`.
- [`test-chay-binary-cu-va-rc3.md`](test-chay-binary-cu-va-rc3.md) — sim chạy bản cũ khi cài đè; gỡ app trước khi test; rc 3 `[false-green]` không phải xanh.
- [`xcodegen-ghi-de-info-plist.md`](xcodegen-ghi-de-info-plist.md) — `xcodegen generate` sinh lại `Info.plist`; mọi key khai trong `project.yml`.
- [`privacy-manifest-phai-khai-tuong-minh.md`](privacy-manifest-phai-khai-tuong-minh.md) — XcodeGen bỏ qua `.xcprivacy`; khai `buildPhase: resources`, cổng 7 soi `.app`.
- [`sua-harness-can-phien-moi.md`](sua-harness-can-phien-moi.md) — hook/agent/skill/workflow mới chỉ có hiệu lực ở phiên MỚI; kiểm hook bằng subprocess.
- [`test-git-trong-hook-dung-repo-that.md`](test-git-trong-hook-dung-repo-that.md) — test gọi `git -C <tmp>` trong pre-commit bị `GIT_DIR` kéo về repo thật; gỡ `GIT_*`.
- [`cong-symbol-debug-chi-thay-symbol-duoc-link.md`](cong-symbol-debug-chi-thay-symbol-duoc-link.md) — type debug không ai dùng bị dead-strip nên cổng không thấy; tên HÀM không có trong binary nào (chỉ type soi được) ⇒ hai mục `[binary]`/`[source-only]`, mỗi tên `[binary]` phải có đối chứng dương trong `.app` Internal; đã chứng minh trên archive thật.

Trạng thái dự án: `docs/ROADMAP.md`.
