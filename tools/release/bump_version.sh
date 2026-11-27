#!/bin/bash
# Bump [version] trong app.config.toml (rồi sinh lại Identity.xcconfig), ghi CHANGELOG.md, tạo commit + tag release.
#
# Chạy trên nhánh `main` sau khi đã merge `develop` vào (xem docs/RELEASE.md):
#
#   ./tools/release/bump_version.sh <major|minor|patch> [--force|--dry-run]
#
# --dry-run: in việc sẽ làm (version mới, tag, đóng dấu What's New), KHÔNG sửa file/commit/tag.
# Bump cũng đóng dấu thẻ What's New (`.unreleased` -> `.released("X.Y.Z")`) vào CÙNG commit bump. Chốt thật
# chống ship thẻ chưa đóng dấu là trình biên dịch (case chỉ có dưới `#if INTERNAL`); bước đóng dấu ở đây để
# archive Release biên dịch được.
#
# Hoàn tác: mọi lần thoát lỗi (ERR, INT, TERM, HUP) sau lần ghi đầu ⇒ hoàn tác rồi KIỂM hậu điều kiện thật (5 file y
# byte bản gốc [app.config.toml, Identity.xcconfig, Features.generated.yml, catalog What's New, CHANGELOG], HEAD cũ, index == HEAD cũ, tag mới không tồn tại). Chỉ in "đã hoàn tác" khi cả bốn đúng; sai
# bất kỳ ⇒ "KHÔNG hoàn tác được: …" + thư mục giữ bản gốc. Commit đi qua index TẠM (GIT_INDEX_FILE) nên index
# thật chỉ bị đụng ở bước cuối cùng (đồng bộ về HEAD mới) — `.git/index.lock` xuất hiện giữa chừng không làm
# index thật lệch.
#
# Rồi: git push origin main --tags && git checkout develop && git merge main && git push
set -Eeuo pipefail

BUMP="${1:-}"
shift || true
FORCE=""
DRY_RUN=0
for ARG in "$@"; do
  case "$ARG" in
    --force) FORCE="--force" ;;
    --dry-run) DRY_RUN=1 ;;
    *) echo "FAIL: đối số lạ '$ARG'" >&2; BAD_ARG=1 ;;
  esac
done

if [[ "$BUMP" != "major" && "$BUMP" != "minor" && "$BUMP" != "patch" || "${BAD_ARG:-0}" == "1" ]]; then
  echo "dùng: $0 <major|minor|patch> [--force|--dry-run]" >&2
  exit 2
fi

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$BRANCH" != "main" && "$BRANCH" != hotfix/* && "$FORCE" != "--force" ]]; then
  echo "FAIL: đang ở nhánh '$BRANCH', không phải 'main' hoặc 'hotfix/*'. Dùng --force nếu chắc chắn." >&2
  exit 1
fi

# Gán riêng (không nhúng trong `[[ … ]]`): git status lỗi ⇒ set -e dừng, không coi output rỗng là "sạch".
STATUS=$(git status --porcelain)
if [[ -n "$STATUS" ]]; then
  echo "FAIL: working tree không sạch — commit hoặc stash trước khi bump version." >&2
  exit 1
fi

# Bố cục repo (đường dẫn file) lấy từ appconfig — một nguồn; lỗi ⇒ set -e dừng (không đoán đường dẫn).
APPCONFIG="tools/common/appconfig.py"
[[ -f "$APPCONFIG" ]] || { echo "FAIL: không thấy $APPCONFIG" >&2; exit 1; }
layout() { python3 -c 'import sys; sys.path.insert(0, "tools/common"); import appconfig; print(getattr(appconfig, sys.argv[1]))' "$1"; }
CONFIG=$(layout CONFIG_FILE)
XCCONFIG=$(layout XCCONFIG)
FEATURES_YML=$(layout FEATURES_YML)
WHATS_NEW_CATALOG=$(layout WHATS_NEW_CATALOG)
[[ -f "$CONFIG" ]] || { echo "FAIL: không thấy $CONFIG" >&2; exit 1; }
[[ -f "$XCCONFIG" ]] || { echo "FAIL: không thấy $XCCONFIG" >&2; exit 1; }

# `get` đọc + kiểm toàn bộ app.config.toml; config hỏng ⇒ in "FAIL: …" rồi set -e dừng.
CUR_SHORT=$(python3 "$APPCONFIG" get version.marketing)
CUR_BUILD=$(python3 "$APPCONFIG" get version.build)

if [[ ! "$CUR_SHORT" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  echo "FAIL: CFBundleShortVersionString '$CUR_SHORT' không phải dạng X.Y.Z" >&2
  exit 1
fi
MAJOR="${BASH_REMATCH[1]}"
MINOR="${BASH_REMATCH[2]}"
PATCH="${BASH_REMATCH[3]}"

case "$BUMP" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
esac

NEW_SHORT="${MAJOR}.${MINOR}.${PATCH}"
NEW_BUILD=$((CUR_BUILD + 1))
TAG="v${NEW_SHORT}"

# for-each-ref: chỉ xét refs/tags (không nhầm nhánh trùng tên) và git lỗi ⇒ set -e dừng (không coi là "chưa có").
# Rollback XOÁ tag $TAG nên điều kiện "trước đó chưa có" phải chắc chắn.
EXISTING_TAG=$(git for-each-ref --format='%(refname)' "refs/tags/$TAG")
if [[ -n "$EXISTING_TAG" ]]; then
  echo "FAIL: tag $TAG đã tồn tại" >&2
  exit 1
fi

STAMP="tools/release/stamp_whats_new.py"
CHANGELOG="CHANGELOG.md"

# ---- PREFLIGHT: kiểm MỌI điều kiện trước khi ghi bất kỳ file nào (kể cả --dry-run) ----
# sed phía dưới chỉ thay được dạng `khoá = "giá trị"` trong mục [version]; dạng khác (nháy đơn, inline table…) mà
# appconfig vẫn đọc được ⇒ dừng ở đây thay vì để bump ghi hụt.
for KEY in marketing build; do
  if [[ $(sed -n '/^\[version\]/,/^\[/p' "$CONFIG" | grep -cE "^$KEY = \"[^\"]*\"$") -ne 1 ]]; then
    echo "FAIL: $CONFIG mục [version] phải có đúng một dòng '$KEY = \"…\"'" >&2
    exit 1
  fi
done
[[ ! -e "$CHANGELOG" || -w "$CHANGELOG" ]] || { echo "FAIL: $CHANGELOG không ghi được" >&2; exit 1; }
[[ -w "$CONFIG" && -w "$XCCONFIG" ]] || { echo "FAIL: $CONFIG/$XCCONFIG không ghi được" >&2; exit 1; }
# index.lock còn sót (git khác đang chạy / chết giữa chừng) ⇒ bước đồng bộ index cuối sẽ fail.
INDEX_LOCK=$(git rev-parse --git-path index.lock)
[[ ! -e "$INDEX_LOCK" ]] || { echo "FAIL: có $INDEX_LOCK — git khác đang chạy? Xoá nếu chắc chắn không, rồi chạy lại." >&2; exit 1; }
OLD_HEAD=$(git rev-parse --verify HEAD)
HAS_CATALOG=0
if [[ -f "$WHATS_NEW_CATALOG" ]]; then
  HAS_CATALOG=1
  # Có catalog mà thiếu script ⇒ không đóng dấu được ⇒ commit bump sẽ mang thẻ chưa đóng dấu (và archive Release
  # lỗi biên dịch). Dừng TRƯỚC khi ghi — không âm thầm bỏ qua.
  [[ -f "$STAMP" ]] || { echo "FAIL: có $WHATS_NEW_CATALOG nhưng thiếu $STAMP — không đóng dấu What's New được; chưa sửa file nào." >&2; exit 1; }
  # --dry-run của stamp chạy đủ mọi kiểm (dạng không tự thay được ⇒ 3) mà không ghi file.
  python3 "$STAMP" --version "$NEW_SHORT" --dry-run >/dev/null 2>&1 || {
    echo "FAIL: đóng dấu What's New $NEW_SHORT không thực hiện được; chưa sửa file nào:" >&2
    python3 "$STAMP" --version "$NEW_SHORT" --dry-run >&2 || true
    exit 1
  }
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] ${CUR_SHORT} (build ${CUR_BUILD}) → ${NEW_SHORT} (build ${NEW_BUILD}), tag ${TAG}"
  echo "[dry-run] sẽ sửa $CONFIG, $XCCONFIG, $FEATURES_YML, $CHANGELOG"
  if [[ "$HAS_CATALOG" -eq 1 ]]; then
    COUNT=$(python3 "$STAMP" --count) || { echo "FAIL: [dry-run] không đếm được chữ unreleased trong $WHATS_NEW_CATALOG" >&2; exit 1; }
    echo "[dry-run] sẽ đóng dấu What's New $NEW_SHORT trong $WHATS_NEW_CATALOG (hiện: $COUNT chỗ unreleased)"
  else
    echo "[dry-run] không có catalog What's New — bỏ qua đóng dấu"
  fi
  echo "[dry-run] không sửa file, không commit, không tag."
  exit 0
fi

# ---- Từ đây là ghi. Ảnh chụp TRƯỚC lần ghi đầu: bản gốc 5 file (rollback chép ngược bằng `cp` — không cần git,
# `git checkout` fail khi index.lock kẹt) + OLD_HEAD (ở trên) + "tag chưa có" (ở trên) + index == OLD_HEAD (cây
# sạch ở trên ⇒ đúng). ----
BACKUP=$(mktemp -d "${TMPDIR:-/tmp}/bump_version.XXXXXX")
TMP_INDEX="$BACKUP/index"
# Features.generated.yml: `render` sinh lại nó (nội dung phụ thuộc công tắc trong config), nên nằm trong danh sách hoàn tác.
TRACKED_FILES=("$CONFIG" "$XCCONFIG" "$FEATURES_YML" "$WHATS_NEW_CATALOG" "$CHANGELOG")
for i in "${!TRACKED_FILES[@]}"; do
  if [[ -e "${TRACKED_FILES[$i]}" ]]; then cp -p "${TRACKED_FILES[$i]}" "$BACKUP/$i"; fi
done

# Hậu điều kiện: in danh sách cái SAI (rỗng = đúng hết). Lệnh git lỗi ⇒ tính là sai (không bao giờ đoán là đúng).
postcondition_failures() {
  local i F H T
  for i in "${!TRACKED_FILES[@]}"; do
    F="${TRACKED_FILES[$i]}"
    if [[ -e "$BACKUP/$i" ]]; then
      cmp -s "$BACKUP/$i" "$F" || echo "file $F"
    else
      [[ ! -e "$F" ]] || echo "file $F (trước đó không có)"
    fi
  done
  H=$(git rev-parse --verify HEAD 2>/dev/null) || H=""
  [[ "$H" == "$OLD_HEAD" ]] || echo "HEAD (phải về $OLD_HEAD, đang ${H:-?})"
  git diff --cached --quiet "$OLD_HEAD" -- 2>/dev/null || echo "index (còn stage khác $OLD_HEAD)"
  if T=$(git for-each-ref --format='%(refname)' "refs/tags/$TAG" 2>/dev/null); then
    [[ -z "$T" ]] || echo "tag $TAG (vẫn tồn tại)"
  else
    echo "tag $TAG (không đọc được refs)"
  fi
}

ROLLING_BACK=0
rollback() {
  local why="$1" code="$2"
  set +e
  trap - ERR
  trap '' INT TERM HUP   # đang hoàn tác: bỏ qua tín hiệu (git con kế thừa SIG_IGN) — không cho cắt ngang giữa chừng
  [[ "$ROLLING_BACK" -eq 0 ]] || exit "$code"
  ROLLING_BACK=1
  echo "FAIL: bump dừng giữa chừng ($why) — đang hoàn tác." >&2
  local i F H
  # Tag chắc chắn do bump tạo (preflight xác nhận chưa có) ⇒ xoá được.
  if [[ -n "$(git for-each-ref --format=x "refs/tags/$TAG" 2>/dev/null)" ]]; then
    git tag -d "$TAG" >/dev/null 2>&1
  fi
  H=$(git rev-parse --verify HEAD 2>/dev/null)
  # update-ref không cần index.lock (khác `git reset`).
  [[ "$H" == "$OLD_HEAD" ]] || git update-ref -m "bump_version: hoàn tác" HEAD "$OLD_HEAD" >/dev/null 2>&1
  # Index thật chỉ đổi ở bước đồng bộ cuối; nếu lệch thì đưa về OLD_HEAD (cần index.lock — kẹt thì fail, hậu
  # điều kiện bắt).
  git diff --cached --quiet "$OLD_HEAD" -- 2>/dev/null || git reset -q "$OLD_HEAD" -- . >/dev/null 2>&1
  rm -f "${CHANGELOG}.tmp"
  for i in "${!TRACKED_FILES[@]}"; do
    F="${TRACKED_FILES[$i]}"
    if [[ -e "$BACKUP/$i" ]]; then
      cmp -s "$BACKUP/$i" "$F" 2>/dev/null || cp -p "$BACKUP/$i" "$F" 2>/dev/null
    else
      rm -f "$F" 2>/dev/null
    fi
  done
  rm -f "$TMP_INDEX" "$TMP_INDEX.lock"
  local BAD
  BAD=$(postcondition_failures)
  if [[ -n "$BAD" ]]; then
    echo "FAIL: KHÔNG hoàn tác được: $(echo "$BAD" | paste -sd ';' -) — bản gốc ở $BACKUP (0=app.config.toml 1=Identity.xcconfig 2=Features.generated.yml 3=catalog 4=CHANGELOG), HEAD cũ $OLD_HEAD." >&2
  else
    rm -rf "$BACKUP"
    echo "FAIL: đã hoàn tác — app.config.toml, Identity.xcconfig, Features.generated.yml, catalog, CHANGELOG, HEAD, index và tag về nguyên trạng." >&2
  fi
  exit "$code"
}
trap 'rollback "lỗi lệnh dòng $LINENO" 1' ERR
trap 'rollback "SIGINT" 130' INT
trap 'rollback "SIGTERM" 143' TERM
trap 'rollback "SIGHUP" 129' HUP   # đóng terminal

# Đóng dấu thẻ What's New (spec D12).
if [[ "$HAS_CATALOG" -eq 1 ]]; then
  python3 "$STAMP" --version "$NEW_SHORT"
fi

# Ghi version vào [version] của app.config.toml (nguồn duy nhất), rồi sinh lại xcconfig từ nó.
sed -i '' -E \
  -e "/^\[version\]/,/^\[/ s/^marketing = \"[^\"]*\"$/marketing = \"$NEW_SHORT\"/" \
  -e "/^\[version\]/,/^\[/ s/^build = \"[^\"]*\"$/build = \"$NEW_BUILD\"/" \
  "$CONFIG"
python3 "$APPCONFIG" render >/dev/null

LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || true)
if [[ -n "$LAST_TAG" ]]; then
  LOG_RANGE="${LAST_TAG}..HEAD"
else
  LOG_RANGE="HEAD"
fi
LOG_ENTRIES=$(git log "$LOG_RANGE" --no-merges --pretty=format:'- %s' 2>/dev/null || true)
[[ -n "$LOG_ENTRIES" ]] || LOG_ENTRIES="- (không có commit mới so với $LAST_TAG)"

[[ -f "$CHANGELOG" ]] || printf '# Changelog\n\n' > "$CHANGELOG"

TODAY=$(date +%Y-%m-%d)
{
  head -2 "$CHANGELOG"
  printf '## %s — %s\n\n%s\n\n' "$TAG" "$TODAY" "$LOG_ENTRIES"
  tail -n +3 "$CHANGELOG"
} > "${CHANGELOG}.tmp"
mv "${CHANGELOG}.tmp" "$CHANGELOG"

# Commit qua index TẠM: index thật (.git/index) không bị stage gì cho tới bước đồng bộ cuối. Hook pre-commit vẫn
# chạy (thấy GIT_INDEX_FILE tạm qua env).
ADD_PATHS=("$CONFIG" "$XCCONFIG" "$FEATURES_YML" "$CHANGELOG")
[[ "$HAS_CATALOG" -eq 0 ]] || ADD_PATHS+=("$WHATS_NEW_CATALOG")
GIT_INDEX_FILE="$TMP_INDEX" git read-tree "$OLD_HEAD"
GIT_INDEX_FILE="$TMP_INDEX" git add -- "${ADD_PATHS[@]}"
GIT_INDEX_FILE="$TMP_INDEX" git commit -q -m "chore(release): bump version to ${NEW_SHORT} (build ${NEW_BUILD})"
git tag -a "$TAG" -m "$TAG"
# Đồng bộ index thật về HEAD mới (bước DUY NHẤT cần .git/index.lock).
git reset -q
trap - ERR INT TERM HUP
rm -rf "$BACKUP"

echo ""
echo "Đã bump ${CUR_SHORT} (build ${CUR_BUILD}) → ${NEW_SHORT} (build ${NEW_BUILD}), tag ${TAG}."
echo "Bước tiếp theo:"
echo "  git push origin ${BRANCH} --tags"
echo "  git checkout develop && git merge ${BRANCH} && git push"
