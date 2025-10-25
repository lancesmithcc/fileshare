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
        $this->api_url = get_option( 'ndk_api_url', 'https://awen01.cc' );
        $this->api_key = get_option( 'ndk_api_key', '' );
    }

    /**
     * Make API request
     */
    private function request( $endpoint, $method = 'GET', $data = null ) {
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

        return array(
            'success' => false,
            'error'   => isset( $decoded['error'] ) ? $decoded['error'] : 'Unknown error',
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
     */
    public function unlock_keypair( $encrypted_private_key, $salt, $nonce, $passphrase ) {
        $data = array(
            'encrypted_private_key' => $encrypted_private_key,
            'salt'                  => $salt,
            'nonce'                 => $nonce,
            'passphrase'            => $passphrase,
        );

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
