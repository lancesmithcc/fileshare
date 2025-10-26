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
     * Cipher suite identifier stored with each encrypted blob.
     */
    const ENVELOPE_ALGORITHM = 'ml-kem+aes256-gcm';

    /**
     * Get user keypair (active or by key_id)
     *
     * @param int         $user_id Target user ID.
     * @param string|null $key_id  Specific key identifier.
     *
     * @return array|null
     */
    public static function get_user_keypair( $user_id, $key_id = null ) {
        global $wpdb;
        $table_name = $wpdb->prefix . 'ndk_keys';

        if ( $key_id ) {
            $keys = $wpdb->get_row(
                $wpdb->prepare(
                    "SELECT * FROM $table_name WHERE user_id = %d AND key_id = %s LIMIT 1",
                    $user_id,
                    $key_id
                ),
                ARRAY_A
            );

            if ( $keys ) {
                return $keys;
            }
        }

        $keys = $wpdb->get_row(
            $wpdb->prepare(
                "SELECT * FROM $table_name WHERE user_id = %d AND active = 1 ORDER BY updated_at DESC LIMIT 1",
                $user_id
            ),
            ARRAY_A
        );

        return $keys;
    }

    /**
     * Save user keypair
     *
     * @param int         $user_id User ID owning the key.
     * @param string      $public_key Kyber public key.
     * @param string      $encrypted_private_key Wrapped private key blob.
     * @param string      $salt Salt associated with the wrapped key.
     * @param string      $nonce Nonce associated with the wrapped key.
     * @param string|null $key_id Optional key identifier.
     * @param bool        $set_active Whether to mark this key active.
     *
     * @return bool
     */
    public static function save_user_keypair( $user_id, $public_key, $encrypted_private_key, $salt, $nonce, $key_id = null, $set_active = true ) {
        global $wpdb;
        $table_name = $wpdb->prefix . 'ndk_keys';

        if ( empty( $key_id ) ) {
            $key_id = self::generate_key_id( $user_id );
        }

        if ( $set_active ) {
            $wpdb->update(
                $table_name,
                array( 'active' => 0 ),
                array( 'user_id' => $user_id ),
                array( '%d' ),
                array( '%d' )
            );
        }

        $existing_id = $wpdb->get_var(
            $wpdb->prepare(
                "SELECT id FROM $table_name WHERE user_id = %d AND key_id = %s LIMIT 1",
                $user_id,
                $key_id
            )
        );

        if ( $existing_id ) {
            $result = $wpdb->update(
                $table_name,
                array(
                    'public_key'            => $public_key,
                    'encrypted_private_key' => $encrypted_private_key,
                    'salt'                  => $salt,
                    'nonce'                 => $nonce,
                    'active'                => $set_active ? 1 : 0,
                ),
                array( 'id' => $existing_id ),
                array( '%s', '%s', '%s', '%s', '%d' ),
                array( '%d' )
            );
        } else {
            $result = $wpdb->insert(
                $table_name,
                array(
                    'user_id'               => $user_id,
                    'key_id'                => $key_id,
                    'public_key'            => $public_key,
                    'encrypted_private_key' => $encrypted_private_key,
                    'salt'                  => $salt,
                    'nonce'                 => $nonce,
                    'active'                => $set_active ? 1 : 0,
                ),
                array( '%d', '%s', '%s', '%s', '%s', '%s', '%d' )
            );
        }

        return false !== $result;
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

        $saved = self::save_user_keypair(
            $user_id,
            $data['public_key'],
            $data['encrypted_private_key'],
            $data['salt'],
            $data['nonce']
        );

        return (bool) $saved;
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

        $key_id = ! empty( $keys['key_id'] )
            ? $keys['key_id']
            : sprintf( 'user-%d-legacy', (int) $recipient_user_id );

        $api = NDK()->get_api_client();
        $result = $api->encrypt( $keys['public_key'], $content );

        if ( ! $result['success'] ) {
            return false;
        }

        $payload = $result['data'];
        $payload['alg']    = self::ENVELOPE_ALGORITHM;
        $payload['key_id'] = $key_id;

        return $payload;
    }

    /**
     * Decrypt content
     */
    public static function decrypt_content( $encrypted_data, $user_id, $passphrase = null ) {
        if ( ! is_array( $encrypted_data ) ) {
            return false;
        }

        $key_id = isset( $encrypted_data['key_id'] ) ? sanitize_text_field( $encrypted_data['key_id'] ) : null;
        $keys   = self::get_user_keypair( $user_id, $key_id );

        if ( ! $keys && $key_id ) {
            // Key may have been marked inactive; fall back to current active key
            $keys = self::get_user_keypair( $user_id );
        }

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

    /**
     * Generate deterministic-ish key identifier for a user
     *
     * @param int $user_id User ID.
     * @return string
     */
    private static function generate_key_id( $user_id ) {
        $suffix = wp_generate_password( 6, false, false );
        return sprintf( 'user-%d-key-%s', (int) $user_id, strtolower( $suffix ) );
    }
}
