---
name: release-aso
description: Sửa metadata App Store (name, subtitle, description, keywords, promotional text, what's new) và ra bản qua tools/aso — ASO, "ra bản", đẩy listing lên App Store Connect an toàn (lint → plan → xác nhận trong chat → apply). Dùng khi user nhờ sửa/đẩy metadata App Store, làm ASO hoặc ra bản. Có hai luồng: sửa metadata và ra bản.
---

## release-aso — sửa metadata App Store và ra bản an toàn

Nguồn sự thật metadata là `store/metadata/**` (bố cục, giới hạn ký tự, khung lúc mới tạo: `store/README.md`).
Mọi thao tác với App Store Connect (ASC) đi qua `tools/aso/aso.py`; ghi lên ASC CHỈ qua `aso.py apply`.
Cổng con người (kind `asc`) và hook: `.claude/skills/factory/autonomy.md`. Quy trình phát hành chung: `docs/RELEASE.md`.

Mọi lệnh chạy **từ gốc repo**, **một lệnh đơn lẻ**, không nối chuỗi (`;`, `&&`, `|`), đúng dạng dưới đây — hook
`guard_asc` chặn dạng khác và `apply` luôn hiện hộp Allow/Deny. `--version <v>` có thể bỏ: mặc định là
`[version] marketing` của `app.config.toml`. Định danh (App Store id, locale, host) đọc từ `app.config.toml`,
không nhập tay vào lệnh.

### Điều kiện tiên quyết (việc của user — agent chỉ kiểm và hướng dẫn)

- `apple.app_store_id` trong `app.config.toml` có giá trị (app record tạo tay trên ASC). Rỗng ⇒ mọi lệnh cần ASC
  từ chối bằng một dòng hướng dẫn; `lint` vẫn chạy local.
- Công cụ `asc` đã cài (một bản cho cả máy, ngoài PATH): `bash tools/aso/install_asc.sh`. Cài là **tải file từ
  mạng ⇒ hỏi user đồng ý trước**, không tự cài.
- Khoá ASC của user: file `asc-listing.json` (`key_id`, `issuer_id`) trong thư mục cấu hình theo `app.slug`
  (`$IOS_APP_FACTORY_CONFIG/<slug>/` hoặc `~/.config/ios-app-factory/<slug>/`; `$ASO_CONFIG` ghi đè) và file
  `.p8` tương ứng (`$ASC_KEY_FILE` hoặc `~/.appstoreconnect/private_keys/AuthKey_<key_id>.p8`). **Không bao giờ
  `cat`/Read/in các file này** — chỉ `ls` kiểm tồn tại; thiếu ⇒ nói user tạo, không tự tạo.
  `ASC_KEY_FILE` trùng tên với biến của `tools/analytics` (skill `product-analytics`), nhưng bên đó dùng khoá khác
  (role Sales and Reports, `key_id` trong `asc.json`). Cách đúng: để TRỐNG biến này và đặt mỗi khoá ở chỗ mặc định
  `~/.appstoreconnect/private_keys/AuthKey_<key_id>.p8` — mỗi công cụ tự tìm `.p8` theo `key_id` của nó. Không
  `export ASC_KEY_FILE` cho cả phiên (công cụ kia sẽ ký bằng nhầm khoá ⇒ 401 khó hiểu); hook chỉ nhận lệnh `aso.py`
  dạng chuẩn (không tiền tố biến), nên lệnh ASO không trỏ khoá tay được — chỉ lệnh của `tools/analytics` mới đặt biến
  ngay trước từng lệnh.
- Trước `plan` đầu tiên: `[web] host_prod` trong `app.config.toml` là host thật của app (không phải giá trị giữ chỗ
  `example.com` của template) và URL trong `store/metadata` (`privacyPolicyUrl`, `supportUrl`, `marketingUrl`) đã sửa
  theo — `lint` đỏ (và `plan` từ chối field đổi) khi URL trỏ host giữ chỗ/dành riêng, hoặc `privacyPolicyUrl`/
  `supportUrl` lệch `host_prod`.
- Lần đầu, khi `store/metadata` còn là khung do template sinh và ASC đã có metadata: `python3 tools/aso/aso.py import --force-over-skeleton`
  (chỉ chạy được khi mọi ô chữ còn chuỗi giữ chỗ; thư mục trống thì dùng `import` không cờ).

### Luồng sửa metadata

1. **Kiểm trước khi sửa**: `python3 tools/aso/aso.py plan`. ASC khác `store/` (có thay đổi không do mình) ⇒
   báo user, dừng, không sửa tiếp.
2. **Sửa** `store/metadata/...` rồi commit git. Chạy `python3 tools/aso/aso.py lint` (giới hạn ký tự/byte,
   chữ giữ chỗ, chữ cấm trong `store/lint.toml`, URL theo host của app, keywords audit) và sửa tới khi sạch
   (rc 0). Khung mới sinh cố ý đỏ cho tới khi mọi chuỗi `TEMPLATE-PLACEHOLDER` được thay bằng chữ thật (cả
   `store/review/notes.txt`). Thiếu thư mục `store/metadata/version/<v>/` của version đang soi (vd sau khi bump)
   cũng là lỗi — `pull-version` (version đã có trên ASC) hoặc tạo thư mục rồi soạn.
3. **Ra plan**: `python3 tools/aso/aso.py plan`. Dán **NGUYÊN VĂN** bản xác nhận (toàn bộ output, kể cả mã plan
   và dòng `Plan:`) vào chat, rồi hỏi đúng một câu: **"push không?"**.
   - `plan` thoát mã 2 (store thiếu locale so với ASC, lint lỗi ở field đang đổi, xoá trắng một field đang có chữ,
     version không còn sửa được…) ⇒ báo nguyên thông báo cho user; chỉ sửa `store/` nếu user muốn; không lách.
     Xoá nội dung field là việc user tự làm trên ASC.
   - Mục **"Cảnh báo (field không đổi)"** = lint thấy vấn đề ở field plan này KHÔNG đổi; không chặn push, nói rõ
     với user và đề xuất sửa lần sau.
4. **Chỉ sau khi user đồng ý trong chat** (cổng `asc` của giám đốc đã mở): chạy đúng
   `python3 tools/aso/aso.py apply --plan '<đường dẫn>' --expect <mã>` — không option nào khác. Truyền `--plan`
   **đúng nguyên đường dẫn ở dòng `Plan:`** (tuyệt đối, trong nháy đơn vì có thể có dấu cách) và `--expect` đúng mã
   đã trình bày. Hook tính lại mã từ file plan — lệch ⇒ chặn; hộp Allow/Deny hiện ra là xác nhận lần hai, **user
   bấm**. **Deny ⇒ dừng**, không thử đường khác.
5. **Báo kết quả**: đã đổi gì, link ASC do lệnh in, và "bạn tự xem lại và tự nộp review — công cụ không nộp".
   Apply lỗi sau khi đã đẩy một phần ⇒ cho user thấy đường dẫn snapshot và gợi ý
   `python3 tools/aso/aso.py restore --snapshot '<thư mục>'`. **`restore` chỉ TẠO plan** (không ghi gì lên ASC):
   trình bày bản xác nhận như bước 3, rồi apply như bước 4. Khoá liệt kê dưới "Không khôi phục được (cấm xoá)" ⇒
   user tự xử lý trên ASC.

Lệnh phụ chỉ đọc: `python3 tools/aso/aso.py snapshot` (chụp trạng thái ASC vào thư mục trạng thái),
`python3 tools/aso/aso.py pull` (kéo remote vào thư mục tạm, in đường dẫn).

## Ra bản

Khi user nói "ra bản …". Mọi ghi lên ASC (upload build, tạo version, gắn build, What's New) chỉ qua
`aso.py apply`. Gặp lỗi ở bất kỳ bước nào ⇒ **dừng, báo nguyên thông báo**. Luồng chạy trong **phiên chính**
(giám đốc), từng bước một cổng theo `.claude/skills/factory/autonomy.md`; subagent bị reset cwd mỗi lệnh Bash
nên không giao luồng này cho subagent.

1. **Chốt kind** `patch|minor|major` theo `docs/RELEASE.md`. Đang ở `develop`, cây sạch (`git status`), test L2 xanh.
2. **Git và bump** theo `docs/RELEASE.md`: PR `develop`→`main`, merge, bump version + tag bằng
   `tools/release/bump_version.sh`, rồi `git push origin main --tags` — push/merge/tag là cổng `push` (hook
   `guard_autonomy` hỏi), từng lệnh đơn lẻ. Bước merge `main` ngược về `develop` (bước 5 của `docs/RELEASE.md`) làm ở
   bước 5 dưới đây, SAU khi build xong (build cần đang ở `main`).
   Trước khi chuyển nhánh, kiểm cây sạch; không sạch ⇒ **dừng và hỏi user**, không stash/bỏ.
3. **Build** (local, không gọi ASC): `build` yêu cầu đang ở nhánh **`main`**, cây sạch, HEAD mang tag `v<v>`,
   file sinh từ `app.config.toml` khớp. `python3 tools/aso/aso.py build --version <v>` — chạy bằng Bash `run_in_background`
   (archive + export + cổng `verify_release_clean`); không chờ bằng sleep/polling. Kết quả: dòng đầu in đường
   dẫn `build.json` trong `<state_dir>/builds/<v>-<b>/`; lệnh từ chối nếu thư mục đó đã có. Preflight lỗi ⇒ sửa
   nguyên nhân, không lách.
4. **Plan release**: `python3 tools/aso/aso.py release-plan --build-json '<đường dẫn build.json>'` (chỉ đọc
   ASC). Dán **NGUYÊN VĂN** bản xác nhận (kể cả `Mã plan` và dòng `Plan:`), hỏi: **"upload build và tạo version không?"**.
   User đồng ý ⇒ `python3 tools/aso/aso.py apply --plan '<đường dẫn dòng Plan:>' --expect <mã>` bằng
   `run_in_background` (upload + chờ build xử lý xong, có thể lâu); hộp Allow/Deny = xác nhận lần hai; Deny ⇒ dừng.
   - Plan thoát mã 2 ⇒ báo nguyên thông báo. Công cụ từ chối thay build đã gắn vào version, từ chối version không
     còn sửa được (đang bán/chờ duyệt) và không tự xoá gì — user xử lý trên ASC.
   - **Apply lỗi giữa chừng**: đọc lỗi (liệt kê bước đã xong), chạy lại `release-plan` với **cùng `build.json`**;
     nếu build đã có trên ASC nó ra plan tiếp tục (không upload lại). Trình bày và apply như trên. Không xoá
     build/version để làm lại.
5. **What's New** — quay về `develop` (`git checkout develop`) rồi **merge `main` vào `develop`** theo bước 5 của
   `docs/RELEASE.md` (`git merge main`, rồi push — cổng `push`), để `develop` mang đúng `[version] marketing` mới. Từ đây
   mọi lệnh `aso.py` truyền **`--version <v>` tường minh**: `python3 tools/aso/aso.py pull-version --version <v>`
   kéo version mới vào `store/metadata/version/<v>/` (từ chối nếu thư mục đã có hoặc app-info lệch). Soạn
   `whatsNew` cho mọi locale đang khai ở `[store] locales`, từ `CHANGELOG.md` của bản này, giọng các bản trước.
   Commit trên `develop` (không bao giờ commit thẳng `main`), rồi `lint --version <v>` → `plan --version <v>` → bản
   xác nhận → "push không?" → `apply` đúng như "Luồng sửa metadata" bước 3–4.
6. **Notes cho Apple Review — mỗi bản, kể cả bản chỉ sửa lỗi.** Công cụ không đẩy ô này lên ASC; **user dán
   tay**. Nguồn sự thật là `store/review/notes.txt`: sửa theo đường đi tới tính năng mới của bản, ngắn (quy ước
   ≤ 384 ký tự của template — ô của Apple nhận dài hơn), không xuống dòng cuối, chỉ nhắc thứ có trong bản Store
   (`aso.py lint` đỏ khi còn chữ giữ chỗ; dài quá quy ước / xuống dòng cuối chỉ cảnh báo). Commit trên `develop`.
7. **Báo user**: link ASC của version, "build <b> đã gắn, What's New đã đẩy — bạn tự xem lại và tự nộp review;
   công cụ không nộp". **Dán NGUYÊN VĂN `store/review/notes.txt`** trong khối code, ghi rõ dán vào App Review
   Information › Notes của version này trước khi nộp. Thiếu bước này thì chưa được báo "sẵn sàng nộp".

Ảnh chụp màn hình/video store không nằm trong công cụ: chuẩn bị và tải lên tay trên ASC (cổng `asc`).

### Thư mục trạng thái

Snapshot, plan, build và ledger nằm ngoài checkout: `~/Library/Application Support/ios-app-factory/<slug>/aso/`
(`$IOS_APP_FACTORY_STATE` ghi đè gốc; `<slug>` = `app.slug` nên nhiều app trên một máy không đè nhau). Mỗi lệnh in
đường dẫn tuyệt đối; có dấu cách ⇒ để trong nháy đơn khi truyền vào `--plan`/`--snapshot`/`--build-json`.

### Commit khi message nhắc tới công cụ

Hook chặn `git commit -m "…"` nếu message trông như lệnh chạy code trong `tools/aso`. Viết message vào file
(thư mục scratchpad) rồi `git commit -F <file>`.

### CẤM (không ngoại lệ)

- Gọi thẳng `asc` (bất kỳ lệnh con nào), chạm vào thư mục cài `asc`, hoặc import/chạy module trong `tools/aso`
  trong tiến trình (`python3 -c …`, REPL, chạy file `.py` khác `aso.py`) — chỉ đi qua `aso.py` như trên.
- Đọc/in file khoá (`asc-listing.json`, `*.p8`); đặt cấu hình git chạy được lệnh (hook chặn).
- Sửa file plan sau khi đã trình bày cho user; cần đổi ⇒ ra plan mới và hỏi lại từ bước 3.
- Chạy `apply` kiểu nối chuỗi, kèm option thừa, hoặc từ thư mục khác gốc repo; chạy `apply` khi user chưa đồng ý
  trong chat hoặc đã Deny.
- Nộp review / submit / publish / release trên ASC; upload build bằng cách nào khác ngoài `aso.py build` + `apply`.
- Xoá/archive bất cứ thứ gì (locale, version, build); `--allow-deletes`; xoá bằng giá trị rỗng/`null`.
- Tự cài `asc` hay công cụ cần tải khi chưa hỏi user.
- Viết script mới hay cách chạy khác để ghi lên ASC — `tools/aso` là đường DUY NHẤT; việc nó chưa làm được thì
  hướng dẫn user làm tay trên ASC.
