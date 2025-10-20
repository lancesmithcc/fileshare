# NEOD Quick Reference Card

**Last Updated:** October 19, 2025

---

## 🔴 CURRENT BLOCKER

**Error:** `Blob.encode[lamports] requires (length 8) Uint8Array`  
**Location:** Frontend transaction creation in `app/static/js/neod.js`  
**Impact:** Users cannot complete SOL donations to receive NEOD  
**Status:** UNRESOLVED after multiple attempted fixes

---

## 🎯 What Works

✅ Backend API fully functional  
✅ Treasury funded (144M NEOD)  
✅ Wallet connection works  
✅ Transaction verification works  
✅ Token transfers work  

## ❌ What's Broken

❌ Frontend cannot create Solana transactions  
❌ web3.js encoding fails in browser  

---

## 🚀 Recommended Fix (When You Return)

### **Option 1: Server-Side Transaction Construction** ⭐ BEST

Move transaction building to backend:

1. **Frontend sends:** `{ amount: 0.005, walletAddress: "abc..." }`
2. **Backend builds:** Unsigned transaction with proper encoding
3. **Backend returns:** Serialized transaction bytes
4. **Frontend:** Asks Phantom to sign the pre-built transaction
5. **Backend:** Submits signed transaction to Solana

**Why:** Avoids all browser web3.js encoding issues

**Files to modify:**
- `app/api.py` - Add endpoint to build transaction
- `app/static/js/neod.js` - Request transaction from backend, sign with Phantom

---

## 📁 Key Files

```
NEOD_STATUS_SUMMARY.md          ← Full status & history
app/neod.py                     ← Backend service (working)
app/static/js/neod.js           ← Frontend (broken)
app/templates/neod/index.html   ← UI template
docs/archive/                   ← Old docs (archived)
```

---

## 🧪 Quick Tests

```bash
# Test backend API
curl -s https://www.awen01.cc/api/v1/neod/info | python3 -m json.tool

# Check treasury balance
curl -s https://api.mainnet-beta.solana.com -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getTokenAccountBalance","params":["46ATtjMBPXu23A1i3gC5cqXoQKwWiC19SPmbW8E8ypW9"]}' \
  | python3 -m json.tool

# Watch logs
tail -f logs/application.log | grep -i neod
```

---

## 💾 Treasury Info

```
Mint:     CQKwcjTXoUYAw25YMpy8khTbpmzWougp11zC3ZZhHkUj
Wallet:   BqZZpDqZrvdj42pXSG6WKpfqAapiSet9mSrSx2XQNPR2
ATA:      46ATtjMBPXu23A1i3gC5cqXoQKwWiC19SPmbW8E8ypW9
Balance:  144,000,000 NEOD
Rate:     0.005 SOL = 1 NEOD
```

---

## 📚 Resources

- Full Status: `NEOD_STATUS_SUMMARY.md`
- Solana Docs: https://docs.solana.com
- Phantom API: https://docs.phantom.app/developer-powertools
- Solana Pay: https://docs.solanapay.com (alternative approach)

---

**TL;DR:** Backend works perfectly. Frontend can't create transactions due to web3.js browser encoding bug. Best fix: move transaction construction to backend.
