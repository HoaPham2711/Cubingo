# Privacy manifest phải khai tường minh trong `project.yml`

Nguồn: comment trong `project.yml` của app gốc (đã dính thật một lần), viết lại cho template.

## Chuyện đã xảy ra
`PrivacyInfo.xcprivacy` nằm đúng thư mục nguồn, build xanh, nhưng file không có trong `.app`. App Store Connect từ
chối bản upload — không có cách nào biết trước lúc build.

## Nguyên nhân
XcodeGen không nhận diện đuôi `.xcprivacy`, nên source glob (`- path: AppHost`) bỏ qua nó hoàn toàn: không vào pha
resources, không lỗi, không cảnh báo.

## Đã áp ở template
- `AppHost/project.yml` khai riêng file `AppHost/AppHost/PrivacyInfo.xcprivacy` (một mục `path:` của target, viết
  tương đối thư mục `AppHost/`) với `buildPhase: resources`.
- Cổng 7 của `tools/release/verify_release_clean.sh` kiểm `.app` Release có `PrivacyInfo.xcprivacy`.

## Bài học
- File có đuôi lạ (manifest, cấu hình, dữ liệu) ⇒ khai tường minh + kiểm trong `.app` đã build, đừng tin "build xanh".
- Thứ chỉ hỏng ở bước upload phải có cổng soi chính binary trước upload — đó là lý do `verify_release_clean.sh` đọc
  `.app`/`.xcarchive` chứ không đọc nguồn.
