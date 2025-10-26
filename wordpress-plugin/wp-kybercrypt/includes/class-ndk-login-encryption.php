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

        // SECURITY: Block classic login if force_quantum_login enabled
        add_action( 'login_init', array( $this, 'block_classic_login' ) );
        add_filter( 'xmlrpc_enabled', array( $this, 'block_xmlrpc_when_quantum_forced' ) );
        add_filter( 'rest_authentication_errors', array( $this, 'block_rest_basic_auth' ) );
    }

    /**
     * Ensure site has a keypair for login encryption
     */
    public function ensure_site_keypair() {
        $site_keys = get_option( 'ndk_site_login_keys' );

        if ( ! NDK_Security::get_login_key_passphrase() ) {
            add_action( 'admin_notices', function() {
                echo '<div class="notice notice-error"><p><strong>WP-KyberCrypt:</strong> Define <code>NDK_LOGIN_KEY_PASSPHRASE</code> in wp-config.php to unlock encrypted logins.</p></div>';
            } );
        }

        if ( ! $site_keys || ! isset( $site_keys['public_key'] ) ) {
            $this->generate_site_keypair();
        }
    }

    /**
     * Generate site-wide keypair for login encryption
     */
    private function generate_site_keypair() {
        $api = NDK()->get_api_client();

        // Require passphrase constant before generating
        $passphrase = NDK_Security::get_login_key_passphrase();
        if ( ! $passphrase ) {
            error_log( 'WP-KyberCrypt: NDK_LOGIN_KEY_PASSPHRASE must be defined before generating site keypair' );
            return false;
        }

        // Passphrase is managed locally by the Python service; no need to send it over HTTP.
        $result = $api->generate_keypair( null );

        if ( ! $result['success'] ) {
            error_log( 'WP-KyberCrypt: Failed to generate site login keypair' );
            return false;
        }

        $data = $result['data'];

        // Store keys WITHOUT passphrase in database
        $site_keys = array(
            'public_key'            => $data['public_key'],
            'encrypted_private_key' => $data['encrypted_private_key'],
            'salt'                  => $data['salt'],
            'nonce'                 => $data['nonce'],
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
        // SECURITY: Validate request method
        $request_method = isset( $_SERVER['REQUEST_METHOD'] ) ? strtoupper( $_SERVER['REQUEST_METHOD'] ) : '';
        if ( $request_method !== 'POST' ) {
            wp_send_json_error( array( 'message' => 'Login failed.' ) );
        }

        // SECURITY: Rate limiting
        $ip = isset( $_SERVER['REMOTE_ADDR'] ) ? $_SERVER['REMOTE_ADDR'] : '0.0.0.0';
        $rate_limit = NDK_Security::check_login_rate_limit( $ip );
        if ( ! $rate_limit['allowed'] ) {
            NDK_Security::record_login_attempt( $ip, false );
            error_log( 'WP-KyberCrypt: login throttled for IP ' . NDK_Security::sanitize_log( $ip ) );
            wp_send_json_error( array( 'message' => 'Login failed.' ) );
        }

        // Verify nonce
        if ( ! isset( $_POST['nonce'] ) || ! wp_verify_nonce( $_POST['nonce'], 'ndk-login-encryption' ) ) {
            NDK_Security::record_login_attempt( $ip, false );
            wp_send_json_error( array( 'message' => 'Login failed.' ) );
        }

        // Get encrypted credentials
        $encrypted_username = isset( $_POST['encrypted_username'] ) ? json_decode( stripslashes( $_POST['encrypted_username'] ), true ) : null;
        $encrypted_password = isset( $_POST['encrypted_password'] ) ? json_decode( stripslashes( $_POST['encrypted_password'] ), true ) : null;
        $remember = isset( $_POST['remember'] ) && $_POST['remember'] === 'true';

        if ( ! $encrypted_username || ! $encrypted_password ) {
            NDK_Security::record_login_attempt( $ip, false );
            wp_send_json_error( array( 'message' => 'Login failed.' ) );
        }

        // Decrypt credentials
        $username = $this->decrypt_credential( $encrypted_username );
        $password = $this->decrypt_credential( $encrypted_password );

        if ( ! $username || ! $password ) {
            NDK_Security::record_login_attempt( $ip, false );
            wp_send_json_error( array( 'message' => 'Login failed.' ) );
        }

        // Authenticate
        $creds = array(
            'user_login'    => $username,
            'user_password' => $password,
            'remember'      => $remember,
        );

        $user = wp_signon( $creds, is_ssl() );

        if ( is_wp_error( $user ) ) {
            // SECURITY: Generic error message, don't leak details
            NDK_Security::record_login_attempt( $ip, false );
            wp_send_json_error( array( 'message' => 'Login failed.' ) );
        }

        // Success - clear rate limit
        NDK_Security::record_login_attempt( $ip, true );

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

        // Require passphrase constant even though we no longer transmit it
        if ( ! NDK_Security::get_login_key_passphrase() ) {
            error_log( 'WP-KyberCrypt: No login key passphrase configured' );
            return false;
        }

        $api = NDK()->get_api_client();

        // Unlock private key without transmitting the passphrase
        $unlock_result = $api->unlock_keypair(
            $site_keys['encrypted_private_key'],
            $site_keys['salt'],
            $site_keys['nonce'],
            null
        );

        if ( ! $unlock_result['success'] ) {
            error_log( 'WP-KyberCrypt: Failed to unlock site private key' );
            return false;
        }

        $private_key = $unlock_result['data']['private_key'];

        // Decrypt the credential
        $decrypt_result = $api->decrypt(
            $private_key,
            $encrypted_data['kem_ciphertext'],
            $encrypted_data['wrapped_key'],
            $encrypted_data['wrap_nonce'],
            $encrypted_data['body_nonce'],
            $encrypted_data['ciphertext']
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
     * Block classic wp-login.php if force_quantum_login is enabled
     */
    public function block_classic_login() {
        // Only enforce if option is enabled
        if ( ! get_option( 'ndk_force_quantum_login', false ) ) {
            return;
        }

        // Allow AJAX requests (for our encrypted login endpoint)
        if ( defined( 'DOING_AJAX' ) && DOING_AJAX ) {
            return;
        }

        // If this is a classic login POST (username/password fields present)
        if ( isset( $_POST['log'] ) || isset( $_POST['pwd'] ) ) {
            wp_die(
                '<h1>Quantum-Safe Login Required</h1>' .
                '<p>This site requires quantum-safe encrypted authentication. Classic username/password login is disabled.</p>' .
                '<p><a href="' . esc_url( wp_login_url() ) . '">← Back to Login</a></p>',
                'Quantum Login Required',
                array( 'response' => 403 )
            );
        }
    }

    /**
     * Block XML-RPC when force_quantum_login is enabled
     */
    public function block_xmlrpc_when_quantum_forced( $enabled ) {
        if ( get_option( 'ndk_force_quantum_login', false ) ) {
            return false;
        }
        return $enabled;
    }

    /**
     * Block REST API basic auth when force_quantum_login is enabled
     */
    public function block_rest_basic_auth( $result ) {
        // Only enforce if option is enabled
        if ( ! get_option( 'ndk_force_quantum_login', false ) ) {
            return $result;
        }

        // If already authenticated (e.g., via session), allow
        if ( is_user_logged_in() ) {
            return $result;
        }

        // Check if HTTP Basic Auth is being attempted
        if ( isset( $_SERVER['PHP_AUTH_USER'] ) || isset( $_SERVER['HTTP_AUTHORIZATION'] ) ) {
            return new WP_Error(
                'rest_quantum_login_required',
                'Quantum-safe authentication required. Basic auth is disabled.',
                array( 'status' => 403 )
            );
        }

        return $result;
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
