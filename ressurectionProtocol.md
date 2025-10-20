
# Resurrection Protocol — Neo Druidic Society

**Site URL:** https://awen01.cc (and https://www.awen01.cc)

Purpose: step-by-step, AI- and human-readable instructions to bring the site back online if it goes down. Follow these steps in order. Each step includes exact commands where applicable and checks to confirm success.

Format contract (short):
- Inputs: access to the server (SSH), project root at /home/lanc3lot/neo-druidic-society, ability to run shell commands.
- Outputs: running Flask process on port 8000 and active Cloudflare Tunnel exposing the app at https://awen01.cc, logs showing successful start.
- Error modes: missing cloudflared binary, missing cloudflared credentials/config, missing virtualenv or dependencies, Flask runtime errors, port mismatch (must be 8000).

High level steps (quick):
1) Check process and logs
2) Verify cloudflared and tunnel credentials
3) Verify Python virtualenv and env vars
4) Start services using start_services.sh (NEW - replaces run_fileshare.sh)
5) Verify site is accessible at https://awen01.cc
6) Troubleshoot common errors

**CRITICAL:** Flask MUST run on port 8000 to match Cloudflare tunnel configuration!

Detailed steps

1) Check current status

- Confirm whether the Flask app or cloudflared are running and inspect logs:
  - ps and grepping for cloudflared and flask:
    ps aux | grep -E "(cloudflared|flask)" | grep -v grep
  - Tail the tunnel and application logs that live in project `logs/`:
    tail -n 50 logs/cloudflared.log
    tail -n 50 logs/flask.log
    tail -n 50 logs/application.log

  Expected: `cloudflared.log` shows recent tunnel connection messages; `flask.log` shows Flask startup on port 8000; `application.log` shows app startup messages. If logs are absent or show errors, proceed to step 2 and 3.

2) Verify cloudflared installation and credentials

- Check cloudflared binary:
  - command -v cloudflared || echo "cloudflared not found"

- Check Cloudflare config file:
  - CONFIG_PATH="$HOME/.cloudflared/config.yml"
  - Verify it exists and contains the correct tunnel configuration:
    cat "$HOME/.cloudflared/config.yml"
  
  Expected config for awen01.cc:
    tunnel: de0f30f9-0b1f-4812-871f-039334db8833
    credentials-file: /home/lanc3lot/.cloudflared/de0f30f9-0b1f-4812-871f-039334db8833.json
    ingress:
      - hostname: awen01.cc
        service: http://localhost:8000
      - hostname: www.awen01.cc
        service: http://localhost:8000
      - service: http_status:404

- Check credentials file exists:
  - ls -l $HOME/.cloudflared/*.json
  - Verify the tunnel ID matches the config

- If credentials or config are missing:
  - Contact the tunnel owner or restore from backup
  - The tunnel is already created and configured for awen01.cc

3) Verify Python virtualenv and environment variables

- Ensure project virtualenv exists and dependencies are installed:
  - cd /home/lanc3lot/neo-druidic-society
  - test -f .venv/bin/activate || (python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt)

- Ensure `.env` (project root) contains required runtime vars. Important keys referenced in `app/config.py`:
  - FLASK_APP=main.py
  - NEO_DRUIDIC_DATABASE_URI (PostgreSQL connection string)
  - NEO_DRUIDIC_SECRET_KEY
  - SOLANA_PRIVATE_KEY (for NEOD token operations)
  - SOLANA_WALLET_ADDRESS
  - SOLANA_RPC_URL (e.g., Helius RPC)
  - NEOD_MINT_ADDRESS
  - NEO_DRUIDIC_MODEL_PATH (for AI features)

- Verify .env exists:
  - test -f .env && echo "✅ .env exists" || echo "❌ .env missing"

4) Start the application using the startup script

**QUICK START (recommended):**
  ```bash
  cd /home/lanc3lot/neo-druidic-society
  ./start_services.sh
  ```

This script will:
- Kill any existing Flask/cloudflared processes
- Start Flask on port 8000 (CRITICAL - must match Cloudflare tunnel config)
- Start Cloudflare tunnel
- Show you the PIDs and log locations

**Manual start (if script fails):**
  ```bash
  cd /home/lanc3lot/neo-druidic-society
  
  # Start Flask on port 8000
  nohup .venv/bin/python -m flask run --host=0.0.0.0 --port=8000 > logs/flask.log 2>&1 &
  
  # Start Cloudflare tunnel
  nohup cloudflared tunnel run > logs/cloudflared.log 2>&1 &
  ```

**For persistent service (systemd):**
  - Example systemd unit (create `/etc/systemd/system/neo-druidic.service`):
    ```ini
    [Unit]
    Description=Neo Druidic Society (Flask + cloudflared)
    After=network.target

    [Service]
    User=lanc3lot
    WorkingDirectory=/home/lanc3lot/neo-druidic-society
    ExecStart=/home/lanc3lot/neo-druidic-society/start_services.sh
    Restart=on-failure
    Environment=PATH=/home/lanc3lot/.local/bin:/home/lanc3lot/neo-druidic-society/.venv/bin:/usr/bin:/bin

    [Install]
    WantedBy=multi-user.target
    ```

  - Then: 
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable --now neo-druidic.service
    ```

5) Verify site is accessible

After starting services, verify the site is live:

```bash
# Check local Flask
curl -s http://localhost:8000/ | head -20

# Check through Cloudflare tunnel
curl -s https://awen01.cc/ | head -20
curl -s https://www.awen01.cc/ | head -20
```

Expected: HTML response with "Neo Druidic Society" in the title.

6) Troubleshooting common errors

**Port mismatch (CRITICAL):**
- Flask MUST run on port 8000 (not 5000 or any other port)
- Cloudflare tunnel config points to localhost:8000
- Check: `ss -ltnp | grep :8000` should show Flask listening
- Fix: Kill Flask and restart with `--port=8000`

**cloudflared fails with "credentials file not found":**
- Ensure $HOME/.cloudflared/config.yml contains correct credentials-file path
- Verify: `cat ~/.cloudflared/config.yml`
- The tunnel ID should be: de0f30f9-0b1f-4812-871f-039334db8833

**cloudflared DNS/lookup errors:**
- Confirm DNS resolver works: `dig protocol-v2.argotunnel.com @1.1.1.1`
- If DNS is blocked, fix /etc/resolv.conf or systemd-resolved
- Restart cloudflared after DNS fix

**Flask exits immediately or import errors:**
- Check logs: `tail -f logs/flask.log` and `logs/application.log`
- Verify virtualenv: `source .venv/bin/activate && pip check`
- Reinstall dependencies: `pip install -r requirements.txt`
- Check .env file exists and has required variables

**Site unreachable from internet (403 errors on NEOD endpoint):**
- Verify Cloudflare WAF rule exists for `/api/v1/neod/purchase`
- Go to Cloudflare Dashboard → Security → WAF → Custom rules
- Should have rule: "Allow NEOD Purchase API" that skips security for that endpoint
- Check Cloudflare → Security → Events for blocked requests

**Tunnel starts but site shows 530 error:**
- Flask is not running or not on port 8000
- Check: `ps aux | grep flask` and `ss -ltnp | grep :8000`
- Restart Flask on correct port: `./start_services.sh`

7) Verification checks after restart

**Process checks:**
```bash
# Both should show running processes
ps aux | grep -E "(cloudflared|flask)" | grep -v grep

# Flask should be listening on port 8000
ss -ltnp | grep :8000
```

**Log checks:**
```bash
# Check Flask startup
tail -n 50 logs/flask.log

# Check Cloudflare tunnel connection
tail -n 50 logs/cloudflared.log | grep -i "registered\|connection"

# Check application logs
tail -n 50 logs/application.log
```

**Connectivity checks:**
```bash
# Local
curl -s http://localhost:8000/ | grep -i "neo druidic"

# Public (through Cloudflare)
curl -s https://awen01.cc/ | grep -i "neo druidic"
curl -s https://www.awen01.cc/ | grep -i "neo druidic"

# NEOD API endpoint (should return JSON error, not 403)
curl -X POST https://www.awen01.cc/api/v1/neod/purchase \
  -H "Content-Type: application/json" \
  -d '{"signature":"test","recipient":"11111111111111111111111111111111"}'
```

8) If you cannot fix on the host

- Alternative: spin up a replacement host with the same project and cloudflared credentials
- Copy `$HOME/.cloudflared/` directory (contains config.yml and credentials JSON)
- Copy `.env` file with all secrets
- Run `./start_services.sh`
- Keep credentials JSON and .env private!

---

## Appendix — Quick Reference

**Site URLs:**
- Primary: https://awen01.cc
- Alternate: https://www.awen01.cc

**Critical Configuration:**
- Flask port: 8000 (MUST match Cloudflare tunnel config)
- Cloudflare tunnel ID: de0f30f9-0b1f-4812-871f-039334db8833
- Project root: /home/lanc3lot/neo-druidic-society
- User: lanc3lot

**Key Files:**
- Startup script: `./start_services.sh`
- Cloudflare config: `~/.cloudflared/config.yml`
- Environment vars: `.env`
- Logs: `logs/flask.log`, `logs/cloudflared.log`, `logs/application.log`

**One-Command Resurrection:**
```bash
cd /home/lanc3lot/neo-druidic-society && ./start_services.sh
```

**Suggested automation for AI handling (machine-readable checklist):**

```json
[
  {"id":1, "name":"check_processes", "cmds":["ps aux | grep -E '(cloudflared|flask)' | grep -v grep","tail -n 50 logs/flask.log","tail -n 50 logs/cloudflared.log"]},
  {"id":2, "name":"verify_cloudflared", "cmds":["command -v cloudflared","cat $HOME/.cloudflared/config.yml"]},
  {"id":3, "name":"verify_venv","cmds":["test -f .venv/bin/activate && echo ok || echo missing","test -f .env && echo ok || echo missing"]},
  {"id":4, "name":"start_services","cmds":["cd /home/lanc3lot/neo-druidic-society","./start_services.sh"]},
  {"id":5, "name":"verify_site","cmds":["curl -s http://localhost:8000/ | head -20","curl -s https://awen01.cc/ | head -20"]}
]
```

---

**Last Updated:** October 19, 2025  
**Tunnel:** awen01.cc (de0f30f9-0b1f-4812-871f-039334db8833)  
**Status:** Active and tested after power loss recovery
