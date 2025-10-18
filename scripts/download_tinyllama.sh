#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODEL_DIR="$PROJECT_ROOT/models"
MODEL_FILE="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"
MODEL_URL="https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/${MODEL_FILE}?download=1"

mkdir -p "$MODEL_DIR"

if [[ -s "$MODEL_PATH" ]]; then
  echo "✅ TinyLlama already present at $MODEL_PATH"
  exit 0
fi

if [[ -f "$MODEL_PATH" ]]; then
  echo "⚠️  Found an empty file at $MODEL_PATH — removing and re-downloading."
  rm -f "$MODEL_PATH"
fi

echo "⬇️  Downloading TinyLlama GGUF (~620 MB) to $MODEL_PATH"
curl -L --fail --progress-bar "$MODEL_URL" -o "$MODEL_PATH"

echo "✅ TinyLlama download complete."
