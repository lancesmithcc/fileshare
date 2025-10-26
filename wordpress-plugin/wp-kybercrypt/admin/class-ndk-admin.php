<?php
/**
 * Admin functionality
 *
 * @package WP_KyberCrypt
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NDK_Admin {

    /**
     * Constructor
     */
    public function __construct() {
        add_action( 'admin_menu', array( $this, 'add_admin_menu' ) );
        add_action( 'admin_init', array( $this, 'register_settings' ) );
        add_action( 'admin_enqueue_scripts', array( $this, 'enqueue_admin_scripts' ) );
        add_action( 'wp_ajax_ndk_test_connection', array( $this, 'ajax_test_connection' ) );
        add_action( 'wp_ajax_ndk_generate_keys', array( $this, 'ajax_generate_keys' ) );
    }

    /**
     * Add admin menu
     */
    public function add_admin_menu() {
        add_menu_page(
            __( 'Kyber Encryption', 'wp-kybercrypt' ),
            __( 'Kyber Encryption', 'wp-kybercrypt' ),
            'manage_options',
            'wp-kybercrypt',
            array( $this, 'render_settings_page' ),
            'dashicons-shield',
            80
        );

        add_submenu_page(
            'wp-kybercrypt',
            __( 'Settings', 'wp-kybercrypt' ),
            __( 'Settings', 'wp-kybercrypt' ),
            'manage_options',
            'wp-kybercrypt',
            array( $this, 'render_settings_page' )
        );

        add_submenu_page(
            'wp-kybercrypt',
            __( 'User Keys', 'wp-kybercrypt' ),
            __( 'User Keys', 'wp-kybercrypt' ),
            'manage_options',
            'ndk-user-keys',
            array( $this, 'render_user_keys_page' )
        );
    }

    /**
     * Register settings
     */
    public function register_settings() {
        // API Settings
        register_setting( 'ndk_api_settings', 'ndk_api_url' );
        register_setting( 'ndk_api_settings', 'ndk_api_key' );

        // Feature Settings
        register_setting( 'ndk_feature_settings', 'ndk_encrypt_posts' );
        register_setting( 'ndk_feature_settings', 'ndk_encrypt_pages' );
        register_setting( 'ndk_feature_settings', 'ndk_encrypt_comments' );
        register_setting( 'ndk_feature_settings', 'ndk_auto_generate_keys' );

        // Security Settings
        register_setting( 'ndk_security_settings', 'ndk_force_quantum_login' );

        // Sanitize callbacks
        add_filter( 'sanitize_option_ndk_api_url', 'esc_url_raw' );
        add_filter( 'sanitize_option_ndk_api_key', 'sanitize_text_field' );
    }

    /**
     * Enqueue admin scripts
     */
    public function enqueue_admin_scripts( $hook ) {
        if ( strpos( $hook, 'wp-kybercrypt' ) === false && strpos( $hook, 'ndk-' ) === false ) {
            return;
        }

        wp_enqueue_style( 'ndk-admin', NDK_PLUGIN_URL . 'admin/css/admin.css', array(), NDK_VERSION );
        wp_enqueue_script( 'ndk-admin', NDK_PLUGIN_URL . 'admin/js/admin.js', array( 'jquery' ), NDK_VERSION, true );

        wp_localize_script( 'ndk-admin', 'ndkAdmin', array(
            'ajaxurl' => admin_url( 'admin-ajax.php' ),
            'nonce'   => wp_create_nonce( 'ndk-admin-nonce' ),
        ) );
    }

    /**
     * Render settings page
     */
    public function render_settings_page() {
        if ( ! current_user_can( 'manage_options' ) ) {
            return;
        }

        if ( isset( $_GET['action'] ) && $_GET['action'] === 'complete_migration' ) {
            if ( ! isset( $_GET['_wpnonce'] ) || ! wp_verify_nonce( $_GET['_wpnonce'], 'ndk-complete-migration' ) ) {
                wp_die( esc_html__( 'Security check failed.', 'wp-kybercrypt' ) );
            }
            NDK_Security::complete_migration();
            echo '<div class="notice notice-success"><p>' . esc_html__( 'Sensitive secrets were removed from the database.', 'wp-kybercrypt' ) . '</p></div>';
        }

        // Handle form submission
        if ( isset( $_POST['ndk_save_settings'] ) && check_admin_referer( 'ndk-save-settings' ) ) {
            update_option( 'ndk_api_url', esc_url_raw( $_POST['ndk_api_url'] ) );
            update_option( 'ndk_encrypt_posts', isset( $_POST['ndk_encrypt_posts'] ) );
            update_option( 'ndk_encrypt_pages', isset( $_POST['ndk_encrypt_pages'] ) );
            update_option( 'ndk_encrypt_comments', isset( $_POST['ndk_encrypt_comments'] ) );
            update_option( 'ndk_auto_generate_keys', isset( $_POST['ndk_auto_generate_keys'] ) );
            update_option( 'ndk_force_quantum_login', isset( $_POST['ndk_force_quantum_login'] ) );

            echo '<div class="notice notice-success"><p>' . __( 'Settings saved successfully!', 'wp-kybercrypt' ) . '</p></div>';
        }

        include NDK_PLUGIN_DIR . 'admin/views/settings.php';
    }

    /**
     * Render user keys page
     */
    public function render_user_keys_page() {
        if ( ! current_user_can( 'manage_options' ) ) {
            return;
        }

        global $wpdb;
        $table_name = $wpdb->prefix . 'ndk_keys';

        $users_with_keys = $wpdb->get_results(
            "SELECT k.*, u.user_login, u.user_email
             FROM $table_name k
             LEFT JOIN {$wpdb->users} u ON k.user_id = u.ID
             ORDER BY k.created_at DESC"
        );

        include NDK_PLUGIN_DIR . 'admin/views/user-keys.php';
    }

    /**
     * AJAX: Test connection
     */
    public function ajax_test_connection() {
        check_ajax_referer( 'ndk-admin-nonce', 'nonce' );

        if ( ! current_user_can( 'manage_options' ) ) {
            wp_send_json_error( array( 'message' => 'Unauthorized' ) );
        }

        $api = NDK()->get_api_client();
        $result = $api->test_connection();

        if ( $result['success'] ) {
            wp_send_json_success( array( 'message' => $result['message'] ) );
        } else {
            wp_send_json_error( array( 'message' => $result['message'] ) );
        }
    }

    /**
     * AJAX: Generate keys for user
     */
    public function ajax_generate_keys() {
        check_ajax_referer( 'ndk-admin-nonce', 'nonce' );

        if ( ! current_user_can( 'manage_options' ) ) {
            wp_send_json_error( array( 'message' => 'Unauthorized' ) );
        }

        $user_id = isset( $_POST['user_id'] ) ? intval( $_POST['user_id'] ) : 0;

        if ( ! $user_id ) {
            wp_send_json_error( array( 'message' => 'Invalid user ID' ) );
        }

        $result = NDK_Encryption::generate_user_keypair( $user_id );

        if ( $result ) {
            wp_send_json_success( array( 'message' => 'Keys generated successfully!' ) );
        } else {
            wp_send_json_error( array( 'message' => 'Failed to generate keys' ) );
        }
    }
}
