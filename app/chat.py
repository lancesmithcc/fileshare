from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from typing import Iterable, Optional

import sqlalchemy as sa
from sqlalchemy.orm import joinedload, selectinload
from cryptography.exceptions import InvalidTag
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from simple_websocket import ConnectionClosed

from .ai import _model_insight
from .chat_crypto import (
    ChatIdentity,
    WrappedMessageKey,
    decrypt_body,
    encrypt_body,
    generate_identity,
    unlock_private_key,
    unwrap_message_key,
    wrap_message_key,
)
from . import chat_session
from .database import db
from .extensions import sock
from .files import _asset_path
from .models import (
    ChatBlock,
    CircleMembership,
    ChatMessage,
    ChatMessageKey,
    ChatThread,
    ChatThreadMember,
    FileAsset,
    User,
)

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

ARCHDRUID_USERNAME = os.environ.get("NEO_DRUIDIC_ARCHDRUID_USERNAME", "archdruid")
ARCHDRUID_EMAIL = os.environ.get(
    "NEO_DRUIDIC_ARCHDRUID_EMAIL", f"{ARCHDRUID_USERNAME}@neo-druidic.local"
)
ARCHDRUID_PASSWORD = os.environ.get(
    "NEO_DRUIDIC_ARCHDRUID_PASSWORD", "eldara-forest-pass"
)

THREAD_PARAM = "thread"
MAX_MESSAGE_LENGTH = 4000
GROUP_MEMBER_LIMIT = 16


@dataclass(frozen=True)
class ThreadSummary:
    thread: ChatThread
    display_name: str
    preview: str
    last_at: datetime | None
    unread_count: int
    is_group: bool
    owner_id: int


@dataclass(eq=False)
class ChatConnection:
    user_id: int
    ws: object
    private_key: Optional[bytes]
    subscribed_threads: set[int] = field(default_factory=set)

    def __hash__(self) -> int:
        return id(self)

    def update_private_key(self, private_key: Optional[bytes]) -> None:
        self.private_key = private_key

    def send_event(self, payload: dict) -> bool:
        try:
            self.ws.send(json.dumps(payload))
            return True
        except ConnectionClosed:
            return False


_thread_subscribers: dict[int, set[ChatConnection]] = defaultdict(set)
_user_connections: dict[int, set[ChatConnection]] = defaultdict(set)
_connection_lock = Lock()


def _register_connection(connection: ChatConnection) -> None:
    with _connection_lock:
        _user_connections[connection.user_id].add(connection)


def _unsubscribe_connection(connection: ChatConnection, thread_id: int) -> None:
    with _connection_lock:
        if thread_id in connection.subscribed_threads:
            connection.subscribed_threads.discard(thread_id)
            subscribers = _thread_subscribers.get(thread_id)
            if subscribers is not None:
                subscribers.discard(connection)
                if not subscribers:
                    _thread_subscribers.pop(thread_id, None)


def _subscribe_connection(connection: ChatConnection, thread_id: int) -> None:
    with _connection_lock:
        connection.subscribed_threads.add(thread_id)
        _thread_subscribers[thread_id].add(connection)


def _unregister_connection(connection: ChatConnection) -> None:
    with _connection_lock:
        for thread_id in list(connection.subscribed_threads):
            subscribers = _thread_subscribers.get(thread_id)
            if subscribers is not None:
                subscribers.discard(connection)
                if not subscribers:
                    _thread_subscribers.pop(thread_id, None)
        connection.subscribed_threads.clear()
        if connection.user_id in _user_connections:
            conns = _user_connections[connection.user_id]
            conns.discard(connection)
            if not conns:
                _user_connections.pop(connection.user_id, None)


def _cleanup_stale_connections(connections: list[ChatConnection]) -> None:
    for connection in connections:
        _unregister_connection(connection)


def _handle_subscribe_event(connection: ChatConnection, thread_id_raw) -> None:
    try:
        thread_id = int(thread_id_raw)
    except (TypeError, ValueError):
        connection.send_event({"type": "error", "message": "Invalid channel identifier."})
        return
    thread = _fetch_thread_for_user(thread_id, connection.user_id)
    if thread is None:
        connection.send_event({"type": "error", "message": "Channel unavailable.", "thread_id": thread_id})
        return
    already = thread_id in connection.subscribed_threads
    _subscribe_connection(connection, thread_id)
    if already:
        connection.send_event(
            {
                "type": "subscribed",
                "thread_id": thread_id,
                "messages": [],
                "locked": connection.private_key is None,
                "display_name": _thread_display_name(thread),
                "is_group": thread.type == "group",
                "owner_id": thread.creator_id,
            }
        )
        return
    messages = _thread_history_for_connection(thread, connection)
    connection.send_event(
        {
            "type": "subscribed",
            "thread_id": thread_id,
            "messages": messages,
            "locked": connection.private_key is None,
            "display_name": _thread_display_name(thread),
            "is_group": thread.type == "group",
            "owner_id": thread.creator_id,
        }
    )


def _handle_unsubscribe_event(connection: ChatConnection, thread_id_raw) -> None:
    try:
        thread_id = int(thread_id_raw)
    except (TypeError, ValueError):
        return
    _unsubscribe_connection(connection, thread_id)
    connection.send_event({"type": "unsubscribed", "thread_id": thread_id})


@sock.route("/chat/ws")
def chat_ws(ws):
    if not current_user.is_authenticated:
        ws.close()
        return

    private_key = chat_session.get_private_key(current_user.chat_identity_version)
    connection = ChatConnection(user_id=current_user.id, ws=ws, private_key=private_key)
    _register_connection(connection)
    connection.send_event({"type": "welcome", "locked": private_key is None})

    try:
        while True:
            try:
                payload = ws.receive()
            except ConnectionClosed:
                break
            if payload is None:
                break
            try:
                data = json.loads(payload)
            except ValueError:
                connection.send_event({"type": "error", "message": "Invalid payload."})
                continue

            action = data.get("action")
            if action == "subscribe":
                _handle_subscribe_event(connection, data.get("thread_id"))
            elif action == "unsubscribe":
                _handle_unsubscribe_event(connection, data.get("thread_id"))
            elif action == "refresh":
                refreshed_key = chat_session.get_private_key(current_user.chat_identity_version)
                connection.update_private_key(refreshed_key)
                connection.send_event({"type": "refreshed", "locked": refreshed_key is None})
            elif action == "ping":
                connection.send_event({"type": "pong"})
            else:
                connection.send_event({"type": "error", "message": "Unknown action."})
    finally:
        _unregister_connection(connection)


@chat_bp.route("/api/context", methods=["GET"])
@login_required
def chat_context_api():
    state = _chat_ready_state()
    private_key = None
    if state == "ready":
        private_key = chat_session.get_private_key(current_user.chat_identity_version)
    summaries = _thread_summaries(private_key)
    threads_payload = [
        {
            "id": summary.thread.id,
            "display_name": summary.display_name,
            "preview": summary.preview,
            "unread_count": summary.unread_count,
            "is_group": summary.is_group,
            "owner_id": summary.owner_id,
        }
        for summary in summaries
    ]
    return jsonify(
        {
            "state": state,
            "max_length": MAX_MESSAGE_LENGTH,
            "threads": threads_payload,
            "current_user_id": current_user.id,
        }
    )


@chat_bp.route("/api/online", methods=["GET"])
@login_required
def chat_online_api():
    """Return a snapshot of active members available for whispers."""
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    online_users = (
        User.query.options(joinedload(User.circle_membership).joinedload(CircleMembership.circle))
        .filter(
            User.id != current_user.id,
            User.status == "active",
            User.last_seen.isnot(None),
            User.last_seen >= cutoff,
        )
        .order_by(User.username.asc())
        .all()
    )

    circle_summary: dict[int | None, dict] = {}
    for user in online_users:
        membership = user.circle_membership
        circle = membership.circle if membership else None
        if circle:
            summary_id: int | str = circle.id
            summary_name = circle.name
        else:
            summary_id = "unaffiliated"
            summary_name = "unaffiliated"
        if summary_id not in circle_summary:
            circle_summary[summary_id] = {
                "id": summary_id,
                "name": summary_name,
                "online_count": 0,
            }
        circle_summary[summary_id]["online_count"] += 1

    current_membership = current_user.circle_membership
    current_circle_id = current_membership.circle_id if current_membership else None

    payload_users = [
        {
            "id": user.id,
            "username": user.username,
            "has_chat_keys": user.has_chat_keys,
            "avatar_url": (
                url_for("social.profile_media", asset=user.profile_image)
                if user.profile_image
                else url_for("static", filename="img/triple.svg.png")
            ),
            "circle": (
                {
                    "id": user.circle_membership.circle.id,
                    "name": user.circle_membership.circle.name,
                }
                if user.circle_membership and user.circle_membership.circle
                else None
            ),
            "same_circle": (
                user.circle_membership.circle_id == current_circle_id
                if user.circle_membership
                else False
            ),
        }
        for user in online_users
    ]

    circle_payload = [
        entry for entry in circle_summary.values() if isinstance(entry["id"], int)
    ]
    circle_payload.sort(key=lambda item: item["name"].lower())
    unaffiliated_entry = circle_summary.get("unaffiliated")
    if unaffiliated_entry:
        circle_payload.append(unaffiliated_entry)

    return jsonify(
        {
            "users": payload_users,
            "circles": circle_payload,
            "total_online": len(payload_users),
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
    )


@chat_bp.route("/api/recipients", methods=["GET"])
@login_required
def chat_recipients_api():
    recipients = _available_users_for_selection()
    payload = []
    for user in recipients:
        payload.append(
            {
                "id": user.id,
                "username": user.username,
                "has_chat_keys": user.has_chat_keys,
                "avatar_url": _avatar_url(user),
                "is_online": user.is_online,
            }
        )
    return jsonify({"users": payload, "generated_at": datetime.utcnow().isoformat() + "Z"})


def _current_identity() -> ChatIdentity | None:
    identity = _identity_from_user(current_user)
    if identity is None:
        current_app.logger.warning("Chat identity missing for user_id=%s", current_user.id)
    return identity


def _chat_ready_state() -> str:
    identity = _current_identity()
    if not identity:
        return "provisioning"
    private_key = chat_session.get_private_key(current_user.chat_identity_version)
    if private_key is None:
        return "locked"
    return "ready"


def _is_user_blocked(user_id: int) -> bool:
    """Check if current user has blocked the specified user."""
    return db.session.query(
        ChatBlock.query.filter_by(
            blocker_id=current_user.id,
            blocked_id=user_id
        ).exists()
    ).scalar()


def _get_blocked_user_id_for_dm(thread: ChatThread) -> int | None:
    """For DM threads, return the other user's ID if current user has them blocked."""
    if thread.type != "dm":
        return None
    other_user = next(
        (member.user for member in thread.members if member.user_id != current_user.id),
        None
    )
    if other_user and _is_user_blocked(other_user.id):
        return other_user.id
    return None


def _thread_display_name(thread: ChatThread) -> str:
    if thread.type == "group":
        return thread.title or "Circle Room"
    other_members = [
        member.user.username
        for member in thread.members
        if member.user_id != current_user.id
    ]
    if not other_members:
        return current_user.username
    return ", ".join(sorted(other_members))


def _thread_participant_users(thread: ChatThread) -> list[User]:
    return [member.user for member in thread.members]


def _identity_from_user(user: User) -> ChatIdentity | None:
    if not user.has_chat_keys:
        return None
    return ChatIdentity(
        public_key=user.chat_public_key,
        encrypted_private_key=user.chat_private_key_encrypted,
        salt=user.chat_key_salt,
        nonce=user.chat_private_key_nonce,
    )


def _provision_identity(user: User, passphrase: str) -> tuple[ChatIdentity, bytes]:
    identity = generate_identity(passphrase)
    now = datetime.utcnow()
    user.chat_public_key = identity.public_key
    user.chat_private_key_encrypted = identity.encrypted_private_key
    user.chat_private_key_nonce = identity.nonce
    user.chat_key_salt = identity.salt
    user.chat_identity_version = (user.chat_identity_version or 0) + 1
    if user.chat_enabled_at is None:
        user.chat_enabled_at = now
    user.chat_keys_rotated_at = now
    db.session.add(user)
    private_key = unlock_private_key(identity, passphrase)
    return identity, private_key


def ensure_chat_identity(user: User, passphrase: str, *, rotate_on_failure: bool = True) -> bytes:
    identity = _identity_from_user(user)
    if identity is None:
        _, private_key = _provision_identity(user, passphrase)
        return private_key
    try:
        return unlock_private_key(identity, passphrase)
    except InvalidTag:
        if not rotate_on_failure:
            raise
        current_app.logger.warning(
            "Rotating chat keys for user_id=%s due to failed unlock.", user.id
        )
        _, private_key = _provision_identity(user, passphrase)
        return private_key


def provision_chat_identity(user: User, passphrase: str) -> None:
    if user.has_chat_keys:
        return
    _provision_identity(user, passphrase)


def _unread_counts(thread_ids: Iterable[int]) -> dict[int, int]:
    if not thread_ids:
        return {}
    rows = (
        db.session.query(ChatMessage.thread_id, sa.func.count(ChatMessageKey.id))
        .join(ChatMessageKey, ChatMessage.id == ChatMessageKey.message_id)
        .filter(ChatMessage.thread_id.in_(thread_ids))
        .filter(ChatMessageKey.user_id == current_user.id)
        .filter(ChatMessageKey.read_at.is_(None))
        .group_by(ChatMessage.thread_id)
        .all()
    )
    return {thread_id: count for thread_id, count in rows}


def _format_timestamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _avatar_url(user: User) -> str:
    if user.profile_image:
        return url_for("social.profile_media", asset=user.profile_image)
    return url_for("static", filename="img/triple.svg.png")


def _shared_hollow_snippets(max_files: int = 6, max_chars: int = 400) -> list[str]:
    assets = (
        FileAsset.query.filter(FileAsset.share_token.isnot(None))
        .order_by(FileAsset.created_at.desc())
        .limit(max_files)
        .all()
    )
    if not assets:
        assets = (
            FileAsset.query.filter(FileAsset.mime_type.like("text/%"))
            .order_by(FileAsset.created_at.desc())
            .limit(max_files)
            .all()
        )

    snippets: list[str] = []
    for asset in assets:
        path = _asset_path(asset)
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                raw = handle.read(max_chars * 2)
        except (OSError, ValueError):
            continue
        text = " ".join(raw.split())
        if not text:
            continue
        snippet = text[:max_chars].strip()
        if not snippet:
            continue
        snippets.append(f"{asset.original_name}: {snippet}")
    return snippets


def _sender_payload(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "avatar_url": _avatar_url(user),
        "profile_url": url_for("social.profile", username=user.username),
        "message_url": url_for("chat.index", **{"with": user.id}),
    }


def _user_can_delete_message(thread: ChatThread, message: ChatMessage, user_id: int) -> bool:
    if message.sender_id == user_id:
        return True
    if thread.type == "group":
        member = next((entry for entry in thread.members if entry.user_id == user_id), None)
        if member and member.is_admin:
            return True
    return False


def _build_message_payload(
    thread: ChatThread,
    message: ChatMessage,
    connection: ChatConnection,
) -> dict:
    locked = connection.private_key is None
    if locked:
        body = "Unlock to reveal this message."
    else:
        body, _ = _unwrap_body(message, connection.private_key, connection.user_id)
    return {
        "id": message.id,
        "body": body,
        "created_at": message.created_at.isoformat() + "Z",
        "created_label": _format_timestamp(message.created_at),
        "sender": _sender_payload(message.sender),
        "is_self": message.sender_id == connection.user_id,
        "locked": locked,
        "can_delete": _user_can_delete_message(thread, message, connection.user_id),
    }


def _broadcast_message(thread: ChatThread, message: ChatMessage) -> None:
    with _connection_lock:
        subscribers = list(_thread_subscribers.get(thread.id, set()))
    if not subscribers:
        return
    stale: list[ChatConnection] = []
    for connection in subscribers:
        payload = {
            "type": "message",
            "thread_id": thread.id,
            "message": _build_message_payload(thread, message, connection),
        }
        if not connection.send_event(payload):
            stale.append(connection)
    if stale:
        _cleanup_stale_connections(stale)


def _broadcast_message_deleted(thread: ChatThread, message_id: int) -> None:
    with _connection_lock:
        subscribers = list(_thread_subscribers.get(thread.id, set()))
    if not subscribers:
        return
    stale: list[ChatConnection] = []
    payload = {"type": "message_deleted", "thread_id": thread.id, "message_id": message_id}
    for connection in subscribers:
        if not connection.send_event(payload):
            stale.append(connection)
    if stale:
        _cleanup_stale_connections(stale)


def _fetch_thread_for_user(thread_id: int, user_id: int) -> ChatThread | None:
    thread = (
        ChatThread.query.options(
            selectinload(ChatThread.members).selectinload(ChatThreadMember.user),
        )
        .filter(ChatThread.id == thread_id)
        .first()
    )
    if not thread:
        return None
    if not any(member.user_id == user_id for member in thread.members):
        return None
    return thread


def _thread_history_for_connection(thread: ChatThread, connection: ChatConnection) -> list[dict]:
    history = (
        ChatMessage.query.filter(ChatMessage.thread_id == thread.id)
        .order_by(ChatMessage.created_at.asc())
        .options(joinedload(ChatMessage.sender), selectinload(ChatMessage.keys))
        .all()
    )
    return [_build_message_payload(thread, message, connection) for message in history]


def _unwrap_body(message: ChatMessage, private_key: bytes, user_id: int) -> tuple[str, bool]:
    entry = next((key for key in message.keys if key.user_id == user_id), None)
    if entry is None:
        return "[unable to decrypt message]", False
    role = "sender" if message.sender_id == user_id else "recipient"
    wrapped = WrappedMessageKey(
        kem_ciphertext=entry.kem_ciphertext,
        wrapped_key=entry.wrapped_key,
        nonce=entry.wrap_nonce,
    )
    try:
        message_key = unwrap_message_key(private_key, wrapped, role=role)
        body = decrypt_body(message_key, message.body_nonce, message.body_ciphertext)
    except (InvalidTag, ValueError):
        current_app.logger.warning("Failed to decrypt message_id=%s for user=%s", message.id, user_id)
        return "[unable to decrypt message]", False
    return body, entry.read_at is not None


def _thread_summaries(private_key: bytes | None) -> list[ThreadSummary]:
    threads = (
        ChatThread.query.join(ChatThreadMember)
        .filter(ChatThreadMember.user_id == current_user.id)
        .options(
            selectinload(ChatThread.members).selectinload(ChatThreadMember.user),
        )
        .all()
    )
    thread_ids = [thread.id for thread in threads]
    unread_lookup = _unread_counts(thread_ids)

    summary_list: list[ThreadSummary] = []
    for thread in threads:
        last_message = (
            ChatMessage.query.filter(ChatMessage.thread_id == thread.id)
            .order_by(ChatMessage.created_at.desc())
            .options(
                joinedload(ChatMessage.sender),
                selectinload(ChatMessage.keys),
            )
            .limit(1)
            .one_or_none()
        )
        preview = "No messages yet."
        last_at = None
        if last_message:
            last_at = last_message.created_at
            if private_key:
                preview, _ = _unwrap_body(last_message, private_key, current_user.id)
            else:
                preview = "Unlock to reveal the latest whisper."
        summary_list.append(
            ThreadSummary(
                thread=thread,
                display_name=_thread_display_name(thread),
                preview=preview,
                last_at=last_at,
                unread_count=unread_lookup.get(thread.id, 0),
                is_group=thread.type == "group",
                owner_id=thread.creator_id,
            )
        )
    summary_list.sort(key=lambda summary: summary.last_at or datetime.min, reverse=True)
    return summary_list


def _load_thread_for_user(thread_id: int) -> ChatThread | None:
    thread = (
        ChatThread.query.options(
            selectinload(ChatThread.members).selectinload(ChatThreadMember.user),
        )
        .filter(ChatThread.id == thread_id)
        .first()
    )
    if not thread:
        return None
    if not any(member.user_id == current_user.id for member in thread.members):
        return None
    return thread


def _ensure_members_have_keys(thread: ChatThread) -> bool:
    missing = [
        member.user.username
        for member in thread.members
        if not member.user.has_chat_keys
    ]
    if missing:
        flash(
            "Encrypted chat requires every member to generate keys first. Missing: {}.".format(
                ", ".join(missing)
            ),
            "warning",
        )
        return False
    return True


def _persist_message(thread: ChatThread, sender: User, plaintext: str) -> ChatMessage:
    message_key = os.urandom(32)
    body_nonce, body_ciphertext = encrypt_body(message_key, plaintext)
    message = ChatMessage(
        thread=thread,
        sender=sender,
        body_ciphertext=body_ciphertext,
        body_nonce=body_nonce,
    )
    db.session.add(message)
    db.session.flush()

    now = datetime.utcnow()
    for member in thread.members:
        role = "sender" if member.user_id == sender.id else "recipient"
        wrapped = wrap_message_key(member.user.chat_public_key, message_key, role=role)
        key_row = ChatMessageKey(
            message=message,
            user_id=member.user_id,
            kem_ciphertext=wrapped.kem_ciphertext,
            wrapped_key=wrapped.wrapped_key,
            wrap_nonce=wrapped.nonce,
            read_at=now if member.user_id == sender.id else None,
        )
        db.session.add(key_row)

    return message


def _handle_member_departure(thread: ChatThread, membership: ChatThreadMember) -> None:
    db.session.delete(membership)
    db.session.flush()
    remaining_members = (
        ChatThreadMember.query.filter(ChatThreadMember.thread_id == thread.id).all()
    )
    if not remaining_members:
        db.session.delete(thread)
        return
    if (
        thread.type == "group"
        and membership.is_admin
        and not any(member.is_admin for member in remaining_members)
    ):
        promote = min(
            remaining_members,
            key=lambda member: member.joined_at or datetime.utcnow(),
        )
        promote.is_admin = True


def _thread_has_archdruid(thread: ChatThread) -> bool:
    username_lower = ARCHDRUID_USERNAME.lower()
    return any(member.user.username.lower() == username_lower for member in thread.members)


def ensure_archdruid_user() -> User:
    username_lower = ARCHDRUID_USERNAME.lower()
    archdruid = (
        User.query.filter(sa.func.lower(User.username) == username_lower)
        .limit(1)
        .one_or_none()
    )
    created = False
    if archdruid is None:
        archdruid = User(
            username=ARCHDRUID_USERNAME,
            email=ARCHDRUID_EMAIL,
            status="active",
            role="arch",
        )
        archdruid.set_password(ARCHDRUID_PASSWORD)
        db.session.add(archdruid)
        db.session.flush()
        created = True
    if not archdruid.has_chat_keys:
        provision_chat_identity(archdruid, ARCHDRUID_PASSWORD)
        created = True
    if created:
        db.session.commit()
    return archdruid


def get_archdruid_user() -> User:
    username_lower = ARCHDRUID_USERNAME.lower()
    archdruid = (
        User.query.filter(sa.func.lower(User.username) == username_lower)
        .limit(1)
        .one_or_none()
    )
    if archdruid is None:
        archdruid = ensure_archdruid_user()
    return archdruid


def _generate_archdruid_prompt(sender: User, body: str, thread: ChatThread) -> str:
    participants = [
        member.user.username
        for member in thread.members
        if member.user_id != sender.id
    ]
    participant_list = ", ".join(sorted(participants))
    knowledge_snippets = _shared_hollow_snippets()
    if knowledge_snippets:
        knowledge_section = (
            "Recent wisdom from the Shared Hollow and Knowledge Garden:\n"
            + "\n".join(f"- {entry}" for entry in knowledge_snippets)
            + "\n\n"
        )
    else:
        knowledge_section = (
            "The Shared Hollow offers no new notes right now; rely on your lived teachings.\n\n"
        )
    return (
        "You are Archdruid Eldara replying in the Neo Druidic Society's encrypted chat.\n"
        f"Participants in this channel: {participant_list or 'just you and the member'}.\n"
        f"{knowledge_section}"
        f"The member {sender.username} says:\n\"{body.strip()}\"\n\n"
        "Respond in a warm, compassionate tone with a concise, actionable insight."
    )


def _maybe_send_archdruid_reply(thread: ChatThread, sender: User, body: str) -> Optional[ChatMessage]:
    if sender.username.lower() == ARCHDRUID_USERNAME.lower():
        return None
    if not _thread_has_archdruid(thread):
        return None
    archdruid = get_archdruid_user()
    if archdruid is None or not archdruid.has_chat_keys:
        return None
    prompt = _generate_archdruid_prompt(sender, body, thread)
    try:
        reply, sources = _model_insight(prompt)
        reply = (reply or "").strip()

        # Append source links if available
        if sources:
            reply += "\n\n📚 Sources:"
            for source in sources:
                reply += f"\n• {source['name']} (relevance: {source['relevance']})"
                reply += f" - /files/preview/{source['id']}"

    except Exception:
        current_app.logger.exception("Archdruid reply generation failed.")
        return None
    if not reply:
        return None
    try:
        arch_message = _persist_message(thread, archdruid, reply)
        return arch_message
    except Exception:
        current_app.logger.exception("Archdruid reply persistence failed.")
        return None


def _collect_thread_messages(thread: ChatThread, private_key: bytes | None) -> list[dict]:
    if private_key is None:
        return []
    messages = (
        ChatMessage.query.filter(ChatMessage.thread_id == thread.id)
        .order_by(ChatMessage.created_at.asc())
        .options(
            joinedload(ChatMessage.sender),
            selectinload(ChatMessage.keys),
        )
        .all()
    )
    rendered: list[dict] = []
    now = datetime.utcnow()
    dirty = False
    for message in messages:
        body, is_read = _unwrap_body(message, private_key, current_user.id)
        entry = next((key for key in message.keys if key.user_id == current_user.id), None)
        if entry and entry.read_at is None and message.sender_id != current_user.id:
            entry.read_at = now
            dirty = True
        rendered.append(
            {
                "id": message.id,
                "body": body,
                "created_at": message.created_at,
                "created_label": _format_timestamp(message.created_at),
                "sender": message.sender,
                 "sender_payload": _sender_payload(message.sender),
                "is_self": message.sender_id == current_user.id,
                "can_delete": _user_can_delete_message(thread, message, current_user.id),
            }
        )
    if dirty:
        db.session.commit()
    return rendered


def _available_users_for_selection() -> list[User]:
    return (
        User.query.filter(
            User.id != current_user.id,
            User.status == "active",
        )
        .order_by(User.username.asc())
        .all()
    )


def _get_or_create_dm_thread(partner: User) -> ChatThread:
    candidate = (
        ChatThread.query.join(ChatThreadMember)
        .filter(ChatThread.type == "dm")
        .filter(ChatThreadMember.user_id.in_([current_user.id, partner.id]))
        .group_by(ChatThread.id)
        .having(sa.func.count(sa.distinct(ChatThreadMember.user_id)) == 2)
        .first()
    )
    if candidate:
        # Ensure there are exactly two members (current + partner).
        member_ids = {member.user_id for member in candidate.members}
        if member_ids == {current_user.id, partner.id}:
            return candidate

    thread = ChatThread(
        type="dm",
        creator=current_user,
    )
    db.session.add(thread)
    db.session.flush()
    db.session.add(ChatThreadMember(thread=thread, user_id=current_user.id, is_admin=True))
    db.session.add(ChatThreadMember(thread=thread, user_id=partner.id, is_admin=True))
    db.session.commit()
    return thread


def _create_group_thread(name: str, member_ids: list[int]) -> tuple[ChatThread | None, str | None, str | None]:
    unique_member_ids = {current_user.id, *member_ids}
    if len(unique_member_ids) < 2:
        return None, "Choose at least one other member for a group channel.", "warning"
    if len(unique_member_ids) > GROUP_MEMBER_LIMIT:
        return (
            None,
            f"Group channels are limited to {GROUP_MEMBER_LIMIT} members.",
            "warning",
        )

    members = (
        User.query.filter(User.id.in_(unique_member_ids))
        .filter(User.status == "active")
        .all()
    )
    if len(members) != len(unique_member_ids):
        return None, "Some selected members are unavailable.", "danger"

    # Validate that all members have chat keys
    missing_keys = [
        member.username
        for member in members
        if not member.has_chat_keys
    ]
    if missing_keys:
        return (
            None,
            f"These members must unlock whispers first: {', '.join(missing_keys)}",
            "warning",
        )

    thread = ChatThread(
        type="group",
        title=name.strip() or "Grove Room",
        creator=current_user,
    )
    db.session.add(thread)
    db.session.flush()
    for member in members:
        db.session.add(
            ChatThreadMember(
                thread=thread,
                user_id=member.id,
                is_admin=member.id == current_user.id,
            )
        )
    db.session.commit()
    return thread, None, None


@chat_bp.route("/", methods=["GET"])
@login_required
def index():
    state = _chat_ready_state()
    private_key = (
        chat_session.get_private_key(current_user.chat_identity_version)
        if state == "ready"
        else None
    )
    thread_id = request.args.get(THREAD_PARAM, type=int)
    start_dm_partner = request.args.get("with", type=int)

    if start_dm_partner and start_dm_partner != current_user.id:
        partner = User.query.get(start_dm_partner)
        if not partner or partner.status != "active":
            flash("That member is not available.", "danger")
        else:
            thread = _get_or_create_dm_thread(partner)
            return redirect(url_for("chat.index", thread=thread.id))

    thread_summaries = _thread_summaries(private_key)
    selected_thread = None
    selected_summary = None
    messages: list[dict] = []

    if thread_id:
        selected_thread = _load_thread_for_user(thread_id)
        if selected_thread is None:
            flash("That channel is not available.", "warning")
        else:
            selected_summary = next(
                (summary for summary in thread_summaries if summary.thread.id == selected_thread.id),
                None,
            )
            if state == "ready":
                messages = _collect_thread_messages(selected_thread, private_key)

    active_recipients = [
        user for user in _available_users_for_selection() if user.has_chat_keys
    ]
    potential_group_members = [
        user for user in _available_users_for_selection() if user.has_chat_keys
    ]
    active_recipient_ids = {member.id for member in active_recipients}
    offline_recipients = [
        member
        for member in potential_group_members
        if member.id not in active_recipient_ids
    ]

    thread_ids = [summary.thread.id for summary in thread_summaries]
    current_thread_id = selected_summary.thread.id if selected_summary else None
    blocked_user_id = _get_blocked_user_id_for_dm(selected_thread) if selected_thread else None
    direct_threads = [summary for summary in thread_summaries if not summary.is_group]
    group_threads = [summary for summary in thread_summaries if summary.is_group]

    return render_template(
        "chat/index.html",
        state=state,
        threads=thread_summaries,
        direct_threads=direct_threads,
        group_threads=group_threads,
        selected_thread=selected_summary,
        selected_thread_members=_thread_participant_users(selected_thread) if selected_thread else [],
        messages=messages,
        active_recipients=active_recipients,
        potential_group_members=potential_group_members,
        offline_recipients=offline_recipients,
        max_message_length=MAX_MESSAGE_LENGTH,
        thread_ids=thread_ids,
        current_thread_id=current_thread_id,
        blocked_user_id=blocked_user_id,
        body_class="chat-page",
    )


@chat_bp.route("/unlock", methods=["POST"])
@login_required
def unlock():
    passphrase = (request.form.get("passphrase") or "").strip()
    if not passphrase:
        flash("Enter your account password to unlock encrypted chat.", "warning")
        return redirect(url_for("chat.index"))

    if _current_identity() is None:
        flash("Chat keys are still being provisioned. Try again shortly.", "warning")
        return redirect(url_for("chat.index"))

    try:
        private_key = ensure_chat_identity(
            current_user,
            passphrase,
            rotate_on_failure=False,
        )
    except InvalidTag:
        flash("That password did not unlock your chat keys.", "danger")
        return redirect(url_for("chat.index"))

    chat_session.store_private_key(private_key, current_user.chat_identity_version)
    flash("Chat unlocked for this session.", "success")
    return redirect(url_for("chat.index"))


@chat_bp.route("/lock", methods=["POST"])
@login_required
def lock():
    chat_session.clear_private_key()
    flash("Chat locked for this session.", "info")
    return redirect(url_for("chat.index"))


@chat_bp.route("/threads/dm", methods=["POST"])
@login_required
def start_dm():
    target_id = request.form.get("recipient_id", type=int)
    is_async = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not target_id or target_id == current_user.id:
        if is_async:
            return jsonify({"ok": False, "error": "invalid"}), 400
        flash("Choose someone else to start a direct message.", "warning")
        return redirect(url_for("chat.index"))
    partner = User.query.get(target_id)
    if not partner or partner.status != "active":
        if is_async:
            return jsonify({"ok": False, "error": "unavailable"}), 404
        flash("That member is not available.", "danger")
        return redirect(url_for("chat.index"))
    if not partner.has_chat_keys:
        if is_async:
            return jsonify({"ok": False, "error": "locked"}), 409
        flash("That member has not finished preparing their whispers.", "warning")
        return redirect(url_for("chat.index"))
    thread = _get_or_create_dm_thread(partner)
    if is_async:
        return jsonify(
            {
                "ok": True,
                "thread_id": thread.id,
                "display_name": partner.username,
                "owner_id": thread.creator_id,
            }
        )
    return redirect(url_for("chat.index", thread=thread.id))


@chat_bp.route("/threads/group", methods=["POST"])
@login_required
def create_group():
    name = (request.form.get("name") or "").strip()
    member_ids = request.form.getlist("members", type=int)
    is_async = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    thread, error_message, category = _create_group_thread(name, member_ids)
    if error_message:
        if is_async:
            return jsonify({"ok": False, "error": error_message}), 400
        flash(error_message, category or "warning")
        return redirect(url_for("chat.index"))

    if thread is None:
        if is_async:
            return jsonify({"ok": False, "error": "Unable to create that circle."}), 400
        flash("Unable to create that circle.", "danger")
        return redirect(url_for("chat.index"))

    if is_async:
        return jsonify(
            {
                "ok": True,
                "thread_id": thread.id,
                "display_name": thread.title or "Grove Room",
                "is_group": True,
                "owner_id": thread.creator_id,
            }
        )
    return redirect(url_for("chat.index", thread=thread.id))


@chat_bp.route("/threads/<int:thread_id>/leave", methods=["POST"])
@login_required
def leave_thread(thread_id: int):
    is_async = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    thread = _load_thread_for_user(thread_id)
    if thread is None:
        if is_async:
            return jsonify({"ok": False, "error": "That whisper is no longer available."}), 404
        flash("That whisper is no longer available.", "warning")
        return redirect(url_for("chat.index"))

    if thread.type != "group":
        if is_async:
            return jsonify({"ok": False, "error": "Only group channels can be left."}), 400
        flash("Only group channels can be left this way.", "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    if thread.creator_id == current_user.id:
        message = "You founded this group. Delete it instead if you no longer need it."
        if is_async:
            return jsonify({"ok": False, "error": message}), 409
        flash(message, "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    membership = (
        ChatThreadMember.query.filter(
            ChatThreadMember.thread_id == thread.id,
            ChatThreadMember.user_id == current_user.id,
        )
        .limit(1)
        .one_or_none()
    )
    if membership is None:
        if is_async:
            return jsonify({"ok": False, "error": "You are not part of that whisper."}), 403
        flash("You are not part of that whisper.", "danger")
        return redirect(url_for("chat.index"))

    _handle_member_departure(thread, membership)
    db.session.commit()

    if is_async:
        return jsonify({"ok": True, "thread_id": thread_id})

    flash("You left the group.", "info")
    return redirect(url_for("chat.index"))


@chat_bp.route("/threads/<int:thread_id>/kick/<int:user_id>", methods=["POST"])
@login_required
def kick_member(thread_id: int, user_id: int):
    is_async = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    thread = _load_thread_for_user(thread_id)
    if thread is None:
        if is_async:
            return jsonify({"ok": False, "error": "That whisper is no longer available."}), 404
        flash("That whisper is no longer available.", "warning")
        return redirect(url_for("chat.index"))

    if thread.type != "group":
        if is_async:
            return jsonify({"ok": False, "error": "Only group channels support kicking members."}), 400
        flash("Only group channels support kicking members.", "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    if thread.creator_id != current_user.id:
        message = "Only the group founder can kick members."
        if is_async:
            return jsonify({"ok": False, "error": message}), 403
        flash(message, "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    if user_id == current_user.id:
        message = "You cannot kick yourself from the group."
        if is_async:
            return jsonify({"ok": False, "error": message}), 400
        flash(message, "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    membership = (
        ChatThreadMember.query.filter(
            ChatThreadMember.thread_id == thread.id,
            ChatThreadMember.user_id == user_id,
        )
        .limit(1)
        .one_or_none()
    )
    if membership is None:
        if is_async:
            return jsonify({"ok": False, "error": "That member is not in this group."}), 404
        flash("That member is not in this group.", "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    kicked_user = membership.user
    _handle_member_departure(thread, membership)
    db.session.commit()

    if is_async:
        return jsonify({"ok": True, "thread_id": thread_id, "user_id": user_id})

    flash(f"{kicked_user.username} has been removed from the group.", "info")
    return redirect(url_for("chat.index", thread=thread_id))


@chat_bp.route("/threads/<int:thread_id>/add-member", methods=["POST"])
@login_required
def add_member(thread_id: int):
    is_async = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    thread = _load_thread_for_user(thread_id)
    if thread is None:
        if is_async:
            return jsonify({"ok": False, "error": "That whisper is no longer available."}), 404
        flash("That whisper is no longer available.", "warning")
        return redirect(url_for("chat.index"))

    if thread.type != "group":
        if is_async:
            return jsonify({"ok": False, "error": "Only group channels support adding members."}), 400
        flash("Only group channels support adding members.", "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    if thread.creator_id != current_user.id:
        message = "Only the group founder can add members."
        if is_async:
            return jsonify({"ok": False, "error": message}), 403
        flash(message, "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    user_id = request.form.get("user_id", type=int)
    if not user_id:
        if is_async:
            return jsonify({"ok": False, "error": "No user specified."}), 400
        flash("No user specified.", "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    # Check if user is already a member
    existing_membership = (
        ChatThreadMember.query.filter(
            ChatThreadMember.thread_id == thread.id,
            ChatThreadMember.user_id == user_id,
        )
        .limit(1)
        .one_or_none()
    )
    if existing_membership:
        if is_async:
            return jsonify({"ok": False, "error": "That user is already in this group."}), 400
        flash("That user is already in this group.", "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    # Check current member count
    current_member_count = (
        ChatThreadMember.query.filter(ChatThreadMember.thread_id == thread.id).count()
    )
    if current_member_count >= GROUP_MEMBER_LIMIT:
        message = f"Group channels are limited to {GROUP_MEMBER_LIMIT} members."
        if is_async:
            return jsonify({"ok": False, "error": message}), 400
        flash(message, "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    # Load the user to add
    new_user = User.query.get(user_id)
    if not new_user or new_user.status != "active":
        if is_async:
            return jsonify({"ok": False, "error": "That user is not available."}), 404
        flash("That user is not available.", "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    # Check if the user has chat keys
    if not new_user.has_chat_keys:
        message = f"{new_user.username} must unlock whispers before joining a group."
        if is_async:
            return jsonify({"ok": False, "error": message}), 400
        flash(message, "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    # Add the member
    new_membership = ChatThreadMember(
        thread=thread,
        user_id=new_user.id,
        is_admin=False,
    )
    db.session.add(new_membership)
    db.session.commit()

    if is_async:
        return jsonify({"ok": True, "thread_id": thread_id, "user_id": user_id})

    flash(f"{new_user.username} has been added to the group.", "info")
    return redirect(url_for("chat.index", thread=thread_id))


@chat_bp.route("/threads/<int:thread_id>/delete", methods=["POST"])
@login_required
def delete_thread(thread_id: int):
    is_async = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    thread = _load_thread_for_user(thread_id)
    if thread is None:
        if is_async:
            return jsonify({"ok": False, "error": "That whisper is no longer available."}), 404
        flash("That whisper is no longer available.", "warning")
        return redirect(url_for("chat.index"))

    is_owner = thread.creator_id == current_user.id
    if thread.type == "group" and (is_owner or current_user.is_arch):
        db.session.delete(thread)
        db.session.commit()
        if is_async:
            return jsonify({"ok": True, "thread_id": thread_id, "deleted": True})
        flash("Group deleted for all members.", "info")
        return redirect(url_for("chat.index"))

    if thread.type == "group" and not (is_owner or current_user.is_arch):
        message = "Only the group founder can delete this room. Choose Leave instead."
        if is_async:
            return jsonify({"ok": False, "error": message}), 403
        flash(message, "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    membership = (
        ChatThreadMember.query.filter(
            ChatThreadMember.thread_id == thread.id,
            ChatThreadMember.user_id == current_user.id,
        )
        .limit(1)
        .one_or_none()
    )
    if membership is None:
        if is_async:
            return jsonify({"ok": False, "error": "You are not part of that whisper."}), 403
        flash("You are not part of that whisper.", "danger")
        return redirect(url_for("chat.index"))

    _handle_member_departure(thread, membership)

    db.session.commit()

    if is_async:
        return jsonify({"ok": True, "thread_id": thread_id})

    flash("Whisper removed.", "info")
    return redirect(url_for("chat.index"))


@chat_bp.route("/messages/<int:message_id>/delete", methods=["POST"])
@login_required
def delete_message(message_id: int):
    is_async = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    delete_scope = request.form.get("scope", "all")  # "self" or "all"

    message = (
        ChatMessage.query.options(
            joinedload(ChatMessage.thread)
            .joinedload(ChatThread.members),
            joinedload(ChatMessage.sender),
            selectinload(ChatMessage.keys),
        )
        .filter(ChatMessage.id == message_id)
        .first()
    )
    if message is None or message.thread is None:
        if is_async:
            return jsonify({"ok": False, "error": "That message has already been cleared."}), 404
        flash("That message has already been cleared.", "warning")
        return redirect(url_for("chat.index"))

    thread = message.thread
    membership = next((member for member in thread.members if member.user_id == current_user.id), None)
    if membership is None:
        if is_async:
            return jsonify({"ok": False, "error": "You are not part of that whisper."}), 403
        flash("You are not part of that whisper.", "danger")
        return redirect(url_for("chat.index"))

    # For one-on-one chats, allow "delete for self" option
    if delete_scope == "self" and thread.type == "dm":
        # Just remove the user's message key to make it unreadable for them
        key = next((k for k in message.keys if k.user_id == current_user.id), None)
        if key:
            db.session.delete(key)
            db.session.commit()

            if is_async:
                return jsonify({"ok": True, "thread_id": thread.id, "message_id": message_id, "scope": "self"})

            flash("Message removed for you.", "info")
            return redirect(url_for("chat.index", thread=thread.id))
        else:
            if is_async:
                return jsonify({"ok": False, "error": "Message key not found."}), 404
            flash("Message key not found.", "warning")
            return redirect(url_for("chat.index", thread=thread.id))

    # For "delete for all" or group messages, check permissions
    can_delete = message.sender_id == current_user.id
    if not can_delete and thread.type == "group" and membership.is_admin:
        can_delete = True
    if not can_delete:
        if is_async:
            return jsonify({"ok": False, "error": "You cannot remove that message."}), 403
        flash("You cannot remove that message.", "danger")
        return redirect(url_for("chat.index", thread=thread.id))

    thread_id = thread.id
    db.session.delete(message)
    db.session.commit()

    _broadcast_message_deleted(thread, message_id)

    if is_async:
        return jsonify({"ok": True, "thread_id": thread_id, "message_id": message_id, "scope": "all"})

    flash("Message removed.", "info")
    return redirect(url_for("chat.index", thread=thread_id))


@chat_bp.route("/block/<int:user_id>", methods=["POST"])
@login_required
def block_user(user_id: int):
    is_async = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if user_id == current_user.id:
        if is_async:
            return jsonify({"ok": False, "error": "You cannot block yourself."}), 400
        flash("You cannot block yourself.", "warning")
        return redirect(url_for("chat.index"))

    target = User.query.get(user_id)
    if not target or target.status != "active":
        if is_async:
            return jsonify({"ok": False, "error": "That user is not available."}), 404
        flash("That user is not available.", "warning")
        return redirect(url_for("chat.index"))

    existing_block = ChatBlock.query.filter_by(
        blocker_id=current_user.id,
        blocked_id=user_id
    ).first()

    if existing_block:
        if is_async:
            return jsonify({"ok": True, "already_blocked": True})
        flash(f"You have already blocked {target.username}.", "info")
        return redirect(url_for("chat.index"))

    block = ChatBlock(blocker_id=current_user.id, blocked_id=user_id)
    db.session.add(block)
    db.session.commit()

    if is_async:
        return jsonify({"ok": True, "user_id": user_id, "username": target.username})

    flash(f"You have blocked {target.username}.", "info")
    return redirect(url_for("chat.index"))


@chat_bp.route("/unblock/<int:user_id>", methods=["POST"])
@login_required
def unblock_user(user_id: int):
    is_async = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    block = ChatBlock.query.filter_by(
        blocker_id=current_user.id,
        blocked_id=user_id
    ).first()

    if not block:
        if is_async:
            return jsonify({"ok": False, "error": "That user is not blocked."}), 404
        flash("That user is not blocked.", "warning")
        return redirect(url_for("chat.index"))

    target = block.blocked
    db.session.delete(block)
    db.session.commit()

    if is_async:
        return jsonify({"ok": True, "user_id": user_id, "username": target.username})

    flash(f"You have unblocked {target.username}.", "info")
    return redirect(url_for("chat.index"))


@chat_bp.route("/send", methods=["POST"])
@login_required
def send():
    state = _chat_ready_state()
    if state != "ready":
        flash("Unlock encrypted chat before sending a message.", "warning")
        return redirect(url_for("chat.index"))

    thread_id = request.form.get("thread_id", type=int)
    body = (request.form.get("body") or "").strip()
    is_async = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not thread_id:
        flash("Pick a channel before sending a message.", "warning")
        return redirect(url_for("chat.index"))
    if not body:
        flash("Share at least a few words.", "warning")
        return redirect(url_for("chat.index", thread=thread_id))
    if len(body) > MAX_MESSAGE_LENGTH:
        flash(f"Messages are limited to {MAX_MESSAGE_LENGTH} characters.", "warning")
        return redirect(url_for("chat.index", thread=thread_id))

    thread = _load_thread_for_user(thread_id)
    if thread is None:
        flash("That channel is not available.", "warning")
        return redirect(url_for("chat.index"))

    if not _ensure_members_have_keys(thread):
        if is_async:
            return jsonify({"ok": False, "error": "keys"}), 400
        return redirect(url_for("chat.index", thread=thread.id))

    if chat_session.get_private_key(current_user.chat_identity_version) is None:
        if is_async:
            return jsonify({"ok": False, "error": "locked"}), 403
        flash("Unlock encrypted chat before sending a message.", "warning")
        return redirect(url_for("chat.index", thread=thread.id))

    message = _persist_message(thread, current_user, body)
    # AI now uses OpenAI API for fast, reliable responses
    arch_message = _maybe_send_archdruid_reply(thread, current_user, body)
    db.session.commit()
    fresh_message = (
        ChatMessage.query.options(joinedload(ChatMessage.sender), selectinload(ChatMessage.keys))
        .get(message.id)
    )
    if fresh_message:
        _broadcast_message(thread, fresh_message)
    if arch_message:
        fresh_arch = (
            ChatMessage.query.options(joinedload(ChatMessage.sender), selectinload(ChatMessage.keys))
            .get(arch_message.id)
        )
        if fresh_arch:
            _broadcast_message(thread, fresh_arch)

    if is_async:
        return jsonify({"ok": True, "message_id": message.id})

    flash("Message sent with lattice-forged secrecy.", "success")
    return redirect(url_for("chat.index", thread=thread.id))
