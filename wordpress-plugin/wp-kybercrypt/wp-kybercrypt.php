<?php
/**
 * Plugin Name: WP-KyberCrypt
 * Plugin URI: https://wp-kybercrypt.com
 * Description: Complete quantum-safe encryption for WordPress using ML-KEM-768 (NIST FIPS 203). Encrypts posts, pages, users, media, forms, comments, and e-commerce data with post-quantum cryptography.
 * Version: 1.0.0
 * Requires at least: 5.8
 * Requires PHP: 7.4
 * Author: WP-KyberCrypt Team
 * Author URI: https://wp-kybercrypt.com
 * License: GPL v3 or later
 * License URI: https://www.gnu.org/licenses/gpl-3.0.html
 * Text Domain: wp-kybercrypt
 * Domain Path: /languages
 */

// If this file is called directly, abort.
if ( ! defined( 'WPINC' ) ) {
    die;
}

// Plugin version
define( 'NDK_VERSION', '1.0.0' );
define( 'NDK_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'NDK_PLUGIN_URL', plugin_dir_url( __FILE__ ) );

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

        // Auto-generate API key on activation
        $api_key = get_option( 'ndk_api_key' );
        if ( empty( $api_key ) ) {
            // Generate a secure random API key
            $api_key = bin2hex( random_bytes( 32 ) );
            update_option( 'ndk_api_key', $api_key );
        }

        // Set default options
        $defaults = array(
            'ndk_api_url' => 'https://awen01.cc',
            'ndk_encrypt_posts' => true,
            'ndk_encrypt_pages' => true,
            'ndk_encrypt_comments' => true,
            'ndk_encrypt_users' => true,
            'ndk_encrypt_options' => true,
            'ndk_encrypt_media' => true,
            'ndk_encrypt_forms' => true,
            'ndk_encrypt_ecommerce' => true,
            'ndk_auto_generate_keys' => true,
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

        $sql = "CREATE TABLE IF NOT EXISTS $table_name (
            id bigint(20) NOT NULL AUTO_INCREMENT,
            user_id bigint(20) NOT NULL,
            public_key text NOT NULL,
            encrypted_private_key text NOT NULL,
            salt varchar(255) NOT NULL,
            nonce varchar(255) NOT NULL,
            created_at datetime DEFAULT CURRENT_TIMESTAMP,
            updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY  (id),
            KEY user_id (user_id)
        ) $charset_collate;";

        require_once( ABSPATH . 'wp-admin/includes/upgrade.php' );
        dbDelta( $sql );
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
