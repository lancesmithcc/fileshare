/**
 * Neo-Druidic Kyber - Admin JavaScript
 */

(function($) {
    'use strict';

    $(document).ready(function() {

        // Test API Connection
        $('#ndk-test-connection').on('click', function(e) {
            e.preventDefault();

            var $button = $(this);
            var $status = $('#ndk-connection-status');

            $button.prop('disabled', true).text('Testing...');
            $status.removeClass('success error').addClass('loading').text('Connecting...');

            $.ajax({
                url: ndkAdmin.ajaxurl,
                type: 'POST',
                data: {
                    action: 'ndk_test_connection',
                    nonce: ndkAdmin.nonce
                },
                success: function(response) {
                    if (response.success) {
                        $status.removeClass('loading error').addClass('success').text('✓ ' + response.data.message);
                    } else {
                        $status.removeClass('loading success').addClass('error').text('✗ ' + response.data.message);
                    }
                },
                error: function() {
                    $status.removeClass('loading success').addClass('error').text('✗ Connection failed');
                },
                complete: function() {
                    $button.prop('disabled', false).text('Test Connection');

                    // Clear status after 5 seconds
                    setTimeout(function() {
                        $status.fadeOut(function() {
                            $(this).removeClass('success error loading').text('').show();
                        });
                    }, 5000);
                }
            });
        });

        // Regenerate user keys
        $(document).on('click', '.ndk-regenerate-keys', function(e) {
            e.preventDefault();

            var $button = $(this);
            var userId = $button.data('user-id');

            if (!confirm('Are you sure you want to regenerate keys for this user? Previously encrypted content will become inaccessible!')) {
                return;
            }

            $button.prop('disabled', true).text('Regenerating...');

            $.ajax({
                url: ndkAdmin.ajaxurl,
                type: 'POST',
                data: {
                    action: 'ndk_generate_keys',
                    nonce: ndkAdmin.nonce,
                    user_id: userId
                },
                success: function(response) {
                    if (response.success) {
                        alert(response.data.message);
                        location.reload();
                    } else {
                        alert('Error: ' + response.data.message);
                        $button.prop('disabled', false).text('Regenerate');
                    }
                },
                error: function() {
                    alert('Failed to regenerate keys');
                    $button.prop('disabled', false).text('Regenerate');
                }
            });
        });

        // Show/hide API key
        var $apiKeyInput = $('#ndk_api_key');
        if ($apiKeyInput.length) {
            var $toggleBtn = $('<button type="button" class="button button-secondary" style="margin-left: 8px;">Show</button>');

            $apiKeyInput.after($toggleBtn);

            $toggleBtn.on('click', function() {
                if ($apiKeyInput.attr('type') === 'password') {
                    $apiKeyInput.attr('type', 'text');
                    $(this).text('Hide');
                } else {
                    $apiKeyInput.attr('type', 'password');
                    $(this).text('Show');
                }
            });
        }

    });

})(jQuery);
