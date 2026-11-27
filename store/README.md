# store/ — nguồn sự thật metadata App Store

## Bố cục

`store/metadata/` đúng bố cục `asc metadata pull` ghi ra:

- `app-info/<locale>.json` — `name`, `subtitle`, `privacyPolicyUrl`.
- `version/<version>/<locale>.json` — `description`, `keywords`, `promotionalText`, `whatsNew`, `supportUrl`, `marketingUrl`.

Giá trị luôn là chuỗi (không `null`, không `default.json`). Locale của listing khai ở `[store] locales` trong
`app.config.toml` (phần tử đầu = locale chính); mỗi locale một file ở `app-info/` và ở thư mục version.
`store/lint.toml` — chữ cấm của riêng app (`banned = []`). `store/review/notes.txt` — notes cho Apple Review.

## Khung lúc mới tạo

App mới nhận khung do `new_app.py` sinh: `name` = tên hiển thị, `subtitle` rỗng, URL theo `web.host_prod`, mọi ô chữ
phải tự viết chứa chuỗi `TEMPLATE-PLACEHOLDER`. `aso.py lint` **cố ý đỏ** cho tới khi mọi chuỗi đó được thay bằng chữ thật —
đó là cổng chặn đẩy khung rỗng lên App Store Connect. Mọi khung `store/` vừa sinh đều ở trạng thái này. URL của khung
lấy host lúc tạo app: còn là host giữ chỗ của template (`example.com`) thì lint cũng đỏ — đặt `[web] host_prod` thật trong
`app.config.toml` rồi sửa `privacyPolicyUrl`/`supportUrl`/`marketingUrl` theo, TRƯỚC lần `plan` đầu tiên. App đã có
metadata trên App Store Connect thì thay khung bằng bản trên đó: `python3 tools/aso/aso.py import --force-over-skeleton`
(chỉ chạy khi mọi ô chữ còn chuỗi giữ chỗ).

## Quy trình sửa

1. Sửa chữ trực tiếp trong `store/metadata/**` (commit git để có lịch sử).
2. `python3 tools/aso/aso.py lint` — giới hạn ký tự/byte, chữ giữ chỗ, chữ cấm, URL theo host (host giữ chỗ/dành riêng,
   host dev, `privacyPolicyUrl`/`supportUrl` lệch `host_prod` ⇒ lỗi; URL khác lệch host ⇒ cảnh báo), notes Apple Review
   (`--version <v>`; mặc định `[version] marketing` — thiếu thư mục `version/<v>/` trong khi đã có version khác là lỗi:
   `pull-version` hoặc tạo thư mục rồi soạn). Không cần app record.
3. `python3 tools/aso/aso.py plan` — so với App Store Connect, in bản xác nhận + mã plan, lưu
   `<state_dir>/plans/<mã>.json`. Cần app record (`apple.app_store_id` trong `app.config.toml`) và khoá ASC. Plan từ chối
   nếu `store/` thiếu locale đang có trên App Store Connect.
4. Đọc bản xác nhận. `apply` chỉ chạy sau khi người bấm Allow ở hộp xác nhận.
5. Người tự bấm nộp review trên App Store Connect — công cụ không bao giờ nộp/publish.

Giới hạn (ASC đếm như sau): `name`, `subtitle` 30 ký tự; `promotionalText` 170; `description`, `whatsNew` 4000;
`keywords` 100 **byte** UTF-8, phân cách bằng dấu phẩy không kèm dấu cách, không lặp từ của name/subtitle.

## Notes cho Apple Review

`store/review/notes.txt` — nội dung ô App Review Information › Notes của bản đang ra; quy ước của template: ngắn (≤ 384
ký tự — ô của Apple nhận dài hơn nhiều), không xuống dòng cuối. Công cụ không đẩy ô này lên App Store Connect (người dán tay
trước khi nộp); `lint` chỉ soi file: còn chữ giữ chỗ ⇒ đỏ; dài quá quy ước hoặc có xuống dòng cuối ⇒ cảnh báo.

## Thư mục trạng thái (ngoài checkout)

Snapshot, plan và ledger KHÔNG nằm trong repo: `~/Library/Application Support/ios-app-factory/<slug>/aso/`
(ghi đè bằng `IOS_APP_FACTORY_STATE`; `<slug>` = `app.slug`, nên nhiều app trên một máy không đè nhau). Mọi lệnh in
đường dẫn tuyệt đối; đường dẫn có dấu cách thì để trong nháy đơn khi dán vào lệnh.
