#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MODELS_DIR="$PROJECT_ROOT/models"
MODEL_FILE="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
MODEL_PATH="$MODELS_DIR/$MODEL_FILE"

# HuggingFace URL for TinyLlama 1.1B Chat Q4_K_M quantization
MODEL_URL="https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"

echo "=== TinyLlama Model Download ==="
echo "Target: $MODEL_PATH"

# Create models directory if it doesn't exist
mkdir -p "$MODELS_DIR"

# Check if model already exists
if [ -f "$MODEL_PATH" ]; then
    echo "✓ Model already exists at $MODEL_PATH"
    echo "  Size: $(du -h "$MODEL_PATH" | cut -f1)"
    exit 0
fi

echo "Downloading TinyLlama 1.1B Chat (Q4_K_M, ~620 MB)..."
echo "From: $MODEL_URL"
echo ""

# Download with curl (with resume support and progress bar)
if command -v curl &> /dev/null; then
    curl -L -C - --progress-bar -o "$MODEL_PATH" "$MODEL_URL"
elif command -v wget &> /dev/null; then
    wget -c --show-progress -O "$MODEL_PATH" "$MODEL_URL"
else
    echo "Error: Neither curl nor wget found. Please install one of them."
    exit 1
fi

echo ""
echo "✓ Download complete!"
echo "  Model saved to: $MODEL_PATH"
echo "  Size: $(du -h "$MODEL_PATH" | cut -f1)"
echo ""
echo "Verifying file integrity..."
if [ -f "$MODEL_PATH" ] && [ -s "$MODEL_PATH" ]; then
    echo "✓ File exists and is not empty"
else
    echo "✗ Error: File is missing or empty"
    exit 1
fi

echo ""
echo "Next steps:"
echo "  1. Install llama-cpp-python:"
echo "     pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu"
echo "  2. Start the Flask app: ./run_fileshare.sh"
