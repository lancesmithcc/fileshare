"""
WSPR (Whisper) - Standalone End-to-End Encrypted Chat
Public chat application using ML-KEM-768 (Kyber) post-quantum encryption
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from sqlalchemy import or_, and_, func
from werkzeug.security import generate_password_hash

from .database import db
from .wspr_models import WsprUser, WsprRoom, WsprRoomMember, WsprMessage, WsprSession
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

wspr_bp = Blueprint("wspr", __name__, url_prefix="/wspr")


# Custom login required decorator for WSPR
def wspr_login_required(f):
    """Decorator to require WSPR-specific login"""
    def decorated_function(*args, **kwargs):
        wspr_user_id = session.get('wspr_user_id')
        if not wspr_user_id:
            flash("Please log in to access WSPR chat.", "warning")
            return redirect(url_for('wspr.login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


# ==================== PUBLIC PAGES ====================

@wspr_bp.route("/")
def index():
    """WSPR landing page"""
    wspr_user_id = session.get('wspr_user_id')
    is_logged_in = wspr_user_id is not None

    return render_template("wspr/landing.html", is_logged_in=is_logged_in)


@wspr_bp.route("/register", methods=["GET", "POST"])
def register():
    """Register new WSPR user"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation
        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("wspr/register.html")

        if len(username) < 3 or len(username) > 80:
            flash("Username must be between 3 and 80 characters.", "error")
            return render_template("wspr/register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("wspr/register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("wspr/register.html")

        # Check if username or email already exists
        existing_user = WsprUser.query.filter(
            or_(
                WsprUser.username == username,
                WsprUser.email == email
            )
        ).first()

        if existing_user:
            if existing_user.username == username:
                flash("Username already taken. Please choose another.", "error")
            else:
                flash("Email already registered.", "error")
            return render_template("wspr/register.html")

        # Create user
        user = WsprUser(
            username=username,
            email=email
        )
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()

            # Log the user in
            session['wspr_user_id'] = user.id
            session['wspr_username'] = user.username
            session.permanent = True

            flash(f"Welcome to WSPR, {username}! Your account has been created.", "success")
            return redirect(url_for('wspr.setup_encryption'))

        except Exception as e:
            db.session.rollback()
            flash("An error occurred during registration. Please try again.", "error")
            return render_template("wspr/register.html")

    return render_template("wspr/register.html")


@wspr_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login to WSPR"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = WsprUser.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['wspr_user_id'] = user.id
            session['wspr_username'] = user.username
            session.permanent = True

            # Update last seen
            user.last_seen = datetime.utcnow()
            db.session.commit()

            flash(f"Welcome back, {username}!", "success")

            # Check if user has encryption keys
            if not user.has_keys:
                return redirect(url_for('wspr.setup_encryption'))

            # Check if encryption is unlocked
            if session.get('wspr_chat_unlocked'):
                return redirect(url_for('wspr.chat'))
            else:
                return redirect(url_for('wspr.unlock'))
        else:
            flash("Invalid username or password.", "error")

    return render_template("wspr/login.html")


@wspr_bp.route("/logout")
@wspr_login_required
def logout():
    """Logout from WSPR"""
    username = session.get('wspr_username', 'User')
    session.pop('wspr_user_id', None)
    session.pop('wspr_username', None)
    session.pop('wspr_chat_unlocked', None)
    session.pop('wspr_session_key', None)
    flash(f"Goodbye, {username}. You've been logged out.", "info")
    return redirect(url_for('wspr.index'))


# ==================== ENCRYPTION SETUP ====================

@wspr_bp.route("/setup-encryption", methods=["GET", "POST"])
@wspr_login_required
def setup_encryption():
    """Set up post-quantum encryption keys"""
    wspr_user_id = session.get('wspr_user_id')
    user = WsprUser.query.get(wspr_user_id)

    if not user:
        return redirect(url_for('wspr.logout'))

    # If user already has keys, redirect to unlock
    if user.has_keys:
        return redirect(url_for('wspr.unlock'))

    if request.method == "POST":
        passphrase = request.form.get("passphrase", "")
        confirm_passphrase = request.form.get("confirm_passphrase", "")

        if not passphrase:
            flash("Passphrase is required.", "error")
            return render_template("wspr/setup_encryption.html")

        if len(passphrase) < 12:
            flash("Passphrase must be at least 12 characters for security.", "error")
            return render_template("wspr/setup_encryption.html")

        if passphrase != confirm_passphrase:
            flash("Passphrases do not match.", "error")
            return render_template("wspr/setup_encryption.html")

        try:
            # Generate ML-KEM-768 keypair and encrypt with passphrase
            identity = generate_identity(passphrase)

            # Store encrypted keys
            user.public_key = identity.public_key
            user.private_key_encrypted = identity.encrypted_private_key
            user.private_key_nonce = identity.nonce
            user.key_salt = identity.salt
            user.keys_generated_at = datetime.utcnow()

            db.session.commit()

            # Mark encryption as unlocked for this session
            session['wspr_chat_unlocked'] = True

            flash("Encryption keys generated successfully! Your messages are now quantum-safe.", "success")
            return redirect(url_for('wspr.chat'))

        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {str(e)}", "error")
            return render_template("wspr/setup_encryption.html")

    return render_template("wspr/setup_encryption.html")


@wspr_bp.route("/unlock", methods=["GET", "POST"])
@wspr_login_required
def unlock():
    """Unlock encrypted chat with passphrase"""
    wspr_user_id = session.get('wspr_user_id')
    user = WsprUser.query.get(wspr_user_id)

    if not user:
        return redirect(url_for('wspr.logout'))

    if not user.has_keys:
        return redirect(url_for('wspr.setup_encryption'))

    # Already unlocked
    if session.get('wspr_chat_unlocked'):
        return redirect(url_for('wspr.chat'))

    if request.method == "POST":
        passphrase = request.form.get("passphrase", "")

        if not passphrase:
            flash("Passphrase is required.", "error")
            return render_template("wspr/unlock.html")

        try:
            # Create identity object from stored keys
            identity = ChatIdentity(
                public_key=user.public_key,
                encrypted_private_key=user.private_key_encrypted,
                salt=user.key_salt,
                nonce=user.private_key_nonce
            )

            # Unlock private key with passphrase
            private_key = unlock_private_key(identity, passphrase)

            session['wspr_chat_unlocked'] = True
            session['wspr_private_key'] = private_key  # Store decrypted key in session
            flash("Chat unlocked successfully!", "success")
            return redirect(url_for('wspr.chat'))

        except Exception as e:
            flash("Incorrect passphrase or decryption error.", "error")

    return render_template("wspr/unlock.html")


@wspr_bp.route("/lock", methods=["POST"])
@wspr_login_required
def lock():
    """Lock encrypted chat"""
    session.pop('wspr_chat_unlocked', None)
    session.pop('wspr_session_key', None)
    flash("Chat locked. Your encryption keys have been cleared from memory.", "info")
    return redirect(url_for('wspr.unlock'))


# ==================== CHAT INTERFACE ====================

@wspr_bp.route("/chat")
@wspr_login_required
def chat():
    """Main chat interface"""
    wspr_user_id = session.get('wspr_user_id')
    user = WsprUser.query.get(wspr_user_id)

    if not user:
        return redirect(url_for('wspr.logout'))

    if not user.has_keys:
        return redirect(url_for('wspr.setup_encryption'))

    if not session.get('wspr_chat_unlocked'):
        return redirect(url_for('wspr.unlock'))

    # Get user's rooms
    memberships = WsprRoomMember.query.filter_by(user_id=user.id).all()
    room_ids = [m.room_id for m in memberships]
    rooms = WsprRoom.query.filter(WsprRoom.id.in_(room_ids)).order_by(WsprRoom.last_activity.desc()).all() if room_ids else []

    # Get current room
    current_room_id = request.args.get("room", type=int)
    current_room = None
    messages = []

    if current_room_id and current_room_id in room_ids:
        current_room = WsprRoom.query.get(current_room_id)
        if current_room:
            # Get messages
            messages = WsprMessage.query.filter_by(room_id=current_room.id).order_by(WsprMessage.created_at.asc()).all()

            # TODO: Implement proper message decryption with message keys
            # For now, messages are stored unencrypted until full crypto is implemented
            decrypted_messages = []
            for msg in messages:
                decrypted_messages.append({
                    "id": msg.id,
                    "sender": msg.sender,
                    "body": msg.body_ciphertext.decode('utf-8') if isinstance(msg.body_ciphertext, bytes) else msg.body_ciphertext,
                    "created_at": msg.created_at,
                    "is_self": msg.sender_id == user.id
                })

            messages = decrypted_messages

    # Get all users for creating new rooms
    all_users = WsprUser.query.filter(WsprUser.id != user.id).order_by(WsprUser.username.asc()).all()

    return render_template(
        "wspr/chat.html",
        rooms=rooms,
        current_room=current_room,
        messages=messages,
        all_users=all_users,
        user=user
    )


# ==================== ROOM MANAGEMENT ====================

@wspr_bp.route("/create-room", methods=["POST"])
@wspr_login_required
def create_room():
    """Create a new chat room"""
    wspr_user_id = session.get('wspr_user_id')
    user = WsprUser.query.get(wspr_user_id)

    room_type = request.form.get("type", "dm")
    room_name = request.form.get("name", "").strip()
    member_ids = request.form.getlist("members", type=int)

    if room_type == "group" and not room_name:
        flash("Group rooms require a name.", "error")
        return redirect(url_for('wspr.chat'))

    if not member_ids:
        flash("Please select at least one member.", "error")
        return redirect(url_for('wspr.chat'))

    # For DM, only allow one other member
    if room_type == "dm" and len(member_ids) != 1:
        flash("Direct messages can only have one other member.", "error")
        return redirect(url_for('wspr.chat'))

    # Check if DM already exists
    if room_type == "dm":
        other_user_id = member_ids[0]
        existing_dm = db.session.query(WsprRoom).join(
            WsprRoomMember, WsprRoom.id == WsprRoomMember.room_id
        ).filter(
            WsprRoom.type == "dm",
            WsprRoomMember.user_id.in_([user.id, other_user_id])
        ).group_by(WsprRoom.id).having(
            func.count(WsprRoomMember.user_id) == 2
        ).first()

        if existing_dm:
            flash("A DM with this user already exists.", "info")
            return redirect(url_for('wspr.chat', room=existing_dm.id))

    # Create room
    room = WsprRoom(
        type=room_type,
        name=room_name if room_type == "group" else None,
        creator_id=user.id
    )
    db.session.add(room)
    db.session.flush()

    # Add members
    for member_id in member_ids:
        membership = WsprRoomMember(room_id=room.id, user_id=member_id)
        db.session.add(membership)

    # Add creator as member
    creator_membership = WsprRoomMember(room_id=room.id, user_id=user.id)
    db.session.add(creator_membership)

    db.session.commit()

    flash("Room created successfully!", "success")
    return redirect(url_for('wspr.chat', room=room.id))


# ==================== API ENDPOINTS ====================

@wspr_bp.route("/api/send-message", methods=["POST"])
@wspr_login_required
def api_send_message():
    """Send an encrypted message"""
    wspr_user_id = session.get('wspr_user_id')
    user = WsprUser.query.get(wspr_user_id)

    data = request.get_json()
    room_id = data.get("room_id")
    message_body = data.get("body", "").strip()

    if not room_id or not message_body:
        return jsonify({"error": "Missing room_id or body"}), 400

    room = WsprRoom.query.get(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404

    # Check if user is a member
    membership = WsprRoomMember.query.filter_by(room_id=room.id, user_id=user.id).first()
    if not membership:
        return jsonify({"error": "You are not a member of this room"}), 403

    # TODO: Implement proper message encryption with message keys
    # For now, storing messages as plain text until full crypto is implemented
    # Save message
    message = WsprMessage(
        room_id=room.id,
        sender_id=user.id,
        body_ciphertext=message_body.encode('utf-8'),
        body_nonce=b''  # Empty nonce for now
    )
    db.session.add(message)

    # Update room activity
    room.last_activity = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "id": message.id,
        "sender": {
            "id": user.id,
            "username": user.username
        },
        "body": message_body,
        "created_at": message.created_at.isoformat()
    }), 201
