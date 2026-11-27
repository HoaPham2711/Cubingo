---
name: product-analytics
description: Kéo số liệu Firebase Analytics (GA4), App Store Connect, crash, sự kiện gói và web (API admin) bằng tools/analytics, gộp thành insights.json + report.md rồi viết báo cáo sản phẩm (độ tin cậy, điểm sáng, điểm cần cải thiện, xu hướng, đề xuất). Dùng khi user hỏi "số liệu tuần này thế nào", "báo cáo analytics", "người dùng đang dùng app ra sao", hoặc cần số thật để quyết định ưu tiên roadmap.
---

## Báo cáo số liệu sản phẩm

Các lệnh ở `tools/analytics/`, chạy từ gốc repo, từng lệnh một. Output nằm ngoài git: `.temp/analytics/`
(gitignored) hoặc thư mục `$ANALYTICS_OUT` nếu đặt — KHÔNG commit số liệu.

```bash
python3 tools/analytics/ga4_pull.py      # Firebase Analytics (GA4 Data API), 90 ngày → <gốc>/ga4/<ngày>/
python3 tools/analytics/asc_pull.py      # App Store Connect (Sales, Subscription, Analytics Reports), 60 ngày → <gốc>/asc/<ngày>/
python3 tools/analytics/crash_pull.py    # crash `app_exception` + bản ghi Crashlytics từ BigQuery → <gốc>/crash/<ngày>/
python3 tools/analytics/subs_pull.py     # sự kiện gói (App Store Server Notifications) qua API admin của web, 30 ngày → <gốc>/subs/<ngày>/subs.json
python3 tools/analytics/web_pull.py      # lượt xem/nguồn/nước/thiết bị + số feedback mở qua API admin, 30 ngày → <gốc>/web/<ngày>/web.json
python3 tools/analytics/digest.py        # gộp → <gốc>/insights.json + <gốc>/report.md
```

`ga4_pull.py` nhận `--days N`, `--today` (gồm số hôm nay, tạm tính), `--dry-run` (chỉ in request, không gọi API,
không cần khoá — dùng để kiểm cấu hình); `asc_pull.py`, `subs_pull.py`, `web_pull.py` nhận `--days N`; `digest.py` nhận `--since YYYY-MM-DD`
(mặc định 28 ngày). Mọi lệnh kéo nhận `--out <thư mục>`. Nguồn nào thiếu khoá/cấu hình thì lệnh tự báo MỘT dòng
hướng dẫn và thoát mã 2 — chuyển nguyên văn cho giám đốc/user, không bịa số thay.

### Cấu hình và khoá (việc của user)

Định danh đọc từ `app.config.toml`: `[analytics] ga4_property`, `[analytics] bq_project` (cho crash), `bundle.store`.
Rỗng ⇒ lệnh từ chối, hướng dẫn điền. Biến môi trường thắng cấu hình:

| Biến | Dùng cho |
|---|---|
| `GA4_PROPERTY_ID`, `GA4_KEY_FILE` | property và file service account (role Viewer) của `ga4_pull.py` |
| `ASC_CONFIG`, `ASC_KEY_FILE` | `asc.json` (`key_id`, `issuer_id`, `vendor_number`) và file `.p8` (role Sales and Reports) |
| `GA4_BQ_PROJECT`, `GA4_BQ_DATASET`, `GA4_BQ_LOCATION` | BigQuery của `crash_pull.py` (service account cần thêm quyền BigQuery) |
| `CRASH_WATCH_FILE` | danh sách issue crash đang theo dõi (không đặt ⇒ `<gốc app>/tools/app/crash_watch.json` của app nếu có, không thì file chung của lõi, chưa theo dõi issue nào) |
| `WEB_ADMIN_TOKEN_FILE` | file chứa `ADMIN_TOKEN` của API web cho `subs_pull.py`/`web_pull.py` (mặc định `<config_dir>/web-admin-token`; host lấy từ `[web] host_prod`) |
| `ANALYTICS_OUT` | gốc thư mục đầu ra thay cho `.temp/analytics` |

Khoá nằm NGOÀI repo, trong thư mục cấu hình theo `app.slug` (`$IOS_APP_FACTORY_CONFIG/<slug>/` hoặc
`~/.config/ios-app-factory/<slug>/`): `analytics-reader.json`, `asc.json`; `.p8` mặc định ở
`~/.appstoreconnect/private_keys/AuthKey_<key_id>.p8`.
`ASC_KEY_FILE` trùng tên với biến của công cụ ASO (skill `release-aso`) nhưng hai bên thường cần hai khoá khác nhau
(ở đây role Sales and Reports, `key_id` trong `asc.json`; ASO dùng khoá App Manager, `key_id` trong `asc-listing.json`).
Không `export` nó cho cả phiên: để trống thì mỗi công cụ tự tìm `.p8` theo `key_id` của mình; cần trỏ tay thì đặt
ngay trước từng lệnh (`ASC_KEY_FILE=<đường dẫn> python3 tools/analytics/asc_pull.py`). Lần đầu dùng Analytics Reports của App Store Connect:
`python3 tools/analytics/asc_pull.py --create-analytics-request` — cần key role Admin, là việc user làm; Apple cần
1–2 ngày mới có báo cáo đầu.

Hai lệnh `subs_pull.py`/`web_pull.py` chỉ cần stdlib: thiếu token hoặc `[web] host_prod` ⇒ ghi nguồn `missing` (rc 0),
HTTP 401 ⇒ rc 2 (sai token), 429 ⇒ rc 2 (IP bị khoá ~1 giờ — đừng thử lại liên tục). `subs.json` chỉ chứa số gộp,
không mã giao dịch; `active_estimate_by_product` là ước lượng từ sự kiện trong cửa sổ.

Ba lệnh kéo còn lại cần các gói Python ở `tools/analytics/requirements.txt` (ký JWT, OAuth Google). Thiếu ⇒ lệnh in
hướng dẫn `python3 -m pip install -r tools/analytics/requirements.txt`: **hỏi user trước khi cài** (có tải mạng).
`digest.py` và test không cần các gói đó.

### Bí mật — quy tắc cứng

- **Không bao giờ `cat`/Read/in file khoá hoặc token.** Chỉ kiểm tồn tại bằng `ls`. Lệnh tự đọc.
- Không dán số doanh thu/người dùng ra dịch vụ ngoài (artifact công khai, issue, PR, web).
- Không tự tạo khoá, không đổi quyền trên Google/App Store Connect: hướng dẫn user.

### `insights.json` (do `digest.py` ghi, đọc nguyên văn — đừng bịa thêm khoá)

```json
{ "generated_at": "ISO",
  "sources": { "ga4|asc|crash|subs|web": { "status": "ok|partial|missing|stale", "run": "YYYY-MM-DD|null", "path": "…|null" } },
  "metrics": [ { "name": "…", "value": 0, "unit": "…", "source": "ga4|asc|crash|subs|web", "period": "từ..tới" } ],
  "notes":   [ "…" ] }
```

`status`: `missing` = chưa kéo; `stale` = lần kéo mới nhất cũ hơn `--since`; `partial` = có báo cáo lỗi lúc kéo
(`_run.json`), chỉ số dựa trên nó bị thiếu — `notes` nói báo cáo nào. Tỉ lệ (giữ chân) có `unit` = `ratio` (0..1).
`report.md` là bản đọc được của cùng dữ liệu (kèm mục theo dõi crash). Mở file JSON gốc trong `<gốc>/<nguồn>/<ngày>/`
khi cần cắt sâu hơn; mọi con số trong báo cáo phải đối chiếu lại được với `insights.json`/file gốc trước khi viết.

### Cấu trúc báo cáo (giữ đúng 5 mục, dẫn số cụ thể cho từng nhận định)

1. **Độ tin cậy của số liệu** — cỡ mẫu, khoảng ngày, nguồn `missing`/`stale`/`partial`, phần nhiễu. Viết TRƯỚC kết luận.
2. **Điểm sáng**
3. **Điểm cần cải thiện**
4. **Xu hướng người dùng** — theo ngày/tuần/version, giữ chân D1/D3/D7 (dòng gộp, không đọc % từng ngày).
5. **Đề xuất** — xếp theo tác động, mỗi đề xuất nối với số liệu ở trên và nói rõ đo lại bằng gì.

So với báo cáo kỳ trước (nếu có trong `<gốc>/reports/`) — xu hướng quan trọng hơn ảnh chụp. Báo cáo đầy đủ viết
tiếng Việt vào `<gốc>/reports/<ngày>-bao-cao.md` (tạo thư mục nếu chưa có); chỉ đề xuất, không tự chỉnh giá hay quảng cáo.

### Bẫy khi đọc số

- **Property GA4 nhận mọi bản build Release**, gồm cả máy dev, TestFlight và App Review: số "người mới" cao hơn
  khách thật. Đối chiếu lượt tải thật ở App Store Connect (`sales.tsv`, dòng tải lần đầu), đừng lấy `newUsers`.
- **Sự kiện mua của GA4 không phải doanh thu**: "bắt đầu gói" (sự kiện) ≠ "trả tiền". Doanh thu và trạng thái trả
  phí chỉ tin báo cáo của App Store Connect (`subscription_events.tsv`, `subscriptions.tsv`).
- **Cột "người" không cộng dồn** giữa nước/version (một người có thể ở nhiều dòng); cột "lượt" cộng được.
- **Cỡ mẫu nhỏ**: dưới ~30 người ở một bước thì chỉ nêu là tín hiệu, không kết luận phần trăm.
- Sự kiện bắt đầu nhiều hơn kết thúc + huỷ ⇒ phiên biến mất không dấu vết (crash, bị kill) — soi theo version
  trước khi quy cho UX.
- **Tham số sự kiện (custom dimension) chỉ có dữ liệu từ ngày đăng ký**; `ga4_pull.py` chỉ dùng trường chuẩn của GA4
  (không custom dimension) — lát cắt theo tham số riêng của app cần báo cáo riêng.
- **Cohort giữ chân** (`retention_daily`) mới có ô khi ngày đó đã trọn; `–`/rỗng là chưa đủ ngày, không phải 0 %.
  Cohort gồm mọi bản cài, cả máy nội bộ — đọc như ước lượng.
- **Export BigQuery trễ ~1 ngày**, App Store Connect trễ 1–2 ngày: số hôm nay thiếu là bình thường; ghi vào "Chưa kiểm được".

### Crash — đọc MỖI lần làm báo cáo

`report.md` có mục theo dõi crash (từ `crash_watch.py`): ĐỌC TRƯỚC khi viết nhận định. Cảnh báo issue đang theo
dõi lan sang máy mới, crash GA4 trên máy chưa gặp, hoặc issue crash mới ⇒ đưa lên **đầu báo cáo**, nêu máy, bản, số
lần. Không có cảnh báo ⇒ một dòng ở mục độ tin cậy ("Crash: không có máy/issue mới").

- Crashlytics ghi `app_exception` khi app **mở lại** sau crash ⇒ crash xảy ra sau event cuối của phiên trước.
- Lỗi non-fatal app tự ghi không sinh `app_exception`; chỉ đọc được ở `records` của `crash_pull.py`.
- Danh sách theo dõi của app là `<gốc app>/tools/app/crash_watch.json` (file của app, ngoài lớp đồng bộ; `crash_watch.py` tự
  đọc khi có, `CRASH_WATCH_FILE` thắng nó). File mặc định `tools/analytics/crash_watch.json` là lõi đồng bộ: đừng
  ghi issue của app vào đó. Dạng: `recent_days`, `issues` [`issue_id`, `name`, `status`, `known_devices` [`model`,
  `os`]], `reviewed` [`model`, `os`, `through`]. Sau khi user đã xem một cảnh báo, cập nhật file của app và commit —
  không cập nhật thì cảnh báo lặp mỗi ngày (cố ý).

### Khi lệnh lỗi

- GA4 `403`: service account chưa có role Viewer trên property (Admin → Property access management).
- App Store Connect báo sai `vendor_number` ở báo cáo Subscription khi Sales vẫn chạy: thường là tài khoản chưa có
  giao dịch subscription; chỉ khi cả Sales lỗi mới kiểm `vendor_number` trong `asc.json`.
- "chưa có report request ONGOING": cần `asc_pull.py --create-analytics-request` một lần (key Admin, việc user).
- Crash: thiếu project BigQuery/dataset ⇒ điền `[analytics] bq_project` (hoặc `GA4_BQ_PROJECT`); export Crashlytics
  chưa bật ⇒ chỉ có phần GA4 của mục crash.
- Nguồn nào chưa kéo được thì báo cáo ghi nguồn đó `missing` — không dựng số thay thế.

### Thêm một lát cắt mới

`tools/analytics/` là lõi đồng bộ (khoá trong `core.lock`): ở repo app KHÔNG sửa file trong đó — hook pre-commit,
`sync_core.py check` và `selfcheck.sh` đều từ chối. Lát cắt dùng được cho mọi app là thay đổi lõi: làm ở repo
template (thêm dòng vào `static_reports()` của `ga4_pull.py`, chỉ số vào `digest.py`, kèm test) → template ra tag mới
→ app chạy `python3 tools/template/sync_core.py sync --to <tag>` để nhận. Phân tích chỉ app này cần: viết ở đường dẫn của app
(vd `<gốc app>/tools/app/`, ngoài lớp đồng bộ), đọc output trong `$ANALYTICS_OUT` / `insights.json` thay vì sửa lõi. Viết code
là việc của vai `platform-engineer` và phải có test.
