<?php
/**
 * API Client for Neo-Druidic Kyber API
 *
 * @package WP_KyberCrypt
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NDK_API_Client {

    /**
     * API base URL
     */
    private $api_url;

    /**
     * API key
     */
    private $api_key;

    /**
     * Constructor
     */
    public function __construct() {
        // Use security helper to get API URL and key from constants or options
        $this->api_url = NDK_Security::get_api_url();
        $this->api_key = NDK_Security::get_api_key();

        // Validate API URL for security
        $validation = NDK_Security::validate_api_url( $this->api_url );
        if ( ! $validation['valid'] ) {
            error_log( 'WP-KyberCrypt API URL validation failed: ' . $validation['error'] );
            add_action( 'admin_notices', function() use ( $validation ) {
                echo '<div class="notice notice-error"><p><strong>WP-KyberCrypt Security Warning:</strong> ' . esc_html( $validation['error'] ) . '</p></div>';
            } );
        } elseif ( isset( $validation['warning'] ) ) {
            error_log( 'WP-KyberCrypt API URL warning: ' . $validation['warning'] );
            add_action( 'admin_notices', function() use ( $validation ) {
                echo '<div class="notice notice-warning"><p><strong>WP-KyberCrypt Security Notice:</strong> ' . esc_html( $validation['warning'] ) . '</p></div>';
            } );
        }
    }

    /**
     * Make API request
     */
    private function request( $endpoint, $method = 'GET', $data = null ) {
        // Validate URL before making request
        $validation = NDK_Security::validate_api_url( $this->api_url );
        if ( ! $validation['valid'] ) {
            return array(
                'success' => false,
                'error'   => 'API URL validation failed: ' . $validation['error'],
            );
        }

        $url = trailingslashit( $this->api_url ) . 'api/v1/kyber/' . ltrim( $endpoint, '/' );

        $args = array(
            'method'  => $method,
            'headers' => array(
                'Content-Type' => 'application/json',
            ),
            'timeout' => 30,
        );

        // Add API key if configured
        if ( ! empty( $this->api_key ) ) {
            $args['headers']['X-API-Key'] = $this->api_key;
        }

        // Add body for POST requests
        if ( $method === 'POST' && $data !== null ) {
            $args['body'] = wp_json_encode( $data );
        }

        $response = wp_remote_request( $url, $args );

        if ( is_wp_error( $response ) ) {
            $error_msg = NDK_Security::sanitize_log( $response->get_error_message() );
            error_log( 'WP-KyberCrypt API request failed: ' . $error_msg );
            return array(
                'success' => false,
                'error'   => $response->get_error_message(),
            );
        }

        $status_code = wp_remote_retrieve_response_code( $response );
        $body = wp_remote_retrieve_body( $response );
        $decoded = json_decode( $body, true );

        if ( $status_code >= 200 && $status_code < 300 ) {
            return array(
                'success' => true,
                'data'    => $decoded,
            );
        }

        $error_msg = isset( $decoded['error'] ) ? $decoded['error'] : 'Unknown error';
        error_log( 'WP-KyberCrypt API error ' . $status_code . ': ' . NDK_Security::sanitize_log( $error_msg ) );

        return array(
            'success' => false,
            'error'   => $error_msg,
            'code'    => $status_code,
        );
    }

    /**
     * Get API info
     */
    public function get_info() {
        return $this->request( 'info', 'GET' );
    }

    /**
     * Generate keypair
     */
    public function generate_keypair( $passphrase = null ) {
        $data = array();
        if ( $passphrase !== null ) {
            $data['passphrase'] = $passphrase;
        }

        return $this->request( 'keypair/generate', 'POST', $data );
    }

    /**
     * Unlock private key
     *
     * SECURITY NOTE: Passphrase should NOT be sent over HTTP.
     * This method should be updated to send only encrypted_private_key, salt, nonce
     * and the Python service should get passphrase from its own environment.
     */
    public function unlock_keypair( $encrypted_private_key, $salt, $nonce, $passphrase = null ) {
        $data = array(
            'encrypted_private_key' => $encrypted_private_key,
            'salt'                  => $salt,
            'nonce'                 => $nonce,
        );

        // DEPRECATED: Sending passphrase over HTTP is insecure
        // TODO: Update Python service to use passphrase from ENV
        if ( $passphrase !== null ) {
            $data['passphrase'] = $passphrase;
        }

        return $this->request( 'keypair/unlock', 'POST', $data );
    }

    /**
     * Encrypt message
     */
    public function encrypt( $recipient_public_key, $plaintext ) {
        $data = array(
            'recipient_public_key' => $recipient_public_key,
            'plaintext'            => $plaintext,
        );

        return $this->request( 'encrypt', 'POST', $data );
    }

    /**
     * Decrypt message
     */
    public function decrypt( $private_key, $kem_ciphertext, $wrapped_key, $wrap_nonce, $body_nonce, $ciphertext ) {
        $data = array(
            'private_key'     => $private_key,
            'kem_ciphertext'  => $kem_ciphertext,
            'wrapped_key'     => $wrapped_key,
            'wrap_nonce'      => $wrap_nonce,
            'body_nonce'      => $body_nonce,
            'ciphertext'      => $ciphertext,
        );

        return $this->request( 'decrypt', 'POST', $data );
    }

    /**
     * Test connection to API
     */
    public function test_connection() {
        $result = $this->get_info();

        if ( $result['success'] ) {
            return array(
                'success' => true,
                'message' => sprintf(
                    'Connected successfully! Algorithm: %s (Security Level: %s)',
                    $result['data']['algorithm'],
                    $result['data']['security_level']
                ),
            );
        }

        return array(
            'success' => false,
            'message' => 'Connection failed: ' . $result['error'],
        );
    }
}
