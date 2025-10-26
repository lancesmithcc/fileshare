<?php
/**
 * Admin Settings Page
 *
 * @package WP_KyberCrypt
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}
?>

<div class="wrap ndk-admin-wrap">
    <h1 style="display: flex; align-items: center; gap: 15px;">
        <img src="<?php echo plugins_url( 'assets/logo.svg', dirname( dirname( __FILE__ ) ) ); ?>" alt="Logo" style="width: 48px; height: 48px;">
        <span>
            <?php _e( 'Neo-Druidic Kyber Encryption Settings', 'wp-kybercrypt' ); ?>
            <span class="ndk-badge">ML-KEM-768</span>
        </span>
    </h1>

    <p class="description">
        <?php _e( 'Configure quantum-safe encryption for your WordPress site using the NIST-standardized ML-KEM-768 (Kyber) post-quantum cryptographic algorithm.', 'wp-kybercrypt' ); ?>
    </p>

    <div class="ndk-admin-content">
        <div class="ndk-main-column">
            <form method="post" action="">
                <?php wp_nonce_field( 'ndk-save-settings' ); ?>

                <div class="ndk-card">
                    <h2><?php _e( 'API Connection', 'wp-kybercrypt' ); ?></h2>

                    <table class="form-table" role="presentation">
                        <tr>
                            <th scope="row">
                                <label for="ndk_api_url"><?php _e( 'API URL', 'wp-kybercrypt' ); ?></label>
                            </th>
                            <td>
                                <?php
                                $api_url = NDK_Security::get_api_url();
                                $api_url_display = ! empty( $api_url ) ? $api_url : 'https://awen01.cc';
                                ?>
                                <input
                                    type="url"
                                    id="ndk_api_url"
                                    name="ndk_api_url"
                                    value="<?php echo esc_attr( $api_url_display ); ?>"
                                    class="regular-text"
                                    required
                                >
                                <p class="description">
                                    <?php _e( 'The base URL of your Neo-Druidic Kyber API endpoint. For security, this should be localhost or a private network URL.', 'wp-kybercrypt' ); ?>
                                </p>
                                <p class="description">
                                    <?php _e( 'HTTP endpoints are only permitted for 127.0.0.1 / ::1. Remote or LAN services must use HTTPS and must never be exposed to the public internet.', 'wp-kybercrypt' ); ?>
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <th scope="row">
                                <?php _e( 'API Key', 'wp-kybercrypt' ); ?>
                            </th>
                            <td>
                                <?php
                                $api_key_configured = defined( 'NDK_API_KEY' ) && NDK_API_KEY;
                                ?>
                                <strong>
                                    <?php if ( $api_key_configured ) : ?>
                                        <span style="color: #46b450;">✅ CONFIGURED</span>
                                        <span style="color: #666; font-size: 12px;">(from wp-config.php)</span>
                                    <?php else : ?>
                                        <span style="color: #dc3232;">❌ NOT CONFIGURED</span>
                                    <?php endif; ?>
                                </strong>
                                <p class="description">
                                    <?php
                                    if ( defined( 'NDK_API_KEY' ) ) {
                                        _e( '<strong>Security:</strong> API key is securely stored in wp-config.php. Do not store in database.', 'wp-kybercrypt' );
                                    } else {
                                        printf(
                                            __( '<strong>Security Requirement:</strong> Define <code>NDK_API_KEY</code> in wp-config.php. The plugin no longer reads API keys from the database. See <a href="%s" target="_blank">Security Guide</a>.', 'wp-kybercrypt' ),
                                            plugins_url( 'SECURITY.md', dirname( dirname( __FILE__ ) ) )
                                        );
                                    }
                                    ?>
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <th scope="row">
                                <?php _e( 'Login Key Passphrase', 'wp-kybercrypt' ); ?>
                            </th>
                            <td>
                                <?php
                                $passphrase_configured = defined( 'NDK_LOGIN_KEY_PASSPHRASE' ) && NDK_LOGIN_KEY_PASSPHRASE;
                                ?>
                                <strong>
                                    <?php if ( $passphrase_configured ) : ?>
                                        <span style="color: #46b450;">✅ CONFIGURED</span>
                                        <span style="color: #666; font-size: 12px;">(from wp-config.php)</span>
                                    <?php else : ?>
                                        <span style="color: #dc3232;">❌ NOT CONFIGURED</span>
                                    <?php endif; ?>
                                </strong>
                                <p class="description">
                                    <?php
                                    if ( defined( 'NDK_LOGIN_KEY_PASSPHRASE' ) ) {
                                        _e( '<strong>Security:</strong> Login key passphrase is securely stored in wp-config.php.', 'wp-kybercrypt' );
                                    } else {
                                        printf(
                                            __( '<strong>Security Requirement:</strong> Define <code>NDK_LOGIN_KEY_PASSPHRASE</code> in wp-config.php. Passphrases are no longer loaded from the database. See <a href="%s" target="_blank">Security Guide</a>.', 'wp-kybercrypt' ),
                                            plugins_url( 'SECURITY.md', dirname( dirname( __FILE__ ) ) )
                                        );
                                    }
                                    ?>
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <th scope="row"><?php _e( 'Connection Status', 'wp-kybercrypt' ); ?></th>
                            <td>
                                <button type="button" id="ndk-test-connection" class="button button-secondary">
                                    <?php _e( 'Test Connection', 'wp-kybercrypt' ); ?>
                                </button>
                                <span id="ndk-connection-status"></span>
                            </td>
                        </tr>
                    </table>
                </div>

                <div class="ndk-card">
                    <h2><?php _e( 'Encryption Features', 'wp-kybercrypt' ); ?></h2>

                    <table class="form-table" role="presentation">
                        <tr>
                            <th scope="row"><?php _e( 'Content Types', 'wp-kybercrypt' ); ?></th>
                            <td>
                                <fieldset>
                                    <label>
                                        <input
                                            type="checkbox"
                                            name="ndk_encrypt_posts"
                                            value="1"
                                            <?php checked( get_option( 'ndk_encrypt_posts', false ) ); ?>
                                        >
                                        <?php _e( 'Enable encryption for Posts', 'wp-kybercrypt' ); ?>
                                    </label>
                                    <br>
                                    <label>
                                        <input
                                            type="checkbox"
                                            name="ndk_encrypt_pages"
                                            value="1"
                                            <?php checked( get_option( 'ndk_encrypt_pages', false ) ); ?>
                                        >
                                        <?php _e( 'Enable encryption for Pages', 'wp-kybercrypt' ); ?>
                                    </label>
                                    <br>
                                    <label>
                                        <input
                                            type="checkbox"
                                            name="ndk_encrypt_comments"
                                            value="1"
                                            <?php checked( get_option( 'ndk_encrypt_comments', false ) ); ?>
                                        >
                                        <?php _e( 'Enable encryption for Comments', 'wp-kybercrypt' ); ?>
                                    </label>
                                </fieldset>
                            </td>
                        </tr>

                        <tr>
                            <th scope="row"><?php _e( 'Key Management', 'wp-kybercrypt' ); ?></th>
                            <td>
                                <label>
                                    <input
                                        type="checkbox"
                                        name="ndk_auto_generate_keys"
                                        value="1"
                                        <?php checked( get_option( 'ndk_auto_generate_keys', true ) ); ?>
                                    >
                                    <?php _e( 'Auto-generate encryption keys for users', 'wp-kybercrypt' ); ?>
                                </label>
                                <p class="description">
                                    <?php _e( 'Automatically generate Kyber keypairs for users when needed. Keys are encrypted with user credentials.', 'wp-kybercrypt' ); ?>
                                </p>
                            </td>
                        </tr>
                    </table>
                </div>

                <div class="ndk-card">
                    <h2><?php _e( 'Security Settings', 'wp-kybercrypt' ); ?></h2>

                    <table class="form-table" role="presentation">
                        <tr>
                            <th scope="row"><?php _e( 'Quantum Login Enforcement', 'wp-kybercrypt' ); ?></th>
                            <td>
                                <label>
                                    <input
                                        type="checkbox"
                                        name="ndk_force_quantum_login"
                                        value="1"
                                        <?php checked( get_option( 'ndk_force_quantum_login', false ) ); ?>
                                    >
                                    <?php _e( 'Force quantum-safe login (block classic wp-login.php)', 'wp-kybercrypt' ); ?>
                                </label>
                                <p class="description">
                                    <?php _e( 'When enabled, all login attempts must use quantum-safe encrypted authentication. Classic username/password forms, XML-RPC, and REST Basic Auth will be blocked. <strong>Warning:</strong> Only enable this after verifying quantum login works correctly.', 'wp-kybercrypt' ); ?>
                                </p>
                            </td>
                        </tr>
                    </table>
                </div>

                <p class="submit">
                    <button type="submit" name="ndk_save_settings" class="button button-primary button-large">
                        <?php _e( 'Save Settings', 'wp-kybercrypt' ); ?>
                    </button>
                </p>
            </form>
        </div>

        <div class="ndk-sidebar-column">
            <div class="ndk-info-card">
                <h3><?php _e( 'About ML-KEM-768', 'wp-kybercrypt' ); ?></h3>
                <p>
                    <?php _e( 'ML-KEM-768 is the NIST-standardized post-quantum key encapsulation mechanism based on the Kyber algorithm.', 'wp-kybercrypt' ); ?>
                </p>
                <ul>
                    <li><strong><?php _e( 'Security Level:', 'wp-kybercrypt' ); ?></strong> NIST Level 3 (AES-192 equivalent)</li>
                    <li><strong><?php _e( 'Quantum-Safe:', 'wp-kybercrypt' ); ?></strong> <?php _e( 'Resistant to quantum computer attacks', 'wp-kybercrypt' ); ?></li>
                    <li><strong><?php _e( 'Standardized:', 'wp-kybercrypt' ); ?></strong> NIST PQC 2024</li>
                </ul>
            </div>

            <div class="ndk-info-card">
                <h3><?php _e( 'Quick Start', 'wp-kybercrypt' ); ?></h3>
                <ol>
                    <li><?php _e( 'Configure API connection above', 'wp-kybercrypt' ); ?></li>
                    <li><?php _e( 'Test the connection', 'wp-kybercrypt' ); ?></li>
                    <li><?php _e( 'Enable encryption for desired content types', 'wp-kybercrypt' ); ?></li>
                    <li><?php _e( 'Edit a post/page and enable encryption in the sidebar', 'wp-kybercrypt' ); ?></li>
                </ol>
            </div>

            <div class="ndk-info-card">
                <h3><?php _e( 'Support', 'wp-kybercrypt' ); ?></h3>
                <p>
                    <?php printf(
                        __( 'Visit <a href="%s" target="_blank">Neo-Druidic Society</a> for documentation and support.', 'wp-kybercrypt' ),
                        'https://awen01.cc'
                    ); ?>
                </p>
            </div>
        </div>
    </div>
</div>
