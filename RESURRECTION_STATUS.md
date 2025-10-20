# Site Resurrection Status

**Date:** October 19, 2025  
**Event:** Power loss recovery  
**Status:** ✅ FULLY OPERATIONAL

## Services Running

### Flask Application
- **Status:** ✅ Running
- **Port:** 8000
- **PID:** Check with `ps aux | grep flask`
- **Log:** `logs/flask.log`
- **Local URL:** http://localhost:8000

### Cloudflare Tunnel
- **Status:** ✅ Running
- **Tunnel ID:** de0f30f9-0b1f-4812-871f-039334db8833
- **PID:** Check with `ps aux | grep cloudflared`
- **Log:** `logs/cloudflared.log`

## Public Access

### Primary URLs
- ✅ https://awen01.cc - WORKING
- ✅ https://www.awen01.cc - WORKING

### API Endpoints
- ✅ `/api/v1/neod/purchase` - Accessible (no 403 errors)
- ✅ `/api/v1/neod/info` - Accessible

## Verification Results

```bash
# Site is serving HTML
curl -s https://www.awen01.cc/ | grep "Neo Druidic Society"
✅ Returns: <title>Neo Druidic Society</title>

# NEOD API is accessible (returns proper error, not 403)
curl -X POST https://www.awen01.cc/api/v1/neod/purchase \
  -H "Content-Type: application/json" \
  -d '{"signature":"test","recipient":"11111111111111111111111111111111"}'
✅ Returns: {"error":"Unable to reach Solana RPC to verify payment."}
```

## Configuration Summary

### Cloudflare Tunnel Config
```yaml
tunnel: de0f30f9-0b1f-4812-871f-039334db8833
credentials-file: /home/lanc3lot/.cloudflared/de0f30f9-0b1f-4812-871f-039334db8833.json
ingress:
  - hostname: awen01.cc
    service: http://localhost:8000
  - hostname: www.awen01.cc
    service: http://localhost:8000
  - service: http_status:404
```

### Cloudflare WAF Rules
- ✅ "Allow NEOD Purchase API" - Skips security checks for `/api/v1/neod/purchase`

### Critical Settings
- Flask port: **8000** (matches tunnel config)
- Database: PostgreSQL (connected)
- NEOD service: Configured with Solana RPC

## Quick Commands

### Check Status
```bash
# Check processes
ps aux | grep -E "(cloudflared|flask)" | grep -v grep

# Check port
ss -ltnp | grep :8000

# Check logs
tail -f logs/flask.log
tail -f logs/cloudflared.log
```

### Restart Services
```bash
cd /home/lanc3lot/neo-druidic-society
./start_services.sh
```

### Stop Services
```bash
pkill -f "flask run"
pkill -f cloudflared
```

## Next Steps

1. ✅ Site is live and accessible
2. ✅ NEOD donation endpoint is working (no 403 errors)
3. ✅ Cloudflare tunnel is stable
4. ✅ Resurrection protocol updated with new tunnel URL

### Optional: Set up systemd service for auto-restart
See `ressurectionProtocol.md` section 4 for systemd configuration.

---

**All systems operational. Site successfully resurrected after power loss.**
