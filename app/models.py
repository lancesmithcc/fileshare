from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy import text

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .database import db


class Circle(db.Model):
    __tablename__ = "circles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    members = db.relationship(
        "CircleMembership",
        back_populates="circle",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Circle {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    grove = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(32), nullable=False, default="member")
    status = db.Column(db.String(16), nullable=False, default="active")
    join_reason = db.Column(db.Text, nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    profile_html = db.Column(db.Text, nullable=True)
    profile_css = db.Column(db.Text, nullable=True)
    profile_js = db.Column(db.Text, nullable=True)
    suspended_until = db.Column(db.DateTime, nullable=True)
    last_seen = db.Column(db.DateTime, nullable=True)
    chat_public_key = db.Column(db.LargeBinary, nullable=True)
    chat_private_key_encrypted = db.Column(db.LargeBinary, nullable=True)
    chat_private_key_nonce = db.Column(db.LargeBinary, nullable=True)
    chat_key_salt = db.Column(db.LargeBinary, nullable=True)
    chat_identity_version = db.Column(db.Integer, nullable=True)
    chat_enabled_at = db.Column(db.DateTime, nullable=True)
    chat_keys_rotated_at = db.Column(db.DateTime, nullable=True)

    posts = db.relationship("Post", back_populates="author", cascade="all, delete")
    comments = db.relationship(
        "Comment", back_populates="author", cascade="all, delete"
    )
    circle_membership = db.relationship(
        "CircleMembership",
        back_populates="member",
        uselist=False,
        cascade="all, delete",
    )
    files = db.relationship(
        "FileAsset",
        back_populates="owner",
        cascade="all, delete-orphan",
        order_by="FileAsset.created_at.desc()",
    )

    folders = db.relationship(
        "FileFolder",
        back_populates="owner",
        cascade="all, delete-orphan",
        order_by="FileFolder.name.asc()",
    )
    chat_threads_created = db.relationship(
        "ChatThread",
        back_populates="creator",
        cascade="all, delete-orphan",
    )
    chat_messages_sent = db.relationship(
        "ChatMessage",
        back_populates="sender",
        cascade="all, delete-orphan",
    )

    @staticmethod
    def _parse_datetime(value: datetime | str | None) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    @property
    def is_arch(self) -> bool:
        return self.role == "arch"

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return self.status == "active"

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"

    @property
    def is_suspended(self) -> bool:
        if self.status != "suspended":
            return False
        until = self._parse_datetime(self.suspended_until)
        if until is None:
            return True
        return until > datetime.utcnow()

    def lift_suspension_if_expired(self) -> bool:
        """Return True if a suspension expired and the user was reinstated."""
        if self.status != "suspended":
            return False
        until = self._parse_datetime(self.suspended_until)
        if until and until <= datetime.utcnow():
            self.status = "active"
            self.suspended_until = None
            return True
        if self.suspended_until and until is None:
            # Stored suspension timestamp could not be parsed; clear it.
            self.status = "active"
            self.suspended_until = None
            return True
        return False

    @property
    def is_online(self) -> bool:
        last_seen = self._parse_datetime(self.last_seen)
        if not last_seen:
            return False
        return datetime.utcnow() - last_seen <= timedelta(minutes=5)

    @property
    def has_chat_keys(self) -> bool:
        return all(
            (
                self.chat_public_key,
                self.chat_private_key_encrypted,
                self.chat_private_key_nonce,
                self.chat_key_salt,
            )
        )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class CircleMembership(db.Model):
    __tablename__ = "circle_memberships"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    circle_id = db.Column(db.Integer, db.ForeignKey("circles.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    member = db.relationship("User", back_populates="circle_membership")
    circle = db.relationship("Circle", back_populates="members")


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    ritual_focus = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    author = db.relationship("User", back_populates="posts")
    comments = db.relationship(
        "Comment",
        back_populates="post",
        cascade="all, delete",
        order_by="Comment.created_at.asc()",
    )

    def __repr__(self) -> str:
        return f"<Post {self.id} by {self.author_id}>"


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)

    author = db.relationship("User", back_populates="comments")
    post = db.relationship("Post", back_populates="comments")

    def __repr__(self) -> str:
        return f"<Comment {self.id} on post {self.post_id}>"


class ChatThread(db.Model):
    __tablename__ = "chat_threads"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(16), nullable=False)  # dm or group
    title = db.Column(db.String(120), nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", back_populates="chat_threads_created")
    members = db.relationship(
        "ChatThreadMember",
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    messages = db.relationship(
        "ChatMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatMessage.created_at.asc()",
    )

    __table_args__ = (
        db.Index("ix_chat_threads_type_created", "type", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ChatThread {self.id} {self.type}>"


class ChatThreadMember(db.Model):
    __tablename__ = "chat_thread_members"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    thread = db.relationship("ChatThread", back_populates="members")
    user = db.relationship("User", backref="chat_thread_memberships")

    __table_args__ = (
        db.UniqueConstraint("thread_id", "user_id", name="uq_thread_user"),
        db.Index("ix_chat_thread_members_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<ChatThreadMember thread={self.thread_id} user={self.user_id}>"


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body_ciphertext = db.Column(db.LargeBinary, nullable=False)
    body_nonce = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    thread = db.relationship("ChatThread", back_populates="messages")
    sender = db.relationship("User", back_populates="chat_messages_sent")
    keys = db.relationship(
        "ChatMessageKey",
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        db.Index("ix_chat_messages_thread_created", "thread_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ChatMessage {self.id} thread={self.thread_id}>"


class ChatMessageKey(db.Model):
    __tablename__ = "chat_message_keys"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kem_ciphertext = db.Column(db.LargeBinary, nullable=False)
    wrapped_key = db.Column(db.LargeBinary, nullable=False)
    wrap_nonce = db.Column(db.LargeBinary, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)

    message = db.relationship("ChatMessage", back_populates="keys")
    user = db.relationship("User", backref="chat_message_keys")

    __table_args__ = (
        db.UniqueConstraint("message_id", "user_id", name="uq_message_user"),
        db.Index("ix_chat_message_keys_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<ChatMessageKey message={self.message_id} user={self.user_id}>"


class ChatBlock(db.Model):
    __tablename__ = "chat_blocks"

    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    blocked_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    blocker = db.relationship("User", foreign_keys=[blocker_id], backref="chat_blocks_initiated")
    blocked = db.relationship("User", foreign_keys=[blocked_id], backref="chat_blocks_received")

    __table_args__ = (
        db.UniqueConstraint("blocker_id", "blocked_id", name="uq_chat_block_pair"),
        db.Index("ix_chat_blocks_blocker", "blocker_id"),
        db.Index("ix_chat_blocks_blocked", "blocked_id"),
    )

    def __repr__(self) -> str:
        return f"<ChatBlock blocker={self.blocker_id} blocked={self.blocked_id}>"


class FileFolder(db.Model):
    __tablename__ = "file_folders"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("file_folders.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    pos_x = db.Column(db.Float, default=0.0, nullable=False)
    pos_y = db.Column(db.Float, default=0.0, nullable=False)

    owner = db.relationship("User", back_populates="folders")
    parent = db.relationship("FileFolder", remote_side=[id], back_populates="children")
    children = db.relationship(
        "FileFolder",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="FileFolder.name.asc()",
    )
    files = db.relationship("FileAsset", back_populates="folder")

    __table_args__ = (
        db.UniqueConstraint(
            "owner_id", "name", "parent_id", name="uq_folder_owner_name_parent"
        ),
    )

    def __repr__(self) -> str:
        return f"<FileFolder {self.name} ({self.id})>"


class FileAsset(db.Model):
    __tablename__ = "file_assets"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), unique=True, nullable=False)
    mime_type = db.Column(db.String(128), nullable=True)
    size = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    share_token = db.Column(db.String(64), unique=True, nullable=True)
    folder_id = db.Column(db.Integer, db.ForeignKey("file_folders.id"), nullable=True, index=True)
    pos_x = db.Column(db.Float, default=0.0, nullable=False)
    pos_y = db.Column(db.Float, default=0.0, nullable=False)

    owner = db.relationship("User", back_populates="files")
    folder = db.relationship("FileFolder", back_populates="files")

    def __repr__(self) -> str:
        return f"<FileAsset {self.original_name} ({self.id})>"


class DocumentEmbedding(db.Model):
    """Vector embeddings for Knowledge Garden files to enable RAG."""
    __tablename__ = "document_embeddings"

    id = db.Column(db.Integer, primary_key=True)
    file_asset_id = db.Column(db.Integer, db.ForeignKey("file_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    # Vector column - will be created as vector(384) when pgvector is installed
    # For now, store as JSON array until pgvector extension is enabled
    embedding = db.Column(db.Text, nullable=False)  # JSON array of floats
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    file_asset = db.relationship("FileAsset", backref=db.backref("embeddings", cascade="all, delete-orphan", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("file_asset_id", "chunk_index", name="uq_file_chunk"),
    )

    def __repr__(self) -> str:
        return f"<DocumentEmbedding file={self.file_asset_id} chunk={self.chunk_index}>"


class NeodMint(db.Model):
    __tablename__ = "neod_mints"

    id = db.Column(db.Integer, primary_key=True)
    mint_address = db.Column(db.String(64), unique=True, nullable=False)
    authority_address = db.Column(db.String(64), nullable=False)
    initial_supply = db.Column(db.BigInteger, nullable=False)
    decimals = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_signature = db.Column(db.String(120), nullable=True)

    def __repr__(self) -> str:
        return f"<NeodMint {self.mint_address}>"


class NeodPurchase(db.Model):
    __tablename__ = "neod_purchases"

    id = db.Column(db.Integer, primary_key=True)
    signature = db.Column(db.String(120), unique=True, nullable=False)
    payer_address = db.Column(db.String(64), nullable=False)
    recipient_address = db.Column(db.String(64), nullable=False)
    sol_lamports = db.Column(db.BigInteger, nullable=False)
    neod_amount = db.Column(db.BigInteger, nullable=False, default=1)
    neod_transfer_signature = db.Column(db.String(120), nullable=False)
    slot = db.Column(db.BigInteger, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<NeodPurchase {self.signature}>"


class SiteSetting(db.Model):
    __tablename__ = "site_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<SiteSetting {self.key}>"


def ensure_file_schema() -> None:
    """Ensure folder support columns/tables exist for file storage."""
    engine = db.get_engine()
    with engine.begin() as connection:
        FileFolder.__table__.create(bind=connection, checkfirst=True)
        
        # PostgreSQL-compatible column check
        inspector = sa.inspect(engine)
        columns = {col['name'] for col in inspector.get_columns('file_assets')}
        
        if "folder_id" not in columns:
            connection.execute(text("ALTER TABLE file_assets ADD COLUMN folder_id INTEGER"))
        if "pos_x" not in columns:
            connection.execute(text("ALTER TABLE file_assets ADD COLUMN pos_x REAL DEFAULT 0"))
        if "pos_y" not in columns:
            connection.execute(text("ALTER TABLE file_assets ADD COLUMN pos_y REAL DEFAULT 0"))

        folder_columns = {col['name'] for col in inspector.get_columns('file_folders')}
        if "pos_x" not in folder_columns:
            connection.execute(text("ALTER TABLE file_folders ADD COLUMN pos_x REAL DEFAULT 0"))
        if "pos_y" not in folder_columns:
            connection.execute(text("ALTER TABLE file_folders ADD COLUMN pos_y REAL DEFAULT 0"))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_file_assets_folder_id ON file_assets(folder_id)"
            )
        )


def ensure_user_schema() -> None:
    """Add role/status metadata to users for admin and approval controls."""
    engine = db.get_engine()
    dialect = engine.dialect.name
    blob_type = "BYTEA" if dialect == "postgresql" else "BLOB"
    with engine.begin() as connection:
        # PostgreSQL-compatible column check
        inspector = sa.inspect(engine)
        columns = {col['name'] for col in inspector.get_columns('users')}
        
        if "role" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'member'"))
        if "status" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(16) DEFAULT 'active'"))
        if "join_reason" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN join_reason TEXT"))
        if "profile_image" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN profile_image VARCHAR(255)"))
        if "profile_html" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN profile_html TEXT"))
        if "profile_css" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN profile_css TEXT"))
        if "profile_js" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN profile_js TEXT"))
        if "suspended_until" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN suspended_until TIMESTAMP"))
        if "last_seen" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN last_seen TIMESTAMP"))
        if "chat_public_key" not in columns:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN chat_public_key {blob_type}"))
        if "chat_private_key_encrypted" not in columns:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN chat_private_key_encrypted {blob_type}"))
        if "chat_private_key_nonce" not in columns:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN chat_private_key_nonce {blob_type}"))
        if "chat_key_salt" not in columns:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN chat_key_salt {blob_type}"))
        if "chat_identity_version" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN chat_identity_version INTEGER"))
        if "chat_enabled_at" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN chat_enabled_at TIMESTAMP"))
        if "chat_keys_rotated_at" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN chat_keys_rotated_at TIMESTAMP"))


def ensure_circle_schema() -> None:
    """Ensure circles track creation timestamp."""
    engine = db.get_engine()
    with engine.begin() as connection:
        # PostgreSQL-compatible column check
        inspector = sa.inspect(engine)
        columns = {col['name'] for col in inspector.get_columns('circles')}
        
        if "created_at" not in columns:
            connection.execute(text("ALTER TABLE circles ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        # Only update NULL values with current timestamp
        connection.execute(
            text(
                "UPDATE circles SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
            )
        )


def ensure_admin_user() -> None:
    """Ensure the designated arch admin exists and is active."""
    admin = (
        User.query.filter(db.func.lower(User.username) == "lancelot")
        .limit(1)
        .one_or_none()
    )
    if not admin:
        return
    dirty = False
    if admin.role != "arch":
        admin.role = "arch"
        dirty = True
    if admin.status != "active":
        admin.status = "active"
        dirty = True
    if admin.suspended_until is not None:
        admin.suspended_until = None
        dirty = True
    if admin.last_seen is None:
        admin.last_seen = datetime.utcnow()
        dirty = True
    if dirty:
        db.session.add(admin)
        db.session.commit()


def ensure_chat_schema() -> None:
    """Ensure encrypted chat tables exist."""
    engine = db.get_engine()
    with engine.begin() as connection:
        ChatThread.__table__.create(bind=connection, checkfirst=True)
        ChatThreadMember.__table__.create(bind=connection, checkfirst=True)
        ChatMessage.__table__.create(bind=connection, checkfirst=True)
        ChatMessageKey.__table__.create(bind=connection, checkfirst=True)
