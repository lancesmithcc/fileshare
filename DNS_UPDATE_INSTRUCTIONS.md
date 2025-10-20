# DNS Update Required for awen01.cc

## Current Status ✅

Your application is **RUNNING** successfully:
- Flask app: http://127.0.0.1:8000
- Cloudflare tunnel: **CONNECTED** (4 connections active)
- Tunnel ID: `de0f30f9-0b1f-4812-871f-039334db8833`
- Database: PostgreSQL connected

## Issue

The DNS record for `awen01.cc` is pointing to an old tunnel ID. You need to update it to the new tunnel.

## Solution: Update DNS in Cloudflare Dashboard

### Option 1: Via Cloudflare Dashboard (Recommended)

1. Go to https://dash.cloudflare.com
2. Select your domain: **awen01.cc**
3. Click on **DNS** in the left sidebar
4. Find the CNAME record for `awen01.cc` (or `@`)
5. Click **Edit** on that record
6. Update the **Target** to: `de0f30f9-0b1f-4812-871f-039334db8833.cfargotunnel.com`
7. Ensure **Proxy status** is **Proxied** (orange cloud icon)
8. Click **Save**

9. If there's a CNAME for `www`:
   - Update it to the same target: `de0f30f9-0b1f-4812-871f-039334db8833.cfargotunnel.com`
   - Ensure it's also **Proxied**

### Option 2: Delete and Recreate via CLI

If you prefer the command line:

```bash
# You'll need to manually delete the old DNS records in the dashboard first
# Then run:
cloudflared tunnel route dns fileshare awen01.cc
cloudflared tunnel route dns fileshare www.awen01.cc
```

## Verification

After updating DNS:

1. Wait 1-2 minutes for DNS propagation
2. Visit https://awen01.cc in your browser
3. You should see the Neo-Druidic Society site!
4. Log in with credentials

## Current Tunnel Info

```
Tunnel Name: fileshare
Tunnel ID: de0f30f9-0b1f-4812-871f-039334db8833
Target CNAME: de0f30f9-0b1f-4812-871f-039334db8833.cfargotunnel.com
```

## Keeping the Service Running

The service is currently running in your terminal. To keep it running:

### Option 1: Use screen or tmux
```bash
# Install screen if needed
sudo apt install screen

# Start a screen session
screen -S fileshare

# Run the app
cd /home/lanc3lot/neo-druidic-society
./run_fileshare.sh

# Detach with: Ctrl+A then D
# Reattach with: screen -r fileshare
```

### Option 2: Create a systemd service (for permanent deployment)

Create `/etc/systemd/system/fileshare.service`:

```ini
[Unit]
Description=Neo-Druidic Society (Flask + Cloudflare Tunnel)
After=network.target postgresql.service

[Service]
Type=simple
User=lanc3lot
WorkingDirectory=/home/lanc3lot/neo-druidic-society
ExecStart=/home/lanc3lot/neo-druidic-society/run_fileshare.sh
Restart=on-failure
RestartSec=10
Environment=PATH=/home/lanc3lot/.local/bin:/home/lanc3lot/neo-druidic-society/.venv/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable fileshare
sudo systemctl start fileshare
sudo systemctl status fileshare
```

---

**Once DNS is updated, your site will be live at https://awen01.cc!** 🌿✨
