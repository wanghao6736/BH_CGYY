#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/dist/nuitka"
TARGET_APP="$OUTPUT_DIR/cgyy-ui.app"
BUILD_APP="$OUTPUT_DIR/main.app"
BACKUP_APP="$OUTPUT_DIR/.cgyy-ui.app.old"
BUILD_DIR="$OUTPUT_DIR/main.build"
DIST_DIR="$OUTPUT_DIR/main.dist"
cd "$ROOT_DIR"

uv sync --group build --extra ocr --extra ui

uv run --group build --extra ocr --extra ui python -m nuitka src/ui/main.py \
  --mode=app \
  --output-dir="$OUTPUT_DIR" \
  --output-filename=cgyy-ui \
  --macos-app-name=cgyy-ui \
  --macos-app-icon="$ROOT_DIR/src/ui/resources/app_icon.icns" \
  --enable-plugin=pyside6 \
  --include-package-data=src.ui.styles \
  --include-package-data=src.ui.resources \
  --python-flag=no_docstrings \
  --python-flag=no_site \
  "$@"

if [ -d "$BUILD_APP" ]; then
  if [ -e "$BACKUP_APP" ]; then
    rm -rf "$BACKUP_APP"
  fi

  if [ -d "$TARGET_APP" ]; then
    mv "$TARGET_APP" "$BACKUP_APP"
  fi

  mv "$BUILD_APP" "$TARGET_APP"
  rm -rf "$BACKUP_APP"
fi

cp "$ROOT_DIR/.env.example" "$OUTPUT_DIR/.env"
rm -rf "$BUILD_DIR" "$DIST_DIR"
