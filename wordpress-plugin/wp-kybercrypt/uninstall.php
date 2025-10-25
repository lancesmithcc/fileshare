<?php
/**
 * Uninstall Script
 *
 * @package WP_KyberCrypt
 */

// If uninstall not called from WordPress, exit
if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
    exit;
}

global $wpdb;

// Delete options
$options = array(
    'ndk_api_url',
    'ndk_api_key',
    'ndk_encrypt_posts',
    'ndk_encrypt_pages',
    'ndk_encrypt_comments',
    'ndk_auto_generate_keys',
);

foreach ( $options as $option ) {
    delete_option( $option );
}

// Delete user keys table
$table_name = $wpdb->prefix . 'ndk_keys';
$wpdb->query( "DROP TABLE IF EXISTS $table_name" );

// Delete post meta
$wpdb->query( "DELETE FROM {$wpdb->postmeta} WHERE meta_key LIKE '_ndk_%'" );

// Delete comment meta
$wpdb->query( "DELETE FROM {$wpdb->commentmeta} WHERE meta_key LIKE '_ndk_%'" );

// Clear any cached data
wp_cache_flush();
