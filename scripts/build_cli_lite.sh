#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${CGYY_NUITKA_MODE:-onefile}"
OUTPUT_DIR="$ROOT_DIR/dist/nuitka"
BUILD_DIR="$OUTPUT_DIR/main_lite.build"
DIST_DIR="$OUTPUT_DIR/main_lite.dist"
ONEFILE_BUILD_DIR="$OUTPUT_DIR/main_lite.onefile-build"
cd "$ROOT_DIR"

uv sync --group build

uv run --group build python -m nuitka src/main_lite.py \
  --mode="$MODE" \
  --output-dir="$OUTPUT_DIR" \
  --output-filename=cgyy-lite \
  --python-flag=no_docstrings \
  --python-flag=no_site \
  --nofollow-import-to=ddddocr,cv2,PIL,numpy,onnxruntime,PySide6 \
  "$@"

cp "$ROOT_DIR/.env.example" "$OUTPUT_DIR/.env"

rm -rf "$BUILD_DIR"
if [ "$MODE" = "onefile" ]; then
  rm -rf "$DIST_DIR" "$ONEFILE_BUILD_DIR"
fi
