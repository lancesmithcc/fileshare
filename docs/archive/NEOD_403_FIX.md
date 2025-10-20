# NEOD 403 Error Fix

## Problem
Users were getting a 403 Forbidden error when trying to donate SOL for NEOD tokens.

## Root Cause
The 403 error is most likely caused by **Cloudflare's security features** blocking the POST request to `/api/v1/neod/purchase`. Cloudflare's WAF (Web Application Firewall), Bot Fight Mode, or Security Level settings can block POST requests that don't have proper headers or that look suspicious.

## Changes Made

### 1. Updated JavaScript Fetch Request (`app/static/js/neod.js`)
- Added `credentials: "same-origin"` to include session cookies
- Added `X-Requested-With: "XMLHttpRequest"` header to identify the request as a legitimate AJAX call

### 2. Updated Flask Session Configuration (`app/config.py`)
- Added `SESSION_COOKIE_SAMESITE = "Lax"` to allow cookies in same-site requests
- Added `SESSION_COOKIE_SECURE = False` for development (set to True in production with HTTPS)
- Added `SESSION_COOKIE_HTTPONLY = True` for security

## Additional Steps Required

### Option 1: Whitelist the API Endpoint in Cloudflare (Recommended)
1. Log in to your Cloudflare dashboard
2. Go to **Security** → **WAF**
3. Create a new WAF rule to skip security checks for the NEOD purchase endpoint:
   - **Field**: URI Path
   - **Operator**: equals
   - **Value**: `/api/v1/neod/purchase`
   - **Action**: Skip (select "All remaining custom rules")

### Option 2: Adjust Cloudflare Security Level
1. Go to **Security** → **Settings**
2. Lower the **Security Level** from "High" to "Medium" or "Low"
3. Test the donation flow

### Option 3: Create a Page Rule
1. Go to **Rules** → **Page Rules**
2. Create a new page rule for `*awen01.cc/api/v1/neod/purchase`
3. Add setting: **Security Level** → **Essentially Off**
4. Save and deploy

### Option 4: Disable Bot Fight Mode (if enabled)
1. Go to **Security** → **Bots**
2. Disable **Bot Fight Mode** or configure it to allow the API endpoint

## Testing
After making these changes:
1. Restart the Flask application
2. Clear your browser cache
3. Try the donation flow again
4. Check the browser's Network tab (F12) to see the actual error details
5. Check Cloudflare's Firewall Events to see if requests are being blocked

## Verification
To verify if Cloudflare is blocking the request:
1. Go to Cloudflare Dashboard → **Security** → **Events**
2. Look for blocked requests to `/api/v1/neod/purchase`
3. Check the "Action" column - if it says "Block" or "Challenge", that's the issue

## Alternative: Bypass Cloudflare for Testing
To test if Cloudflare is the issue, you can temporarily:
1. Access the site directly via IP:port (e.g., `http://10.0.0.179:5000`)
2. If the donation works without Cloudflare, then Cloudflare is definitely the issue

## Production Recommendations
1. Set `SESSION_COOKIE_SECURE = True` when using HTTPS
2. Configure Cloudflare to whitelist the API endpoint
3. Consider adding rate limiting to prevent abuse
4. Monitor Cloudflare's Firewall Events for false positives
