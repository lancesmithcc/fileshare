from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .database import db
from .models import User
from .chat import ensure_chat_identity, provision_chat_identity
from . import chat_session

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("social.feed"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        reason = request.form.get("join_reason", "").strip()

        if not username or not email or not password:
            flash("Username, email, and password are required.", "danger")
        elif User.query.filter(
            db.func.lower(User.username) == username.lower()
        ).first():
            flash("That name is already in use among the groves.", "warning")
        elif User.query.filter_by(email=email).first():
            flash("Someone already receives missives at that email.", "warning")
        else:
            user = User(
                username=username,
                email=email,
                status="pending",
                join_reason=reason or None,
            )
            user.set_password(password)
            provision_chat_identity(user, password)
            db.session.add(user)

            db.session.commit()
            current_app.logger.info("New membership awaiting approval: %s", username)
            flash("Your request is with the arch druids. You will be notified once approved.", "info")
            return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("social.feed"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter(
            db.func.lower(User.username) == username.lower()
        ).first()

        if user and user.check_password(password):
            if user.lift_suspension_if_expired():
                db.session.add(user)
                db.session.commit()
            if user.status == "suspended":
                if user.suspended_until:
                    flash(
                        "Your membership is suspended until {} UTC.".format(
                            user.suspended_until.strftime("%Y-%m-%d %H:%M")
                        ),
                        "danger",
                    )
                else:
                    flash("Your membership is suspended until the arch lifts the mantle.", "danger")
                return redirect(url_for("auth.login"))
            if not user.is_active:
                if user.is_pending:
                    flash("Your membership awaits arch approval. Please check back soon.", "warning")
                else:
                    flash("Your account is not active. Reach out to the arch druids for assistance.", "danger")
                return redirect(url_for("auth.login"))
            user.last_seen = datetime.utcnow()
            private_key = ensure_chat_identity(user, password)
            db.session.add(user)
            db.session.commit()
            chat_session.store_private_key(private_key, user.chat_identity_version)
            login_user(user, remember=remember)
            flash("The circle recognizes you. Welcome back.", "success")
            return redirect(url_for("social.feed"))

        flash("The spirits do not recognize those credentials.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    chat_session.clear_private_key()
    logout_user()
    flash("Until the next gathering.", "info")
    return redirect(url_for("auth.login"))
