# Neo-Druidic Kyber Encryption for WordPress

Quantum-safe encryption for WordPress using ML-KEM-768 (Kyber) post-quantum cryptography.

## Description

This plugin integrates with the Neo-Druidic Society's Kyber API to provide enterprise-grade, quantum-safe encryption for your WordPress content. Using the NIST-standardized ML-KEM-768 algorithm (the final Kyber variant), your content is protected against both classical and quantum computer attacks.

### Features

- **Post-Quantum Security**: Uses ML-KEM-768, resistant to quantum computer attacks
- **NIST Standardized**: Based on the official NIST PQC standard (2024)
- **Flexible Encryption**: Encrypt posts, pages, and comments
- **Automatic Key Management**: Auto-generates encryption keypairs for users
- **Hybrid Encryption**: Combines Kyber KEM with AES-GCM for optimal performance
- **WordPress Best Practices**: Follows all WordPress coding standards
- **Secure by Design**: Private keys encrypted with user credentials
- **Shortcode Support**: `[ndk_encrypted]` for inline encrypted content

### Security Level

- **Algorithm**: ML-KEM-768 (Module-Lattice Key Encapsulation Mechanism)
- **Security Level**: NIST Level 3 (equivalent to AES-192)
- **Public Key**: 1184 bytes
- **Ciphertext**: 1088 bytes
- **Shared Secret**: 32 bytes

## Installation

### From WordPress Admin

1. Download the plugin ZIP file
2. Go to WordPress Admin > Plugins > Add New > Upload Plugin
3. Choose the ZIP file and click "Install Now"
4. Activate the plugin

### Manual Installation

1. Upload the `neo-druidic-kyber` folder to `/wp-content/plugins/`
2. Activate the plugin through the 'Plugins' menu in WordPress
3. Go to Kyber Encryption settings to configure

## Configuration

### 1. API Setup

1. Navigate to **Kyber Encryption > Settings** in WordPress admin
2. Enter your Neo-Druidic API URL (default: `https://awen01.cc`)
3. (Optional) Add your API key if authentication is required
4. Click "Test Connection" to verify setup

### 2. Enable Encryption

Choose which content types to encrypt:
- **Posts**: Encrypt blog posts
- **Pages**: Encrypt static pages
- **Comments**: Encrypt user comments

### 3. Enable Auto-Key Generation

Enable "Auto-generate encryption keys for users" to automatically create Kyber keypairs when needed.

## Usage

### Encrypting Posts/Pages

1. Create or edit a post/page
2. In the **Quantum Encryption** meta box (right sidebar)
3. Check "Encrypt this content"
4. Publish or update the post

Your content is now quantum-safe encrypted!

### Shortcode Usage

Encrypt specific content blocks:

```
[ndk_encrypted]
This content is quantum-encrypted and only visible to logged-in users.
[/ndk_encrypted]
```

### Programmatic Usage

```php
// Encrypt content for a user
$encrypted_data = NDK_Encryption::encrypt_content( $content, $user_id );

// Decrypt content
$plaintext = NDK_Encryption::decrypt_content( $encrypted_data, $user_id );

// Generate keys for a user
NDK_Encryption::generate_user_keypair( $user_id );
```

## API Endpoints

The plugin communicates with these Kyber API endpoints:

- `GET /api/v1/kyber/info` - Get algorithm information
- `POST /api/v1/kyber/keypair/generate` - Generate new keypair
- `POST /api/v1/kyber/keypair/unlock` - Unlock encrypted private key
- `POST /api/v1/kyber/encrypt` - Encrypt message
- `POST /api/v1/kyber/decrypt` - Decrypt message

## Database Schema

The plugin creates one table: `wp_ndk_keys`

```sql
CREATE TABLE wp_ndk_keys (
    id bigint(20) AUTO_INCREMENT PRIMARY KEY,
    user_id bigint(20) NOT NULL,
    public_key text NOT NULL,
    encrypted_private_key text NOT NULL,
    salt varchar(255) NOT NULL,
    nonce varchar(255) NOT NULL,
    created_at datetime DEFAULT CURRENT_TIMESTAMP,
    updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY user_id (user_id)
);
```

## Security Considerations

### Key Management

- **Private keys** are encrypted with user-specific passphrases derived from WordPress credentials
- Keys are stored in the database with **AES-256 encryption**
- Each user has a unique keypair
- Lost passphrases = lost access to encrypted content (by design)

### Best Practices

1. **Backup Regularly**: Encrypted content cannot be recovered without keys
2. **Strong Passwords**: User passwords secure their private keys
3. **HTTPS Required**: Always use SSL/TLS for API communication
4. **API Key**: Use API key authentication in production
5. **Test First**: Test encryption on non-production content first

## Requirements

- **WordPress**: 5.8 or higher
- **PHP**: 7.4 or higher
- **Neo-Druidic API**: Active Kyber API endpoint
- **HTTPS**: Recommended for secure API communication

## Frequently Asked Questions

### Is this really quantum-safe?

Yes! ML-KEM-768 (Kyber) is the NIST-standardized post-quantum algorithm designed to resist attacks from quantum computers. It's part of the NIST Post-Quantum Cryptography project.

### What happens if I lose my encryption keys?

Encrypted content cannot be recovered without the proper keys. This is a feature, not a bug - true end-to-end encryption means only authorized users can decrypt content.

### Can I migrate encrypted content?

Yes, but you must export both the content and the encryption keys from the `wp_ndk_keys` table. Keys are user-specific and tied to WordPress user IDs.

### Does this slow down my site?

The encryption happens server-side via API calls. Performance impact depends on your API endpoint. For best performance, host the Kyber API on the same server or nearby infrastructure.

### Can I use my own Kyber API?

Yes! The plugin is designed to work with any compatible ML-KEM-768 API endpoint. Simply point the API URL to your own instance.

## Changelog

### 1.0.0 (2024-10-24)
- Initial release
- ML-KEM-768 (Kyber) integration
- Post, page, and comment encryption
- Automatic key management
- WordPress best practices compliance
- Admin dashboard with connection testing
- User key management interface
- Shortcode support

## Credits

- **Developed by**: WP-KyberCrypt Team
- **Algorithm**: NIST ML-KEM-768 (Kyber)
- **License**: GPL v3 or later

## Support

For support, documentation, and updates, visit: https://awen01.cc

## License

This plugin is licensed under the GPL v3 or later.

```
Copyright (C) 2024 WP-KyberCrypt Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
```

---

**Protect your WordPress content with quantum-safe encryption. The future is now.** 🔐
