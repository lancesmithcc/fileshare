<?php
/**
 * Encryption Helper Class
 *
 * @package WP_KyberCrypt
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NDK_Encryption {

    /**
     * Get or create user keypair
     */
    public static function get_user_keypair( $user_id ) {
        global $wpdb;
        $table_name = $wpdb->prefix . 'ndk_keys';

        $keys = $wpdb->get_row(
            $wpdb->prepare(
                "SELECT * FROM $table_name WHERE user_id = %d",
                $user_id
            ),
            ARRAY_A
        );

        return $keys;
    }

    /**
     * Save user keypair
     */
    public static function save_user_keypair( $user_id, $public_key, $encrypted_private_key, $salt, $nonce ) {
        global $wpdb;
        $table_name = $wpdb->prefix . 'ndk_keys';

        $existing = self::get_user_keypair( $user_id );

        if ( $existing ) {
            return $wpdb->update(
                $table_name,
                array(
                    'public_key'            => $public_key,
                    'encrypted_private_key' => $encrypted_private_key,
                    'salt'                  => $salt,
                    'nonce'                 => $nonce,
                ),
                array( 'user_id' => $user_id ),
                array( '%s', '%s', '%s', '%s' ),
                array( '%d' )
            );
        }

        return $wpdb->insert(
            $table_name,
            array(
                'user_id'               => $user_id,
                'public_key'            => $public_key,
                'encrypted_private_key' => $encrypted_private_key,
                'salt'                  => $salt,
                'nonce'                 => $nonce,
            ),
            array( '%d', '%s', '%s', '%s', '%s' )
        );
    }

    /**
     * Generate keypair for user
     */
    public static function generate_user_keypair( $user_id, $passphrase = null ) {
        $api = NDK()->get_api_client();

        // Use user's password hash as passphrase if none provided
        if ( $passphrase === null ) {
            $user = get_userdata( $user_id );
            if ( ! $user ) {
                return false;
            }
            // Use a derivation of the user's password hash for encryption
            $passphrase = hash( 'sha256', $user->user_pass . $user->ID . 'ndk-kyber' );
        }

        $result = $api->generate_keypair( $passphrase );

        if ( ! $result['success'] ) {
            return false;
        }

        $data = $result['data'];

        return self::save_user_keypair(
            $user_id,
            $data['public_key'],
            $data['encrypted_private_key'],
            $data['salt'],
            $data['nonce']
        );
    }

    /**
     * Encrypt content
     */
    public static function encrypt_content( $content, $recipient_user_id ) {
        $keys = self::get_user_keypair( $recipient_user_id );

        if ( ! $keys ) {
            // Auto-generate keys if enabled
            if ( get_option( 'ndk_auto_generate_keys', true ) ) {
                self::generate_user_keypair( $recipient_user_id );
                $keys = self::get_user_keypair( $recipient_user_id );
            }

            if ( ! $keys ) {
                return false;
            }
        }

        $api = NDK()->get_api_client();
        $result = $api->encrypt( $keys['public_key'], $content );

        if ( ! $result['success'] ) {
            return false;
        }

        return $result['data'];
    }

    /**
     * Decrypt content
     */
    public static function decrypt_content( $encrypted_data, $user_id, $passphrase = null ) {
        $keys = self::get_user_keypair( $user_id );

        if ( ! $keys ) {
            return false;
        }

        // Get passphrase if not provided
        if ( $passphrase === null ) {
            $user = get_userdata( $user_id );
            if ( ! $user ) {
                return false;
            }
            $passphrase = hash( 'sha256', $user->user_pass . $user->ID . 'ndk-kyber' );
        }

        $api = NDK()->get_api_client();

        // Unlock private key
        $unlock_result = $api->unlock_keypair(
            $keys['encrypted_private_key'],
            $keys['salt'],
            $keys['nonce'],
            $passphrase
        );

        if ( ! $unlock_result['success'] ) {
            return false;
        }

        $private_key = $unlock_result['data']['private_key'];

        // Decrypt content
        $decrypt_result = $api->decrypt(
            $private_key,
            $encrypted_data['kem_ciphertext'],
            $encrypted_data['wrapped_key'],
            $encrypted_data['wrap_nonce'],
            $encrypted_data['body_nonce'],
            $encrypted_data['ciphertext']
        );

        if ( ! $decrypt_result['success'] ) {
            return false;
        }

        return $decrypt_result['data']['plaintext'];
    }
}
