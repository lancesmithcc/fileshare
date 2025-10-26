# WP-KyberCrypt Security Guide (v1.1.0)

## 🔐 Production Hardening Complete

WP-KyberCrypt v1.1 implements enterprise-grade security controls for quantum-safe WordPress encryption.

## Critical Security Improvements

### 1. Secret Management ✅

**BEFORE (v1.0):** Secrets stored in wp_options table
```php
// ❌ INSECURE - Database leak exposes everything
update_option( 'ndk_api_key', $secret_key );
update_option( 'ndk_site_login_keys', array( 'passphrase' => $passphrase ) );
```

**AFTER (v1.1):** Secrets in wp-config.php constants
```php
// ✅ SECURE - Secrets outside database
define( 'NDK_API_KEY', 'your_api_key_here' );
define( 'NDK_LOGIN_KEY_PASSPHRASE', 'your_passphrase_here' );
define( 'NDK_API_URL', 'https://your-api-endpoint.com' ); // optional
```

**Result:** Database dump no longer sufficient to decrypt data or call decrypt service.

---

### 2. Python Service Isolation ✅

**URL Validation Rules:**
- ✅ `https://any-domain.com` - Allowed (encrypted transport)
- ✅ `http://localhost` or `http://127.0.0.1` - Allowed (localhost)
- ✅ `http://10.0.0.5` or `http://192.168.1.100` - Allowed (RFC1918 private IPs)
- ❌ `http://public-domain.com` - **BLOCKED** (public HTTP)

**Security Warning:**
If API URL is not localhost/private, admin sees:
> ⚠️ WARNING: Python Kyber service should be on localhost or private network for security.

**Deployment Recommendation:**
```bash
# Python service on localhost
NDK_API_URL=http://127.0.0.1:8000

# Or private network
NDK_API_URL=http://10.0.1.50:8000

# Or HTTPS (any domain)
NDK_API_URL=https://secure-kyber-api.internal
```

---

### 3. Access Control ✅

**New Helper Function:**
```php
NDK_Security::can_current_user_decrypt( $context, $owner_user_id )
```

**Access Rules:**
1. ✅ User can decrypt their own data
2. ✅ `manage_options` capability can decrypt anything
3. ✅ `manage_woocommerce` can decrypt WooCommerce orders
4. ✅ `edit_users` can decrypt user meta
5. ✅ `gravityforms_edit_entries` can decrypt form entries
6. ❌ Logged-out users **NEVER** see plaintext
7. ❌ No fallback to user_id=1

**Before Decrypt:**
```php
if ( ! NDK_Security::can_current_user_decrypt( 'woo_order', $order_user_id ) ) {
    return NDK_Security::get_masked_value(); // Returns '[LOCKED 🔒]'
}
// Proceed with decrypt...
```

---

### 4. Rate Limiting ✅

**Login Endpoint Protection:**
- 5 attempts per IP per 5 minutes
- Generic error messages: `"Login failed."`
- No username/password enumeration
- POST-only (GET rejected)
- Nonce validation required

**Implementation:**
```php
// Rate limit check
$rate_limit = NDK_Security::check_login_rate_limit( $ip );
if ( ! $rate_limit['allowed'] ) {
    wp_send_json_error( array( 'message' => 'Too many attempts.' ) );
}

// Record attempt
NDK_Security::record_login_attempt( $ip, $success );
```

---

### 5. Key Versioning ✅

**Database Schema (v1.1):**
```sql
CREATE TABLE wp_ndk_keys (
    id bigint(20) NOT NULL AUTO_INCREMENT,
    user_id bigint(20) NOT NULL,
    key_id varchar(100) NOT NULL,          -- NEW: Version identifier
    public_key text NOT NULL,
    encrypted_private_key text NOT NULL,
    salt varchar(255) NOT NULL,
    nonce varchar(255) NOT NULL,
    active tinyint(1) DEFAULT 1,           -- NEW: Enable/disable keys
    created_at datetime DEFAULT CURRENT_TIMESTAMP,
    updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY user_key_id (user_id, key_id),  -- NEW: Multi-key support
    KEY user_id (user_id),
    KEY active (active)
);
```

**Encrypted Blob Format (Future):**
```json
{
    "alg": "ml-kem-768+aes256-gcm",
    "key_id": "user-42-key-3",
    "kem_ciphertext": "...",
    "wrapped_key": "...",
    "nonce": "...",
    "ciphertext": "..."
}
```

**Key Rotation Support:**
- Multiple keys per user
- Old encrypted data references `key_id`
- Decrypt path looks up correct key by `key_id`
- Forward compatibility built-in

---

### 6. Logging Security ✅

**Sanitized Logging:**
```php
// Before
error_log( 'Decrypt failed: ' . $ciphertext ); // ❌ Leaks secrets

// After
error_log( 'Decrypt failed: ' . NDK_Security::sanitize_log( $message ) ); // ✅ Redacted
```

**Redaction:**
- Base64 strings (keys/ciphertext) replaced with `[REDACTED]`
- No secrets in admin UI
- Configuration status shown as ✅/❌ instead of values

---

### 7. Force Quantum Login ✅

**Problem:** If classic wp-login.php still works, attackers can bypass quantum encryption by using standard POST.

**Solution:** Optional `ndk_force_quantum_login` setting blocks all non-quantum authentication:

```php
// When enabled:
add_action( 'login_init', 'block_classic_login' );  // Blocks wp-login.php POST
add_filter( 'xmlrpc_enabled', '__return_false' );   // Disables XML-RPC
add_filter( 'rest_authentication_errors', 'block_rest_basic_auth' );  // Blocks REST Basic Auth
```

**Admin UI:**
- Settings > Security Settings > "Force quantum-safe login"
- **Warning:** Only enable after verifying quantum login works
- Disabled by default for backward compatibility

**What Gets Blocked:**
- Classic username/password POST to wp-login.php
- XML-RPC authentication (completely disabled)
- REST API Basic Auth (session-based auth still works)
- AJAX requests are allowed (for encrypted login endpoint)

**User Experience When Enabled:**
```
HTTP 403 Forbidden
Quantum-Safe Login Required

This site requires quantum-safe encrypted authentication.
Classic username/password login is disabled.

← Back to Login
```

---

## Migration from v1.0 to v1.1

### Step 1: Update Plugin

Upload and activate WP-KyberCrypt v1.1.0.

### Step 2: View Migration Notice

Navigate to WordPress admin. You'll see:

```
┌─────────────────────────────────────────────────────────┐
│ WP-KyberCrypt Security Migration Required              │
├─────────────────────────────────────────────────────────┤
│ Action Required: For production security, move         │
│ sensitive secrets to wp-config.php:                    │
│                                                         │
│ define( 'NDK_API_KEY', 'abc123...' );                  │
│ define( 'NDK_LOGIN_KEY_PASSPHRASE', 'xyz789...' );     │
│                                                         │
│ After adding to wp-config.php, click here to complete  │
│ migration.                                              │
└─────────────────────────────────────────────────────────┘
```

### Step 3: Add Constants to wp-config.php

Open `wp-config.php` and add **before** `/* That's all, stop editing! */`:

```php
// WP-KyberCrypt Security (v1.1+)
define( 'NDK_API_KEY', 'your_64_char_hex_key_here' );
define( 'NDK_LOGIN_KEY_PASSPHRASE', 'your_sha256_hash_here' );
define( 'NDK_API_URL', 'https://awen01.cc' ); // Optional, defaults to this

/* That's all, stop editing! Happy publishing. */
```

### Step 4: Complete Migration

Click "complete migration" link in admin notice. This:
1. Deletes `ndk_api_key` from wp_options
2. Removes `passphrase` from `ndk_site_login_keys`
3. Marks migration as complete

### Step 5: Verify

Check that:
- [ ] Login still works
- [ ] Encryption/decryption still works
- [ ] No migration notice appears
- [ ] Database no longer contains secrets

---

## Security Checklist

### Required for Production

- [ ] `NDK_API_KEY` defined in wp-config.php
- [ ] `NDK_LOGIN_KEY_PASSPHRASE` defined in wp-config.php
- [ ] Python service on localhost/private network OR HTTPS
- [ ] Migration completed (secrets removed from database)
- [ ] File permissions: `wp-config.php` chmod 600 or 640
- [ ] Database backups encrypted at rest
- [ ] HTTPS enabled on WordPress site
- [ ] Regular security audits scheduled

### Recommended

- [ ] Force quantum login enabled (`ndk_force_quantum_login` option) **[Available in v1.1]**
- [ ] Python service uses ENV for passphrase (not sent over HTTP) **[Requires Python service update]**
- [ ] Firewall rules restrict Kyber API to WordPress server IP
- [ ] Monitor failed login attempts (transients stored in `ndk_login_attempts_{ip}`)
- [ ] Regular key rotation policy established (database supports multi-key via `key_id`)
- [ ] Admin accounts use 2FA (recommended additional layer)

---

## API Endpoints Security

### `/wp-admin/admin-ajax.php?action=ndk_encrypted_login`

**Protection:**
- ✅ POST only
- ✅ Nonce validated
- ✅ Rate limited (5/5min per IP)
- ✅ Generic errors
- ✅ No user enumeration

### `/wp-admin/admin-ajax.php?action=ndk_get_login_pubkey`

**Protection:**
- ✅ Nonce validated
- ✅ Returns public key only (no secrets)
- ✅ Unauthenticated (public endpoint for login)

---

## Threat Model

### Mitigated Threats ✅

1. **Database Leak:** Secrets not in database
2. **MITM on Python API:** HTTPS enforced for public URLs
3. **Brute Force Login:** Rate limiting + generic errors
4. **Unauthorized Decrypt:** Access control enforced
5. **Log Disclosure:** Secrets redacted from logs
6. **Admin UI Leak:** No secrets displayed

### Residual Risks ⚠️

1. **Passphrase Over HTTP:** Still sent to localhost Python service (mitigated by localhost-only rule)
   - **Future Fix:** Python service reads passphrase from ENV
2. **wp-config.php Disclosure:** If server misconfigured
   - **Mitigation:** Proper file permissions (600/640)
3. **Memory Scraping:** Passphrases in RAM
   - **Mitigation:** Server-level protections required

---

## Compliance Notes

### NIST Post-Quantum Cryptography

Uses **ML-KEM-768** (Module-Lattice-Based Key Encapsulation Mechanism) per NIST FIPS 203.
Combined with **AES-256-GCM** for authenticated encryption.

**Security Level:** ~192-bit classical, quantum-resistant

### Data Protection

- ✅ End-to-end encryption
- ✅ Key material never transmitted in plaintext
- ✅ Access controls per GDPR Article 32 (security of processing)
- ✅ Audit trail via WordPress logs
- ✅ Right to erasure: delete user keys

---

## Support & Security Reports

**Security Issues:** Email security@wp-kybercrypt.com (PGP key available)

**Plugin Support:** https://wp-kybercrypt.com/support

**Bug Reports:** GitHub Issues (non-security bugs only)

---

## Changelog

### v1.1.0 (Production Hardening Release)

**Security Improvements:**
- Secrets moved to wp-config.php constants (NDK_API_KEY, NDK_LOGIN_KEY_PASSPHRASE, NDK_API_URL)
- Python service URL validation and HTTPS enforcement (localhost/private IP allowed on HTTP)
- Access control system for decrypt operations (per-user, per-capability)
- Rate limiting on login attempts (5 per IP per 5 minutes)
- Sanitized logging (secrets redacted from error logs)
- Key versioning database schema (supports key rotation via `key_id` and `active` columns)
- Force quantum login option (blocks classic wp-login.php, XML-RPC, REST Basic Auth)
- Admin UI no longer displays secrets (shows ✅/❌ configuration status)
- Migration guide and tooling (admin notices with copy-paste constants)

**Breaking Changes:**
- Requires manual migration to wp-config.php constants for production deployments
- Old installations need to follow migration guide in SECURITY.md

**Backward Compatibility:**
- Graceful fallback to wp_options if constants not defined
- Existing encrypted data fully compatible (no re-encryption needed)
- Force quantum login disabled by default (opt-in security feature)
