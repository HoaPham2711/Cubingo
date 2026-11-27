#!/bin/bash
# Cổng tự kiểm của template VÀ của mọi app sinh ra từ nó: chứng minh khung còn nguyên vẹn VÀ cổng release có gác thật.
#
#   tools/template/selfcheck.sh            # đầy đủ (test iOS, StoreKit; ở template thêm bước 9 — số đo ở README của template)
#   tools/template/selfcheck.sh --quick    # bỏ test iOS, StoreKit, build UI test, rc 3, bước 9
#   tools/template/selfcheck.sh --kind     # chỉ in loại repo (template | app) rồi thoát
#
# Template hay app — cùng luật với hook pre-commit (`repo_kind`): repo là TEMPLATE khi HEAD track file đánh dấu
# new_app.py của template trong tools/template (HEAD chưa có commit: xét index), mọi repo khác là APP. Khác nhau ở:
#   bước 1 — template: `manifest.py check` (mọi file có lớp sở hữu); app: `sync_core.py check` (lõi khớp core.lock);
#   bước 9 — chỉ template (tổ hợp tắt hết, gỡ mẫu, tạo app mới thật); app in một dòng BỎ QUA;
#   dòng cuối — `[selfcheck] TEMPLATE ĐẠT` hoặc `[selfcheck] APP ĐẠT`.
#
# Chạy lần lượt, dừng ở lỗi đầu tiên, mỗi bước xong in `[selfcheck] <bước>: OK`. Exit 0 = template đạt.
# Điểm mấu chốt: build Release phải QUA verify_release_clean.sh, build Internal phải BỊ TỪ CHỐI và phải chứa MỌI tên
# `[binary]` của debug_symbols.txt (đối chứng dương); bộ chạy test phải trả rc 3 `[false-green]` khi chỉ định test
# không tồn tại — một cổng chỉ biết nói PASS thì không chứng minh được gì. Bản đầy đủ chạy thêm test StoreKit
# (`run_tests.py --storekit`, sau L2); ở template thêm bước 9, theo thứ tự: tổ hợp tắt hết (`feature_matrix_check.sh`),
# gỡ tính năng mẫu (`sample_removal_check.sh`, chỉ khi cây còn mẫu), rồi tạo app mới thật và kiểm nó
# (`new_app_check.sh`) — bước này luôn CUỐI. Các script đó là của template (không có ở app). Cần ≥ 10 GB đĩa trống
# (mỗi bản chép một simulator + DerivedData; các bản chép chạy lần lượt và tự dọn).
#
# Tính năng mẫu (`AppHost/AppHost/Features/Sample/`): khi cây CÒN mẫu, cổng 14 của verify_release_clean.sh được bỏ qua
# bằng `ALLOW_SAMPLE_IN_RELEASE=1` — đặt RIÊNG cho từng lệnh verify, không export (để sample_removal_check.sh chạy bên
# dưới không thừa hưởng) — kèm đối chứng dương: thiếu biến thì chính .app Release đó PHẢI bị cổng 14 từ chối. Khi mẫu
# đã gỡ (app thật, hoặc bản chép của sample_removal_check.sh), không đặt biến: cổng 14 gác thật. Chạy ở tiến trình tiền cảnh: hai test SIGINT của
# tools/release/test_bump_version.py đỏ khi shell chạy selfcheck như job nền `( … ) &` (SIGINT bị bỏ qua ở đó).
set -u

QUICK=0
KIND_ONLY=0
for ARG in "$@"; do
  case "$ARG" in
    --quick) QUICK=1 ;;
    --kind) KIND_ONLY=1 ;;
    *) echo "dùng: $0 [--quick | --kind]" >&2; exit 2 ;;
  esac
done

# Biến GIT_* thừa hưởng (vd chạy từ hook) thắng `git -C` ⇒ gỡ hết trước khi hỏi git.
for V in $(compgen -e); do
  case "$V" in GIT_*) unset "$V" ;; esac
done

# Gốc repo theo vị trí script (chạy từ thư mục nào cũng được; đường dẫn có dấu cách vẫn đúng).
ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel) || { echo "FAIL: không tìm được gốc repo git" >&2; exit 1; }
cd "$ROOT" || exit 1

# Template hay app: cùng luật với `repo_kind` của .githooks/pre-commit (file đánh dấu track trong HEAD; HEAD chưa có ⇒ index).
TEMPLATE_MARKER="tools/template/new_app.py"
if git rev-parse --verify -q "HEAD^{commit}" >/dev/null 2>&1; then
  if git cat-file -e "HEAD:$TEMPLATE_MARKER" 2>/dev/null; then KIND=template; else KIND=app; fi
elif git ls-files --error-unmatch -- ":(literal)$TEMPLATE_MARKER" >/dev/null 2>&1; then
  KIND=template
else
  KIND=app
fi
if [ "$KIND_ONLY" -eq 1 ]; then echo "$KIND"; exit 0; fi
if [ "$KIND" = template ]; then KIND_LABEL="TEMPLATE"; else KIND_LABEL="APP"; fi
echo "[selfcheck] loại repo: $KIND"

step_ok() { echo "[selfcheck] $1: OK"; }
fail() { echo "[selfcheck] FAIL: $1" >&2; exit 1; }
const() { python3 -c 'import sys; sys.path.insert(0, "tools/common"); import appconfig; print(getattr(appconfig, sys.argv[1]))' "$1"; }

PROJECT=$(const PROJECT) && SCHEME=$(const SCHEME) && STORE_SCHEME=$(const STORE_SCHEME) && PROJ_DIR=$(const PROJ_DIR) \
  || fail "không đọc được hằng số bố cục từ tools/common/appconfig.py"
[ -n "$PROJECT" ] && [ -n "$SCHEME" ] && [ -n "$STORE_SCHEME" ] && [ -n "$PROJ_DIR" ] || fail "hằng số bố cục rỗng"

# 1. Config + định danh
python3 tools/common/appconfig.py check || fail "appconfig.py check"
step_ok "appconfig check"
python3 tools/common/lint_identity.py || fail "lint_identity.py"
step_ok "lint_identity"
# Id sản phẩm: file .storekit (test StoreKit + Run từ Xcode) phải khớp [purchases] product_ids (paywall tắt ⇒ SKIP).
python3 tools/release/check_storekit.py || fail "check_storekit.py"
step_ok "check_storekit"
# Danh sách symbol debug khớp nguồn: type khai trong #if INTERNAL phải có tên ở mục [binary] của debug_symbols.txt (lõi) hoặc debug_symbols.app.txt (app),
# hàm/biến có marker ở [source-only], và ngược lại (tên đúng mục, không mồ côi).
python3 tools/release/lint_debug_symbols.py || fail "lint_debug_symbols.py"
step_ok "lint_debug_symbols"
# Kiểu seed/store giả của route preview (*PreviewSeed/*PreviewStore) chỉ trong #if targetEnvironment(simulator).
python3 tools/release/lint_preview_code.py || fail "lint_preview_code.py"
step_ok "lint_preview_code"
# Cờ FEATURE_* chỉ ở AppHost/; Core/ và CoreTests/ không nhắc khối tuỳ chọn (CoreOptional/).
python3 tools/common/lint_feature_flag.py || fail "lint_feature_flag.py"
step_ok "lint_feature_flag"
# `import Firebase*` chỉ ở FirebaseSink.swift (+ AppCheckTokenSource.swift của khối WebAPI), đúng module được phép.
python3 tools/telemetry/lint_firebase_imports.py || fail "lint_firebase_imports.py"
step_ok "lint_firebase_imports"
# Biên tính năng mẫu: cú pháp khối `// sample:…`, không symbol Sample* ngoài khối, Core/ không biết mẫu, tài liệu gieo
# tả mẫu trong khối (đã gỡ: chỉ soi tài liệu gieo không sót dấu vết).
python3 tools/template/remove_sample.py --check || fail "remove_sample.py --check"
step_ok "remove_sample --check"
if [ "$KIND" = template ]; then
  # Mọi file track thuộc đúng một lớp sở hữu (template.manifest.toml), mục khai đều khớp file, thư mục gieo không đè file
  # sync/seed, file sync/seed không trỏ tới file chỉ-template, khối `template:` trong file seed đúng cú pháp (luật a–f).
  python3 tools/template/manifest.py check || fail "manifest.py check"
  step_ok "manifest check"
else
  # App: mọi file lớp đồng bộ giống hệt digest trong core.lock (M/D), không file mới trong thư mục lõi (A).
  python3 tools/template/sync_core.py check || fail "sync_core.py check — lõi lệch core.lock (sửa ở template rồi đồng bộ)"
  step_ok "sync_core check"
fi

# 2. Unit test của các bộ công cụ (không loại trừ test nào). Thư mục KHÔNG viết cứng: mọi `tools/<d>/` có `test_*.py` đều
# chạy, cùng `web/tools/` (cổng site/sitemap/changelog + predeploy) khi có (thêm bộ công cụ mới có test ⇒ tự vào cổng;
# app sinh ra chỉ có những bộ nó có). Mẫu `-p` luôn trong nháy đơn.
UNIT_DIRS=()
LAST_DIR=""
for T in tools/*/test_*.py web/tools/test_*.py; do
  [ -e "$T" ] || continue
  D=$(dirname "$T")
  [ "$D" = "$LAST_DIR" ] && continue
  UNIT_DIRS+=("$D")
  LAST_DIR="$D"
done
[ "${#UNIT_DIRS[@]}" -ge 1 ] && printf '%s\n' "${UNIT_DIRS[@]}" | grep -qx 'tools/common' \
  || fail "không tìm thấy thư mục unit test (tools/<d>/test_*.py) — ít nhất tools/common phải có"
for D in "${UNIT_DIRS[@]}"; do
  python3 -m unittest discover -s "$D" -p 'test_*.py' || fail "unittest $D"
  step_ok "unittest $D"
done
mkdir -p "$ROOT/.temp" && python3 tools/i18n/lint_localizable.py --self-test > "$ROOT/.temp/selfcheck-i18n-selftest.log" 2>&1 \
  || { cat "$ROOT/.temp/selfcheck-i18n-selftest.log" >&2; fail "lint_localizable.py --self-test"; }
step_ok "i18n self-test"

# 2b. web/ (npm): test (vitest — Miniflare, D1 cục bộ, không mạng) + typecheck của Worker API và site. `npm ci` là bước
# DUY NHẤT của selfcheck cần mạng (tải phụ thuộc theo web/package-lock.json) ⇒ chỉ chạy ở bản đầy đủ; --quick in BỎ QUA.
# Cần Node >= 22.12 (web/.nvmrc, `engines`): thiếu node/npm hoặc bản cũ ⇒ đỏ ở bản đầy đủ.
if [ ! -f web/package.json ]; then
  echo "[selfcheck] web npm: BỎ QUA (không có web/package.json)"
elif [ "$QUICK" -eq 1 ]; then
  echo "[selfcheck] web npm (npm ci, npm test, npm run typecheck): BỎ QUA (--quick)"
else
  command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 \
    || fail "web/ cần Node >= 22.12 + npm (web/.nvmrc) — không thấy node/npm trên PATH"
  node -e 'const [a, b] = process.versions.node.split(".").map(Number); process.exit(a > 22 || (a === 22 && b >= 12) ? 0 : 1)' \
    || fail "web/ cần Node >= 22.12 (web/.nvmrc) — máy đang có $(node --version 2>/dev/null)"
  mkdir -p "$ROOT/.temp"
  WEB_LOG="$ROOT/.temp/selfcheck-web-npm.log"
  if ! ( cd web && npm ci && npm test && npm run typecheck ) > "$WEB_LOG" 2>&1; then
    tail -40 "$WEB_LOG" >&2
    fail "web: npm ci && npm test && npm run typecheck (log: $WEB_LOG)"
  fi
  step_ok "web npm ci + test + typecheck"
fi

# 3. Lint harness (bỏ qua khi template chưa có .claude/)
if [ -d .claude ]; then
  python3 tools/factory/lint_harness.py || fail "lint_harness.py"
  step_ok "lint_harness"
else
  echo "[selfcheck] lint_harness: BỎ QUA (chưa có .claude/)"
fi

# 4. Sinh project
( cd "$PROJ_DIR" && xcodegen generate ) || fail "xcodegen generate"
step_ok "xcodegen generate"

# 4b. Biên lõi: Core/ biên dịch MỘT MÌNH (target static library CoreOnly, không ship). Một tham chiếu từ Core/ tới
# kiểu của app ⇒ build này đỏ. Chạy cả ở --quick (vài giây, không cần simulator).
CORE_ONLY_SCHEME=$(const CORE_ONLY_SCHEME) && [ -n "$CORE_ONLY_SCHEME" ] || fail "không đọc được CORE_ONLY_SCHEME"
CORE_LOG="$ROOT/.temp/selfcheck-coreonly-build.log"
if ! xcodebuild build -project "$PROJECT" -scheme "$CORE_ONLY_SCHEME" -configuration Debug \
     -destination 'generic/platform=iOS Simulator' -derivedDataPath "$ROOT/.temp/DerivedData/selfcheck-coreonly" \
     CODE_SIGNING_ALLOWED=NO > "$CORE_LOG" 2>&1; then
  grep -E "error:" "$CORE_LOG" | head -20 >&2
  tail -10 "$CORE_LOG" >&2
  fail "build $CORE_ONLY_SCHEME (Debug) — Core/ phụ thuộc thứ không có trong Core/?"
fi
step_ok "$CORE_ONLY_SCHEME"

# 5. Toàn bộ test iOS (Debug, Simulator) + chứng minh bộ chạy test biết đỏ + build target UI test
if [ "$QUICK" -eq 0 ]; then
  python3 tools/dev/run_tests.py --full || fail "run_tests.py --full"
  step_ok "run_tests --full"

  # Cổng chống xanh giả phải thực sự bắn: chỉ định một class không tồn tại ⇒ rc 3 + `[false-green]`.
  FG_OUT=$(python3 tools/dev/run_tests.py --no-build KhongTonTaiTests 2>&1)
  FG_RC=$?
  if [ "$FG_RC" -ne 3 ] || ! grep -qF "[false-green]" <<< "$FG_OUT"; then
    echo "$FG_OUT" >&2
    fail "run_tests.py --no-build KhongTonTaiTests trả rc=$FG_RC (phải 3 kèm [false-green]) — cổng xanh giả không gác"
  fi
  step_ok "run_tests xanh giả ⇒ rc 3"

  # LiveStoreClientTests (StoreKit thật qua SKTestSession) bị scheme chính skip — chạy riêng qua scheme StoreKit.
  python3 tools/dev/run_tests.py --storekit || fail "run_tests.py --storekit"
  step_ok "run_tests --storekit"

  # Target AppHostUITests + scheme UIShots không nằm trong L1/L2 — build ở đây để chúng không mục âm thầm.
  UIT_LOG="$ROOT/.temp/selfcheck-uishots-build.log"
  if ! xcodebuild build-for-testing -project "$PROJECT" -scheme "$(const UISHOTS_SCHEME)" -configuration Debug \
       -destination 'generic/platform=iOS Simulator' -derivedDataPath "$ROOT/.temp/DerivedData/selfcheck-uishots" \
       CODE_SIGNING_ALLOWED=NO > "$UIT_LOG" 2>&1; then
    tail -30 "$UIT_LOG" >&2
    fail "build-for-testing scheme UIShots (Debug)"
  fi
  step_ok "build-for-testing UIShots"
else
  echo "[selfcheck] run_tests --full, xanh giả ⇒ rc 3, run_tests --storekit, build-for-testing UIShots: BỎ QUA (--quick)"
fi

# 6. Plist Firebase giả (template không chứa plist thật)
WORK="$ROOT/.temp/selfcheck"
FIREBASE_DIR="$WORK/firebase"
DD="$WORK/DerivedData"
rm -rf "$FIREBASE_DIR"
python3 tools/common/appconfig.py fixture-plist --out "$FIREBASE_DIR" || fail "fixture-plist"
[ -f "$FIREBASE_DIR/GoogleService-Info-Prod.plist" ] && [ -f "$FIREBASE_DIR/GoogleService-Info-Dev.plist" ] \
  || fail "fixture-plist không sinh đủ hai plist"
step_ok "fixture plist Firebase"

# Build một config không ký cho thiết bị; in đường dẫn .app ra stdout (log build ra stderr→file).
build_app() {  # $1 = scheme, $2 = config
  local log="$WORK/build-$2.log" app
  rm -rf "$DD/Build/Products"
  if ! xcodebuild -project "$PROJECT" -scheme "$1" -configuration "$2" -destination 'generic/platform=iOS' \
       -derivedDataPath "$DD" CODE_SIGNING_ALLOWED=NO FIREBASE_PLIST_DIR="$FIREBASE_DIR" build > "$log" 2>&1; then
    tail -30 "$log" >&2
    return 1
  fi
  app=$(find "$DD/Build/Products/$2-iphoneos" -maxdepth 1 -name '*.app' | head -1)
  [ -d "$app" ] || { echo "không thấy .app trong $DD/Build/Products/$2-iphoneos" >&2; return 1; }
  # Giữ lại bản .app (build sau xoá Products của build trước) để các script tự kiểm của template còn đọc được .app Release + Internal.
  rm -rf "$WORK/apps/$2"; mkdir -p "$WORK/apps/$2"
  cp -R "$app" "$WORK/apps/$2/" || return 1
  printf '%s\n' "$WORK/apps/$2/$(basename "$app")"
}

# Cây còn tính năng mẫu ⇒ cho cổng 14 qua (từng lệnh, không export); đã gỡ ⇒ "0" = cổng 14 gác thật.
SAMPLE_DIR="AppHost/AppHost/Features/Sample"
if [ -d "$SAMPLE_DIR" ]; then ALLOW_SAMPLE=1; else ALLOW_SAMPLE=0; fi

# 7. Release phải sạch
APP_REL=$(build_app "$STORE_SCHEME" Release) || fail "build Release"
step_ok "build Release"
# ALLOW_FIXTURE_PLIST=1: template không có plist Firebase thật — chỉ selfcheck được phép cho plist fixture qua cổng.
# ALLOW_SITE_PLACEHOLDER=1: trang web của template (và app vừa sinh) còn chữ giữ chỗ — cổng 16 hạ chúng thành cảnh báo.
ALLOW_FIXTURE_PLIST=1 ALLOW_SITE_PLACEHOLDER=1 ALLOW_SAMPLE_IN_RELEASE="$ALLOW_SAMPLE" tools/release/verify_release_clean.sh "$APP_REL" \
  || fail "verify_release_clean.sh từ chối bản Release"
if [ "$ALLOW_SAMPLE" = 1 ]; then
  step_ok "verify Release (cây còn tính năng mẫu — cổng 14 bỏ qua bằng ALLOW_SAMPLE_IN_RELEASE=1)"
else
  step_ok "verify Release (tính năng mẫu đã gỡ — cổng 14 gác thật)"
fi

# 7b. Đối chứng dương cổng 14 (chỉ khi cây còn mẫu): KHÔNG có biến cho phép ⇒ chính .app Release vừa qua PHẢI bị từ
#     chối, và CHỈ vì cổng 14 (một dòng FAIL duy nhất) — cổng biết cắn, và mốc `SampleItemStore` có thật trong binary.
if [ "$ALLOW_SAMPLE" = 1 ]; then
  S14_OUT=$(ALLOW_FIXTURE_PLIST=1 ALLOW_SITE_PLACEHOLDER=1 ALLOW_SAMPLE_IN_RELEASE=0 SKIP_CATALOG_CHECK=1 \
            tools/release/verify_release_clean.sh "$APP_REL" 2>&1)
  S14_RC=$?
  S14_FAILS=$(grep -c "^FAIL:" <<< "$S14_OUT")
  if [ "$S14_RC" -ne 1 ] || ! grep -qF "còn tính năng mẫu trong bản Store" <<< "$S14_OUT" || [ "$S14_FAILS" -ne 1 ]; then
    echo "$S14_OUT" >&2
    fail "đối chứng dương cổng 14: thiếu ALLOW_SAMPLE_IN_RELEASE, .app Release còn mẫu phải bị từ chối (rc=$S14_RC, $S14_FAILS dòng FAIL — cần rc 1 và đúng 1 dòng FAIL của cổng 14)"
  fi
  step_ok "đối chứng dương cổng 14 (Release còn mẫu bị từ chối khi không có biến)"
fi

# 8. Internal PHẢI bị từ chối — vì bundle id Internal khác Store và vì còn InternalDebugMarkerView.
APP_INT=$(build_app "$SCHEME" Internal) || fail "build Internal"
step_ok "build Internal"
INT_OUT=$(ALLOW_FIXTURE_PLIST=1 ALLOW_SITE_PLACEHOLDER=1 ALLOW_SAMPLE_IN_RELEASE="$ALLOW_SAMPLE" tools/release/verify_release_clean.sh "$APP_INT" 2>&1)
INT_RC=$?
if [ "$INT_RC" -eq 0 ]; then
  echo "$INT_OUT" >&2
  fail "verify_release_clean.sh CHO QUA bản Internal — cổng không gác"
fi
if [ "$INT_RC" -ne 1 ]; then
  echo "$INT_OUT" >&2
  fail "verify_release_clean.sh trả rc=$INT_RC (phải là 1 = từ chối vì nội dung) với bản Internal"
fi
for NEEDLE in "bundle id" "InternalDebugMarkerView"; do
  if ! grep -qF "$NEEDLE" <<< "$INT_OUT"; then
    echo "$INT_OUT" >&2
    fail "bản Internal bị từ chối nhưng không vì '$NEEDLE' — cổng bị từ chối sai lý do"
  fi
done
step_ok "verify Internal bị từ chối"

# 8b. Đối chứng dương của cổng 1: MỌI tên [binary] phải có trong .app Internal. Một tên không thấy ở đây (type bị
#     optimizer bỏ, gõ sai, đổi tên) là mục vô tác dụng — cổng 1 trên bản Release sẽ gác một chuỗi không bao giờ có.
tools/release/verify_release_clean.sh --expect-debug-symbols "$APP_INT" || fail "đối chứng dương symbol debug trên bản Internal"
step_ok "đối chứng dương symbol debug (Internal)"

# 9. Chỉ template: tổ hợp tắt hết, gỡ mẫu, tạo app mới thật — mỗi bước một bản chép tạm riêng; tạo app mới luôn CUỐI.
if [ "$KIND" != template ]; then
  echo "[selfcheck] bước 9 (tổ hợp tắt hết, gỡ mẫu, tạo app mới): BỎ QUA — đây là app, bước này chỉ chạy ở template"
elif [ "$QUICK" -eq 0 ]; then
  for S in feature_matrix_check.sh sample_removal_check.sh new_app_check.sh; do
    [ -x "tools/template/$S" ] || fail "template thiếu tools/template/$S (hoặc mất bit thực thi)"
  done
  tools/template/feature_matrix_check.sh || fail "feature_matrix_check.sh"
  step_ok "tổ hợp tắt hết"
  if [ -d "$SAMPLE_DIR" ]; then
    tools/template/sample_removal_check.sh || fail "sample_removal_check.sh"
    step_ok "gỡ tính năng mẫu"
  else
    echo "[selfcheck] gỡ tính năng mẫu: BỎ QUA (mẫu đã gỡ)"
  fi
  tools/template/new_app_check.sh || fail "new_app_check.sh"
  step_ok "tạo app mới thật + kiểm repo sinh ra"
else
  echo "[selfcheck] bước 9 (tổ hợp tắt hết, gỡ mẫu, tạo app mới): BỎ QUA (--quick)"
fi

if [ "$QUICK" -eq 0 ]; then
  echo "[selfcheck] $KIND_LABEL ĐẠT"
else
  echo "[selfcheck] $KIND_LABEL ĐẠT (--quick: chưa chạy test iOS, StoreKit và bước 9)"
fi
