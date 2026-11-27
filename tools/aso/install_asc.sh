#!/usr/bin/env bash
# Cài CLI `asc` đúng version ghim trong ASC_VERSION, có kiểm SHA-256: với file checksums của release
# VÀ (nếu không rỗng) với giá trị ghim trong ASC_SHA256.
# Tải từ GitHub release rorkai/App-Store-Connect-CLI (không dùng brew vì không ghim được).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VER="$(tr -d '[:space:]' < "$HERE/ASC_VERSION")"
BASE="https://github.com/rorkai/App-Store-Connect-CLI/releases/download/${VER}"
ASSET="asc_${VER}_macOS_arm64"
SUMS="asc_${VER}_checksums.txt"
# Một bản cho cả máy, dùng chung mọi app (khớp appconfig.shared_bin_dir() + asc_cli.asc_bin()).
DEST_DIR="${IOS_APP_FACTORY_BIN:-$HOME/.local/share/ios-app-factory}/asc/${VER}"

if [ "$(uname -m)" != "arm64" ]; then
  echo "Lỗi: script chỉ hỗ trợ macOS arm64 (máy này: $(uname -m))." >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -fsSL -o "$TMP/$ASSET" "$BASE/$ASSET"
curl -fsSL -o "$TMP/$SUMS" "$BASE/$SUMS"

EXPECTED="$(awk -v n="$ASSET" '$2==n || $2=="*"n {print $1; exit}' "$TMP/$SUMS")"
if [ -z "$EXPECTED" ]; then
  echo "Lỗi: không thấy $ASSET trong $SUMS." >&2
  exit 1
fi
ACTUAL="$(shasum -a 256 "$TMP/$ASSET" | awk '{print $1}')"
if [ "$EXPECTED" != "$ACTUAL" ]; then
  echo "Lỗi: SHA-256 không khớp (cần $EXPECTED, nhận $ACTUAL)." >&2
  exit 1
fi

PIN="$(tr -d '[:space:]' < "$HERE/ASC_SHA256" 2>/dev/null | tr 'A-F' 'a-f' || true)"
if [ -n "$PIN" ]; then
  if [ "$PIN" != "$ACTUAL" ]; then
    echo "Lỗi: SHA-256 khác giá trị ghim trong tools/aso/ASC_SHA256 (ghim $PIN, nhận $ACTUAL)." >&2
    exit 1
  fi
else
  echo "SHA-256 của $ASSET: $ACTUAL"
  echo "Chưa ghim: ghi giá trị này vào tools/aso/ASC_SHA256 sau khi user xác nhận."
fi

mkdir -p "$DEST_DIR"
install -m 755 "$TMP/$ASSET" "$DEST_DIR/asc"
# Chạy `version` với env sạch như asc_cli: bỏ mọi ASC_*, tắt telemetry.
(
  for v in $(compgen -e); do
    case "$v" in ASC_*) unset "$v" ;; esac
  done
  export ASC_TELEMETRY_DISABLED=1 DO_NOT_TRACK=1
  "$DEST_DIR/asc" version
)
