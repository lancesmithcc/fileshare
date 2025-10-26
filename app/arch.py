from __future__ import annotations

from datetime import datetime, timedelta

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from .database import db
from .extensions import login_manager
from .models import Comment, Post, User
from .site_settings import ALLOWED_SETTING_KEYS, update_settings

arch_bp = Blueprint("arch", __name__, url_prefix="/arch")


@arch_bp.before_request
def enforce_arch_access():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()
    if not current_user.is_arch:
        abort(403)
    return None


@arch_bp.route("/")
def dashboard():
    pending_members = (
        User.query.filter_by(status="pending")
        .order_by(User.id.asc())
        .all()
    )
    active_members = (
        User.query.filter_by(status="active")
        .order_by(User.username.asc())
        .all()
    )
    suspended_members = (
        User.query.filter_by(status="suspended")
        .order_by(User.username.asc())
        .all()
    )
    return render_template(
        "arch/dashboard.html",
        pending_members=pending_members,
        active_members=active_members,
        suspended_members=suspended_members,
    )


@arch_bp.post("/users/<int:user_id>/approve")
def approve_user(user_id: int):
    member = User.query.get_or_404(user_id)
    if member.is_arch:
        flash("Arch druids are already vested with full access.", "info")
        return redirect(url_for("arch.dashboard"))
    if member.status == "active":
        flash(f"{member.username} already walks among the circles.", "info")
        return redirect(url_for("arch.dashboard"))
    member.status = "active"
    member.suspended_until = None
    db.session.add(member)
    db.session.commit()
    flash(f"{member.username} is now welcomed into the society.", "success")
    return redirect(url_for("arch.dashboard"))


@arch_bp.post("/users/<int:user_id>/role")
def update_user_role(user_id: int):
    member = User.query.get_or_404(user_id)
    if member.id == current_user.id:
        flash("You cannot alter your own mantle.", "info")
        return redirect(url_for("arch.dashboard"))

    role_map = {
        "member": "a member",
        "arch": "an arch druid",
    }
    new_role = request.form.get("role", "").strip()
    if new_role not in role_map:
        flash("Choose a valid role for the circle.", "warning")
        return redirect(url_for("arch.dashboard"))

    if member.role == new_role:
        flash(f"{member.username} already serves as {role_map[new_role]}.", "info")
        return redirect(url_for("arch.dashboard"))

    if member.is_arch and new_role != "arch":
        remaining_arches = (
            User.query.filter(User.role == "arch", User.id != member.id).count()
        )
        if remaining_arches == 0:
            flash("At least one arch druid must remain to steward the site.", "warning")
            return redirect(url_for("arch.dashboard"))

    member.role = new_role
    db.session.add(member)
    db.session.commit()
    flash(f"{member.username} now walks as {role_map[new_role]}.", "success")
    return redirect(url_for("arch.dashboard"))


@arch_bp.post("/users/<int:user_id>/suspend")
def suspend_user(user_id: int):
    member = User.query.get_or_404(user_id)
    if member.is_arch:
        flash("An arch druid cannot suspend their own mantle.", "warning")
        return redirect(url_for("arch.dashboard"))
    duration_value = request.form.get("duration_value", type=float)
    duration_unit = request.form.get("duration_unit", "hours")
    if not duration_value or duration_value <= 0:
        flash("Provide a suspension duration greater than zero.", "warning")
        return redirect(url_for("arch.dashboard"))

    if duration_unit == "weeks":
        delta = timedelta(weeks=duration_value)
    elif duration_unit == "days":
        delta = timedelta(days=duration_value)
    else:
        delta = timedelta(hours=duration_value)

    member.status = "suspended"
    current_until = member.suspended_until
    if isinstance(current_until, str):
        try:
            current_until = datetime.fromisoformat(current_until)
        except ValueError:
            current_until = None
    base = current_until if current_until and current_until > datetime.utcnow() else datetime.utcnow()
    member.suspended_until = base + delta
    db.session.add(member)
    db.session.commit()
    until_text = member.suspended_until.strftime("%Y-%m-%d %H:%M UTC")
    flash(f"{member.username} is suspended until {until_text}.", "warning")
    return redirect(url_for("arch.dashboard"))


@arch_bp.post("/users/<int:user_id>/unsuspend")
def unsuspend_user(user_id: int):
    member = User.query.get_or_404(user_id)
    if member.is_arch:
        flash("Arch druids remain ever-present.", "info")
        return redirect(url_for("arch.dashboard"))
    member.status = "active"
    member.suspended_until = None
    db.session.add(member)
    db.session.commit()
    flash(f"{member.username} has been welcomed back into the circle.", "success")
    return redirect(url_for("arch.dashboard"))


@arch_bp.post("/users/<int:user_id>/delete")
def delete_user(user_id: int):
    member = User.query.get_or_404(user_id)
    if member.is_arch:
        flash("Arch druids cannot be deleted.", "warning")
        return redirect(url_for("arch.dashboard"))
    username = member.username
    db.session.delete(member)
    db.session.commit()
    flash(f"Removed {username} and their contributions from the grove.", "warning")
    return redirect(url_for("arch.dashboard"))


@arch_bp.post("/settings")
def store_settings():
    updates = {}
    for key in ALLOWED_SETTING_KEYS:
        if key not in request.form:
            continue
        value = request.form.get(key, "")
        if key != "custom_css":
            value = value.strip()
        updates[key] = value
    if updates:
        update_settings(updates)
        flash("Site design and settings updated.", "success")
    else:
        flash("No settings were changed.", "info")
    return redirect(url_for("arch.dashboard"))


@arch_bp.post("/stream/posts/<int:post_id>/remove")
def remove_post(post_id: int):
    post = Post.query.get_or_404(post_id)
    author = post.author.username if post.author else "Unknown"
    db.session.delete(post)
    db.session.commit()
    flash(f"Removed post from {author}.", "warning")
    return redirect(url_for("social.feed"))


@arch_bp.post("/stream/comments/<int:comment_id>/remove")
def remove_comment(comment_id: int):
    comment = Comment.query.get_or_404(comment_id)
    author = comment.author.username if comment.author else "Unknown"
    db.session.delete(comment)
    db.session.commit()
    flash(f"Removed comment by {author}.", "warning")
    return redirect(url_for("social.feed"))
