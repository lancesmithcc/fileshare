# NEOD Donation Debugging Guide

**Date:** October 19, 2025

## Quick Diagnosis

### Step 1: Check Browser Console

1. Open the NEOD page: https://www.awen01.cc/neod
2. Press F12 to open Developer Tools
3. Click the "Console" tab
4. Look for any red error messages

**Common errors:**
- `Uncaught ReferenceError` - JavaScript file not loading
- `Failed to fetch` - Network/CORS issue
- `403 Forbidden` - Cloudflare blocking
- `TypeError` - JavaScript bug

### Step 2: Check Network Tab

1. In Developer Tools, click "Network" tab
2. Try to donate SOL
3. Look for a POST request to `/api/v1/neod/purchase`

**What to check:**
- Is the request being made at all?
- What's the status code? (should be 404, 400, or 503 for test data, NOT 403)
- What's the response body?

### Step 3: Check Wallet Connection

1. Can you click "Connect Wallet"?
2. Does Phantom pop up?
3. Does it show "Connected: [your address]"?

### Step 4: Check Transaction

1. Can you click "Send SOL"?
2. Does Phantom pop up asking to approve?
3. Does the transaction go through in Phantom?
4. What happens after you approve?

## Common Issues & Solutions

### Issue 1: "No Solana wallet detected"

**Cause:** Phantom wallet extension not installed or not detected

**Solution:**
1. Install Phantom from https://phantom.app
2. Refresh the page
3. Make sure you're using Chrome, Brave, or Edge (not Firefox)

### Issue 2: Wallet connects but "Send SOL" button disabled

**Cause:** Amount is below minimum or quote calculation failed

**Solution:**
1. Make sure amount is at least 0.005 SOL
2. Check browser console for JavaScript errors
3. Try refreshing the page (Ctrl+Shift+R for hard refresh)

### Issue 3: Transaction approved in Phantom but no NEOD received

**Cause:** Backend API call failing

**Check logs:**
```bash
tail -f /home/lanc3lot/neo-druidic-society/logs/flask.log | grep -i "POST.*purchase"
```

**Look for:**
- POST request to `/api/v1/neod/purchase`
- Status code (should be 201 for success)
- Any error messages

### Issue 4: 403 Forbidden error

**Cause:** Cloudflare WAF blocking the request

**Solution:**
1. Check Cloudflare Dashboard → Security → Events
2. Look for blocked requests to `/api/v1/neod/purchase`
3. Verify WAF rule exists: "Allow NEOD Purchase API"
4. Rule should skip security for `/api/v1/neod/purchase`

### Issue 5: JavaScript not loading latest version

**Cause:** Browser cache

**Solution:**
1. Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
2. Clear browser cache
3. Check version in page source: should be `neod.js?v=20251019`

### Issue 6: "Unable to reach Solana RPC" error

**Cause:** RPC endpoint down or rate limited

**Check:**
```bash
# Test RPC
curl -X POST https://api.mainnet-beta.solana.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
```

**Solution:**
- Service automatically falls back to public RPC
- Wait a moment and try again
- Check logs for RPC failures

## Manual Testing

### Test 1: Check API Endpoint

```bash
# Should return NEOD info (no 403)
curl -s https://www.awen01.cc/api/v1/neod/info | python3 -m json.tool
```

Expected: JSON with `available_supply: 144000000`

### Test 2: Test Purchase Endpoint (will fail but shouldn't 403)

```bash
curl -X POST https://www.awen01.cc/api/v1/neod/purchase \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{
    "signature": "test123",
    "recipient": "BqZZpDqZrvdj42pXSG6WKpfqAapiSet9mSrSx2XQNPR2"
  }'
```

Expected: `{"error":"Transaction test123 not found on-chain."}` (404)
NOT: `403 Forbidden`

### Test 3: Check Treasury Balance

```bash
curl -s https://api.mainnet-beta.solana.com -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"getTokenAccountBalance",
    "params":["46ATtjMBPXu23A1i3gC5cqXoQKwWiC19SPmbW8E8ypW9"]
  }' | python3 -m json.tool
```

Expected: `"amount": "144000000"`

## Monitoring Real-Time

### Watch Flask Logs

```bash
tail -f /home/lanc3lot/neo-druidic-society/logs/flask.log
```

### Watch Application Logs

```bash
tail -f /home/lanc3lot/neo-druidic-society/logs/application.log | grep -i neod
```

### Watch for POST Requests

```bash
tail -f /home/lanc3lot/neo-druidic-society/logs/flask.log | grep "POST.*neod"
```

## What to Report

When reporting an issue, please provide:

1. **What you see:** Exact error message or behavior
2. **Browser console:** Any red errors (F12 → Console)
3. **Network tab:** Status code of `/api/v1/neod/purchase` request
4. **Wallet:** Did Phantom pop up? Did transaction go through?
5. **Transaction signature:** If Phantom shows a signature, copy it

## Expected Flow

1. ✅ Page loads with "Connect Wallet" button
2. ✅ Click "Connect Wallet" → Phantom pops up
3. ✅ Approve in Phantom → Button shows "Connected: abc...xyz"
4. ✅ Enter amount (min 0.005 SOL) → Quote updates
5. ✅ Click "Send SOL" → Phantom pops up with transaction
6. ✅ Approve in Phantom → Transaction submits
7. ✅ Page shows "Transaction submitted: abc...xyz"
8. ✅ Wait for confirmation (~30 seconds)
9. ✅ Backend verifies transaction
10. ✅ Backend sends NEOD to your wallet
11. ✅ Page shows "Blessings received! X NEOD on the way"

## Still Not Working?

1. Check all steps above
2. Try in incognito/private browsing mode
3. Try a different browser
4. Check Cloudflare firewall events
5. Restart Flask: `./start_services.sh`
6. Check server logs for errors

---

**Need help?** Share:
- Browser console errors
- Network tab screenshot
- Exact error message you see
