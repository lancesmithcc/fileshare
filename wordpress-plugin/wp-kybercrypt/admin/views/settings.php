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
    <h1>
        <?php _e( 'Neo-Druidic Kyber Encryption Settings', 'wp-kybercrypt' ); ?>
        <span class="ndk-badge">ML-KEM-768</span>
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
                                <input
                                    type="url"
                                    id="ndk_api_url"
                                    name="ndk_api_url"
                                    value="<?php echo esc_attr( get_option( 'ndk_api_url', 'https://awen01.cc' ) ); ?>"
                                    class="regular-text"
                                    required
                                >
                                <p class="description">
                                    <?php _e( 'The base URL of your Neo-Druidic Kyber API endpoint.', 'wp-kybercrypt' ); ?>
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <th scope="row">
                                <label for="ndk_api_key"><?php _e( 'API Key', 'wp-kybercrypt' ); ?></label>
                            </th>
                            <td>
                                <input
                                    type="password"
                                    id="ndk_api_key"
                                    name="ndk_api_key"
                                    value="<?php echo esc_attr( get_option( 'ndk_api_key', '' ) ); ?>"
                                    class="regular-text"
                                    autocomplete="off"
                                >
                                <p class="description">
                                    <?php _e( 'Optional API key for authentication (if required by your API endpoint).', 'wp-kybercrypt' ); ?>
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
