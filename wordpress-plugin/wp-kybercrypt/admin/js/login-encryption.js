/**
 * WP-KyberCrypt Login Encryption
 * Quantum-safe WordPress authentication
 */

(function($) {
    'use strict';

    var ndkLoginEncryption = {
        publicKey: null,
        apiUrl: null,

        init: function() {
            // Get API URL from settings
            this.getApiUrl();

            // Fetch site public key
            this.fetchPublicKey();

            // Intercept all login forms
            this.interceptLoginForms();
        },

        getApiUrl: function() {
            var self = this;
            // Try to get from WordPress options via AJAX
            $.ajax({
                url: ndkLogin.ajaxUrl,
                type: 'POST',
                data: {
                    action: 'ndk_get_api_url',
                    nonce: ndkLogin.nonce
                },
                success: function(response) {
                    if (response.success && response.data.api_url) {
                        self.apiUrl = response.data.api_url;
                    } else {
                        // Fallback to default
                        self.apiUrl = 'https://awen01.cc';
                    }
                },
                error: function() {
                    // Fallback to default
                    self.apiUrl = 'https://awen01.cc';
                }
            });
        },

        fetchPublicKey: function() {
            var self = this;

            $.ajax({
                url: ndkLogin.ajaxUrl,
                type: 'POST',
                data: {
                    action: 'ndk_get_login_pubkey',
                    nonce: ndkLogin.nonce
                },
                success: function(response) {
                    if (response.success && response.data.public_key) {
                        self.publicKey = response.data.public_key;
                        console.log('🔐 Kyber public key loaded for quantum-safe login');
                    } else {
                        console.error('Failed to fetch login public key');
                    }
                },
                error: function() {
                    console.error('Error fetching login public key');
                }
            });
        },

        interceptLoginForms: function() {
            var self = this;

            // Wait for DOM ready
            $(document).ready(function() {
                // Standard WordPress login form
                $('#loginform, #ndk_loginform, form[name="loginform"]').on('submit', function(e) {
                    e.preventDefault();
                    self.handleLogin($(this));
                    return false;
                });
            });
        },

        handleLogin: function($form) {
            var self = this;

            if (!self.publicKey) {
                alert('Encryption not ready. Please wait a moment and try again.');
                return;
            }

            // Get form values
            var username = $form.find('input[name="log"], input[type="text"]').first().val();
            var password = $form.find('input[name="pwd"], input[type="password"]').first().val();
            var remember = $form.find('input[name="rememberme"], input[type="checkbox"]').first().is(':checked');
            var redirectTo = $form.find('input[name="redirect_to"]').val() || window.location.href;

            if (!username || !password) {
                alert('Please enter your username and password.');
                return;
            }

            // Show loading indicator
            var $submitBtn = $form.find('input[type="submit"]');
            var originalText = $submitBtn.val();
            $submitBtn.val('🔐 Encrypting...').prop('disabled', true);

            // Encrypt credentials with Kyber
            Promise.all([
                self.encryptWithKyber(username),
                self.encryptWithKyber(password)
            ])
            .then(function(results) {
                var encryptedUsername = results[0];
                var encryptedPassword = results[1];

                // Send encrypted login
                return self.sendEncryptedLogin(encryptedUsername, encryptedPassword, remember, redirectTo);
            })
            .then(function(response) {
                if (response.success) {
                    $submitBtn.val('✓ Success! Redirecting...');
                    // Redirect to destination
                    window.location.href = response.data.redirect_to;
                } else {
                    $submitBtn.val(originalText).prop('disabled', false);
                    alert('Login failed: ' + (response.data.message || 'Unknown error'));
                }
            })
            .catch(function(error) {
                console.error('Login encryption error:', error);
                $submitBtn.val(originalText).prop('disabled', false);
                alert('Encryption error: ' + error.message);
            });
        },

        encryptWithKyber: function(plaintext) {
            var self = this;

            return new Promise(function(resolve, reject) {
                if (!self.apiUrl) {
                    reject(new Error('API URL not configured'));
                    return;
                }

                $.ajax({
                    url: self.apiUrl + '/api/v1/kyber/encrypt',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({
                        public_key: self.publicKey,
                        plaintext: plaintext
                    }),
                    success: function(response) {
                        if (response.success && response.data) {
                            resolve(response.data);
                        } else {
                            reject(new Error('Encryption failed: ' + (response.message || 'Unknown error')));
                        }
                    },
                    error: function(xhr, status, error) {
                        reject(new Error('API request failed: ' + error));
                    }
                });
            });
        },

        sendEncryptedLogin: function(encryptedUsername, encryptedPassword, remember, redirectTo) {
            return new Promise(function(resolve, reject) {
                $.ajax({
                    url: ndkLogin.ajaxUrl,
                    type: 'POST',
                    data: {
                        action: 'ndk_encrypted_login',
                        nonce: ndkLogin.nonce,
                        encrypted_username: JSON.stringify(encryptedUsername),
                        encrypted_password: JSON.stringify(encryptedPassword),
                        remember: remember ? 'true' : 'false',
                        redirect_to: redirectTo
                    },
                    success: function(response) {
                        resolve(response);
                    },
                    error: function(xhr, status, error) {
                        reject(new Error('Login request failed: ' + error));
                    }
                });
            });
        }
    };

    // Initialize on page load
    $(function() {
        ndkLoginEncryption.init();
    });

})(jQuery);
