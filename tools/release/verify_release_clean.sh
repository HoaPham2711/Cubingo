#!/bin/bash
# Chứng minh bản đem lên App Store KHÔNG chứa code debug và mang đúng định danh Store.
#
# Bọc #if INTERNAL đủ hay chưa là thứ không thể xác nhận bằng mắt — file này soi binary thật.
# Chạy TRƯỚC mỗi lần upload; `tools/template/selfcheck.sh` chạy nó trên cả build Release (phải qua) lẫn build
# Internal (phải bị từ chối) để chứng minh chính cổng này có gác.
#
#   ./tools/release/verify_release_clean.sh <path/to/App.app | path/to/X.xcarchive>
#   ./tools/release/verify_release_clean.sh --expect-debug-symbols <path/to/Internal.app>
#
# Exit: 0 sạch · 1 có lỗi · 2 sai cách dùng / không đọc được .app.
# Mọi giá trị định danh đọc từ app.config.toml qua tools/common/appconfig.py — script không chứa literal nào.
#
# `--expect-debug-symbols` = ĐỐI CHỨNG DƯƠNG của cổng 1 (chạy trên .app INTERNAL, selfcheck bước 8): MỌI tên ở mục
# `[binary]` của debug_symbols.txt PHẢI tìm thấy trong binary đó; tên không thấy là "mục vô tác dụng" (type bị
# optimizer bỏ, gõ sai, đổi tên) ⇒ rc 1. Chỉ chạy phần symbol — không đọc cấu hình, không kiểm định danh. Không có
# đối chứng này, một tên không bao giờ xuất hiện trong binary nằm trong danh sách cho an tâm giả.
#
# ALLOW_FIXTURE_PLIST=1 — cho phép GoogleService-Info.plist fixture (`appconfig.py fixture-plist`). CHỈ
# tools/template/selfcheck.sh đặt biến này (template không có plist thật); bản đem upload thì không bao giờ.
# ALLOW_SAMPLE_IN_RELEASE=1 — bỏ qua cổng 14 (binary còn tính năng mẫu `SampleItemStore`). CHỈ các script tự kiểm của
# template đặt (khi cây còn mẫu); luồng ra bản thì không bao giờ.
# ALLOW_SITE_PLACEHOLDER=1 — cổng 16 chạy check_site.py KHÔNG `--release` (chữ giữ chỗ của trang web chỉ cảnh báo). CHỈ
# selfcheck.sh / feature_matrix_check.sh đặt (template + app vừa sinh còn chữ giữ chỗ); bị từ chối với .xcarchive.
# SKIP_SYMBOL_LINT=1 / SKIP_CATALOG_CHECK=1 — bỏ các kiểm trên NGUỒN (lint_debug_symbols / String Catalog); chỉ test
# của chính script này đặt (repo giả không có nguồn Swift).
set -u

MODE=release
if [ "${1:-}" = "--expect-debug-symbols" ]; then
  MODE=control
  shift
fi
TARGET="${1:-}"
if [ -z "$TARGET" ] || [ ! -e "$TARGET" ] || [ "$#" -gt 1 ]; then
  echo "dùng: $0 <path/to/App.app | path/to/X.xcarchive>" >&2
  echo "      $0 --expect-debug-symbols <path/to/Internal.app>" >&2
  exit 2
fi

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
APPCONFIG="$REPO_ROOT/tools/common/appconfig.py"

# Đọc một khoá cấu hình; lỗi (config hỏng / thiếu khoá) ⇒ KHÔNG đoán, dừng với FAIL.
# appconfig tìm gốc repo theo cwd nên luôn chạy trong $REPO_ROOT.
cfg_get() {
  local v
  v=$(cd "$REPO_ROOT" && python3 "$APPCONFIG" get "$1") || { echo "FAIL: không đọc được '$1' từ app.config.toml" >&2; exit 1; }
  printf '%s' "$v"
}
# Khoá tuỳ chọn: thiếu ⇒ chuỗi rỗng (chỉ gọi sau khi config đã đọc được ở trên).
cfg_get_opt() { (cd "$REPO_ROOT" && python3 "$APPCONFIG" get "$1" 2>/dev/null) || true; }
# Hằng số của appconfig (không phải định danh) — một nguồn với code sinh plist fixture.
cfg_const() { python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import appconfig; print(getattr(appconfig, sys.argv[2]))' \
  "$REPO_ROOT/tools/common" "$1"; }

# 0. Cấu hình phải đọc được VÀ file sinh ra (Identity.xcconfig, Features.generated.yml, Entitlements.generated.yml, PrivacyInfo.xcprivacy, AppHost.entitlements) phải khớp nó — nếu không, mọi so sánh bên dưới so với giá trị
#    không phải thứ đã build vào .app. (Chế độ đối chứng chỉ soi symbol ⇒ bỏ qua phần cấu hình.)
if [ "$MODE" = release ]; then
CHECK_OUT=$(cd "$REPO_ROOT" && python3 "$APPCONFIG" check 2>&1)
CHECK_RC=$?
case "$CHECK_RC" in
  0) ;;
  1) echo "$CHECK_OUT" >&2; echo "FAIL: file sinh ra (Identity.xcconfig / Features.generated.yml / Entitlements.generated.yml / PrivacyInfo.xcprivacy / AppHost.entitlements) cũ so với app.config.toml — chạy appconfig.py render rồi build lại" >&2; exit 1 ;;
  *) echo "$CHECK_OUT" >&2; echo "FAIL: app.config.toml hỏng (xem dòng FAIL ở trên) — không kiểm được bản build" >&2; exit 1 ;;
esac

BUNDLE_STORE=$(cfg_get bundle.store)
NAME_STORE=$(cfg_get app.display_name)
NAME_INTERNAL=$(cfg_get app.display_name_internal)
VER_MARKETING=$(cfg_get version.marketing)
VER_BUILD=$(cfg_get version.build)
[ -n "$BUNDLE_STORE" ] && [ -n "$NAME_STORE" ] && [ -n "$NAME_INTERNAL" ] && [ -n "$VER_MARKETING" ] && [ -n "$VER_BUILD" ] \
  || { echo "FAIL: bundle.store / app.display_name / app.display_name_internal / version.* rỗng" >&2; exit 1; }
FIXTURE_MARK_KEY=$(cfg_const FIXTURE_MARK_KEY) && FIXTURE_API_KEY=$(cfg_const FIXTURE_API_KEY) \
  && [ -n "$FIXTURE_MARK_KEY" ] && [ -n "$FIXTURE_API_KEY" ] \
  || { echo "FAIL: không đọc được dấu nhận biết plist fixture từ appconfig.py" >&2; exit 1; }
HOST_PROD=$(cfg_get_opt web.host_prod)
HOST_DEV=$(cfg_get_opt web.host_dev)
PAYWALL_CFG=$(cfg_get_opt features.paywall)
fi

# .xcarchive → tìm .app bên trong
if [[ "$TARGET" == *.xcarchive ]]; then
  APP=$(find "$TARGET/Products/Applications" -maxdepth 1 -name "*.app" | head -1)
else
  APP="$TARGET"
fi
[ -d "$APP" ] || { echo "không tìm thấy .app trong $TARGET" >&2; exit 2; }

EXEC_NAME=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$APP/Info.plist" 2>/dev/null) \
  || { echo "FAIL: không thể đọc CFBundleExecutable từ $APP/Info.plist" >&2; exit 2; }
BIN="$APP/$EXEC_NAME"
[ -f "$BIN" ] || { echo "không tìm thấy binary $BIN" >&2; exit 2; }
[ -r "$BIN" ] || { echo "FAIL: không thể đọc $BIN (permission denied)" >&2; exit 1; }

FAIL=0
WORK=$(mktemp -d "${TMPDIR:-/tmp}/verify_release_clean.XXXXXX") || { echo "FAIL: không tạo được thư mục tạm" >&2; exit 1; }
trap 'rm -rf "$WORK"' EXIT

# 1. Symbol debug. Soi MỌI Mach-O trong .app (binary chính, framework, và `<App>.debug.dylib` của build Debug), không
#    chỉ binary chính. Tên type Swift nằm trong mangled symbol lẫn metadata string ⇒ soi cả `nm` lẫn `strings`.
#    Danh sách = HỢP của tools/release/debug_symbols.txt (lõi) và AppHost/Config/debug_symbols.app.txt (app, vắng =
#    rỗng), mỗi file HAI mục: chỉ `[binary]` (tên type — metadata reflection giữ lại) được
#    soi ở đây; `[source-only]` (tên hàm/biến — bị strip khỏi mọi binary) chỉ ghim ở nguồn bằng lint_debug_symbols.py.
#    Mục [binary] rỗng / thiếu file / tên trước mọi mục / mục lạ ⇒ FAIL (không được qua trống).
SYMS_FILE="$WORK/symbols.txt"
MACHO_COUNT=0
while IFS= read -r -d '' f; do
  if file -b "$f" 2>/dev/null | grep -q "Mach-O"; then
    MACHO_COUNT=$((MACHO_COUNT + 1))
    { nm -a "$f" 2>/dev/null; strings -a "$f" 2>/dev/null; } >> "$SYMS_FILE" || true
  fi
done < <(find "$APP" -type f -print0)

if [ "$MACHO_COUNT" -eq 0 ] || [ ! -s "$SYMS_FILE" ]; then
  echo "FAIL: không trích được symbol nào từ $APP (không có Mach-O hợp lệ hoặc kiến trúc không hỗ trợ)" >&2
  exit 1
fi

SYMBOL_LIST="$REPO_ROOT/tools/release/debug_symbols.txt"
# Danh sách của APP (app sở hữu, cùng định dạng): vắng file = rỗng. Cổng đọc HỢP của hai file.
APP_SYMBOL_LIST="$REPO_ROOT/AppHost/Config/debug_symbols.app.txt"
if [ ! -f "$SYMBOL_LIST" ]; then
  echo "FAIL: thiếu $SYMBOL_LIST — không có danh sách symbol debug để kiểm"
  exit 1
fi
BIN_NAMES=()
SRC_COUNT=0
LIST_BAD=0
SEEN_NAMES=$'\n'   # "<tên>|<file>" mỗi dòng — để bắt tên có ở cả hai file
read_symbol_list() {   # $1 = đường dẫn file, $2 = nhãn hiển thị
  local list="$1" label="$2" pat other
  SECTION=""
  LINE_NO=0
  while IFS= read -r pat || [ -n "$pat" ]; do
    LINE_NO=$((LINE_NO + 1))
    # Cắt khoảng trắng đầu/cuối — [:space:] gồm cả \r của file CRLF. Không cắt thì "Foo " hay "Foo\r" không bao giờ
    # khớp và symbol đó âm thầm hết được gác. Dòng rỗng sau khi cắt thì bỏ qua.
    pat="${pat#"${pat%%[![:space:]]*}"}"
    pat="${pat%"${pat##*[![:space:]]}"}"
    case "$pat" in ''|'#'*) continue ;; esac
    case "$pat" in
      '[binary]') SECTION=binary; continue ;;
      '[source-only]') SECTION=source; continue ;;
      '['*']') echo "FAIL: $label:$LINE_NO: mục lạ '$pat' (chỉ có [binary] và [source-only])"
               LIST_BAD=1; SECTION=bad; continue ;;
    esac
    case "$SECTION" in
      binary|source)
        # Cùng một tên ở file KHÁC ⇒ lỗi (tên của lõi chỉ ở file lõi, tên của app chỉ ở file app).
        other=$(printf '%s' "$SEEN_NAMES" | grep -F -x -e "$pat|$SYMBOL_LIST_OTHER" 2>/dev/null || true)
        if [ -n "$other" ]; then
          echo "FAIL: $label:$LINE_NO: '$pat' khai trùng — đã có ở file kia (debug_symbols.txt và debug_symbols.app.txt không được trùng tên)"
          LIST_BAD=1
        fi
        SEEN_NAMES="$SEEN_NAMES$pat|$label"$'\n'
        if [ "$SECTION" = binary ]; then BIN_NAMES+=("$pat"); else SRC_COUNT=$((SRC_COUNT + 1)); fi ;;
      bad) ;;
      *) echo "FAIL: $label:$LINE_NO: '$pat' đứng trước mọi mục — không biết soi binary hay chỉ ghim nguồn"
         LIST_BAD=1 ;;
    esac
  done < "$list"
}
SYMBOL_LIST_OTHER=""
read_symbol_list "$SYMBOL_LIST" "debug_symbols.txt"
if [ -f "$APP_SYMBOL_LIST" ]; then
  SYMBOL_LIST_OTHER="debug_symbols.txt"
  read_symbol_list "$APP_SYMBOL_LIST" "debug_symbols.app.txt"
fi
BIN_COUNT=${#BIN_NAMES[@]}

if [ "$MODE" = control ]; then
  # Đối chứng dương: mọi tên [binary] PHẢI có trong binary Internal — tên không thấy ở đây thì cổng 1 trên bản Release
  # gác một chuỗi không bao giờ xuất hiện.
  if [ "$LIST_BAD" -ne 0 ] || [ "$BIN_COUNT" -eq 0 ]; then
    [ "$BIN_COUNT" -eq 0 ] && echo "FAIL: $SYMBOL_LIST: mục [binary] không có dòng nào có hiệu lực — không có gì để đối chứng"
    exit 1
  fi
  MISSING=0
  for pat in "${BIN_NAMES[@]}"; do
    if ! grep -qF -e "$pat" "$SYMS_FILE"; then
      echo "FAIL: mục vô tác dụng: '$pat' ([binary]) không có trong binary của $APP — type bị optimizer bỏ, gõ sai hay" \
           "đã đổi tên; cổng 1 sẽ gác một chuỗi không bao giờ xuất hiện. Sửa tên hoặc bỏ dòng."
      MISSING=$((MISSING + 1))
    fi
  done
  if [ "$MISSING" -ne 0 ]; then
    echo "--- đối chứng dương: $MISSING/$BIN_COUNT tên [binary] vô tác dụng ---"
    exit 1
  fi
  echo "PASS: đối chứng dương — $BIN_COUNT/$BIN_COUNT tên [binary] có trong $APP ($MACHO_COUNT Mach-O);" \
       "$SRC_COUNT tên [source-only] không soi binary (chỉ ghim ở nguồn)"
  exit 0
fi

if [ "$LIST_BAD" -ne 0 ]; then
  FAIL=1
fi
if [ "$BIN_COUNT" -eq 0 ]; then
  echo "FAIL: $SYMBOL_LIST: mục [binary] không có dòng nào có hiệu lực — cổng symbol sẽ qua trống"
  FAIL=1
else
  for pat in "${BIN_NAMES[@]}"; do
    if grep -qF -e "$pat" "$SYMS_FILE"; then
      echo "FAIL: còn symbol debug '$pat' trong binary"
      FAIL=1
    fi
  done
fi
echo "  cổng 1: soi $BIN_COUNT tên [binary] trong $MACHO_COUNT Mach-O; $SRC_COUNT tên [source-only] không soi binary" \
     "(tên hàm bị strip — chỉ ghim ở nguồn)"
# 1b. Danh sách khớp nguồn (type INTERNAL-only đủ tên, tên đúng mục, không mồ côi) — cùng lint với pre-commit/selfcheck.
if [ "${SKIP_SYMBOL_LINT:-0}" != "1" ]; then
  if ! python3 "$REPO_ROOT/tools/release/lint_debug_symbols.py"; then
    echo "FAIL: debug_symbols.txt lệch nguồn (lint_debug_symbols.py) — cổng 1 có thể đang soi thiếu/sai tên"
    FAIL=1
  fi
fi

# 2. Bundle id — bắt lỗi archive nhầm scheme (bản Internal không được lên store).
BID=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Info.plist" 2>/dev/null) \
  || { echo "FAIL: không thể đọc CFBundleIdentifier từ $APP/Info.plist" >&2; exit 2; }
if [ "$BID" != "$BUNDLE_STORE" ]; then
  echo "FAIL: bundle id là '$BID', phải là '$BUNDLE_STORE'"
  FAIL=1
fi

# 3. Tên hiển thị + version — PHẢI bằng đúng cấu hình (không chỉ "khác tên Internal"): bắt archive nhầm config
#    Internal, lẫn build từ cấu hình cũ (xcconfig chưa render lại / Info.plist sinh lệch).
DISPLAY_NAME=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleDisplayName' "$APP/Info.plist" 2>/dev/null) || DISPLAY_NAME=""
if [ "$DISPLAY_NAME" != "$NAME_STORE" ]; then
  if [ "$DISPLAY_NAME" == "$NAME_INTERNAL" ]; then
    echo "FAIL: CFBundleDisplayName là '$DISPLAY_NAME' (tên config Internal) — không được lên App Store"
  else
    echo "FAIL: CFBundleDisplayName là '$DISPLAY_NAME', phải là app.display_name '$NAME_STORE'"
  fi
  FAIL=1
fi
GOT_MARKETING=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Info.plist" 2>/dev/null) || GOT_MARKETING=""
if [ "$GOT_MARKETING" != "$VER_MARKETING" ]; then
  echo "FAIL: CFBundleShortVersionString là '$GOT_MARKETING', phải là version.marketing '$VER_MARKETING'"
  FAIL=1
fi
GOT_BUILD=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$APP/Info.plist" 2>/dev/null) || GOT_BUILD=""
if [ "$GOT_BUILD" != "$VER_BUILD" ]; then
  echo "FAIL: CFBundleVersion là '$GOT_BUILD', phải là version.build '$VER_BUILD'"
  FAIL=1
fi

# 10. Web host — chỉ khi app có web (web.host_prod khác rỗng). Bản Store PHẢI nói chuyện với production; trỏ nhầm
#     dev là lỗi không thấy bằng mắt: app chạy bình thường nhưng dữ liệu người dùng thật nằm ở hệ thống thử.
#     Universal Link (entitlement associated-domains, appconfig.py render quản): có host ⇒ khoá đó (nếu có) phải mang
#     ĐÚNG MỘT mục `applinks:` và là `applinks:<host_prod>` (thiếu/sai ⇒ link mở Safari thay vì app; `?mode=developer`
#     ⇒ AASA không qua CDN của Apple); bản ĐÃ KÝ có host mà THIẾU hẳn khoá cũng FAIL (project.yml chưa include fragment,
#     hoặc chưa chạy render/xcodegen); không host ⇒ không được có khoá (app không có web thì không tuyên bố domain nào).
#     Build không ký (CODE_SIGNING_ALLOWED=NO, selfcheck) không có entitlement ⇒ in rõ dòng BỎ QUA; khi đó bước 0
#     (`appconfig.py check`) đã giữ file entitlements nguồn khớp cấu hình. Archive đã ký thì kiểm thật.
# "Đã ký" = có chữ ký CỦA BUNDLE (`_CodeSignature/CodeResources`). KHÔNG dùng `codesign -dv` rc: linker arm64 tự ký
# ad-hoc mọi Mach-O (flag linker-signed) kể cả khi CODE_SIGNING_ALLOWED=NO ⇒ rc 0 cả với build không ký.
SIGNED=0
[ -f "$APP/_CodeSignature/CodeResources" ] && SIGNED=1
ENTS=$(codesign -d --entitlements :- "$APP" 2>/dev/null || true)
if [ "$SIGNED" = 0 ]; then
  echo "  cổng 10 BỎ QUA: build không ký — entitlement (associated-domains) chưa soi; archive đã ký mới kiểm được"
fi
# In "KEY" + từng mục của associated-domains (một dòng một mục) nếu entitlement có khoá; không ⇒ rỗng.
ASSOC=$(printf '%s' "$ENTS" | python3 -c '
import plistlib, sys
raw = sys.stdin.buffer.read()
i = raw.find(b"<?xml")
try:
    ents = plistlib.loads(raw[i:]) if i >= 0 else {}
except Exception:
    print("UNREADABLE"); sys.exit(0)
v = ents.get("com.apple.developer.associated-domains") if isinstance(ents, dict) else None
if v is not None:
    print("KEY")
    for d in (v if isinstance(v, list) else [v]):
        print(d)
')
if [ "$ASSOC" = "UNREADABLE" ]; then
  echo "FAIL: không đọc được entitlement của bản đã ký"
  FAIL=1
fi
if [ -n "$HOST_PROD" ]; then
  WEB_HOST=$(/usr/libexec/PlistBuddy -c 'Print :WebHost' "$APP/Info.plist" 2>/dev/null) || true
  if [ "$WEB_HOST" != "$HOST_PROD" ]; then
    echo "FAIL: WebHost là '$WEB_HOST', bản Store phải là '$HOST_PROD'"
    FAIL=1
  fi
  if [ "$(printf '%s\n' "$ASSOC" | head -1)" = "KEY" ]; then
    # So từng mục theo host (bỏ tiền tố `applinks:`/`webcredentials:` và `?mode=…`), không so chuỗi con: host dev có
    # thể là chuỗi con của host prod (prod `www.x.com`, dev `x.com`).
    if [ -n "$HOST_DEV" ] && printf '%s\n' "$ASSOC" | sed -n '2,$p' | sed -e 's/^[A-Za-z]*://' -e 's/?.*$//' \
         | grep -qixF "$HOST_DEV"; then
      echo "FAIL: entitlement associated-domains trỏ tới host dev '$HOST_DEV'"
      FAIL=1
    fi
    APPLINKS=$(printf '%s\n' "$ASSOC" | grep '^applinks:' || true)
    if [ "$APPLINKS" != "applinks:$HOST_PROD" ]; then
      echo "FAIL: associated-domains phải có đúng một mục applinks:$HOST_PROD, đang có: $(printf '%s' "$APPLINKS" | tr '\n' ' ')"
      FAIL=1
    fi
  elif [ "$SIGNED" = 1 ]; then
    echo "FAIL: bản đã ký thiếu entitlement associated-domains (applinks:$HOST_PROD) — project.yml phải include Config/Entitlements.generated.yml, rồi appconfig.py render + xcodegen generate"
    FAIL=1
  fi
elif [ "$(printf '%s\n' "$ASSOC" | head -1)" = "KEY" ]; then
  echo "FAIL: web.host_prod rỗng nhưng entitlement có associated-domains — chạy appconfig.py render rồi build lại"
  FAIL=1
fi

# 13. Paywall + StoreKit. LUÔN kiểm (bật hay tắt paywall): .app KHÔNG chứa file `*.storekit` nào — cấu hình StoreKit
#     local là resource của test bundle (project.yml), lọt vào .app là dữ liệu thử (giá, id) đi lên App Store, dù app có
#     bán gì hay không. Info.plist `FeaturePaywall` phải khớp cấu hình (bắt .app build từ cấu hình khác). Chỉ khi
#     `features.paywall` bật: `ProductIDs` khác rỗng (không thì paywall không có gói nào để bán), `WebHost` khác rỗng
#     (paywall bắt buộc có link Điều khoản/Quyền riêng tư = https://<WebHost>/terms|privacy/ — Guideline 3.1.2).
case "$PAYWALL_CFG" in True) WANT_PAYWALL=YES ;; *) WANT_PAYWALL=NO ;; esac
GOT_PAYWALL=$(/usr/libexec/PlistBuddy -c 'Print :FeaturePaywall' "$APP/Info.plist" 2>/dev/null) || GOT_PAYWALL=""
if [ "$GOT_PAYWALL" != "$WANT_PAYWALL" ]; then
  echo "FAIL: FeaturePaywall là '$GOT_PAYWALL', cấu hình features.paywall ⇒ '$WANT_PAYWALL' — .app build từ cấu hình khác?"
  FAIL=1
fi
if [ "$WANT_PAYWALL" = YES ]; then
  PIDS=$(/usr/libexec/PlistBuddy -c 'Print :ProductIDs' "$APP/Info.plist" 2>/dev/null) || PIDS=""
  if [ -z "${PIDS//[[:space:]]/}" ]; then
    echo "FAIL: paywall bật nhưng Info.plist ProductIDs rỗng — paywall không có gói nào để bán"
    FAIL=1
  fi
  PW_HOST=$(/usr/libexec/PlistBuddy -c 'Print :WebHost' "$APP/Info.plist" 2>/dev/null) || PW_HOST=""
  if [ -z "${PW_HOST//[[:space:]]/}" ]; then
    echo "FAIL: paywall bật nhưng Info.plist WebHost rỗng — paywall cần link Điều khoản/Quyền riêng tư"
    FAIL=1
  fi
else
  echo "  cổng 13 (paywall): BỎ QUA ProductIDs/WebHost — features.paywall tắt (vẫn kiểm .storekit)"
fi
SK_FILES=$(find "$APP" -iname '*.storekit' 2>/dev/null)
if [ -n "$SK_FILES" ]; then
  echo "FAIL: .app chứa file cấu hình StoreKit local (chỉ được là resource của test bundle):"
  while IFS= read -r f; do echo "  $f"; done <<< "$SK_FILES"
  FAIL=1
fi

# 14. Tính năng mẫu của template (`AppHost/AppHost/Features/Sample/`) không được lên App Store: app thật phải gỡ nó
#     bằng `tools/template/remove_sample.py`. Mốc là tên type `SampleItemStore` trong cùng bản dump nm + strings của
#     cổng 1 (class Swift ⇒ tên nằm trong metadata reflection + mangled symbol, đo trên build Release thật).
#     ALLOW_SAMPLE_IN_RELEASE=1 — CHỈ ba script tự kiểm của template (selfcheck.sh khi cây còn mẫu,
#     feature_matrix_check.sh, new_app_check.sh của template qua selfcheck) đặt; luồng ra bản (docs/RELEASE.md) không bao giờ đặt.
#     Biến chỉ có hiệu lực với `.app` trần (sản phẩm build của tự kiểm); `.xcarchive` là hiện vật ra bản thật ⇒ đặt
#     biến cho archive là FAIL (không bao giờ bỏ qua).
SAMPLE_MARKER="SampleItemStore"
if grep -qF -e "$SAMPLE_MARKER" "$SYMS_FILE"; then
  if [ "${ALLOW_SAMPLE_IN_RELEASE:-0}" = "1" ] && [[ "$TARGET" == *.xcarchive ]]; then
    echo "FAIL: còn tính năng mẫu trong bản Store — ALLOW_SAMPLE_IN_RELEASE=1 không áp dụng cho .xcarchive (hiện vật ra" \
         "bản thật); chạy tools/template/remove_sample.py"
    FAIL=1
  elif [ "${ALLOW_SAMPLE_IN_RELEASE:-0}" = "1" ]; then
    echo "  cổng 14 (tính năng mẫu): BỎ QUA — binary còn '$SAMPLE_MARKER' nhưng ALLOW_SAMPLE_IN_RELEASE=1" \
         "(chỉ dành cho tự kiểm của template; bản upload KHÔNG BAO GIỜ đặt biến này)"
  else
    echo "FAIL: còn tính năng mẫu trong bản Store — chạy tools/template/remove_sample.py (binary chứa '$SAMPLE_MARKER')"
    FAIL=1
  fi
fi

# 4. Tài liệu / dữ liệu mẫu không lẫn vào bundle.
#    (a) Không file `*.md` nào trong resource CỦA APP: README là tài liệu cho người đọc NGUỒN (vd
#        `Features/Sample/README.md`); project.yml loại `**/*.md` khỏi resource của app, cổng này giữ điều đó.
#        Bỏ qua `Frameworks/`, `PlugIns/` và mọi thư mục `*.bundle`: đó là nội dung bên thứ ba/target khác (SDK ship
#        resource bundle kèm README là chuyện bình thường), không phải tài liệu nguồn của app lọt vào.
#    (b) `SampleData/` (folder reference cho review UI trên Simulator, nếu có) không chứa file nào khác `README.md` — ai
#        thả dữ liệu THẬT vào rồi lỡ archive thì dữ liệu đó ship lên App Store (README.md ở đó cũng bị (a) bắt).
MD_FILES=$(find "$APP" \( -type d \( -path "$APP/Frameworks" -o -path "$APP/PlugIns" -o -name '*.bundle' \) -prune \) \
  -o -type f -iname '*.md' -print 2>/dev/null)
if [ -n "$MD_FILES" ]; then
  echo "FAIL: .app chứa file Markdown (tài liệu nguồn không được là resource — xem excludes trong project.yml):"
  while IFS= read -r f; do echo "  $f"; done <<< "$MD_FILES"
  FAIL=1
fi
SAMPLE_DATA="$APP/SampleData"
if [ -d "$SAMPLE_DATA" ]; then
  EXTRA=$(find "$SAMPLE_DATA" -type f ! -name "README.md")
  if [ -n "$EXTRA" ]; then
    echo "FAIL: SampleData chứa file ngoài README.md:"
    while IFS= read -r f; do echo "  $f"; done <<< "$EXTRA"
    FAIL=1
  fi
fi

# 5. Firebase — bản Release PHẢI trỏ project PROD (BUNDLE_ID trong plist == bundle.store).
#    Lớp lỗi không thể thấy bằng mắt hay lúc chạy: app chạy bình thường, dữ liệu lặng lẽ chảy về project dev.
#    Cơ chế chọn plist ở BUILD (project.yml, build phase) tồn tại để kiểm được điều này từ .app.
#    ĐỪNG kiểm `IS_ANALYTICS_ENABLED`: khoá đó luôn `false` trong plist do console sinh ra, không nói gì về GA.
GSP="$APP/GoogleService-Info.plist"
if [ ! -f "$GSP" ]; then
  echo "FAIL: thiếu GoogleService-Info.plist trong .app (build phase chọn plist trong project.yml không chạy?)"
  FAIL=1
else
  GSP_BUNDLE=$(/usr/libexec/PlistBuddy -c 'Print :BUNDLE_ID' "$GSP" 2>/dev/null) || GSP_BUNDLE=""
  GSP_PROJECT=$(/usr/libexec/PlistBuddy -c 'Print :PROJECT_ID' "$GSP" 2>/dev/null) || GSP_PROJECT="?"
  GSP_MARK=$(/usr/libexec/PlistBuddy -c "Print :$FIXTURE_MARK_KEY" "$GSP" 2>/dev/null) || GSP_MARK=""
  GSP_API=$(/usr/libexec/PlistBuddy -c 'Print :API_KEY' "$GSP" 2>/dev/null) || GSP_API=""
  if [ -n "$GSP_MARK" ] || [ "$GSP_API" = "$FIXTURE_API_KEY" ]; then
    # Plist fixture BUNDLE_ID đúng id Store nên lọt mọi kiểm bên dưới — phải bắt bằng dấu nhận biết riêng.
    if [ "${ALLOW_FIXTURE_PLIST:-0}" = "1" ]; then
      echo "  GoogleService-Info.plist là FIXTURE (được phép: ALLOW_FIXTURE_PLIST=1 — chỉ dùng cho selfcheck)"
    else
      echo "FAIL: GoogleService-Info.plist là plist FIXTURE (appconfig.py fixture-plist), không phải plist thật của Firebase"
      FAIL=1
    fi
  fi
  if [ "$GSP_BUNDLE" != "$BUNDLE_STORE" ]; then
    echo "FAIL: GoogleService-Info.plist mang BUNDLE_ID '$GSP_BUNDLE' — bản Release phải là project prod"
    FAIL=1
  else
    echo "  Firebase project: $GSP_PROJECT (prod)"
  fi
fi

# 6. Không được lẫn plist nguồn vào bản ship (chúng là file build-time, không phải resource).
for stray in GoogleService-Info-Dev.plist GoogleService-Info-Prod.plist; do
  if [ -f "$APP/$stray" ]; then
    echo "FAIL: .app chứa $stray — plist nguồn không được khai là resource"
    FAIL=1
  fi
done

# 7. Privacy manifest — thiếu là App Store Connect từ chối bản upload, và không có cách nào biết trước lúc build.
#    Có thì khai báo phải khớp công tắc ĐÃ BUILD VÀO .app (Info.plist FeaturePaywall/FeatureWebAPI/FeatureAppleAds,
#    YES|NO): khối bật thì đủ kiểu dữ liệu của khối, khối tắt thì không còn kiểu nào của khối. Bảng công tắc ↔ khoá
#    Info ↔ kiểu dữ liệu là `appconfig.PRIVACY_BLOCKS` (một nguồn với mẫu manifest mà `appconfig.py render` cắt).
if [ ! -f "$APP/PrivacyInfo.xcprivacy" ]; then
  echo "FAIL: thiếu PrivacyInfo.xcprivacy trong .app"
  FAIL=1
else
  GATE7_OUT=$(python3 -c '
import plistlib, sys
sys.path.insert(0, sys.argv[1])
import appconfig
app = sys.argv[2]
bad = []
try:
    with open(app + "/Info.plist", "rb") as f:
        info = plistlib.load(f)
    with open(app + "/PrivacyInfo.xcprivacy", "rb") as f:
        manifest = plistlib.load(f)
    declared = {d.get("NSPrivacyCollectedDataType") for d in manifest.get("NSPrivacyCollectedDataTypes", [])
                if isinstance(d, dict)}
except Exception as e:
    print(f"FAIL: không đọc được Info.plist / PrivacyInfo.xcprivacy của .app: {e}")
    sys.exit(1)
for b in appconfig.PRIVACY_BLOCKS:
    key, sw = b["info_key"], b["switch"]
    flag = info.get(key)
    if flag not in ("YES", "NO"):
        bad.append(f"FAIL: Info.plist {key} là {flag!r} (cần YES|NO) — không đối chiếu được privacy manifest")
        continue
    for t in b["types"]:
        if flag == "YES" and t not in declared:
            bad.append(f"FAIL: privacy manifest THIẾU {t} — {key} = YES (khối {sw} bật)")
        elif flag == "NO" and t in declared:
            bad.append(f"FAIL: privacy manifest còn khai {t} — {key} = NO (khối {sw} tắt)")
print("\n".join(bad))
sys.exit(1 if bad else 0)
' "$REPO_ROOT/tools/common" "$APP" 2>&1)
  GATE7_RC=$?
  if [ "$GATE7_RC" -ne 0 ]; then
    echo "$GATE7_OUT"
    echo "  → chạy python3 tools/common/appconfig.py render (manifest sinh từ AppHost/Config/PrivacyInfo.template.xcprivacy) rồi build lại"
    FAIL=1
  fi
fi

# 9. Orientation vs iPad — App Store Connect từ chối (lỗi 90474) khi app khai hỗ trợ iPad
#    (TARGETED_DEVICE_FAMILY có "2") + thiếu UIRequiresFullScreen + không đủ 4 hướng. Thứ chỉ lộ ra SAU 20 phút
#    archive + upload, trong khi đọc Info.plist mất 0.1s.
FAMILY=$(/usr/libexec/PlistBuddy -c 'Print :UIDeviceFamily' "$APP/Info.plist" 2>/dev/null | tr -d ' \n') || FAMILY=""
case "$FAMILY" in
  *2*)
    FULLSCREEN=$(/usr/libexec/PlistBuddy -c 'Print :UIRequiresFullScreen' "$APP/Info.plist" 2>/dev/null) || FULLSCREEN=""
    # iPad đọc `~ipad` nếu có (iPhone khoá dọc + iPad xoay 4 hướng) — chỉ đọc key chung thì báo FAIL giả.
    ORIENTS=$(/usr/libexec/PlistBuddy -c 'Print :UISupportedInterfaceOrientations~ipad' "$APP/Info.plist" 2>/dev/null) \
      || ORIENTS=$(/usr/libexec/PlistBuddy -c 'Print :UISupportedInterfaceOrientations' "$APP/Info.plist" 2>/dev/null) \
      || ORIENTS=""
    ALL4=1
    for o in Portrait PortraitUpsideDown LandscapeLeft LandscapeRight; do
      echo "$ORIENTS" | grep -q "UIInterfaceOrientation$o" || ALL4=0
    done
    if [ "$FULLSCREEN" != "true" ] && [ "$ALL4" -eq 0 ]; then
      echo "FAIL: app khai iPad (UIDeviceFamily=$FAMILY) nhưng thiếu UIRequiresFullScreen và không đủ 4 hướng"
      echo "      → App Store Connect sẽ từ chối với lỗi 90474. Sửa ở project.yml, không sửa .xcodeproj."
      FAIL=1
    fi
    ;;
esac

# 11. What's New — bản Store không được còn thẻ `.unreleased`. CHỐT CHÍNH là trình biên dịch (case `.unreleased` chỉ có
#     dưới `#if INTERNAL`); mục này là lưới phụ rẻ, báo sớm bằng chữ: `stamp_whats_new.py --check` rc 1 nếu text thô
#     catalog còn chuỗi `unreleased`. Thiếu catalog ⇒ rc 0.
WN_RC=0
python3 "$REPO_ROOT/tools/release/stamp_whats_new.py" --check || WN_RC=$?
case "$WN_RC" in
  0) ;;
  1) echo "FAIL: What's New còn chữ 'unreleased' trong catalog — bump_version.sh chưa đóng dấu?"; FAIL=1 ;;
  *) echo "FAIL: What's New — stamp_whats_new.py --check lỗi lạ rc=$WN_RC (xem lỗi trên)"; FAIL=1 ;;
esac

# 12. String Catalog — bản ship phải chứa ĐÚNG tập chuỗi user thấy, và đủ bản dịch cho mọi ngôn ngữ đã khai ở
#     `[i18n] languages`. Kiểm trên SOURCE (build lại 2 config) chứ không trên .app: catalog trong bundle đã compile
#     thành .strings. `verify_catalog.py` tự bỏ qua khi chỉ có `en`. Bỏ qua bằng SKIP_CATALOG_CHECK=1 khi chỉ muốn
#     soi binary.
if [ "${SKIP_CATALOG_CHECK:-0}" != "1" ]; then
  echo "--- kiểm String Catalog ---"
  if ! python3 "$REPO_ROOT/tools/i18n/lint_localizable.py"; then
    echo "FAIL: lint String Catalog không sạch"
    FAIL=1
  fi
  if ! python3 "$REPO_ROOT/tools/i18n/verify_catalog.py" --check --clean; then
    echo "FAIL: cổng String Catalog không đạt"
    FAIL=1
  fi
fi

# 15. Lõi không lệch template — chỉ ở APP. Viết MỘT lần ở `gate15_kind`, bằng GIT THUẦN (không dựa tool Python mà app
#     có thể đã xoá): repo mà LỊCH SỬ từng có core.lock là APP, kể cả khi file đánh dấu của template đang được track
#     (app gỡ lock rồi thêm file đánh dấu bằng `--no-verify` không thành "template"). Lịch sử chưa từng có lock ⇒ nhận
#     diện DƯƠNG là TEMPLATE khi `new_app.py` của template (thư mục tools/template) được track trong HEAD (HEAD chưa có: trong index) — file lớp
#     template_only, không bao giờ có ở app; MỌI repo khác là APP. Gốc KHÔNG phải repo git (cây xuất ra) ⇒ có file đánh
#     dấu trên đĩa là template, không thì app — in rõ điều đó. Ở app: core.lock phải được TRACK (có trên đĩa mà không
#     track — `git rm --cached` rồi commit `--no-verify` — vẫn FAIL; gốc không phải repo git ⇒ phải có trên đĩa),
#     manifest.py + sync_core.py phải còn (thiếu — kể cả đã bị commit gỡ bằng `--no-verify` — ⇒ FAIL kèm cách khôi
#     phục), rồi mọi file lớp đồng bộ phải giống hệt digest trong core.lock (M/D) và không có file mới track trong thư
#     mục lớp đồng bộ (A) — lưới cuối khi pre-commit bị lách (`--no-verify`, clone chưa đặt core.hooksPath). Soi working tree.
gate15_git() {   # git trên REPO_ROOT với môi trường đã gỡ mọi GIT_* (biến của hook/repo khác không lọt vào)
  ( while IFS= read -r v; do unset "$v"; done < <(compgen -e | grep '^GIT_' || true)
    git --no-optional-locks -C "$REPO_ROOT" "$@" )
}
GATE15_MARKER="tools/template/new_app.py"
gate15_kind() {  # đặt GATE15_KIND = template | app; GATE15_GIT = 1 khi gốc là repo git; GATE15_HISTORY = 1 khi lịch sử từng có lock
  local top
  GATE15_GIT=""
  GATE15_HISTORY=""
  top=$(gate15_git rev-parse --show-toplevel 2>/dev/null) || top=""
  if [ -n "$top" ] && [ "$(cd "$top" && pwd -P)" = "$(cd "$REPO_ROOT" && pwd -P)" ]; then
    GATE15_GIT=1
    if [ -n "$(gate15_git log -1 --full-history --format=%H -- core.lock 2>/dev/null)" ]; then
      GATE15_HISTORY=1
      GATE15_KIND=app
    elif gate15_git rev-parse --verify -q "HEAD^{commit}" >/dev/null 2>&1; then
      if gate15_git cat-file -e "HEAD:$GATE15_MARKER" 2>/dev/null; then GATE15_KIND=template; else GATE15_KIND=app; fi
    elif gate15_git ls-files --error-unmatch -- ":(literal)$GATE15_MARKER" >/dev/null 2>&1; then
      GATE15_KIND=template
    else
      GATE15_KIND=app
    fi
  else
    echo "  cổng 15: gốc không phải repo git — quyết định theo file $GATE15_MARKER trên đĩa"
    if [ -f "$REPO_ROOT/$GATE15_MARKER" ]; then GATE15_KIND=template; else GATE15_KIND=app; fi
  fi
}
gate15_kind
GATE15_MISSING=""
if [ "$GATE15_KIND" = app ]; then
  if [ -n "$GATE15_HISTORY" ]; then GATE15_WHY="lịch sử có core.lock"; else GATE15_WHY="không có $GATE15_MARKER"; fi
  for tool in tools/template/manifest.py tools/template/sync_core.py; do
    if [ ! -f "$REPO_ROOT/$tool" ]; then
      echo "FAIL: đây là app ($GATE15_WHY) nhưng thiếu $tool (file lớp đồng bộ) — khôi phục: git" \
           "restore --staged --worktree $tool, hoặc từ lịch sử (git log --diff-filter=D --oneline -- $tool rồi git checkout" \
           "<commit>^ -- $tool), hoặc đồng bộ lại từ template"
      FAIL=1
      GATE15_MISSING=1
    fi
  done
  GATE15_LOCK_OK=1
  GATE15_LOCK_WHAT="core.lock được track"
  if [ -n "$GATE15_GIT" ]; then
    # Được track = index có mục core.lock (stage 0) MANG NỘI DUNG. Chặt hơn `git ls-files --error-unmatch`: mục của
    # `git add -N` (intent-to-add) cũng hiện ở ls-files nhưng rỗng và không vào commit nào — lock khi đó vẫn chỉ nằm
    # trên đĩa. Không có mục ⇒ cat-file lỗi ⇒ 0.
    [ "$(gate15_git cat-file -s ":core.lock" 2>/dev/null || echo 0)" -gt 0 ] || GATE15_LOCK_OK=""
  else
    GATE15_LOCK_WHAT="core.lock trên đĩa"
    if [ ! -e "$REPO_ROOT/core.lock" ] && [ ! -L "$REPO_ROOT/core.lock" ]; then GATE15_LOCK_OK=""; fi
  fi
  if [ -z "$GATE15_MISSING" ] && [ -z "$GATE15_LOCK_OK" ]; then
    GATE15_LOCK_HELP="khôi phục: git restore --staged --worktree core.lock (vừa gỡ), hoặc từ lịch sử: git log --diff-filter=D --oneline -- core.lock rồi git checkout <commit>^ -- core.lock, hoặc đồng bộ lại từ template"
    if [ -n "$GATE15_GIT" ] && { [ -e "$REPO_ROOT/core.lock" ] || [ -L "$REPO_ROOT/core.lock" ]; }; then
      GATE15_LOCK_HELP="file còn trên đĩa nhưng KHÔNG được track (clone khác sẽ không có nó) — git add core.lock"
    fi
    if [ -n "$GATE15_HISTORY" ]; then
      echo "FAIL: đây là app ($GATE15_WHY) nhưng không có $GATE15_LOCK_WHAT — lock đã bị gỡ; $GATE15_LOCK_HELP"
    else
      # Không có dấu nào: không phân biệt được app mất lock với template mất file đánh dấu ⇒ nêu cả hai.
      echo "FAIL: không có $GATE15_LOCK_WHAT và cũng không có $GATE15_MARKER — một trong hai: (1) đây là APP đã mất" \
           "lock: $GATE15_LOCK_HELP; (2) đây là TEMPLATE mà $GATE15_MARKER đã bị gỡ: khôi phục: git restore --staged" \
           "--worktree $GATE15_MARKER, hoặc từ lịch sử (git log --diff-filter=D --oneline -- $GATE15_MARKER rồi git" \
           "checkout <commit>^ -- $GATE15_MARKER) rồi commit (loại repo xét theo HEAD)"
    fi
    FAIL=1
    GATE15_MISSING=1
  fi
fi
if [ "$GATE15_KIND" = app ] && [ -z "$GATE15_MISSING" ]; then
  SYNC_RC=0
  python3 "$REPO_ROOT/tools/template/sync_core.py" check --root "$REPO_ROOT" || SYNC_RC=$?
  case "$SYNC_RC" in
    0) ;;
    1) echo "FAIL: file lớp đồng bộ lệch core.lock (dòng M/D/A ở trên) — file do template sở hữu: sửa ở template rồi chạy" \
            "tools/template/sync_core.py sync --to <tag>; file mới (A) thì chuyển sang chỗ của app hoặc thêm vào template"
       FAIL=1 ;;
    *) echo "FAIL: core.lock bị gỡ, hỏng hoặc không kiểm được (sync_core.py check rc=$SYNC_RC, xem dòng FAIL: ở trên)"
       FAIL=1 ;;
  esac
elif [ "$GATE15_KIND" = template ]; then
  echo "  cổng 15 (lõi khớp core.lock): BỎ QUA — có tools/template/new_app.py, đây là template (cổng chỉ áp ở app)"
fi

# 16. Site của app — chỉ khi app có web (web.host_prod khác rỗng). App nướng cứng link `/privacy/`, `/terms/`,
#     `/support/`, `/` (Core/Bootstrap/AppConfig.swift; paywall bắt buộc link Điều khoản/Quyền riêng tư — Guideline
#     3.1.2): bản lên Store đòi các trang đó có NỘI DUNG THẬT. `web/tools/check_site.py --release` (đồng bộ) phải xanh:
#     đủ trang bất biến, không còn `TEMPLATE-PLACEHOLDER`, privacy khớp công tắc `[features]`, không dấu khối/biến gieo
#     sót. Site ở NGOÀI repo ⇒ khai `[web] external_site = true`: cổng in `SKIP (web.external_site)` thấy rõ, không đòi
#     công cụ. Không khai mà thiếu `web/site/public/` ⇒ FAIL (check_site.py tự SKIP khi thiếu thư mục — cổng không bao
#     giờ in OK trong trường hợp đó). Có host mà thiếu công cụ ⇒ FAIL.
#     ALLOW_SITE_PLACEHOLDER=1 — CHỈ selfcheck.sh đặt (template + app vừa sinh còn chữ giữ chỗ): chạy KHÔNG `--release`
#     (giữ chỗ hạ thành cảnh báo, các kiểm khác vẫn gác). Như cổng 14: biến chỉ có hiệu lực với `.app` trần; với
#     `.xcarchive` (hiện vật ra bản thật) đặt biến là FAIL. Deploy site prod (`npm run deploy:prod`) chạy cùng cổng.
SITE_TOOL="$REPO_ROOT/web/tools/check_site.py"
SITE_EXTERNAL=$(cfg_get_opt web.external_site)
if [ -z "$HOST_PROD" ]; then
  echo "  cổng 16 (site): BỎ QUA — web.host_prod rỗng (app không có web)"
elif [ "$SITE_EXTERNAL" = "True" ]; then
  echo "  cổng 16 (site): SKIP (web.external_site) — site của app ở ngoài repo; tự bảo đảm https://$HOST_PROD/privacy/," \
       "/terms/, /support/ có nội dung thật trước khi nộp"
elif [ ! -d "$REPO_ROOT/web/site/public" ]; then
  echo "FAIL: cổng 16 — web.host_prod có giá trị nhưng không có web/site/public/ (app nướng cứng /privacy/, /terms/," \
       "/support/) — nhận trang bằng sync_core.py sync --adopt-new-seed, hoặc khai [web] external_site = true nếu site ở ngoài repo"
  FAIL=1
elif [ ! -f "$SITE_TOOL" ]; then
  echo "FAIL: cổng 16 — web.host_prod có giá trị nhưng thiếu web/tools/check_site.py (file lớp đồng bộ) — đồng bộ lại từ template"
  FAIL=1
elif [ "${ALLOW_SITE_PLACEHOLDER:-0}" = "1" ] && [[ "$TARGET" == *.xcarchive ]]; then
  echo "FAIL: cổng 16 — ALLOW_SITE_PLACEHOLDER=1 không áp dụng cho .xcarchive (hiện vật ra bản thật); viết nội dung thật" \
       "cho web/site/public rồi chạy python3 web/tools/check_site.py --release"
  FAIL=1
else
  SITE_FLAGS=(--release)
  if [ "${ALLOW_SITE_PLACEHOLDER:-0}" = "1" ]; then
    SITE_FLAGS=()
    echo "  cổng 16 (site): chữ giữ chỗ chỉ CẢNH BÁO — ALLOW_SITE_PLACEHOLDER=1 (chỉ dành cho tự kiểm của template;" \
         "bản upload KHÔNG BAO GIỜ đặt biến này)"
  fi
  if python3 "$SITE_TOOL" ${SITE_FLAGS[@]+"${SITE_FLAGS[@]}"} --root "$REPO_ROOT"; then
    echo "  cổng 16 (site): OK"
  else
    echo "FAIL: cổng 16 — nội dung site chưa sẵn sàng (dòng FAIL: ở trên) — sửa web/site/public rồi chạy" \
         "python3 web/tools/check_site.py --release"
    FAIL=1
  fi
fi

if [ "$FAIL" -eq 0 ]; then
  echo "PASS: $APP sạch (không symbol debug, bundle id + tên hiển thị đúng, Firebase prod, privacy manifest, paywall, không còn tính năng mẫu, What's New đóng dấu, String Catalog đúng, lõi khớp core.lock, site sẵn sàng)"
  exit 0
fi
echo "--- $APP KHÔNG đạt, KHÔNG upload ---"
exit 1
