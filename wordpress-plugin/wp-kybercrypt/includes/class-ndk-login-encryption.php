<?php
/**
 * Login Encryption - Quantum-safe WordPress authentication
 *
 * @package WP_KyberCrypt
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NDK_Login_Encryption {

    /**
     * Constructor
     */
    public function __construct() {
        // Initialize site keypair on activation
        add_action( 'init', array( $this, 'ensure_site_keypair' ) );

        // Add login page scripts
        add_action( 'login_enqueue_scripts', array( $this, 'enqueue_login_scripts' ) );

        // AJAX endpoint for getting public key
        add_action( 'wp_ajax_nopriv_ndk_get_login_pubkey', array( $this, 'ajax_get_login_pubkey' ) );

        // AJAX endpoint for encrypted login
        add_action( 'wp_ajax_nopriv_ndk_encrypted_login', array( $this, 'ajax_encrypted_login' ) );

        // Also hook into embedded login forms (like in encrypted content)
        add_action( 'wp_enqueue_scripts', array( $this, 'enqueue_frontend_login_scripts' ) );

        // AJAX endpoint for getting API URL
        add_action( 'wp_ajax_nopriv_ndk_get_api_url', array( $this, 'ajax_get_api_url' ) );

        // Add quantum security badge to login form
        add_action( 'login_form', array( $this, 'add_quantum_security_badge' ) );
        add_action( 'login_footer', array( $this, 'add_login_footer_badge' ) );
    }

    /**
     * Ensure site has a keypair for login encryption
     */
    public function ensure_site_keypair() {
        $site_keys = get_option( 'ndk_site_login_keys' );

        if ( ! $site_keys || ! isset( $site_keys['public_key'] ) ) {
            $this->generate_site_keypair();
        }
    }

    /**
     * Generate site-wide keypair for login encryption
     */
    private function generate_site_keypair() {
        $api = NDK()->get_api_client();

        // Generate with a strong site-specific passphrase
        $passphrase = hash( 'sha256', AUTH_KEY . SECURE_AUTH_KEY . 'ndk-site-login' );

        $result = $api->generate_keypair( $passphrase );

        if ( ! $result['success'] ) {
            error_log( 'WP-KyberCrypt: Failed to generate site login keypair' );
            return false;
        }

        $data = $result['data'];

        $site_keys = array(
            'public_key'            => $data['public_key'],
            'encrypted_private_key' => $data['encrypted_private_key'],
            'salt'                  => $data['salt'],
            'nonce'                 => $data['nonce'],
            'passphrase'            => $passphrase,
        );

        update_option( 'ndk_site_login_keys', $site_keys );

        return true;
    }

    /**
     * Enqueue scripts for login page
     */
    public function enqueue_login_scripts() {
        wp_enqueue_script(
            'ndk-login-encryption',
            NDK_PLUGIN_URL . 'admin/js/login-encryption.js',
            array( 'jquery' ),
            NDK_VERSION,
            true
        );

        wp_localize_script(
            'ndk-login-encryption',
            'ndkLogin',
            array(
                'ajaxUrl' => admin_url( 'admin-ajax.php' ),
                'nonce'   => wp_create_nonce( 'ndk-login-encryption' ),
            )
        );
    }

    /**
     * Enqueue scripts for frontend login forms
     */
    public function enqueue_frontend_login_scripts() {
        // Only on pages with login forms
        if ( ! is_user_logged_in() ) {
            wp_enqueue_script(
                'ndk-login-encryption',
                NDK_PLUGIN_URL . 'admin/js/login-encryption.js',
                array( 'jquery' ),
                NDK_VERSION,
                true
            );

            wp_localize_script(
                'ndk-login-encryption',
                'ndkLogin',
                array(
                    'ajaxUrl' => admin_url( 'admin-ajax.php' ),
                    'nonce'   => wp_create_nonce( 'ndk-login-encryption' ),
                )
            );
        }
    }

    /**
     * AJAX: Get API URL
     */
    public function ajax_get_api_url() {
        $api_url = get_option( 'ndk_api_url', 'https://awen01.cc' );

        wp_send_json_success( array(
            'api_url' => $api_url,
        ) );
    }

    /**
     * AJAX: Get public key for login encryption
     */
    public function ajax_get_login_pubkey() {
        $site_keys = get_option( 'ndk_site_login_keys' );

        if ( ! $site_keys || ! isset( $site_keys['public_key'] ) ) {
            wp_send_json_error( array( 'message' => 'Site keypair not initialized' ) );
        }

        wp_send_json_success( array(
            'public_key' => $site_keys['public_key'],
        ) );
    }

    /**
     * AJAX: Handle encrypted login
     */
    public function ajax_encrypted_login() {
        // Verify nonce
        if ( ! isset( $_POST['nonce'] ) || ! wp_verify_nonce( $_POST['nonce'], 'ndk-login-encryption' ) ) {
            wp_send_json_error( array( 'message' => 'Invalid nonce' ) );
        }

        // Get encrypted credentials
        $encrypted_username = isset( $_POST['encrypted_username'] ) ? json_decode( stripslashes( $_POST['encrypted_username'] ), true ) : null;
        $encrypted_password = isset( $_POST['encrypted_password'] ) ? json_decode( stripslashes( $_POST['encrypted_password'] ), true ) : null;
        $remember = isset( $_POST['remember'] ) && $_POST['remember'] === 'true';

        if ( ! $encrypted_username || ! $encrypted_password ) {
            wp_send_json_error( array( 'message' => 'Missing credentials' ) );
        }

        // Decrypt credentials
        $username = $this->decrypt_credential( $encrypted_username );
        $password = $this->decrypt_credential( $encrypted_password );

        if ( ! $username || ! $password ) {
            wp_send_json_error( array( 'message' => 'Failed to decrypt credentials' ) );
        }

        // Authenticate
        $creds = array(
            'user_login'    => $username,
            'user_password' => $password,
            'remember'      => $remember,
        );

        $user = wp_signon( $creds, is_ssl() );

        if ( is_wp_error( $user ) ) {
            wp_send_json_error( array(
                'message' => $user->get_error_message(),
            ) );
        }

        // Success - return redirect URL
        $redirect_to = isset( $_POST['redirect_to'] ) ? esc_url_raw( $_POST['redirect_to'] ) : admin_url();

        wp_send_json_success( array(
            'message'     => 'Login successful',
            'redirect_to' => $redirect_to,
        ) );
    }

    /**
     * Decrypt credential using site keypair
     */
    private function decrypt_credential( $encrypted_data ) {
        $site_keys = get_option( 'ndk_site_login_keys' );

        if ( ! $site_keys ) {
            return false;
        }

        $api = NDK()->get_api_client();

        // Unlock private key
        $unlock_result = $api->unlock_private_key(
            $site_keys['encrypted_private_key'],
            $site_keys['passphrase'],
            $site_keys['salt'],
            $site_keys['nonce']
        );

        if ( ! $unlock_result['success'] ) {
            error_log( 'WP-KyberCrypt: Failed to unlock site private key' );
            return false;
        }

        $private_key = $unlock_result['data']['private_key'];

        // Decrypt the credential
        $decrypt_result = $api->decrypt(
            $encrypted_data['ciphertext'],
            $private_key
        );

        if ( ! $decrypt_result['success'] ) {
            error_log( 'WP-KyberCrypt: Failed to decrypt credential' );
            return false;
        }

        return $decrypt_result['data']['plaintext'];
    }

    /**
     * Get site public key (for admin display)
     */
    public static function get_site_public_key() {
        $site_keys = get_option( 'ndk_site_login_keys' );
        return $site_keys ? $site_keys['public_key'] : null;
    }

    /**
     * Regenerate site keypair
     */
    public static function regenerate_site_keypair() {
        $instance = new self();
        return $instance->generate_site_keypair();
    }

    /**
     * Add quantum security badge to login form
     */
    public function add_quantum_security_badge() {
        ?>
        <div class="ndk-quantum-badge" style="margin-bottom: 16px; padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; text-align: center; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);">
            <div style="color: #fff; font-size: 18px; margin-bottom: 4px;">🔐 Quantum-Safe Login</div>
            <div style="color: rgba(255,255,255,0.9); font-size: 12px; font-weight: 500;">Protected with ML-KEM-768 Post-Quantum Encryption</div>
        </div>
        <?php
    }

    /**
     * Add quantum security footer badge
     */
    public function add_login_footer_badge() {
        ?>
        <style>
            .ndk-quantum-badge {
                animation: ndk-pulse 2s ease-in-out infinite;
            }
            @keyframes ndk-pulse {
                0%, 100% { box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3); }
                50% { box-shadow: 0 4px 25px rgba(102, 126, 234, 0.5); }
            }
            #loginform {
                border-top: 3px solid #667eea !important;
            }
        </style>
        <div style="text-align: center; margin-top: 20px; color: #667eea; font-size: 11px;">
            <strong>🛡️ Your login credentials are encrypted with NIST-standardized post-quantum cryptography</strong>
        </div>
        <?php
    }
}
