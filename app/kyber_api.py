"""
Kyber (ML-KEM-768) Quantum-Safe Encryption API

This module provides REST API endpoints for post-quantum cryptographic operations
using the ML-KEM-768 algorithm (NIST's standardized Kyber variant).
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from pqcrypto.kem import ml_kem_768

from .chat_crypto import (
    decrypt_body,
    encrypt_body,
    generate_identity,
    unlock_private_key,
    unwrap_message_key,
    wrap_message_key,
    ChatIdentity,
    WrappedMessageKey,
)

logger = logging.getLogger(__name__)

kyber_api_bp = Blueprint("kyber_api", __name__, url_prefix="/api/v1/kyber")


def _enforce_api_key():
    """Enforce API key authentication for Kyber endpoints."""
    allowed_keys = current_app.config.get("AI_API_KEYS", set())

    # Also check for a dedicated Kyber API key
    kyber_key = current_app.config.get("KYBER_API_KEY")
    if kyber_key:
        allowed_keys = allowed_keys | {kyber_key}

    if not allowed_keys:
        return None  # No API key required if none configured

    supplied = request.headers.get("X-API-Key")
    if supplied in allowed_keys:
        return None

    logger.warning("Rejected Kyber API request with missing or invalid API key.")
    return jsonify({"error": "Unauthorized"}), 401


def _b64_encode(data: bytes) -> str:
    """Encode bytes to base64 string."""
    return base64.b64encode(data).decode("ascii")


def _b64_decode(data: str) -> bytes:
    """Decode base64 string to bytes."""
    try:
        return base64.b64decode(data)
    except Exception:
        raise ValueError("Invalid base64 encoding")


@kyber_api_bp.route("/info", methods=["GET"])
def info():
    """Get information about the Kyber implementation."""
    return jsonify({
        "algorithm": "ML-KEM-768",
        "description": "NIST-standardized post-quantum key encapsulation mechanism",
        "public_key_size": 1184,
        "private_key_size": 2400,
        "ciphertext_size": 1088,
        "shared_secret_size": 32,
        "security_level": "NIST Level 3 (equivalent to AES-192)",
        "version": "1.0.0"
    })


@kyber_api_bp.route("/keypair/generate", methods=["POST"])
def generate_keypair():
    """
    Generate a new Kyber keypair.

    Request JSON:
    {
        "passphrase": "optional passphrase to encrypt private key"
    }

    Response:
    {
        "public_key": "base64-encoded public key",
        "private_key": "base64-encoded private key (or encrypted if passphrase provided)",
        "salt": "base64-encoded salt (if passphrase provided)",
        "nonce": "base64-encoded nonce (if passphrase provided)"
    }
    """
    api_guard = _enforce_api_key()
    if api_guard:
        return api_guard

    payload = request.get_json(silent=True) or {}
    passphrase = payload.get("passphrase")

    if passphrase:
        # Generate identity with encrypted private key
        identity = generate_identity(passphrase)
        return jsonify({
            "public_key": _b64_encode(identity.public_key),
            "encrypted_private_key": _b64_encode(identity.encrypted_private_key),
            "salt": _b64_encode(identity.salt),
            "nonce": _b64_encode(identity.nonce),
            "encrypted": True
        })
    else:
        # Generate raw keypair
        public_key, private_key = ml_kem_768.generate_keypair()
        return jsonify({
            "public_key": _b64_encode(public_key),
            "private_key": _b64_encode(private_key),
            "encrypted": False
        })


@kyber_api_bp.route("/keypair/unlock", methods=["POST"])
def unlock_keypair():
    """
    Unlock an encrypted private key with a passphrase.

    Request JSON:
    {
        "encrypted_private_key": "base64-encoded encrypted private key",
        "salt": "base64-encoded salt",
        "nonce": "base64-encoded nonce",
        "passphrase": "the passphrase"
    }

    Response:
    {
        "private_key": "base64-encoded decrypted private key"
    }
    """
    api_guard = _enforce_api_key()
    if api_guard:
        return api_guard

    payload = request.get_json(silent=True) or {}

    try:
        encrypted_private_key = _b64_decode(payload.get("encrypted_private_key", ""))
        salt = _b64_decode(payload.get("salt", ""))
        nonce = _b64_decode(payload.get("nonce", ""))
        passphrase = payload.get("passphrase", "")

        if not passphrase:
            return jsonify({"error": "Passphrase is required"}), 400

        identity = ChatIdentity(
            public_key=b"",  # Not needed for unlock
            encrypted_private_key=encrypted_private_key,
            salt=salt,
            nonce=nonce
        )

        private_key = unlock_private_key(identity, passphrase)

        return jsonify({
            "private_key": _b64_encode(private_key)
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to unlock private key: {e}")
        return jsonify({"error": "Invalid passphrase or corrupted data"}), 400


@kyber_api_bp.route("/encapsulate", methods=["POST"])
def encapsulate():
    """
    Encapsulate a shared secret using a public key (KEM encryption).

    Request JSON:
    {
        "public_key": "base64-encoded Kyber public key"
    }

    Response:
    {
        "ciphertext": "base64-encoded KEM ciphertext",
        "shared_secret": "base64-encoded shared secret"
    }
    """
    api_guard = _enforce_api_key()
    if api_guard:
        return api_guard

    payload = request.get_json(silent=True) or {}

    try:
        public_key = _b64_decode(payload.get("public_key", ""))

        if len(public_key) != 1184:
            return jsonify({"error": "Invalid public key size (expected 1184 bytes)"}), 400

        ciphertext, shared_secret = ml_kem_768.encrypt(public_key)

        return jsonify({
            "ciphertext": _b64_encode(ciphertext),
            "shared_secret": _b64_encode(shared_secret)
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Encapsulation failed: {e}")
        return jsonify({"error": "Encapsulation failed"}), 500


@kyber_api_bp.route("/decapsulate", methods=["POST"])
def decapsulate():
    """
    Decapsulate a shared secret using a private key (KEM decryption).

    Request JSON:
    {
        "private_key": "base64-encoded Kyber private key",
        "ciphertext": "base64-encoded KEM ciphertext"
    }

    Response:
    {
        "shared_secret": "base64-encoded shared secret"
    }
    """
    api_guard = _enforce_api_key()
    if api_guard:
        return api_guard

    payload = request.get_json(silent=True) or {}

    try:
        private_key = _b64_decode(payload.get("private_key", ""))
        ciphertext = _b64_decode(payload.get("ciphertext", ""))

        if len(private_key) != 2400:
            return jsonify({"error": "Invalid private key size (expected 2400 bytes)"}), 400

        if len(ciphertext) != 1088:
            return jsonify({"error": "Invalid ciphertext size (expected 1088 bytes)"}), 400

        shared_secret = ml_kem_768.decrypt(private_key, ciphertext)

        return jsonify({
            "shared_secret": _b64_encode(shared_secret)
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Decapsulation failed: {e}")
        return jsonify({"error": "Decapsulation failed"}), 500


@kyber_api_bp.route("/encrypt", methods=["POST"])
def encrypt_message():
    """
    Encrypt a message using hybrid encryption (Kyber KEM + AES-GCM).

    Request JSON:
    {
        "recipient_public_key": "base64-encoded Kyber public key",
        "plaintext": "the message to encrypt"
    }

    Response:
    {
        "kem_ciphertext": "base64-encoded KEM ciphertext",
        "wrapped_key": "base64-encoded wrapped AES key",
        "wrap_nonce": "base64-encoded wrap nonce",
        "body_nonce": "base64-encoded body nonce",
        "ciphertext": "base64-encoded encrypted message"
    }
    """
    api_guard = _enforce_api_key()
    if api_guard:
        return api_guard

    payload = request.get_json(silent=True) or {}

    try:
        public_key = _b64_decode(payload.get("recipient_public_key", ""))
        plaintext = payload.get("plaintext", "")

        if not plaintext:
            return jsonify({"error": "Plaintext is required"}), 400

        # Generate a random message key
        import os
        message_key = os.urandom(32)

        # Wrap the message key for the recipient
        wrapped = wrap_message_key(public_key, message_key, "recipient")

        # Encrypt the message body
        body_nonce, ciphertext = encrypt_body(message_key, plaintext)

        return jsonify({
            "kem_ciphertext": _b64_encode(wrapped.kem_ciphertext),
            "wrapped_key": _b64_encode(wrapped.wrapped_key),
            "wrap_nonce": _b64_encode(wrapped.nonce),
            "body_nonce": _b64_encode(body_nonce),
            "ciphertext": _b64_encode(ciphertext)
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return jsonify({"error": "Encryption failed"}), 500


@kyber_api_bp.route("/decrypt", methods=["POST"])
def decrypt_message():
    """
    Decrypt a message using hybrid encryption (Kyber KEM + AES-GCM).

    Request JSON:
    {
        "private_key": "base64-encoded Kyber private key",
        "kem_ciphertext": "base64-encoded KEM ciphertext",
        "wrapped_key": "base64-encoded wrapped AES key",
        "wrap_nonce": "base64-encoded wrap nonce",
        "body_nonce": "base64-encoded body nonce",
        "ciphertext": "base64-encoded encrypted message"
    }

    Response:
    {
        "plaintext": "the decrypted message"
    }
    """
    api_guard = _enforce_api_key()
    if api_guard:
        return api_guard

    payload = request.get_json(silent=True) or {}

    try:
        private_key = _b64_decode(payload.get("private_key", ""))
        kem_ciphertext = _b64_decode(payload.get("kem_ciphertext", ""))
        wrapped_key = _b64_decode(payload.get("wrapped_key", ""))
        wrap_nonce = _b64_decode(payload.get("wrap_nonce", ""))
        body_nonce = _b64_decode(payload.get("body_nonce", ""))
        ciphertext = _b64_decode(payload.get("ciphertext", ""))

        # Reconstruct the wrapped message key
        wrapped = WrappedMessageKey(
            kem_ciphertext=kem_ciphertext,
            wrapped_key=wrapped_key,
            nonce=wrap_nonce
        )

        # Unwrap the message key
        message_key = unwrap_message_key(private_key, wrapped, "recipient")

        # Decrypt the message body
        plaintext = decrypt_body(message_key, body_nonce, ciphertext)

        return jsonify({
            "plaintext": plaintext
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return jsonify({"error": "Decryption failed or invalid key"}), 400
