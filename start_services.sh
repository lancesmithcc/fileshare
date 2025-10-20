#!/bin/bash
# Start Neo Druidic Society services

cd /home/lanc3lot/neo-druidic-society

# Kill any existing instances
pkill -f "flask run"
pkill -f cloudflared

# Wait a moment
sleep 2

# Start Flask on port 8000 (matches Cloudflare tunnel config)
echo "Starting Flask on port 8000..."
nohup .venv/bin/python -m flask run --host=0.0.0.0 --port=8000 > logs/flask.log 2>&1 &
FLASK_PID=$!
echo "Flask started with PID: $FLASK_PID"

# Wait for Flask to start
sleep 3

# Start Cloudflare tunnel
echo "Starting Cloudflare tunnel..."
nohup cloudflared tunnel run > logs/cloudflared.log 2>&1 &
TUNNEL_PID=$!
echo "Cloudflare tunnel started with PID: $TUNNEL_PID"

echo ""
echo "✅ Services started successfully!"
echo "Flask: http://localhost:8000"
echo "Public: https://www.awen01.cc"
echo ""
echo "To check logs:"
echo "  Flask: tail -f logs/flask.log"
echo "  Cloudflare: tail -f logs/cloudflared.log"
