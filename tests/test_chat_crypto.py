import os
import unittest

from cryptography.exceptions import InvalidTag

from app.chat_crypto import (
    decrypt_body,
    encrypt_body,
    generate_identity,
    unlock_private_key,
    unwrap_message_key,
    wrap_message_key,
)


class ChatCryptoTests(unittest.TestCase):
    def test_identity_unlock_roundtrip(self):
        identity = generate_identity("forest passphrase")
        private_key = unlock_private_key(identity, "forest passphrase")
        self.assertIsInstance(private_key, bytes)
        self.assertGreater(len(private_key), 0)
        with self.assertRaises(InvalidTag):
            unlock_private_key(identity, "incorrect")

    def test_payload_roundtrip_for_sender_and_recipient(self):
        sender_identity = generate_identity("sender secret")
        recipient_identity = generate_identity("recipient secret")
        sender_private = unlock_private_key(sender_identity, "sender secret")
        recipient_private = unlock_private_key(recipient_identity, "recipient secret")

        message_key = os.urandom(32)
        body_nonce, body_ciphertext = encrypt_body(message_key, "Quantum grove message")

        sender_wrap = wrap_message_key(sender_identity.public_key, message_key, role="sender")
        recipient_wrap = wrap_message_key(recipient_identity.public_key, message_key, role="recipient")

        sender_unwrapped = unwrap_message_key(sender_private, sender_wrap, role="sender")
        recipient_unwrapped = unwrap_message_key(recipient_private, recipient_wrap, role="recipient")

        self.assertEqual(sender_unwrapped, recipient_unwrapped)

        decrypted = decrypt_body(sender_unwrapped, body_nonce, body_ciphertext)
        self.assertEqual(decrypted, "Quantum grove message")


if __name__ == "__main__":
    unittest.main()
