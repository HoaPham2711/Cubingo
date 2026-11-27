# Việc tay cho app mới — Cubingo

App sinh từ template tag `v0.6.0-1-g20b1621` ngày 2026-11-27 (bundle id `com.vimindtech.cubingo`). Lệnh tạo app chỉ làm những gì làm được
trên máy, không cần tài khoản: định danh, cấu hình, `core.lock`, kho git cục bộ. Các bước dưới đây cần người (tài khoản,
quyết định, thiết bị). Đánh dấu `[x]` khi xong; xoá file này khi hết việc.

## Định danh & cấu hình (`app.config.toml`, rồi `python3 tools/common/appconfig.py render`)

- [ ] Team id thật ở `[apple] team_id`.
- [ ] Web host (`[web] host_prod` / `host_dev`) và e-mail hỗ trợ (`[support] email`) thật. Đổi host TRƯỚC lần `plan` đầu tiên của
      metadata App Store, rồi sửa URL trong `store/metadata/**` (`privacyPolicyUrl`, `supportUrl`, `marketingUrl`) theo host mới —
      khung sinh lúc tạo app mang host lúc đó; lint của metadata đỏ khi URL trỏ host giữ chỗ (`example.com`…) hoặc
      `privacyPolicyUrl`/`supportUrl` lệch `host_prod`.
- [ ] Product id thật ở `[purchases]` và trong `AppHost/StoreKitConfig/Products.storekit` (sửa cùng lúc —
      `tools/release/check_storekit.py` gác), hoặc tắt paywall (`[features] paywall = false`).

## App Store Connect & dịch vụ

- [ ] App record + bundle id (Store và internal) + capability (In-App Purchase…) trên App Store Connect / Developer.
- [ ] **Associated Domains** bật trên App ID của CẢ bundle id Store lẫn internal (Developer › Identifiers): app khai entitlement
      `applinks:<host>` khi `[web] host_prod` có giá trị, nên profile ký thiếu capability này thì build đã ký lỗi. Link chỉ MỞ app khi
      host trả tệp `apple-app-site-association` ở `/.well-known/` — site `web/site` phục vụ nó (dựng từ `[web] app_paths`) sau khi
      deploy (mục "Web & hạ tầng"); thử Universal Link trên thiết bị thật sau lần deploy đầu.
- [ ] Sau khi app record có: điền `[apple] app_store_id` ở `app.config.toml`, rồi `python3 tools/common/appconfig.py render`. Link
      App Store trên trang chủ web được quyết định LÚC TẠO APP (lúc đó chưa có id ⇒ không có link): thêm tay
      `https://apps.apple.com/app/id<id>` vào `web/site/public/index.html` (sửa `<lastmod>` của trang trong `sitemap.xml` cùng commit).
- [ ] Sản phẩm IAP + nhóm subscription khớp `[purchases]`.
- [ ] Project Firebase; đặt hai plist `GoogleService-Info-Prod.plist` và `GoogleService-Info-Dev.plist` vào
      thư mục `Firebase/` (tạo mới) bên trong `AppHost/` (thiếu ⇒ build `Internal`/`Release` lỗi, cố ý).
- [ ] Nhãn App Privacy trên App Store Connect khớp privacy manifest. Manifest `AppHost/AppHost/PrivacyInfo.xcprivacy` do
      `appconfig.py render` SINH từ mẫu `AppHost/Config/PrivacyInfo.template.xcprivacy` theo `[features]` (khối tắt ⇒ không khai
      dữ liệu của nó; cổng 7 của `verify_release_clean.sh` đối chiếu) — không sửa tay file sinh; app khai thêm dữ liệu thì sửa mẫu
      rồi render.

## Nội dung

- [ ] AppIcon — template chưa có asset catalog: thêm `Assets.xcassets` + AppIcon vào `AppHost/AppHost/`.
- [ ] Thay nội dung tour onboarding (`AppHost/AppHost/AppOnboarding.swift`), bảng so sánh paywall
      (`AppHost/AppHost/AppPaywall.swift`), thẻ What's New (`AppHost/AppHost/WhatsNew/WhatsNewCatalog.swift`).
- [ ] Màu nhấn / theme của app ở `AppHost/AppHost/AppTheme.swift`.
- [ ] Metadata App Store: viết chữ thật vào `store/metadata/**` thay mọi chuỗi giữ chỗ (`store/README.md`: bố cục, giới hạn ký tự);
      `python3 tools/aso/aso.py lint` phải xanh — khung mới sinh cố ý đỏ để khỏi đẩy chữ giữ chỗ lên App Store Connect. Đẩy lên App
      Store Connect: skill `release-aso` (plan → người xác nhận → `apply`); cần `asc` (`bash tools/aso/install_asc.sh`, tải từ mạng) và
      khoá App Store Connect của người (`asc-listing.json` + file `.p8` ngoài repo — không đưa vào repo, agent không đọc).
- [ ] Ảnh store (screenshot iPhone + iPad), ảnh/video quảng bá, Custom Product Page trên App Store Connect — tự làm tay; công cụ
      chưa mang.
- [ ] Notes cho Apple Review mỗi bản (`store/review/notes.txt`, lint của metadata đỏ khi còn chữ giữ chỗ) — người dán vào App Store Connect.
- [ ] Trang web `web/site/public/` (trang chủ, privacy, terms, support, changelog): thay mọi `TEMPLATE-PLACEHOLDER` bằng nội dung thật
      (mô tả app, tên pháp lý, ngày hiệu lực, luật áp dụng, FAQ), host/e-mail thật (không `example.com`; link canonical và `mailto:`
      khớp `web.host_prod`/`support.email`) — `python3 web/tools/check_site.py --release` phải xanh (cổng 16 của
      `verify_release_clean.sh` chặn bản Store tới lúc đó). `privacyPolicyUrl`, `supportUrl`, `marketingUrl` trong `store/` trỏ tới
      các trang này nên site prod phải lên TRƯỚC khi nộp.
- [ ] Số liệu (tuỳ chọn): `[analytics] ga4_property` / `bq_project`, khoá đọc GA4 / App Store Connect ở thư mục cấu hình ngoài repo,
      rồi `tools/analytics` (skill `product-analytics`; cần `python3 -m pip install -r tools/analytics/requirements.txt` — người đồng ý).

## Web & hạ tầng

Chi tiết từng lệnh: `web/README.md` §"Deploy". Mọi bước dưới đây cần tài khoản Cloudflare/Apple/Firebase — do người làm.

- [ ] Domain của `[web] host_prod` trên Cloudflare (zone); `host_dev` là subdomain của nó.
- [ ] `cd web && npm ci` (Node >= 22.12 — `web/.nvmrc`), rồi `npx wrangler login`.

Chỉ khi `[features] web_api` bật (app CÓ API — tắt thì app không có API: bỏ qua bốn mục dưới và mục App Store Server
Notifications; `npm run deploy:*` chỉ deploy site, không đòi D1 / App Check. App bật paywall muốn nhận thông báo đăng ký thì
bật `web_api`):

- [ ] D1 ×2: `npx wrangler d1 create <slug>` và `npx wrangler d1 create <slug>-dev` (tên = `[app] slug`); dán `database_id` vào
      `[cloudflare] d1_prod` / `d1_dev` ở `app.config.toml`, rồi `python3 tools/common/appconfig.py render` (sinh lại hai
      `web/*/wrangler.jsonc`) và commit.
- [ ] Migration TRƯỚC lần deploy API đầu (và trước mỗi deploy API có migration mới): trong `web/api`,
      `npx wrangler d1 migrations apply <slug>-dev --env dev --remote` rồi `npx wrangler d1 migrations apply <slug> --remote`.
- [ ] Token admin ×2 (chuỗi ngẫu nhiên dài, mỗi môi trường một token): trong `web/api`,
      `npx wrangler secret put ADMIN_TOKEN --env dev` và `npx wrangler secret put ADMIN_TOKEN`. Lưu token prod vào file
      `web-admin-token` trong thư mục cấu hình ngoài repo (`python3 tools/common/appconfig.py config-dir`) — `tools/analytics`
      (`subs_pull`, `web_pull`) đọc từ đó; không đưa vào repo.
- [ ] Firebase App Check: bật App Check (App Attest) cho app trên Firebase; điền
      `[firebase] app_check_prod` / `app_check_dev` = `"<projectId>:<projectNumber>"` rồi `appconfig.py render`.

Mọi app có web:

- [ ] Deploy dev: `cd web && npm run deploy:dev` (có API: tự từ chối khi D1 id / App Check còn thiếu, API trước site sau; không
      có API: chỉ site); thử `https://<host_dev>/.well-known/apple-app-site-association`.
- [ ] Custom domain prod: gắn `host_prod` cho Worker `<slug>-site` trên Cloudflare (dev tự gắn qua `routes` của file sinh).
- [ ] Deploy prod: `cd web && npm run deploy:prod` (thêm cổng sitemap, changelog, `check_site.py --release`) — site prod phải lên
      TRƯỚC bản app cần nó (`docs/RELEASE.md`).
- [ ] Site ở NGOÀI repo (không dùng `web/site/public/`)? Đặt `[web] external_site = true` — không thì cổng 16 của
      `verify_release_clean.sh` FAIL khi có `web.host_prod` mà thiếu `web/site/public/`.
- [ ] (Chỉ khi `web_api` bật) App Store Server Notifications V2 trên App Store Connect (App Information): URL production
      `https://<host_prod>/api/v1/appstore/notifications` và URL sandbox `https://<host_dev>/api/v1/appstore/notifications`; bấm
      "Send Test Notification" để thử.
- [ ] (paywall + `web_api`, sau khi đặt URL ở trên) Nhãn App Privacy thêm **Purchases** (Purchase History — không liên kết danh
      tính, không tracking): API lưu thông báo mua hàng (mã giao dịch, sản phẩm, giá, storefront, hạn) 400 ngày; trang privacy
      đã có phần `data-feature="purchase_records"` (`check_site.py` gác).

## Kho & thiết bị

- [ ] Tạo remote + push lần đầu (do người làm — lệnh tạo app không tạo remote).
- [ ] `git config core.hooksPath .githooks` ở MỖI clone mới từ remote (lệnh tạo app đã đặt cho repo vừa tạo). Người tự chạy; agent
      không đặt được (hook `guard_asc` chặn lệnh này) — nhờ người dùng.
- [ ] Chạy trên thiết bị thật (scheme `AppHost`, config `Internal`): StoreKit, Firebase, mời đánh giá, Mail.
- [ ] Bản Store đầu tiên: skill `release-aso` luồng "Ra bản" (archive `Release` + `verify_release_clean.sh` + upload lên App Store
      Connect qua công cụ, mỗi bước ghi do người duyệt — `docs/RELEASE.md`); bấm nộp duyệt là việc của người.
