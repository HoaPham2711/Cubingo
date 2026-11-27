#!/usr/bin/env bash
# Sinh lại bảng tra của bộ giải hai pha ⇒ AppHost/AppHost/Features/Solver/Resources/kociemba-tables.bin.
# Chỉ cần chạy khi đổi toạ độ/định dạng bảng (README cùng thư mục).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SRC="$ROOT/AppHost/AppHost/Features"
OUT="$ROOT/AppHost/AppHost/Features/Solver/Resources/kociemba-tables.bin"
BUILD="${TMPDIR:-/tmp}/cubingo-kociemba-gen"
mkdir -p "$BUILD" "$(dirname "$OUT")"
swiftc -O -o "$BUILD/gen" \
  "$SRC/Cube/CubeFace.swift" "$SRC/Cube/CubeMove.swift" "$SRC/Cube/CubeGeometry.swift" \
  "$SRC/Cube/CubeFacelets.swift" "$SRC/Cube/CubeCubies.swift" \
  "$SRC/Solver/SolverKociembaCoords.swift" "$SRC/Solver/SolverKociembaTables.swift" \
  "$ROOT/tools/app/kociemba/main.swift"
"$BUILD/gen" "$OUT"
