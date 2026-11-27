# web/ — site tĩnh + API tuỳ chọn (Cloudflare Workers)

Monorepo npm (workspaces) chạy trên Cloudflare Workers. Mọi định danh (tên Worker, host, bundle, team, D1, App Check)
đọc từ `app.config.toml`; hai `wrangler.jsonc` là FILE SINH — sửa `app.config.toml` rồi
`python3 tools/common/appconfig.py render`, không sửa tay.

| Thư mục | Lớp | Nội dung |
|---|---|---|
| `site/src/`, `site/test/`, `site/package.json`, `site/tsconfig.json`, `site/vitest.config.ts` | đồng bộ | Worker nhỏ của site |
| `site/public/**`, `site/releases.json` | gieo (app sở hữu) | trang tĩnh + nguồn changelog |
| `site/wrangler.jsonc`, `api/wrangler.jsonc` | sinh | cấu hình Cloudflare |
| `api/**` (trừ `wrangler.jsonc`) | đồng bộ | API Hono + D1 (feedback, thông báo App Store, admin, số web) |
| `tools/` | đồng bộ | cổng sitemap / changelog / nội dung site + test của `scripts/` (Python stdlib) |
| `scripts/predeploy.mjs` | đồng bộ | `npm run deploy:*`: kiểm cấu hình rồi deploy đúng thứ tự (API chỉ khi `web_api`) |

App cần route riêng ⇒ thêm vào template (file đồng bộ) hoặc dựng một Worker riêng của app ngoài `web/site` và
`web/api` — sửa tại chỗ file đồng bộ sẽ bị cổng lệch lõi chặn.

## Lệnh

```bash
cd web
npm ci                 # cần Node >= 22.12 (.nvmrc); bước có mạng duy nhất
npm test               # vitest của api (Miniflare, D1 cục bộ) + site (gọi thẳng worker với env giả)
npm run typecheck
python3 -m unittest discover -s tools -p "test_*.py"
```

Test không gọi mạng, không cần tài khoản Cloudflare. Deploy (dev lẫn prod) cần tài khoản Cloudflare ⇒ là việc của
người, không chạy trong test hay bởi agent (§"Deploy").

Phụ thuộc ghim đúng phiên bản (không `^`). Bump `wrangler` thì bump `@cloudflare/workers-types` CÙNG LÚC (kiểu của
runtime đi theo bản wrangler/workerd) rồi `npm install` một lần để cập nhật lock. `@cloudflare/vitest-pool-workers`
0.22.0 đã bị đánh dấu deprecated — đang dùng vì chưa có bản thay ổn định cho vitest 4 (nợ ở `docs/ROADMAP.md`).

## Site (`site/`)

Workers static assets phục vụ `site/public/`; Worker `site/src/worker.ts` chạy trước asset ở:

- `/.well-known/apple-app-site-association` — JSON dựng từ biến `APP_IDS` (`<team>.<bundle>`, nhiều giá trị ngăn bằng
  dấu phẩy) và `APP_PATHS` (JSON của `[web] app_paths`): dev phục vụ bundle Internal, prod bundle Store; `app_paths`
  rỗng ⇒ `{"applinks":{"details":[]}}`. `Content-Type: application/json`, cache 1 giờ, không redirect.
- `/api/*` — chuyển nguyên request sang Worker API qua service binding `API` (chỉ có khi `features.web_api`); không
  có ⇒ 404 `{"error":"no_api"}`. Site đứng một mình vẫn deploy được.
- `NOINDEX = "1"` (env dev) ⇒ mọi phản hồi có `X-Robots-Tag: noindex`; ở dev Worker chạy trước MỌI đường dẫn để trang
  tĩnh cũng nhận header này.

### Trang

App nướng cứng `/`, `/privacy/`, `/terms/`, `/support/` — bốn trang này phải luôn có (`site/test/static-paths.test.ts`,
`web/tools/check_site.py`). Trang được dựng lúc tạo app từ thư mục gieo của template: thay tên app, host, e-mail hỗ trợ và
cắt khối `<!-- feature:<công tắc>:begin|end -->` theo `[features]` (cùng cú pháp mẫu privacy manifest). Sau đó trang
thuộc app — sửa tay trực tiếp:

- thay mọi chỗ `TEMPLATE-PLACEHOLDER` (mô tả app, tên pháp lý, ngày hiệu lực, luật áp dụng, FAQ);
- đổi công tắc `[features]` ⇒ thêm/bỏ phần `data-feature="<công tắc>"` tương ứng trong `privacy/index.html` (và dòng
  `<script src="/m.js">` khi đổi `web_api`) — `check_site.py` báo lệch;
- có `apple.app_store_id` ⇒ thêm link App Store lên landing (`https://apps.apple.com/app/id<id>`).

`m.js` là beacon số liệu web không cookie (`POST /api/v1/public/beacon`, hợp đồng ở `api/src/routes/beacon.ts`); chỉ
gắn vào trang khi `features.web_api`. Link có `data-out="<mã>"` được đếm là `outbound`.

## Cổng (`web/tools/`)

| Lệnh | Kiểm | Chạy ở |
|---|---|---|
| `python3 web/tools/check_sitemap.py [--staged]` | mỗi `public/**/index.html` có đúng một `<url>` (host = `web.host_prod`); `<lastmod>` ≥ ngày commit cuối của trang; `--staged`: trang đang commit cần `lastmod` hôm nay | pre-commit khi commit đụng `web/site/public/`; trước deploy prod |
| `python3 web/tools/check_site.py [--release]` | đủ trang bất biến; `TEMPLATE-PLACEHOLDER` (lỗi khi `--release`, cảnh báo khi không); privacy `data-feature` ⇔ công tắc (`purchase_records` = paywall + `web_api`); `m.js` chỉ khi `web_api`; không còn dấu khối / biến gieo; `--release`: `web.host_prod`/e-mail hỗ trợ không phải host giữ chỗ, link canonical trỏ `web.host_prod`, `mailto:` = `support.email` | pre-commit (không `--release`); trước deploy prod (`--release`) |
| `python3 web/tools/changelog.py [--check] [--live X.Y.Z]` | sinh vùng `releases:begin…end` của `/changelog/` từ `site/releases.json`, chỉ các bản ≤ bản đang bán (iTunes Lookup theo `bundle.store`; chưa lên Store ⇒ chưa liệt kê, không lỗi) + `lastmod`; `--check` lệch ⇒ rc 1 | sau khi bản mới được duyệt; trước deploy prod |

Sitemap viết tay: sửa trang ⇒ sửa `<lastmod>` của trang đó thành hôm nay trong cùng commit; thêm/xoá trang ⇒
thêm/xoá `<url>`.

`site/releases.json` — mới nhất trước:

```json
[
  {"version": "1.1.0", "date": "2030-02-01", "notes": ["Export: files are ready sooner.", "Small fixes."]}
]
```

## API (`api/`)

Hono trên Cloudflare Workers + D1 (`api/migrations/`). Mọi route dưới `/api/v1`, tới được qua site (service binding
`API`, chỉ có khi `features.web_api` bật). **`web_api` tắt ⇒ app KHÔNG có API**: site trả 404 `no_api` cho `/api/*`,
`npm run deploy:*` chỉ deploy site, không cần D1/App Check, `subs_pull`/`web_pull` ghi `missing`; `api/wrangler.jsonc` vẫn
sinh (mã đồng bộ) nhưng không dùng. App bật paywall muốn nhận App Store Server Notifications ⇒ bật `web_api`.

| Route | Ai gọi | Ghi chú |
|---|---|---|
| `POST /feedback` | app (`CoreOptional/WebAPI`) | App Check bắt buộc ở prod (`APP_CHECK_REQUIRED=1`), dev thì không; giới hạn theo IP/giờ + toàn cục/ngày |
| `POST /appstore/notifications` | App Store Server Notifications V2 | JWS kiểm chuỗi tới Apple Root CA G3; bundle khác `ASSN_BUNDLE_ID` (bundle Store ở CẢ prod lẫn dev — Sandbox về dev vẫn mang bundle Store) hoặc môi trường ngoài `ASSN_ENVIRONMENTS` ⇒ 200, không lưu |
| `GET /admin/stats`, `GET /admin/feedback[/:id]`, `POST /admin/feedback/:id[/delete]`, `GET /admin/subscription-events` | người / `tools/analytics` | `Authorization: Bearer <ADMIN_TOKEN>`; 10 lần sai/giờ ⇒ khoá IP một giờ |
| `POST /public/beacon` | `site/public/m.js` | số liệu web không cookie (hợp đồng ở `api/src/routes/beacon.ts`) |

Cron hằng ngày (`triggers.crons`) chỉ dọn bảng (`api/src/cron.ts`). `ASSN_ENVIRONMENTS` (sinh: prod `Production`, dev
`Sandbox`) RỖNG ⇒ API bỏ MỌI thông báo App Store (vẫn trả 200) — `predeploy.mjs` từ chối deploy khi đó. Biến
`APP_CHECK_JWKS` CHỈ dành cho test (khoá giả thay JWKS của Google) — không bao giờ khai trong cấu hình deploy;
`predeploy.mjs` từ chối nếu thấy nó ở bất kỳ env nào của hai `wrangler.jsonc`. Nó KHÔNG thấy secret của Cloudflare:
không bao giờ `wrangler secret put APP_CHECK_JWKS` (ở prod, biến đó cho phép ai có khoá riêng tương ứng giả App Check).

Không có trang admin: đọc số/feedback bằng `tools/analytics` (`web_pull`, `subs_pull` — token ở file `web-admin-token` trong
thư mục cấu hình ngoài repo) hoặc `curl -H "Authorization: Bearer $(cat <file token>)" https://<host_prod>/api/v1/admin/stats`.

## Deploy

Việc của NGƯỜI (cần tài khoản Cloudflare; agent không chạy `wrangler login`/`deploy`/`--remote`/`secret put`). Thứ tự
lần đầu ở `docs/NEW_APP_CHECKLIST.md` của app (khi có API: D1 ×2, migration, `ADMIN_TOKEN` ×2, App Check, URL App Store
Server Notifications; luôn: custom domain prod).

```bash
cd web
npm run deploy:dev     # = node scripts/predeploy.mjs dev --deploy:  kiểm → API dev (nếu có) → site dev
npm run deploy:prod    # = node scripts/predeploy.mjs prod --deploy: kiểm → check_sitemap → changelog --check → check_site --release → API prod (nếu có) → site prod
```

- `scripts/predeploy.mjs <dev|prod> [--deploy]` đọc hai `wrangler.jsonc` SINH. App CÓ API ⇔ site của môi trường đó có service
  binding `API` (sinh khi `features.web_api`). Từ chối (rc 1, mỗi lý do một dòng `TỪ CHỐI:`, không chạy lệnh nào) khi: thiếu/hỏng
  file sinh của site (hoặc của api khi có API); có biến chỉ-test `APP_CHECK_JWKS` ở bất kỳ đâu; và CHỈ khi có API: D1
  `database_id` còn `TODO-d1-id` (`[cloudflare] d1_dev|d1_prod` rỗng), `APP_CHECK_PROJECTS` rỗng ở prod (`[firebase]
  app_check_prod`; dev chỉ `CẢNH BÁO:` — dev không bắt buộc App Check), `ASSN_ENVIRONMENTS` rỗng, và (prod) `web.host_prod` là
  host giữ chỗ/dành riêng (`example.com`, `*.test`, `*.invalid`, `localhost`…; app chỉ site: `check_site.py --release` bắt
  trước mọi deploy prod). Sửa `app.config.toml` ⇒ `python3 tools/common/appconfig.py render` ⇒
  chạy lại. Với `--deploy` dừng ở lệnh lỗi đầu tiên. Không cờ ⇒ chỉ kiểm.
- **Migration TRƯỚC khi deploy API** (chỉ khi có API) (lần đầu và mỗi khi có file mới trong `api/migrations/`), trong `web/api`:
  `npx wrangler d1 migrations apply <slug>-dev --env dev --remote` (dev) / `npx wrangler d1 migrations apply <slug> --remote`
  (prod). API mới chạy trên bảng cũ ⇒ lỗi 500.
- **API trước site** (khi có API, `--deploy` làm vậy): site gọi API qua service binding — binding tới Worker chưa tồn
  tại làm deploy site lỗi.
- Site ở NGOÀI repo (không dùng `site/public/`): khai `[web] external_site = true` — cổng 16 của `verify_release_clean.sh` in
  `SKIP (web.external_site)`; mặc định false ⇒ có `web.host_prod` mà thiếu `site/public/` là FAIL.
- **Dev trước prod**: thử `npm run deploy:dev` + AASA dev (`https://<host_dev>/.well-known/apple-app-site-association`)
  rồi mới prod. Web prod lên TRƯỚC bản app cần nó (`docs/RELEASE.md`).
- Link App Store trên trang chủ được quyết định LÚC TẠO APP (khối `app_store` chỉ giữ khi đã có `apple.app_store_id`): có id
  sau đó ⇒ sửa tay `site/public/index.html` (+ `<lastmod>` trong `sitemap.xml`).
