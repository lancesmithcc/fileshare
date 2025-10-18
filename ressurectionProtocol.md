
# Resurrection Protocol — fileshare

Purpose: step-by-step, AI- and human-readable instructions to bring the site back online if it goes down. Follow these steps in order. Each step includes exact commands where applicable and checks to confirm success.

Format contract (short):
- Inputs: access to the server (SSH), project root at /home/bodhi/neo-druidic-society, ability to run shell commands.
- Outputs: running Flask process and active Cloudflare Tunnel exposing the app, logs showing successful start.
- Error modes: missing cloudflared binary, missing cloudflared credentials/config, missing virtualenv or dependencies, Flask runtime errors.

High level steps (quick):
1) Check process and logs
2) Verify cloudflared and tunnel credentials
3) Verify Python virtualenv and env vars
4) Start services using run_fileshare.sh
5) Troubleshoot common errors

Detailed steps

1) Check current status

- Confirm whether the Flask app or cloudflared are running and inspect logs:
  - ps and grepping for cloudflared and flask:
    ps aux | grep -E "(cloudflared|flask)" | grep -v grep
  - Tail the tunnel and application logs that live in project `logs/`:
    tail -n 200 logs/fileshare_supervisor.log
    tail -n 200 logs/application.log

  Expected: `fileshare_supervisor.log` shows recent `Starting cloudflared tunnel 'fileshare'` lines and registered connections; `application.log` shows app startup messages. If either log is absent, proceed to step 2 and 3.

2) Verify cloudflared installation and credentials

- Check cloudflared binary:
  - command -v cloudflared || echo "cloudflared not found"

- Check Cloudflare config file (used by `run_fileshare.sh`):
  - CONFIG_PATH="$HOME/.cloudflared/config.yml"
  - Verify it exists and contains `credentials-file:` pointing to a JSON under `$HOME/.cloudflared`.
    grep -n "credentials-file" "$HOME/.cloudflared/config.yml" || true

- Check credentials and origin cert:
  - ls -l $HOME/.cloudflared/*.json
  - test -f $HOME/.cloudflared/cert.pem && echo cert exists || echo cert missing

- If credentials or cert are missing:
  - Run interactive login on the host that should own the tunnel (requires CF account):
    cloudflared login
  - Create the tunnel (example):
    cloudflared tunnel create fileshare
  - Update $HOME/.cloudflared/config.yml with `credentials-file: /home/<user>/.cloudflared/<tunnel-id>.json` and routes (the `run_fileshare.sh` expects that file to be set).

3) Verify Python virtualenv and environment variables

- Ensure project virtualenv exists and dependencies are installed:
  - cd /home/bodhi/neo-druidic-society
  - test -f .venv/bin/activate || (python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt)

- Ensure `.env` (project root) contains required runtime vars or that they are present in the environment. Important keys referenced in `app/config.py` and `run_fileshare.sh`:
  - FLASK_APP, FLASK_RUN_PORT, NEO_DRUIDIC_MODEL_PATH, SOLANA_PRIVATE_KEY, SOLANA_RPC_URL, NEO_DRUIDIC_SECRET_KEY, etc.

- If you prefer not to store secrets in `.env`, export them in the environment before running.

4) Start the application using the provided runner

- Use the repository script which performs checks and starts both Flask and the Cloudflare tunnel:
  - cd /home/bodhi/neo-druidic-society
  - Make executable if needed: chmod +x run_fileshare.sh
  - Run it in a foreground session for monitoring: ./run_fileshare.sh

- To run in background / supervised mode, use a terminal multiplexer or systemd unit (example systemd service provided below if you want to create it):
  - Example systemd unit (create `/etc/systemd/system/fileshare.service`):
    [Unit]
    Description=Fileshare (Flask + cloudflared)
    After=network.target

    [Service]
    User=bodhi
    WorkingDirectory=/home/bodhi/neo-druidic-society
    ExecStart=/home/bodhi/neo-druidic-society/run_fileshare.sh
    Restart=on-failure
    Environment=PATH=/home/bodhi/.local/bin:/home/bodhi/neo-druidic-society/.venv/bin:/usr/bin:/bin

    [Install]
    WantedBy=multi-user.target

  - Then: sudo systemctl daemon-reload; sudo systemctl enable --now fileshare.service

5) Troubleshooting common errors

- cloudflared fails with "credentials file not found" or config missing
  - Ensure $HOME/.cloudflared/config.yml contains a valid `credentials-file:` path.
  - Run `cloudflared login` and `cloudflared tunnel create fileshare` on the server and update config.

- cloudflared logs show DNS/lookup errors (e.g., `lookup protocol-v2.argotunnel.com on 127.0.0.53:53: no such host`)
  - Confirm the server's DNS resolver works: dig protocol-v2.argotunnel.com @1.1.1.1
  - If DNS is blocked, fix resolver (e.g. edit /etc/resolv.conf or use systemd-resolved configuration). Restart cloudflared after resolver fix.

- Flask process exits immediately or logs "This is a development server. Do not use it in production"
  - The project uses `flask run` (development server). For production, run behind a WSGI server like gunicorn. To get it running quickly, ensure the virtualenv and dependencies are installed and re-run `./run_fileshare.sh`.
  - Check `logs/application.log` and stdout from `./run_fileshare.sh` for Python tracebacks; fix missing modules or import errors.

- If the tunnel starts but site is unreachable from the internet
  - Confirm Cloudflare DNS (the CNAME or route) is configured for the tunnel in Cloudflare dashboard or via `cloudflared route dns` configuration.
  - Confirm `cloudflared tunnel list` shows the `fileshare` tunnel and that it is `RUNNING` (use `cloudflared tunnel info fileshare` on the host or check `cloudflared tunnel list` remotely).

6) Verification checks after restart

- Confirm Flask is listening locally:
  - ss -ltnp | grep :8000

- Confirm cloudflared is running and attached to the tunnel:
  - ps aux | grep cloudflared
  - cloudflared tunnel list

- Check the logs for a successful handshake and registered connections:
  - tail -n 200 logs/fileshare_supervisor.log | grep "Registered tunnel connection" || true

7) If you cannot fix on the host

- Alternative: spin up a replacement host with the same project and cloudflared credentials JSON copied to `$HOME/.cloudflared/` and the same `config.yml`, then run `./run_fileshare.sh` there. Keep credentials JSON private.

Appendix — Suggested automation for AI handling (machine-readable checklist)

- Step objects (JSON-like):
  - {"id":1, "name":"check_processes", "cmds":["ps aux | grep -E '(cloudflared|flask)' | grep -v grep","tail -n 200 logs/fileshare_supervisor.log"]}
  - {"id":2, "name":"verify_cloudflared", "cmds":["command -v cloudflared","test -f $HOME/.cloudflared/config.yml && echo ok || echo missing"]}
  - {"id":3, "name":"verify_venv","cmds":["test -f .venv/bin/activate && echo ok || echo missing",". .venv/bin/activate && pip check || true"]}
  - {"id":4, "name":"start_runner","cmds":["./run_fileshare.sh"]}

Commit note: This file documents the known run script (`run_fileshare.sh`) and Cloudflare tunnel usage. It should be stored at project root as `ressurectionProtocol.md`.
