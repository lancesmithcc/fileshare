from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pqcrypto.kem import ml_kem_768


PASS_KDF_ITERATIONS = 200_000
BODY_ASSOCIATED_DATA = b"nds-chat-body-v1"
WRAP_ASSOCIATED_SENDER = b"nds-chat-wrap-sender-v1"
WRAP_ASSOCIATED_RECIPIENT = b"nds-chat-wrap-recipient-v1"


@dataclass(frozen=True)
class ChatIdentity:
    public_key: bytes
    encrypted_private_key: bytes
    salt: bytes
    nonce: bytes


@dataclass(frozen=True)
class WrappedMessageKey:
    kem_ciphertext: bytes
    wrapped_key: bytes
    nonce: bytes


def _derive_passphrase_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PASS_KDF_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def _derive_wrap_key(shared_secret: bytes, info: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=info,
    )
    return hkdf.derive(shared_secret)


def generate_identity(passphrase: str) -> ChatIdentity:
    """Create a new Kyber keypair and wrap the private key with the provided passphrase."""
    public_key, private_key = ml_kem_768.generate_keypair()
    salt = os.urandom(16)
    nonce = os.urandom(12)
    aes_key = _derive_passphrase_key(passphrase, salt)
    encrypted_private_key = AESGCM(aes_key).encrypt(nonce, private_key, None)
    return ChatIdentity(
        public_key=public_key,
        encrypted_private_key=encrypted_private_key,
        salt=salt,
        nonce=nonce,
    )


def unlock_private_key(identity: ChatIdentity, passphrase: str) -> bytes:
    """Return the decrypted private key. Raises InvalidTag when the passphrase is wrong."""
    aes_key = _derive_passphrase_key(passphrase, identity.salt)
    return AESGCM(aes_key).decrypt(identity.nonce, identity.encrypted_private_key, None)


def wrap_message_key(public_key: bytes, message_key: bytes, role: str) -> WrappedMessageKey:
    """Wrap the symmetric message key for either sender or recipient."""
    if public_key is None:
        raise ValueError("Public key is required to wrap the message key.")
    info = WRAP_ASSOCIATED_SENDER if role == "sender" else WRAP_ASSOCIATED_RECIPIENT
    kem_ciphertext, shared_secret = ml_kem_768.encrypt(public_key)
    wrap_key = _derive_wrap_key(shared_secret, info)
    nonce = os.urandom(12)
    wrapped_key = AESGCM(wrap_key).encrypt(nonce, message_key, None)
    return WrappedMessageKey(
        kem_ciphertext=kem_ciphertext,
        wrapped_key=wrapped_key,
        nonce=nonce,
    )


def unwrap_message_key(private_key: bytes, wrapped: WrappedMessageKey, role: str) -> bytes:
    """Recover the symmetric message key for the given wrapper."""
    info = WRAP_ASSOCIATED_SENDER if role == "sender" else WRAP_ASSOCIATED_RECIPIENT
    shared_secret = ml_kem_768.decrypt(private_key, wrapped.kem_ciphertext)
    wrap_key = _derive_wrap_key(shared_secret, info)
    return AESGCM(wrap_key).decrypt(wrapped.nonce, wrapped.wrapped_key, None)


def encrypt_body(message_key: bytes, plaintext: str) -> tuple[bytes, bytes]:
    """Encrypt the message body with the provided symmetric key."""
    if not isinstance(plaintext, str):
        raise TypeError("Plaintext must be a string.")
    nonce = os.urandom(12)
    ciphertext = AESGCM(message_key).encrypt(nonce, plaintext.encode("utf-8"), BODY_ASSOCIATED_DATA)
    return nonce, ciphertext


def decrypt_body(message_key: bytes, nonce: bytes, ciphertext: bytes) -> str:
    """Decrypt a previously encrypted message body."""
    plaintext = AESGCM(message_key).decrypt(nonce, ciphertext, BODY_ASSOCIATED_DATA)
    return plaintext.decode("utf-8")

