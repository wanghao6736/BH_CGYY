#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC_PNG="${1:-$ROOT_DIR/src/ui/resources/app_icon.png}"
OUT_DIR="${2:-$ROOT_DIR/src/ui/resources}"
BASENAME="${3:-app_icon}"

if [ ! -f "$SRC_PNG" ]; then
  echo "Source PNG not found: $SRC_PNG" >&2
  echo "Usage: $0 [source.png] [output_dir] [basename]" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

ICONSET_DIR="$OUT_DIR/${BASENAME}.iconset"
ICNS_PATH="$OUT_DIR/${BASENAME}.icns"
ICO_PATH="$OUT_DIR/${BASENAME}.ico"

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

# Build all required iconset sizes for macOS icns.
sips -z 16 16 "$SRC_PNG" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
sips -z 32 32 "$SRC_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "$SRC_PNG" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
sips -z 64 64 "$SRC_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "$SRC_PNG" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
sips -z 256 256 "$SRC_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "$SRC_PNG" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
sips -z 512 512 "$SRC_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "$SRC_PNG" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
cp "$SRC_PNG" "$ICONSET_DIR/icon_512x512@2x.png"

iconutil -c icns "$ICONSET_DIR" -o "$ICNS_PATH"
rm -rf "$ICONSET_DIR"

# Optional: produce ICO if ImageMagick is available.
if command -v magick >/dev/null 2>&1; then
  magick "$SRC_PNG" -define icon:auto-resize=16,24,32,48,64,128,256 "$ICO_PATH"
elif command -v convert >/dev/null 2>&1; then
  convert "$SRC_PNG" -define icon:auto-resize=16,24,32,48,64,128,256 "$ICO_PATH"
fi

echo "Generated macOS icon: $ICNS_PATH"
if [ -f "$ICO_PATH" ]; then
  echo "Generated Windows icon: $ICO_PATH"
fi
