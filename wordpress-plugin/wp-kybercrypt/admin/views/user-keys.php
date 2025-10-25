<?php
/**
 * User Keys Management Page
 *
 * @package WP_KyberCrypt
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}
?>

<div class="wrap ndk-admin-wrap">
    <h1><?php _e( 'User Encryption Keys', 'wp-kybercrypt' ); ?></h1>

    <p class="description">
        <?php _e( 'Manage Kyber encryption keypairs for WordPress users. Each user has a unique keypair for quantum-safe encryption.', 'wp-kybercrypt' ); ?>
    </p>

    <div class="ndk-card">
        <table class="wp-list-table widefat fixed striped">
            <thead>
                <tr>
                    <th><?php _e( 'User', 'wp-kybercrypt' ); ?></th>
                    <th><?php _e( 'Email', 'wp-kybercrypt' ); ?></th>
                    <th><?php _e( 'Public Key', 'wp-kybercrypt' ); ?></th>
                    <th><?php _e( 'Created', 'wp-kybercrypt' ); ?></th>
                    <th><?php _e( 'Actions', 'wp-kybercrypt' ); ?></th>
                </tr>
            </thead>
            <tbody>
                <?php if ( ! empty( $users_with_keys ) ) : ?>
                    <?php foreach ( $users_with_keys as $key_data ) : ?>
                        <tr>
                            <td>
                                <strong><?php echo esc_html( $key_data->user_login ); ?></strong>
                                <br>
                                <small>ID: <?php echo esc_html( $key_data->user_id ); ?></small>
                            </td>
                            <td><?php echo esc_html( $key_data->user_email ); ?></td>
                            <td>
                                <code class="ndk-key-preview">
                                    <?php echo esc_html( substr( $key_data->public_key, 0, 32 ) ); ?>...
                                </code>
                            </td>
                            <td><?php echo esc_html( mysql2date( get_option( 'date_format' ), $key_data->created_at ) ); ?></td>
                            <td>
                                <button
                                    type="button"
                                    class="button button-small ndk-regenerate-keys"
                                    data-user-id="<?php echo esc_attr( $key_data->user_id ); ?>"
                                >
                                    <?php _e( 'Regenerate', 'wp-kybercrypt' ); ?>
                                </button>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                <?php else : ?>
                    <tr>
                        <td colspan="5" class="ndk-empty-state">
                            <?php _e( 'No encryption keys found. Keys are generated automatically when users create encrypted content.', 'wp-kybercrypt' ); ?>
                        </td>
                    </tr>
                <?php endif; ?>
            </tbody>
        </table>
    </div>

    <div class="ndk-info-banner">
        <h3><?php _e( 'Important Security Information', 'wp-kybercrypt' ); ?></h3>
        <p>
            <?php _e( 'Private keys are encrypted with user credentials and cannot be recovered without the user\'s password. Regenerating keys will cause previously encrypted content to become inaccessible.', 'wp-kybercrypt' ); ?>
        </p>
    </div>
</div>
