<?php
/**
 * Content Encryption - Hooks into WordPress content
 *
 * @package WP_KyberCrypt
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NDK_Content_Encryption {

    /**
     * Constructor
     */
    public function __construct() {
        // Post/Page encryption hooks - ALWAYS enabled to support per-post encryption
        add_filter( 'content_save_pre', array( $this, 'encrypt_post_content' ), 10, 1 );
        add_filter( 'the_content', array( $this, 'decrypt_post_content' ), 999, 1 );

        // Comment encryption hooks
        if ( get_option( 'ndk_encrypt_comments', false ) ) {
            add_filter( 'preprocess_comment', array( $this, 'encrypt_comment_content' ), 10, 1 );
            add_filter( 'comment_text', array( $this, 'decrypt_comment_content' ), 999, 2 );
        }

        // User data encryption hooks
        if ( get_option( 'ndk_encrypt_users', false ) ) {
            add_action( 'user_register', array( $this, 'encrypt_user_data' ), 10, 1 );
            add_action( 'profile_update', array( $this, 'encrypt_user_data' ), 10, 1 );
            add_filter( 'get_user_metadata', array( $this, 'decrypt_user_metadata' ), 10, 4 );
        }

        // Options encryption hooks
        if ( get_option( 'ndk_encrypt_options', false ) ) {
            add_filter( 'pre_update_option', array( $this, 'encrypt_sensitive_options' ), 10, 3 );
            add_filter( 'option_*', array( $this, 'decrypt_sensitive_options' ), 10, 2 );
        }

        // Media metadata encryption hooks
        if ( get_option( 'ndk_encrypt_media', false ) ) {
            add_filter( 'wp_update_attachment_metadata', array( $this, 'encrypt_attachment_metadata' ), 10, 2 );
            add_filter( 'wp_get_attachment_metadata', array( $this, 'decrypt_attachment_metadata' ), 10, 2 );
        }

        // E-commerce hooks (WooCommerce, Easy Digital Downloads)
        if ( get_option( 'ndk_encrypt_ecommerce', false ) ) {
            // WooCommerce
            add_action( 'woocommerce_new_order', array( $this, 'encrypt_order_data' ), 10, 1 );
            add_filter( 'woocommerce_order_get_billing_email', array( $this, 'decrypt_order_field' ), 10, 2 );

            // Easy Digital Downloads
            add_action( 'edd_insert_payment', array( $this, 'encrypt_edd_payment_data' ), 10, 2 );
        }

        // Gravity Forms hooks
        if ( get_option( 'ndk_encrypt_forms', false ) ) {
            add_action( 'gform_after_submission', array( $this, 'encrypt_gravity_forms_entry' ), 10, 2 );
            add_filter( 'gform_get_input_value', array( $this, 'decrypt_gravity_forms_field' ), 10, 4 );
        }

        // Meta box for manual encryption
        add_action( 'add_meta_boxes', array( $this, 'add_encryption_meta_box' ) );
        add_action( 'save_post', array( $this, 'save_encryption_meta' ) );

        // Shortcode for encrypted content
        add_shortcode( 'ndk_encrypted', array( $this, 'encrypted_shortcode' ) );
    }

    /**
     * Encrypt post content before saving
     */
    public function encrypt_post_content( $content ) {
        // Only encrypt if user is logged in and has keys
        if ( ! is_user_logged_in() ) {
            return $content;
        }

        $post_id = isset( $_POST['post_ID'] ) ? intval( $_POST['post_ID'] ) : 0;

        // Check if post should be encrypted - check $_POST directly since meta isn't saved yet
        $should_encrypt = isset( $_POST['ndk_encrypt_content'] ) ? true : false;

        // Also check existing meta for already-encrypted posts being updated
        if ( ! $should_encrypt && $post_id ) {
            $should_encrypt = get_post_meta( $post_id, '_ndk_encrypt_content', true );
        }

        if ( ! $should_encrypt ) {
            // If encryption was unchecked, decrypt the content
            if ( $post_id && get_post_meta( $post_id, '_ndk_is_encrypted', true ) ) {
                delete_post_meta( $post_id, '_ndk_encrypted_data' );
                delete_post_meta( $post_id, '_ndk_is_encrypted' );
            }
            return $content;
        }

        // Encrypt for the post author
        $author_id = get_post_field( 'post_author', $post_id );
        if ( ! $author_id ) {
            $author_id = get_current_user_id();
        }

        $encrypted = NDK_Encryption::encrypt_content( $content, $author_id );

        if ( ! $encrypted ) {
            return $content; // Fallback to original if encryption fails
        }

        // Store encrypted data as post meta
        update_post_meta( $post_id, '_ndk_encrypted_data', $encrypted );
        update_post_meta( $post_id, '_ndk_is_encrypted', true );

        // Return marker content
        return '[NDK_ENCRYPTED_CONTENT]';
    }

    /**
     * Decrypt post content when displaying
     */
    public function decrypt_post_content( $content ) {
        global $post;

        if ( ! $post ) {
            return $content;
        }

        $is_encrypted = get_post_meta( $post->ID, '_ndk_is_encrypted', true );

        if ( ! $is_encrypted || $content !== '[NDK_ENCRYPTED_CONTENT]' ) {
            return $content;
        }

        // Encrypted content - check if user is logged in
        if ( ! is_user_logged_in() ) {
            $redirect_to = get_permalink();

            ob_start();
            ?>
            <div class="ndk-encrypted-login-wrapper" style="max-width: 500px; margin: 40px auto; padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.3);">
                <div style="text-align: center; margin-bottom: 25px;">
                    <div style="font-size: 48px; margin-bottom: 10px;">🔐</div>
                    <h3 style="margin: 0; color: #fff; font-size: 24px; font-weight: 600;">Quantum-Encrypted Content</h3>
                    <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">Protected with ML-KEM-768 Post-Quantum Cryptography</p>
                </div>

                <div style="background: #fff; padding: 25px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
                    <p style="margin: 0 0 20px 0; color: #333; text-align: center; font-weight: 500;">You must log in to view this content</p>

                    <?php
                    $login_args = array(
                        'echo' => true,
                        'redirect' => $redirect_to,
                        'form_id' => 'ndk_loginform',
                        'label_username' => __( 'Username or Email' ),
                        'label_password' => __( 'Password' ),
                        'label_remember' => __( 'Remember Me' ),
                        'label_log_in' => __( 'Login to Decrypt' ),
                        'id_username' => 'ndk_user_login',
                        'id_password' => 'ndk_user_pass',
                        'id_remember' => 'ndk_rememberme',
                        'id_submit' => 'ndk_wp-submit',
                        'remember' => true,
                        'value_username' => '',
                        'value_remember' => false
                    );
                    wp_login_form( $login_args );
                    ?>

                    <style>
                        #ndk_loginform p { margin-bottom: 15px; }
                        #ndk_loginform label { display: block; margin-bottom: 5px; color: #333; font-weight: 500; font-size: 14px; }
                        #ndk_loginform input[type="text"],
                        #ndk_loginform input[type="password"] {
                            width: 100%;
                            padding: 12px;
                            border: 2px solid #e0e0e0;
                            border-radius: 6px;
                            font-size: 14px;
                            transition: border-color 0.3s;
                            box-sizing: border-box;
                        }
                        #ndk_loginform input[type="text"]:focus,
                        #ndk_loginform input[type="password"]:focus {
                            outline: none;
                            border-color: #667eea;
                        }
                        #ndk_loginform input[type="checkbox"] {
                            margin-right: 5px;
                        }
                        #ndk_loginform input[type="submit"] {
                            width: 100%;
                            padding: 12px;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: #fff;
                            border: none;
                            border-radius: 6px;
                            font-size: 16px;
                            font-weight: 600;
                            cursor: pointer;
                            transition: transform 0.2s, box-shadow 0.2s;
                        }
                        #ndk_loginform input[type="submit"]:hover {
                            transform: translateY(-2px);
                            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
                        }
                        #ndk_loginform .login-remember {
                            margin-bottom: 20px;
                        }
                        #ndk_loginform .login-remember label {
                            display: inline;
                            font-weight: normal;
                        }
                    </style>
                </div>

                <div style="text-align: center; margin-top: 20px;">
                    <p style="margin: 0; color: rgba(255,255,255,0.8); font-size: 12px;">
                        <strong>Why Quantum Encryption?</strong><br>
                        This content is secured against future quantum computer attacks using NIST-standardized ML-KEM-768.
                    </p>
                </div>
            </div>
            <?php
            return ob_get_clean();
        }

        if ( ! NDK_Security::can_current_user_decrypt( 'post_content', (int) $post->post_author ) ) {
            return '<p class="ndk-error">' . esc_html( NDK_Security::get_masked_value() ) . '</p>';
        }

        $encrypted_data = get_post_meta( $post->ID, '_ndk_encrypted_data', true );

        if ( ! $encrypted_data ) {
            return '<p class="ndk-error">' . __( '[Encrypted content not available]', 'wp-kybercrypt' ) . '</p>';
        }

        $owner_id = (int) $post->post_author;
        $decrypted = NDK_Encryption::decrypt_content( $encrypted_data, $owner_id );

        if ( ! $decrypted ) {
            return '<p class="ndk-error">' . __( '[Unable to decrypt content - you may not have permission]', 'wp-kybercrypt' ) . '</p>';
        }

        return '<div class="ndk-decrypted-content">' . $decrypted . '</div>';
    }

    /**
     * Encrypt comment content
     */
    public function encrypt_comment_content( $commentdata ) {
        if ( ! is_user_logged_in() || empty( $commentdata['comment_content'] ) ) {
            return $commentdata;
        }

        $user_id = get_current_user_id();
        $encrypted = NDK_Encryption::encrypt_content( $commentdata['comment_content'], $user_id );

        if ( $encrypted ) {
            // Store original as comment meta (will be added after insert)
            $commentdata['comment_content'] = '[NDK_ENCRYPTED_COMMENT]';
            $commentdata['_ndk_encrypted_data'] = $encrypted;
            $commentdata['_ndk_is_encrypted'] = true;
        }

        return $commentdata;
    }

    /**
     * Decrypt comment content
     */
    public function decrypt_comment_content( $comment_text, $comment ) {
        if ( ! is_user_logged_in() || $comment_text !== '[NDK_ENCRYPTED_COMMENT]' ) {
            return $comment_text;
        }

        $encrypted_data = get_comment_meta( $comment->comment_ID, '_ndk_encrypted_data', true );

        if ( ! $encrypted_data ) {
            return __( '[Encrypted comment]', 'wp-kybercrypt' );
        }

        if ( ! NDK_Security::can_current_user_decrypt( 'comment', (int) $comment->user_id ) ) {
            return NDK_Security::get_masked_value();
        }

        $owner_id = (int) $comment->user_id;
        $decrypted = NDK_Encryption::decrypt_content( $encrypted_data, $owner_id );

        return $decrypted ? $decrypted : __( '[Unable to decrypt comment]', 'wp-kybercrypt' );
    }

    /**
     * Add encryption meta box
     */
    public function add_encryption_meta_box() {
        $post_types = array( 'post', 'page' );

        foreach ( $post_types as $post_type ) {
            add_meta_box(
                'ndk_encryption_meta_box',
                __( 'Quantum Encryption', 'wp-kybercrypt' ),
                array( $this, 'render_encryption_meta_box' ),
                $post_type,
                'side',
                'high'
            );
        }
    }

    /**
     * Render encryption meta box
     */
    public function render_encryption_meta_box( $post ) {
        wp_nonce_field( 'ndk_encryption_meta_box', 'ndk_encryption_meta_box_nonce' );

        $encrypt_content = get_post_meta( $post->ID, '_ndk_encrypt_content', true );
        $is_encrypted = get_post_meta( $post->ID, '_ndk_is_encrypted', true );

        ?>
        <div class="ndk-meta-box">
            <?php if ( $is_encrypted ) : ?>
                <div class="notice notice-success inline">
                    <p><strong><?php _e( 'This content is quantum-encrypted!', 'wp-kybercrypt' ); ?></strong></p>
                    <p><?php _e( 'Protected with ML-KEM-768 (Kyber) post-quantum cryptography.', 'wp-kybercrypt' ); ?></p>
                </div>
            <?php endif; ?>

            <p>
                <label>
                    <input type="checkbox" name="ndk_encrypt_content" value="1" <?php checked( $encrypt_content, 1 ); ?>>
                    <?php _e( 'Encrypt this content', 'wp-kybercrypt' ); ?>
                </label>
            </p>

            <p class="description">
                <?php _e( 'Enable quantum-safe encryption for this post. Content will be encrypted using ML-KEM-768 (Kyber).', 'wp-kybercrypt' ); ?>
            </p>
        </div>
        <?php
    }

    /**
     * Save encryption meta
     */
    public function save_encryption_meta( $post_id ) {
        if ( ! isset( $_POST['ndk_encryption_meta_box_nonce'] ) ) {
            return;
        }

        if ( ! wp_verify_nonce( $_POST['ndk_encryption_meta_box_nonce'], 'ndk_encryption_meta_box' ) ) {
            return;
        }

        if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) {
            return;
        }

        if ( ! current_user_can( 'edit_post', $post_id ) ) {
            return;
        }

        $encrypt_content = isset( $_POST['ndk_encrypt_content'] ) ? 1 : 0;
        update_post_meta( $post_id, '_ndk_encrypt_content', $encrypt_content );
    }

    /**
     * Encrypted content shortcode
     */
    public function encrypted_shortcode( $atts, $content = '' ) {
        if ( ! is_user_logged_in() || empty( $content ) ) {
            return '<p class="ndk-encrypted-shortcode">' . __( '[Encrypted Content - Login Required]', 'wp-kybercrypt' ) . '</p>';
        }

        $user_id = get_current_user_id();

        if ( ! NDK_Security::can_current_user_decrypt( 'post_content', $user_id ) ) {
            return '<p class="ndk-encrypted-shortcode">' . esc_html( NDK_Security::get_masked_value() ) . '</p>';
        }

        // Try to decrypt if already encrypted
        if ( strpos( $content, '[NDK_ENCRYPTED:' ) === 0 ) {
            // Extract encrypted data from shortcode
            preg_match( '/\[NDK_ENCRYPTED:(.*?)\]/', $content, $matches );

            if ( isset( $matches[1] ) ) {
                $encrypted_data = json_decode( base64_decode( $matches[1] ), true );
                $decrypted = NDK_Encryption::decrypt_content( $encrypted_data, $user_id );

                return $decrypted ? '<div class="ndk-decrypted-shortcode">' . do_shortcode( $decrypted ) . '</div>' : '[Unable to decrypt]';
            }
        }

        // Encrypt the content
        $encrypted = NDK_Encryption::encrypt_content( $content, $user_id );

        if ( ! $encrypted ) {
            return $content; // Fallback
        }

        $encoded = base64_encode( wp_json_encode( $encrypted ) );

        return '<div class="ndk-encrypted-shortcode">[NDK_ENCRYPTED:' . $encoded . ']</div>';
    }

    /**
     * Encrypt user data on registration or profile update
     */
    public function encrypt_user_data( $user_id ) {
        // Get sensitive user meta fields
        $sensitive_fields = array(
            'billing_email', 'billing_phone', 'billing_address_1', 'billing_address_2',
            'billing_city', 'billing_state', 'billing_postcode', 'billing_country',
            'shipping_address_1', 'shipping_address_2', 'shipping_city',
            'shipping_state', 'shipping_postcode', 'shipping_country'
        );

        foreach ( $sensitive_fields as $field ) {
            $value = get_user_meta( $user_id, $field, true );
            if ( ! empty( $value ) && strpos( $value, '[NDK_ENCRYPTED]' ) !== 0 ) {
                $encrypted = NDK_Encryption::encrypt_content( $value, $user_id );
                if ( $encrypted ) {
                    update_user_meta( $user_id, $field, '[NDK_ENCRYPTED]' . base64_encode( wp_json_encode( $encrypted ) ) );
                }
            }
        }
    }

    /**
     * Decrypt user metadata when retrieved
     */
    public function decrypt_user_metadata( $value, $object_id, $meta_key, $single ) {
        if ( is_string( $value ) && strpos( $value, '[NDK_ENCRYPTED]' ) === 0 ) {
            if ( ! NDK_Security::can_current_user_decrypt( 'user_meta', (int) $object_id ) ) {
                return NDK_Security::get_masked_value();
            }
            $encrypted_data = json_decode( base64_decode( substr( $value, 15 ) ), true );
            $decrypted = NDK_Encryption::decrypt_content( $encrypted_data, $object_id );
            return $decrypted ? $decrypted : $value;
        }
        return $value;
    }

    /**
     * Encrypt sensitive WordPress options
     */
    public function encrypt_sensitive_options( $value, $option, $old_value ) {
        // List of sensitive options to encrypt
        $sensitive_options = array(
            'admin_email', 'mailserver_login', 'mailserver_pass',
            'woocommerce_stripe_settings', 'woocommerce_paypal_settings',
            'edd_settings', 'gf_stripe_settings'
        );

        if ( in_array( $option, $sensitive_options, true ) && ! empty( $value ) ) {
            if ( is_string( $value ) && strpos( $value, '[NDK_ENCRYPTED]' ) !== 0 ) {
                $encrypted = NDK_Encryption::encrypt_content( $value, 1 ); // Use admin user
                return $encrypted ? '[NDK_ENCRYPTED]' . base64_encode( wp_json_encode( $encrypted ) ) : $value;
            } elseif ( is_array( $value ) ) {
                // Encrypt array values recursively
                array_walk_recursive( $value, function( &$item ) {
                    if ( is_string( $item ) && strpos( $item, '[NDK_ENCRYPTED]' ) !== 0 ) {
                        $encrypted = NDK_Encryption::encrypt_content( $item, 1 );
                        $item = $encrypted ? '[NDK_ENCRYPTED]' . base64_encode( wp_json_encode( $encrypted ) ) : $item;
                    }
                });
                return $value;
            }
        }
        return $value;
    }

    /**
     * Decrypt sensitive options when retrieved
     */
    public function decrypt_sensitive_options( $value, $option ) {
        if ( is_string( $value ) && strpos( $value, '[NDK_ENCRYPTED]' ) === 0 ) {
            if ( ! NDK_Security::can_current_user_decrypt( 'options', 1 ) ) {
                return NDK_Security::get_masked_value();
            }
            $encrypted_data = json_decode( base64_decode( substr( $value, 15 ) ), true );
            $decrypted = NDK_Encryption::decrypt_content( $encrypted_data, 1 );
            return $decrypted ? $decrypted : $value;
        } elseif ( is_array( $value ) ) {
            array_walk_recursive( $value, function( &$item ) {
                if ( is_string( $item ) && strpos( $item, '[NDK_ENCRYPTED]' ) === 0 ) {
                    if ( ! NDK_Security::can_current_user_decrypt( 'options', 1 ) ) {
                        $item = NDK_Security::get_masked_value();
                        return;
                    }
                    $encrypted_data = json_decode( base64_decode( substr( $item, 15 ) ), true );
                    $decrypted = NDK_Encryption::decrypt_content( $encrypted_data, 1 );
                    $item = $decrypted ? $decrypted : $item;
                }
            });
        }
        return $value;
    }

    /**
     * Encrypt attachment metadata
     */
    public function encrypt_attachment_metadata( $data, $attachment_id ) {
        if ( isset( $data['file'] ) && strpos( $data['file'], '[NDK_ENCRYPTED]' ) !== 0 ) {
            $author_id = get_post_field( 'post_author', $attachment_id );
            $encrypted = NDK_Encryption::encrypt_content( wp_json_encode( $data ), $author_id );
            if ( $encrypted ) {
                return array( '_ndk_encrypted' => base64_encode( wp_json_encode( $encrypted ) ) );
            }
        }
        return $data;
    }

    /**
     * Decrypt attachment metadata
     */
    public function decrypt_attachment_metadata( $data, $attachment_id ) {
        if ( is_array( $data ) && isset( $data['_ndk_encrypted'] ) ) {
            $author_id = get_post_field( 'post_author', $attachment_id );
            if ( ! NDK_Security::can_current_user_decrypt( 'attachment', (int) $author_id ) ) {
                return array(
                    '_ndk_locked' => true,
                    'message'     => NDK_Security::get_masked_value(),
                );
            }
            $encrypted_data = json_decode( base64_decode( $data['_ndk_encrypted'] ), true );
            $decrypted = NDK_Encryption::decrypt_content( $encrypted_data, $author_id );
            return $decrypted ? json_decode( $decrypted, true ) : $data;
        }
        return $data;
    }

    /**
     * Encrypt WooCommerce order data
     */
    public function encrypt_order_data( $order_id ) {
        $order = wc_get_order( $order_id );
        if ( ! $order ) {
            return;
        }

        $customer_id = $order->get_customer_id();
        if ( ! $customer_id ) {
            $customer_id = 1; // Default to admin if guest
        }

        // Encrypt billing details
        $billing_fields = array(
            'billing_email', 'billing_phone', 'billing_address_1', 'billing_address_2',
            'billing_city', 'billing_state', 'billing_postcode'
        );

        foreach ( $billing_fields as $field ) {
            $value = $order->{"get_$field"}();
            if ( ! empty( $value ) ) {
                $encrypted = NDK_Encryption::encrypt_content( $value, $customer_id );
                if ( $encrypted ) {
                    update_post_meta( $order_id, "_$field", '[NDK_ENCRYPTED]' . base64_encode( wp_json_encode( $encrypted ) ) );
                }
            }
        }
    }

    /**
     * Decrypt WooCommerce order field
     */
    public function decrypt_order_field( $value, $order ) {
        if ( is_string( $value ) && strpos( $value, '[NDK_ENCRYPTED]' ) === 0 ) {
            $customer_id = (int) $order->get_customer_id();
            if ( ! NDK_Security::can_current_user_decrypt( 'woo_order', $customer_id ) ) {
                return NDK_Security::get_masked_value();
            }
            $key_holder = $customer_id ?: 1;
            $encrypted_data = json_decode( base64_decode( substr( $value, 15 ) ), true );
            $decrypted = NDK_Encryption::decrypt_content( $encrypted_data, $key_holder );
            return $decrypted ? $decrypted : $value;
        }
        return $value;
    }

    /**
     * Encrypt Easy Digital Downloads payment data
     */
    public function encrypt_edd_payment_data( $payment_id, $payment_data ) {
        $customer_id = ! empty( $payment_data['user_info']['id'] ) ? $payment_data['user_info']['id'] : 1;

        // Encrypt email and customer info
        if ( ! empty( $payment_data['user_info']['email'] ) ) {
            $encrypted = NDK_Encryption::encrypt_content( $payment_data['user_info']['email'], $customer_id );
            if ( $encrypted ) {
                update_post_meta( $payment_id, '_edd_payment_user_email', '[NDK_ENCRYPTED]' . base64_encode( wp_json_encode( $encrypted ) ) );
            }
        }
    }

    /**
     * Encrypt Gravity Forms entry after submission
     */
    public function encrypt_gravity_forms_entry( $entry, $form ) {
        $user_id = ! empty( $entry['created_by'] ) ? $entry['created_by'] : 1;

        // Get all form fields
        foreach ( $form['fields'] as $field ) {
            $field_id = $field->id;
            $field_value = isset( $entry[ $field_id ] ) ? $entry[ $field_id ] : '';

            // Skip empty values
            if ( empty( $field_value ) ) {
                continue;
            }

            // Encrypt sensitive field types
            $sensitive_types = array( 'email', 'phone', 'address', 'name', 'textarea', 'text' );
            if ( in_array( $field->type, $sensitive_types, true ) ) {
                $encrypted = NDK_Encryption::encrypt_content( $field_value, $user_id );
                if ( $encrypted ) {
                    // Update the entry field value
                    global $wpdb;
                    $table_name = $wpdb->prefix . 'gf_entry_meta';
                    $encrypted_value = '[NDK_ENCRYPTED]' . base64_encode( wp_json_encode( $encrypted ) );

                    $wpdb->update(
                        $table_name,
                        array( 'meta_value' => $encrypted_value ),
                        array(
                            'entry_id' => $entry['id'],
                            'meta_key' => $field_id
                        ),
                        array( '%s' ),
                        array( '%d', '%s' )
                    );
                }
            }
        }

        // Encrypt partial entry data
        $this->encrypt_gravity_forms_partial_entries( $form['id'], $user_id );
    }

    /**
     * Encrypt Gravity Forms partial entries
     */
    private function encrypt_gravity_forms_partial_entries( $form_id, $user_id ) {
        global $wpdb;
        $table_name = $wpdb->prefix . 'gf_draft_submissions';

        // Get all partial entries for this form
        $partial_entries = $wpdb->get_results(
            $wpdb->prepare(
                "SELECT * FROM $table_name WHERE form_id = %d AND submission LIKE %s",
                $form_id,
                '%' . $wpdb->esc_like( '' ) . '%'
            )
        );

        foreach ( $partial_entries as $partial ) {
            $submission_data = maybe_unserialize( $partial->submission );
            if ( is_array( $submission_data ) && ! empty( $submission_data['partial_entry'] ) ) {
                // Encrypt the entire partial entry data
                $encrypted = NDK_Encryption::encrypt_content( wp_json_encode( $submission_data ), $user_id );
                if ( $encrypted ) {
                    $wpdb->update(
                        $table_name,
                        array( 'submission' => '[NDK_ENCRYPTED]' . base64_encode( wp_json_encode( $encrypted ) ) ),
                        array( 'uuid' => $partial->uuid ),
                        array( '%s' ),
                        array( '%s' )
                    );
                }
            }
        }
    }

    /**
     * Decrypt Gravity Forms field value when retrieved
     */
    public function decrypt_gravity_forms_field( $value, $entry, $field, $input_id ) {
        if ( is_string( $value ) && strpos( $value, '[NDK_ENCRYPTED]' ) === 0 ) {
            $owner_id = ! empty( $entry['created_by'] ) ? (int) $entry['created_by'] : 0;
            if ( ! NDK_Security::can_current_user_decrypt( 'gravity_forms', $owner_id ) ) {
                return NDK_Security::get_masked_value();
            }
            $key_holder = $owner_id ?: 1;
            $encrypted_data = json_decode( base64_decode( substr( $value, 15 ) ), true );
            $decrypted = NDK_Encryption::decrypt_content( $encrypted_data, $key_holder );
            return $decrypted ? $decrypted : $value;
        }
        return $value;
    }
}
