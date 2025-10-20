#!/usr/bin/env bash
set -euo pipefail

# Ensure PATH includes user-local bin so cloudflared is found.
export PATH="$HOME/.local/bin:$PATH"

PROJECT_ROOT="/home/lanc3lot/neo-druidic-society"

if [[ ! -f "$PROJECT_ROOT/.venv/bin/activate" ]]; then
  echo "Virtualenv not found at $PROJECT_ROOT/.venv. Run 'python3 -m venv .venv' and reinstall requirements." >&2
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared binary not found. Install it or place it in \$HOME/.local/bin/cloudflared." >&2
  exit 1
fi

# Ensure credentials file path is present in config.
CONFIG_PATH="$HOME/.cloudflared/config.yml"
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Missing Cloudflare config at $CONFIG_PATH. Create it before running." >&2
  exit 1
fi

CREDENTIAL_PATH=$(awk '/credentials-file:/ {print $2}' "$CONFIG_PATH")
if [[ -z "$CREDENTIAL_PATH" || "$CREDENTIAL_PATH" == *"REPLACE_WITH_TUNNEL_ID"* ]]; then
  echo "Update credentials-file in $CONFIG_PATH with the JSON from 'cloudflared tunnel create'." >&2
  exit 1
fi

if [[ ! -f "$CREDENTIAL_PATH" ]]; then
  echo "Credentials file '$CREDENTIAL_PATH' not found. Run 'cloudflared login' and 'cloudflared tunnel create fileshare' on this machine." >&2
  exit 1
fi

# Ensure origin cert is present (created by cloudflared login).
if [[ ! -f "$HOME/.cloudflared/cert.pem" ]]; then
  echo "Origin certificate missing at ~/.cloudflared/cert.pem. Run 'cloudflared login' to generate it." >&2
  exit 1
fi

# Replace this with your actual tunnel name if it differs.
TUNNEL_NAME="${TUNNEL_NAME:-fileshare}"

source "$PROJECT_ROOT/.venv/bin/activate"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$PROJECT_ROOT/.env"
  set +a
fi

export FLASK_APP="${FLASK_APP:-main.py}"
export FLASK_RUN_HOST="${FLASK_RUN_HOST:-0.0.0.0}"
export FLASK_RUN_PORT="${FLASK_RUN_PORT:-8000}"
export NEO_DRUIDIC_URL_SCHEME="${NEO_DRUIDIC_URL_SCHEME:-https}"

cd "$PROJECT_ROOT"

echo "Starting Flask app on ${FLASK_RUN_HOST}:${FLASK_RUN_PORT}..."
flask run &
FLASK_PID=$!

cleanup() {
  echo "Shutting down..."
  kill "$FLASK_PID" 2>/dev/null || true
  if [[ -n "${TUNNEL_PID:-}" ]]; then
    kill "$TUNNEL_PID" 2>/dev/null || true
  fi
}

trap cleanup INT TERM

echo "Starting cloudflared tunnel '${TUNNEL_NAME}'..."
cloudflared tunnel run "$TUNNEL_NAME" &
TUNNEL_PID=$!

wait "$FLASK_PID"
wait "$TUNNEL_PID"
