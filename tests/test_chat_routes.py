import os
import shutil
import tempfile
import unittest
from datetime import datetime

from app import create_app
from app.chat import ARCHDRUID_USERNAME, ensure_archdruid_user
from app.chat_crypto import generate_identity
from app.config import Config
from app.database import db
from app.models import ChatMessage, ChatMessageKey, ChatThread, ChatThreadMember, User


class ChatRouteTests(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(prefix="neo_chat_", suffix=".db")
        self.storage_dir = tempfile.mkdtemp(prefix="neo_chat_storage_")
        os.environ["NEO_DRUIDIC_DATABASE_URI"] = f"sqlite:///{self.db_path}"
        os.environ["NEO_DRUIDIC_STORAGE_DIR"] = self.storage_dir
        self._orig_db_uri = Config.SQLALCHEMY_DATABASE_URI
        self._orig_storage_root = Config.STORAGE_ROOT
        self._orig_log_root = getattr(Config, "LOG_ROOT", None)
        Config.SQLALCHEMY_DATABASE_URI = f"sqlite:///{self.db_path}"
        Config.STORAGE_ROOT = self.storage_dir
        if self._orig_log_root is not None:
            Config.LOG_ROOT = self.storage_dir
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self._seed_users()
        ensure_archdruid_user()
        self.arch_user = User.query.filter_by(username=ARCHDRUID_USERNAME).one()
        self.arch_id = self.arch_user.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        shutil.rmtree(self.storage_dir, ignore_errors=True)
        os.environ.pop("NEO_DRUIDIC_DATABASE_URI", None)
        os.environ.pop("NEO_DRUIDIC_STORAGE_DIR", None)
        Config.SQLALCHEMY_DATABASE_URI = self._orig_db_uri
        Config.STORAGE_ROOT = self._orig_storage_root
        if self._orig_log_root is not None:
            Config.LOG_ROOT = self._orig_log_root

    def _seed_users(self):
        now = datetime.utcnow()

        alice_password = "password1"
        alice_identity = generate_identity(alice_password)
        alice = User(
            username="alice",
            email="alice@example.com",
            status="active",
            role="member",
        )
        alice.set_password(alice_password)
        alice.chat_public_key = alice_identity.public_key
        alice.chat_private_key_encrypted = alice_identity.encrypted_private_key
        alice.chat_private_key_nonce = alice_identity.nonce
        alice.chat_key_salt = alice_identity.salt
        alice.chat_identity_version = 1
        alice.chat_enabled_at = now
        alice.chat_keys_rotated_at = now

        bob_password = "password2"
        bob_identity = generate_identity(bob_password)
        bob = User(
            username="bob",
            email="bob@example.com",
            status="active",
            role="member",
        )
        bob.set_password(bob_password)
        bob.chat_public_key = bob_identity.public_key
        bob.chat_private_key_encrypted = bob_identity.encrypted_private_key
        bob.chat_private_key_nonce = bob_identity.nonce
        bob.chat_key_salt = bob_identity.salt
        bob.chat_identity_version = 1
        bob.chat_enabled_at = now
        bob.chat_keys_rotated_at = now

        charlie_password = "password3"
        charlie_identity = generate_identity(charlie_password)
        charlie = User(
            username="charlie",
            email="charlie@example.com",
            status="active",
            role="member",
        )
        charlie.set_password(charlie_password)
        charlie.chat_public_key = charlie_identity.public_key
        charlie.chat_private_key_encrypted = charlie_identity.encrypted_private_key
        charlie.chat_private_key_nonce = charlie_identity.nonce
        charlie.chat_key_salt = charlie_identity.salt
        charlie.chat_identity_version = 1
        charlie.chat_enabled_at = now
        charlie.chat_keys_rotated_at = now

        db.session.add_all([alice, bob, charlie])
        db.session.commit()
        self.alice_id = alice.id
        self.bob_id = bob.id
        self.charlie_id = charlie.id

    def _login(self, username: str, password: str):
        response = self.client.post(
            "/auth/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        return response

    def _logout(self):
        return self.client.post("/auth/logout", follow_redirects=True)

    def test_send_and_receive_encrypted_message(self):
        # Alice unlocks and opens a DM with Bob.
        self._login("alice", "password1")
        dm_response = self.client.post(
            "/chat/threads/dm",
            data={"recipient_id": self.bob_id},
            follow_redirects=True,
        )
        self.assertEqual(dm_response.status_code, 200)

        thread = ChatThread.query.filter_by(type="dm").one()

        send_response = self.client.post(
            "/chat/send",
            data={"thread_id": thread.id, "body": "Under the oak canopy."},
            follow_redirects=True,
        )
        self.assertEqual(send_response.status_code, 200)

        message = ChatMessage.query.one()
        self.assertEqual(message.thread_id, thread.id)

        keys = ChatMessageKey.query.filter_by(message_id=message.id).all()
        self.assertEqual(len(keys), 2)
        alice_key = next(key for key in keys if key.user_id == self.alice_id)
        bob_key = next(key for key in keys if key.user_id == self.bob_id)
        self.assertIsNotNone(alice_key.read_at)
        self.assertIsNone(bob_key.read_at)

        self._logout()

        # Bob unlocks and views the thread, confirming plaintext render.
        self._login("bob", "password2")
        conversation = self.client.get(f"/chat/?thread={thread.id}", follow_redirects=True)
        self.assertEqual(conversation.status_code, 200)
        self.assertIn(b"Under the oak canopy.", conversation.data)

        bob_key = ChatMessageKey.query.filter_by(message_id=message.id, user_id=self.bob_id).one()
        self.assertIsNotNone(bob_key.read_at)

    def test_group_room_message_distribution(self):
        self._login("alice", "password1")
        group_response = self.client.post(
            "/chat/threads/group",
            data={"name": "Moon Council", "members": [self.bob_id, self.charlie_id]},
            follow_redirects=True,
        )
        self.assertEqual(group_response.status_code, 200)
        thread = ChatThread.query.filter_by(type="group").one()

        send_response = self.client.post(
            "/chat/send",
            data={"thread_id": thread.id, "body": "Gather at dusk."},
            follow_redirects=True,
        )
        self.assertEqual(send_response.status_code, 200)

        message = ChatMessage.query.one()
        keys = ChatMessageKey.query.filter_by(message_id=message.id).all()
        self.assertEqual(len(keys), 3)

        unread_recipients = {key.user_id for key in keys if key.read_at is None}
        self.assertEqual(unread_recipients, {self.bob_id, self.charlie_id})

        self._logout()

        # Bob unlocks and loads the room, reading the message.
        self._login("bob", "password2")
        conversation = self.client.get(f"/chat/?thread={thread.id}", follow_redirects=True)
        self.assertEqual(conversation.status_code, 200)
        self.assertIn(b"Gather at dusk.", conversation.data)

        bob_key = ChatMessageKey.query.filter_by(message_id=message.id, user_id=self.bob_id).one()
        self.assertIsNotNone(bob_key.read_at)

    def test_archdruid_auto_reply(self):
        self._login("alice", "password1")
        dm_response = self.client.post(
            "/chat/threads/dm",
            data={"recipient_id": self.arch_id},
            follow_redirects=True,
        )
        self.assertEqual(dm_response.status_code, 200)

        thread = (
            ChatThread.query.join(ChatThreadMember)
            .filter(ChatThread.type == "dm")
            .filter(ChatThreadMember.user_id == self.arch_id)
            .order_by(ChatThread.id.desc())
            .first()
        )
        self.assertIsNotNone(thread)

        send_response = self.client.post(
            "/chat/send",
            data={"thread_id": thread.id, "body": "Archdruid, what blessing do you suggest?"},
            follow_redirects=True,
        )
        self.assertEqual(send_response.status_code, 200)

        messages = (
            ChatMessage.query.filter_by(thread_id=thread.id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        self.assertGreaterEqual(len(messages), 2)
        self.assertEqual(messages[-1].sender_id, self.arch_id)


if __name__ == "__main__":
    unittest.main()
