# NEOD Lamports Encoding Fix

## Issue
When attempting to donate SOL to receive NEOD tokens, users encountered the error:
```
Blob.encode[lamports] requires (length 8) Uint8Array
```

## Root Cause
The error was caused by multiple issues in the frontend JavaScript:

1. **Duplicate Library Loading**: The Solana web3.js library was being loaded twice:
   - Once via CDN in the template (`@solana/web3.js@1.73.0`)
   - Once dynamically by the neod.js script (attempting to load `@solana/web3.js@1.95.3`)
   
2. **Version Mismatch**: Different versions of the library were referenced in different places, causing inconsistent behavior.

3. **Lamports Type Issue**: The `lamports` parameter needs to be a proper integer, not a float, to avoid encoding issues with certain versions of the Solana web3.js library.

## Solution Applied

### 1. Removed Duplicate Script Loading
**File**: `app/templates/neod/index.html`
- Removed the hardcoded CDN script tag for Solana web3.js
- Let the neod.js script handle dynamic loading

### 2. Standardized on Version 1.73.0 IIFE
**Files**: `app/static/js/neod.js` and `app/templates/neod/index.html`
- Changed default web3.js source to use version 1.73.0 IIFE format
- Updated data attribute to point to CDN instead of local vendor file
- Version 1.73.0 is more stable for browser usage than 1.95.3

### 3. Ensured Integer Lamports Value
**File**: `app/static/js/neod.js`
- Added `Math.floor()` to ensure lamports is always an integer
- This prevents any floating-point precision issues

## Changes Made

### app/static/js/neod.js
```javascript
// Changed default CDN URL
const src = root.dataset.web3Src || "https://unpkg.com/@solana/web3.js@1.73.0/lib/index.iife.min.js";

// Ensured integer lamports
const lamportsInt = Math.floor(lamports);

transaction.add(
  web3.SystemProgram.transfer({
    fromPubkey: fromPubkey,
    toPubkey: toPubkey,
    lamports: lamportsInt,
  })
);
```

### app/templates/neod/index.html
```html
<!-- Updated data attribute -->
data-web3-src="https://unpkg.com/@solana/web3.js@1.73.0/lib/index.iife.min.js"

<!-- Removed duplicate script tag -->
{% block extra_scripts %}
<script src="{{ url_for('static', filename='js/neod.js') }}?v=20251019p"></script>
{% endblock %}
```

## Testing Steps

1. Clear browser cache to ensure old scripts are not cached
2. Navigate to the NEOD donation page
3. Connect Phantom wallet
4. Enter a SOL amount (minimum 0.005 SOL)
5. Click "Send SOL & Receive NEOD"
6. Approve the transaction in Phantom
7. Verify the transaction completes without the Blob.encode error

## Technical Details

### Why Version 1.73.0?
- More stable for browser environments
- IIFE (Immediately Invoked Function Expression) format works better in browsers
- Properly handles the lamports encoding without requiring additional type conversions

### Why Remove Duplicate Loading?
- Loading the library twice can cause namespace conflicts
- Different versions may have incompatible APIs
- Single dynamic loading ensures consistency

### Why Math.floor()?
- Ensures lamports is always an integer
- Prevents floating-point precision issues
- Some web3.js versions are strict about numeric types

## Related Files
- `/app/static/js/neod.js` - Main NEOD donation frontend logic
- `/app/templates/neod/index.html` - NEOD donation page template
- `/app/neod.py` - Backend NEOD service (unchanged)

## Status
✅ **FIXED** - The lamports encoding error should now be resolved.

## Date
October 19, 2025
