#!/usr/bin/env bash
# Quick Start Script for Neo-Druidic Society
# Run this after completing Cloudflare tunnel setup

set -euo pipefail

echo "🌿 Neo-Druidic Society - Quick Start"
echo "===================================="
echo ""

# Check if cloudflared is authenticated
if [[ ! -f "$HOME/.cloudflared/cert.pem" ]]; then
    echo "❌ Cloudflare not authenticated yet."
    echo "   Run: cloudflared login"
    echo ""
    exit 1
fi

# Check if tunnel exists
if ! cloudflared tunnel list 2>/dev/null | grep -q "fileshare"; then
    echo "❌ Tunnel 'fileshare' not created yet."
    echo "   Run: cloudflared tunnel create fileshare"
    echo ""
    exit 1
fi

# Check if config is updated
if grep -q "REPLACE_WITH_TUNNEL_ID" "$HOME/.cloudflared/config.yml" 2>/dev/null; then
    echo "❌ Config file not updated yet."
    echo "   Edit: ~/.cloudflared/config.yml"
    echo "   Replace REPLACE_WITH_TUNNEL_ID with your tunnel ID"
    echo ""
    exit 1
fi

echo "✅ All prerequisites met!"
echo ""
echo "Starting services..."
echo ""

cd /home/lanc3lot/neo-druidic-society
./run_fileshare.sh
