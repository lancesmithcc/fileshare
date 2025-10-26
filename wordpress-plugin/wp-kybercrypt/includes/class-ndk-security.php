<?php
/**
 * Security Helpers for WP-KyberCrypt
 *
 * @package WP_KyberCrypt
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NDK_Security {

    /**
     * Check if current user can decrypt content
     *
     * @param string $context Context like 'woo_order', 'gravity_forms', 'user_meta', 'post_content'
     * @param int    $owner_user_id The user ID who owns the encrypted data
     * @return bool
     */
    public static function can_current_user_decrypt( $context, $owner_user_id = 0 ) {
        // Never decrypt for logged-out users
        if ( ! is_user_logged_in() ) {
            return false;
        }

        $current_user_id = get_current_user_id();

        // User can always decrypt their own data
        if ( $owner_user_id && $current_user_id === (int) $owner_user_id ) {
            return true;
        }

        // Administrators and high-level capabilities can decrypt
        if ( current_user_can( 'manage_options' ) ) {
            return true;
        }

        // WooCommerce shop managers
        if ( $context === 'woo_order' && current_user_can( 'manage_woocommerce' ) ) {
            return true;
        }

        // User editors can view user meta
        if ( $context === 'user_meta' && current_user_can( 'edit_users' ) ) {
            return true;
        }

        // Gravity Forms administrators
        if ( $context === 'gravity_forms' && current_user_can( 'gravityforms_edit_entries' ) ) {
            return true;
        }

        // Default deny
        return false;
    }

    /**
     * Get masked value for when decryption is not allowed
     *
     * @return string
     */
    public static function get_masked_value() {
        return '[LOCKED 🔒]';
    }

    /**
     * Normalize host string for comparisons
     *
     * @param string $host Raw host
     * @return string
     */
    private static function normalize_host( $host ) {
        if ( empty( $host ) ) {
            return '';
        }

        $host = strtolower( trim( $host ) );

        if ( substr( $host, 0, 1 ) === '[' && substr( $host, -1 ) === ']' ) {
            $host = substr( $host, 1, -1 );
        }

        return $host;
    }

    /**
     * Determine if host refers to local loopback
     *
     * @param string $host Host string
     * @return bool
     */
    private static function is_loopback_host( $host ) {
        $host = self::normalize_host( $host );
        return in_array( $host, array( '127.0.0.1', 'localhost', '::1' ), true );
    }

    /**
     * Validate API URL for security
     *
     * @param string $url The API URL to validate
     * @return array Array with 'valid' boolean and 'error' message
     */
    public static function validate_api_url( $url ) {
        if ( empty( $url ) ) {
            return array(
                'valid' => false,
                'error' => 'API URL cannot be empty.',
            );
        }

        $parsed = parse_url( $url );

        if ( ! $parsed || empty( $parsed['scheme'] ) || empty( $parsed['host'] ) ) {
            return array(
                'valid' => false,
                'error' => 'Invalid API URL format.',
            );
        }

        $scheme      = strtolower( $parsed['scheme'] );
        $host        = self::normalize_host( $parsed['host'] );
        $is_loopback = self::is_loopback_host( $host );
        $is_private  = self::is_private_ip( $host );

        if ( 'http' === $scheme && ! $is_loopback ) {
            return array(
                'valid' => false,
                'error' => 'HTTP transport is only permitted for localhost (127.0.0.1 / ::1). Use HTTPS for remote Kyber services.',
            );
        }

        if ( ! $is_loopback && ! $is_private ) {
            return array(
                'valid'   => true,
                'warning' => 'Kyber microservice MUST run on localhost or a private RFC1918 network. Public endpoints are unsafe.',
            );
        }

        return array( 'valid' => true );
    }

    /**
     * Check if IP is in private range (RFC1918)
     *
     * @param string $ip IP address or hostname
     * @return bool
     */
    private static function is_private_ip( $ip ) {
        $ip = self::normalize_host( $ip );

        if ( empty( $ip ) ) {
            return false;
        }

        if ( ! filter_var( $ip, FILTER_VALIDATE_IP ) ) {
            $resolved = gethostbyname( $ip );
            if ( $resolved && $resolved !== $ip ) {
                $ip = $resolved;
            }
        }

        if ( ! filter_var( $ip, FILTER_VALIDATE_IP ) ) {
            return false;
        }

        return ! filter_var(
            $ip,
            FILTER_VALIDATE_IP,
            FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE
        );
    }

    /**
     * Rate limit check for login attempts
     *
     * @param string $ip IP address
     * @return array Array with 'allowed' boolean and optional 'message'
     */
    public static function check_login_rate_limit( $ip ) {
        $transient_key = 'ndk_login_attempts_' . md5( $ip );
        $attempts      = get_transient( $transient_key );

        if ( false === $attempts ) {
            $attempts = 0;
        }

        // More than 5 attempts in 5 minutes = blocked
        if ( $attempts >= 5 ) {
            return array(
                'allowed' => false,
                'message' => 'Too many login attempts. Please try again later.',
            );
        }

        return array( 'allowed' => true );
    }

    /**
     * Record login attempt
     *
     * @param string $ip IP address
     * @param bool   $success Whether login was successful
     */
    public static function record_login_attempt( $ip, $success = false ) {
        $transient_key = 'ndk_login_attempts_' . md5( $ip );

        if ( $success ) {
            // Clear attempts on successful login
            delete_transient( $transient_key );
        } else {
            // Increment failed attempts
            $attempts = (int) get_transient( $transient_key );
            $attempts++;
            set_transient( $transient_key, $attempts, 5 * MINUTE_IN_SECONDS );
        }
    }

    /**
     * Get API key from constant or fallback to option (backward compat)
     *
     * @return string
     */
    public static function get_api_key() {
        if ( defined( 'NDK_API_KEY' ) && NDK_API_KEY ) {
            return NDK_API_KEY;
        }

        return '';
    }

    /**
     * Get API URL from constant or fallback to option (backward compat)
     *
     * @return string
     */
    public static function get_api_url() {
        // Prefer constant from wp-config.php
        if ( defined( 'NDK_API_URL' ) && NDK_API_URL ) {
            return NDK_API_URL;
        }

        // Fallback to option for backward compatibility
        return get_option( 'ndk_api_url', 'https://awen01.cc' );
    }

    /**
     * Get login key passphrase from constant or fallback to option (backward compat)
     *
     * @return string|null
     */
    public static function get_login_key_passphrase() {
        if ( defined( 'NDK_LOGIN_KEY_PASSPHRASE' ) && NDK_LOGIN_KEY_PASSPHRASE ) {
            return NDK_LOGIN_KEY_PASSPHRASE;
        }

        return null;
    }

    /**
     * Sanitize log output - remove sensitive data
     *
     * @param string $message Log message
     * @return string Sanitized message
     */
    public static function sanitize_log( $message ) {
        // Remove base64-looking strings (likely keys/ciphertext)
        $message = preg_replace( '/[A-Za-z0-9+\/]{40,}={0,2}/', '[REDACTED]', $message );
        return $message;
    }

    /**
     * Check if migration notice should be shown
     *
     * @return bool
     */
    public static function should_show_migration_notice() {
        // Already migrated or dismissed
        if ( get_option( 'ndk_secrets_migrated' ) || get_option( 'ndk_migration_dismissed' ) ) {
            return false;
        }

        $api_key   = get_option( 'ndk_api_key' );
        $site_keys = get_option( 'ndk_site_login_keys' );
        $pass_in_db = ( $site_keys && isset( $site_keys['passphrase'] ) && ! empty( $site_keys['passphrase'] ) );

        return ( ! empty( $api_key ) || $pass_in_db );
    }

    /**
     * Get migration instructions for admin
     *
     * @return array
     */
    public static function get_migration_instructions() {
        $instructions = array();
        $api_key      = get_option( 'ndk_api_key' );
        $site_keys    = get_option( 'ndk_site_login_keys' );

        if ( ! empty( $api_key ) ) {
            $instructions[] = array(
                'constant' => 'NDK_API_KEY',
                'value'    => $api_key,
            );
        }

        if ( $site_keys && isset( $site_keys['passphrase'] ) && ! empty( $site_keys['passphrase'] ) ) {
            $instructions[] = array(
                'constant' => 'NDK_LOGIN_KEY_PASSPHRASE',
                'value'    => $site_keys['passphrase'],
            );
        }

        return $instructions;
    }

    /**
     * Complete migration - remove sensitive data from options
     */
    public static function complete_migration() {
        // Remove API key from options
        delete_option( 'ndk_api_key' );

        // Remove passphrase from site login keys
        $site_keys = get_option( 'ndk_site_login_keys' );
        if ( $site_keys && isset( $site_keys['passphrase'] ) ) {
            unset( $site_keys['passphrase'] );
            update_option( 'ndk_site_login_keys', $site_keys );
        }

        // Mark as migrated
        update_option( 'ndk_secrets_migrated', true );
    }
}
