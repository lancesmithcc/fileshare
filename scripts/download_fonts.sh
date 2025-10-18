#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FONT_DIR="$PROJECT_ROOT/app/static/fonts"
FONT_FILE="Jost-Variable.ttf"
FONT_URL="https://raw.githubusercontent.com/google/fonts/main/ofl/jost/Jost%5Bwght%5D.ttf"

mkdir -p "$FONT_DIR"
TARGET="$FONT_DIR/$FONT_FILE"

if [[ -s "$TARGET" ]]; then
  echo "✅ Font already present at $TARGET"
  exit 0
fi

if [[ -f "$TARGET" ]]; then
  echo "⚠️  Found an empty font file at $TARGET — removing before re-download."
  rm -f "$TARGET"
fi

echo "⬇️  Downloading Jost variable font to $TARGET"
curl -L --fail --progress-bar "$FONT_URL" -o "$TARGET"

echo "✅ Font download complete."
