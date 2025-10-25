from __future__ import annotations

import base64

from flask import session

SESSION_PRIVATE_KEY = "chat_private_key"
SESSION_PRIVATE_KEY_VERSION = "chat_private_key_version"


def store_private_key(private_key: bytes, version: int | None) -> None:
    session[SESSION_PRIVATE_KEY] = base64.b64encode(private_key).decode("ascii")
    session[SESSION_PRIVATE_KEY_VERSION] = version


def get_private_key(expected_version: int | None) -> bytes | None:
    stored = session.get(SESSION_PRIVATE_KEY)
    version = session.get(SESSION_PRIVATE_KEY_VERSION)
    if stored is None or version is None:
        return None
    if expected_version is not None and version != expected_version:
        clear_private_key()
        return None
    try:
        return base64.b64decode(stored)
    except (ValueError, TypeError):
        clear_private_key()
        return None


def clear_private_key() -> None:
    session.pop(SESSION_PRIVATE_KEY, None)
    session.pop(SESSION_PRIVATE_KEY_VERSION, None)
