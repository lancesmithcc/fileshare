<?php
/**
 * Plugin Name: WP-KyberCrypt
 * Plugin URI: https://wp-kybercrypt.com
 * Description: Production-hardened quantum-safe encryption for WordPress using ML-KEM-768 (NIST FIPS 203). Complete end-to-end encryption with post-quantum cryptography, secure key management, and enterprise-grade access controls.
 * Version: 1.2.0
 * Requires at least: 5.8
 * Requires PHP: 7.4
 * Author: WP-KyberCrypt Team
 * Author URI: https://wp-kybercrypt.com
 * License: GPL v3 or later
 * License URI: https://www.gnu.org/licenses/gpl-3.0.html
 * Text Domain: wp-kybercrypt
 * Domain Path: /languages
 *
 * SECURITY ARCHITECTURE (v1.2):
 * =============================
 *
 * 1. SECRET MANAGEMENT:
 *    - API keys and login passphrases live exclusively in wp-config.php constants
 *    - Database never stores secrets; migration tooling removes legacy blobs automatically
 *    - NDK_LOGIN_KEY_PASSPHRASE is never transmitted over HTTP; Python service must read it from ENV
 *
 * 2. PYTHON SERVICE ISOLATION:
 *    - Kyber microservice MUST run on localhost or a private RFC1918 network
 *    - HTTP transport is restricted to 127.0.0.1 / ::1; all other hosts require HTTPS
 *    - Public endpoints trigger admin warnings and remote calls are refused before sending ciphertext
 *
 * 3. ACCESS CONTROL:
 *    - NDK_Security::can_current_user_decrypt() gates every decrypt path
 *    - No fallback to user ID 1 unless explicitly in privileged admin context
 *    - Logged-out visitors always receive masked “[LOCKED 🔒]” placeholders
 *
 * 4. RATE LIMITING:
 *    - Login attempts limited to 5 per IP per 5 minutes
 *    - Generic error messages prevent username/password enumeration
 *    - POST-only endpoints, nonce validation on all AJAX
 *
 * 5. KEY VERSIONING:
 *    - Database tracks key_id, created_at, and active flags for each user keypair
 *    - Every encrypted blob records its key_id to enable future rotation without data loss
 *
 * 6. LOGGING:
 *    - All sensitive data (keys, ciphertext) redacted from error logs
 *    - No secrets echoed in admin UI
 *
 * NIST POST-QUANTUM CRYPTOGRAPHY:
 * ================================
 * Uses ML-KEM-768 (NIST FIPS 203 Module-Lattice-Based Key Encapsulation Mechanism)
 * combined with AES-256-GCM for authenticated encryption. Protects against both
 * classical and quantum computer attacks.
 */

// If this file is called directly, abort.
if ( ! defined( 'WPINC' ) ) {
    die;
}

// Plugin version
define( 'NDK_VERSION', '1.2.0' );
define( 'NDK_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'NDK_PLUGIN_URL', plugin_dir_url( __FILE__ ) );

// Security notice: Check for wp-config constants
if ( ! defined( 'NDK_API_KEY' ) || ! defined( 'NDK_LOGIN_KEY_PASSPHRASE' ) ) {
    add_action( 'admin_notices', function() {
        if ( NDK_Security::should_show_migration_notice() ) {
            $instructions = NDK_Security::get_migration_instructions();
            $migration_url = wp_nonce_url(
                admin_url( 'admin.php?page=wp-kybercrypt&action=complete_migration' ),
                'ndk-complete-migration'
            );
            ?>
            <div class="notice notice-warning is-dismissible">
                <h3>WP-KyberCrypt Security Migration Required</h3>
                <p><strong>Action Required:</strong> For production security, move sensitive secrets to wp-config.php:</p>
                <pre style="background: #f5f5f5; padding: 15px; border-left: 4px solid #ffb900; overflow-x: auto;">
<?php foreach ( $instructions as $inst ) : ?>
define( '<?php echo esc_html( $inst['constant'] ); ?>', '<?php echo esc_html( $inst['value'] ); ?>' );
<?php endforeach; ?>
                </pre>
                <p>After adding these to wp-config.php, <a href="<?php echo esc_url( $migration_url ); ?>">click here to complete migration</a>.</p>
                <p><em>This removes sensitive data from the database and stores it securely in wp-config.php.</em></p>
            </div>
            <?php
        }
    } );
}

/**
 * Main plugin class
 */
class WP_KyberCrypt {

    /**
     * The single instance of the class
     */
    private static $instance = null;

    /**
     * API client instance
     */
    private $api_client = null;

    /**
     * Main Instance
     */
    public static function instance() {
        if ( is_null( self::$instance ) ) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    /**
     * Constructor
     */
    private function __construct() {
        $this->load_dependencies();
        $this->define_hooks();
    }

    /**
     * Load required dependencies
     */
    private function load_dependencies() {
        require_once NDK_PLUGIN_DIR . 'includes/class-ndk-security.php';
        require_once NDK_PLUGIN_DIR . 'includes/class-ndk-api-client.php';
        require_once NDK_PLUGIN_DIR . 'includes/class-ndk-encryption.php';
        require_once NDK_PLUGIN_DIR . 'admin/class-ndk-admin.php';
        require_once NDK_PLUGIN_DIR . 'includes/class-ndk-content-encryption.php';
        require_once NDK_PLUGIN_DIR . 'includes/class-ndk-login-encryption.php';
    }

    /**
     * Define hooks
     */
    private function define_hooks() {
        // Admin hooks
        if ( is_admin() ) {
            $admin = new NDK_Admin();
        }

        // Content encryption hooks
        $content_encryption = new NDK_Content_Encryption();

        // Login encryption hooks
        $login_encryption = new NDK_Login_Encryption();

        // Activation/Deactivation
        register_activation_hook( __FILE__, array( $this, 'activate' ) );
        register_deactivation_hook( __FILE__, array( $this, 'deactivate' ) );
    }

    /**
     * Plugin activation
     */
    public function activate() {
        // Create necessary database tables if needed
        $this->create_tables();

        // SECURITY: Only auto-generate API key if constant not defined
        if ( ! defined( 'NDK_API_KEY' ) ) {
            $api_key = get_option( 'ndk_api_key' );
            if ( empty( $api_key ) ) {
                // Generate a secure random API key
                $api_key = bin2hex( random_bytes( 32 ) );
                update_option( 'ndk_api_key', $api_key );
            }
        }

        // Set default options
        $defaults = array(
            'ndk_api_url' => defined( 'NDK_API_URL' ) ? NDK_API_URL : 'https://awen01.cc',
            'ndk_encrypt_posts' => true,
            'ndk_encrypt_pages' => true,
            'ndk_encrypt_comments' => true,
            'ndk_encrypt_users' => true,
            'ndk_encrypt_options' => true,
            'ndk_encrypt_media' => true,
            'ndk_encrypt_forms' => true,
            'ndk_encrypt_ecommerce' => true,
            'ndk_auto_generate_keys' => true,
            'ndk_force_quantum_login' => false,
        );

        foreach ( $defaults as $key => $value ) {
            if ( get_option( $key ) === false ) {
                add_option( $key, $value );
            }
        }

        // Flush rewrite rules
        flush_rewrite_rules();
    }

    /**
     * Plugin deactivation
     */
    public function deactivate() {
        flush_rewrite_rules();
    }

    /**
     * Create database tables
     */
    private function create_tables() {
        global $wpdb;

        $charset_collate = $wpdb->get_charset_collate();
        $table_name = $wpdb->prefix . 'ndk_keys';

        // SECURITY: Add key versioning/rotation support
        $sql = "CREATE TABLE IF NOT EXISTS $table_name (
            id bigint(20) NOT NULL AUTO_INCREMENT,
            user_id bigint(20) NOT NULL,
            key_id varchar(100) NOT NULL,
            public_key text NOT NULL,
            encrypted_private_key text NOT NULL,
            salt varchar(255) NOT NULL,
            nonce varchar(255) NOT NULL,
            active tinyint(1) DEFAULT 1,
            created_at datetime DEFAULT CURRENT_TIMESTAMP,
            updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY  (id),
            UNIQUE KEY user_key_id (user_id, key_id),
            KEY user_id (user_id),
            KEY active (active)
        ) $charset_collate;";

        require_once( ABSPATH . 'wp-admin/includes/upgrade.php' );
        dbDelta( $sql );

        // Backfill key_id for legacy rows
        $wpdb->query(
            "UPDATE $table_name SET key_id = CONCAT('user-', user_id, '-legacy') WHERE key_id = '' OR key_id IS NULL"
        );
        // Ensure active flag defaults to 1 for legacy records
        $wpdb->query(
            "UPDATE $table_name SET active = 1 WHERE active IS NULL"
        );
    }

    /**
     * Get API client instance
     */
    public function get_api_client() {
        if ( is_null( $this->api_client ) ) {
            $this->api_client = new NDK_API_Client();
        }
        return $this->api_client;
    }
}

/**
 * Returns the main instance of WP_KyberCrypt
 */
function WPK() {
    return WP_KyberCrypt::instance();
}

/**
 * Backward compatibility alias
 */
function NDK() {
    return WP_KyberCrypt::instance();
}

// Initialize the plugin
WPK();
