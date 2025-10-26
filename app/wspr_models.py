"""
WSPR (Whisper) - Standalone End-to-End Encrypted Chat
Separate models from the main Neo-Druidic Society application
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from .database import db


class WsprUser(UserMixin, db.Model):
    """
    Separate user model for WSPR chat application.
    This is independent from the main Neo-Druidic Society users.
    """
    __tablename__ = "wspr_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_seen = db.Column(db.DateTime, nullable=True)

    # ML-KEM-768 (Kyber) encryption keys
    public_key = db.Column(db.LargeBinary, nullable=True)  # 1184 bytes
    private_key_encrypted = db.Column(db.LargeBinary, nullable=True)  # Encrypted with passphrase
    private_key_nonce = db.Column(db.LargeBinary, nullable=True)  # 24 bytes nonce
    key_salt = db.Column(db.LargeBinary, nullable=True)  # 32 bytes salt
    keys_generated_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    rooms_created = db.relationship(
        "WsprRoom",
        back_populates="creator",
        cascade="all, delete-orphan",
    )
    messages_sent = db.relationship(
        "WsprMessage",
        back_populates="sender",
        cascade="all, delete-orphan",
    )

    def set_password(self, password: str):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password"""
        return check_password_hash(self.password_hash, password)

    @property
    def has_keys(self) -> bool:
        """Check if user has encryption keys"""
        return all([
            self.public_key,
            self.private_key_encrypted,
            self.private_key_nonce,
            self.key_salt
        ])

    def __repr__(self) -> str:
        return f"<WsprUser {self.username}>"


class WsprRoom(db.Model):
    """Chat rooms for WSPR"""
    __tablename__ = "wspr_rooms"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(16), nullable=False)  # 'dm' or 'group'
    name = db.Column(db.String(120), nullable=True)  # For group chats
    creator_id = db.Column(db.Integer, db.ForeignKey("wspr_users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    creator = db.relationship("WsprUser", back_populates="rooms_created")
    members = db.relationship(
        "WsprRoomMember",
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    messages = db.relationship(
        "WsprMessage",
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WsprMessage.created_at.asc()",
    )

    __table_args__ = (
        db.Index("ix_wspr_rooms_type_activity", "type", "last_activity"),
    )

    def __repr__(self) -> str:
        return f"<WsprRoom {self.id} {self.type}>"


class WsprRoomMember(db.Model):
    """Room membership for WSPR"""
    __tablename__ = "wspr_room_members"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("wspr_rooms.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("wspr_users.id", ondelete="CASCADE"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_read_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    room = db.relationship("WsprRoom", back_populates="members")
    user = db.relationship("WsprUser", backref="room_memberships")

    __table_args__ = (
        db.UniqueConstraint("room_id", "user_id", name="uq_wspr_room_user"),
        db.Index("ix_wspr_room_members_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<WsprRoomMember room={self.room_id} user={self.user_id}>"


class WsprMessage(db.Model):
    """Encrypted messages for WSPR"""
    __tablename__ = "wspr_messages"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("wspr_rooms.id", ondelete="CASCADE"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("wspr_users.id"), nullable=False)

    # Encrypted message data
    body_ciphertext = db.Column(db.LargeBinary, nullable=False)
    body_nonce = db.Column(db.LargeBinary, nullable=False)  # 24 bytes

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    room = db.relationship("WsprRoom", back_populates="messages")
    sender = db.relationship("WsprUser", back_populates="messages_sent")

    __table_args__ = (
        db.Index("ix_wspr_messages_room_created", "room_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<WsprMessage {self.id} in room {self.room_id}>"


class WsprSession(db.Model):
    """
    Session tracking for online users.
    Used for presence indicators and WebSocket session management.
    """
    __tablename__ = "wspr_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("wspr_users.id", ondelete="CASCADE"), nullable=False)
    session_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_ping = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    user = db.relationship("WsprUser", backref="sessions")

    __table_args__ = (
        db.Index("ix_wspr_sessions_user_ping", "user_id", "last_ping"),
    )

    def __repr__(self) -> str:
        return f"<WsprSession user={self.user_id}>"
