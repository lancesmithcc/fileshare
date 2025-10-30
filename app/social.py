import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

from flask import (
    Blueprint,
    abort,
    flash,
    current_app,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from markupsafe import Markup, escape
from sqlalchemy.orm import joinedload

import requests

from .database import db
from .models import Circle, CircleMembership, Comment, Post, User
from werkzeug.utils import secure_filename

PRUNE_THRESHOLD = timedelta(days=11)
LINK_PATTERN = re.compile(r"(https?://[^\s<]+)", re.IGNORECASE)
CACHE_TTL = timedelta(hours=6)
_preview_cache: dict[str, dict] = {}

social_bp = Blueprint("social", __name__)


def _profile_storage_root() -> Path:
    root = Path(current_app.config["STORAGE_ROOT"]).expanduser()
    destination = root / "profiles"
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def _user_profile_dir(user_id: int) -> Path:
    directory = _profile_storage_root() / f"user_{user_id}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _normalize_dt(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def _prune_circles() -> None:
    """Remove circles older than the threshold with fewer than two members."""
    threshold = datetime.utcnow() - PRUNE_THRESHOLD
    stale_circles = (
        Circle.query.options(joinedload(Circle.members).joinedload(CircleMembership.member)).all()
    )
    deleted = False
    for circle in stale_circles:
        created_at = _normalize_dt(circle.created_at)
        if created_at is None:
            continue
        active_members = [
            membership.member
            for membership in circle.members
            if membership.member and membership.member.status == "active"
        ]
        if len(active_members) >= 2:
            continue
        if created_at > threshold:
            continue
        db.session.delete(circle)
        deleted = True
    if deleted:
        db.session.commit()


def _linkify(text: str) -> Markup:
    escaped = escape(text)

    def replace(match: re.Match[str]) -> str:
        url = match.group(0)
        safe_url = escape(url)
        return (
            f'<a href="{safe_url}" target="_blank" rel="noopener" class="inline-link">{safe_url}</a>'
        )

    linked = LINK_PATTERN.sub(lambda m: replace(m), escaped)
    return Markup(linked.replace("\n", "<br>"))


def _fetch_preview(url: str) -> dict | None:
    now = datetime.utcnow()
    cached = _preview_cache.get(url)
    if cached and now - cached["fetched_at"] < CACHE_TTL:
        return cached["data"]

    headers = {"User-Agent": "NeoDruidicSociety/1.0 (+https://fileshare.lancesmith.cc)"}
    try:
        resp = requests.get(url, timeout=5, headers=headers)
        if resp.status_code >= 400:
            return None
    except requests.RequestException:
        return None

    html = resp.text[:200000]

    def _find_meta(pattern: str) -> str | None:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    title = _find_meta(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']')
    if not title:
        title = _find_meta(r'<meta[^>]+name=["\']title["\'][^>]+content=["\']([^"\']+)["\']')
    if not title:
        title = _find_meta(r'<title[^>]*>([^<]+)</title>')

    description = _find_meta(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']')
    if not description:
        description = _find_meta(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']')

    image = _find_meta(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']')
    if image:
        image = urljoin(url, image)
    else:
        image = f"https://image.thum.io/get/width/600/{quote_plus(url)}"

    domain = urlparse(url).netloc

    data = {
        "url": url,
        "title": title or url,
        "description": description,
        "image": image,
        "domain": domain,
    }
    _preview_cache[url] = {"data": data, "fetched_at": now}
    return data


def _build_post_context(post: Post) -> dict:
    body_html = _linkify(post.body)
    match = LINK_PATTERN.search(post.body or "")
    preview = None
    if match:
        preview = _fetch_preview(match.group(0))
    return {"record": post, "body_html": body_html, "preview": preview}


@social_bp.route("/")
def index():
    query_text = (request.query_string or b"").decode()
    if (
        request.args.get("threads") is not None
        or request.args.get("chat") is not None
        or "threads" in query_text
        or "chat" in query_text
    ):
        return redirect(url_for("chat.index"))
    if current_user.is_authenticated:
        return redirect(url_for("social.feed"))
    return redirect(url_for("auth.login"))


@social_bp.route("/feed")
@login_required
def feed():
    circle_filter = request.args.get("circle")
    query = Post.query.order_by(Post.created_at.desc())
    if circle_filter:
        query = (
            query.join(Post.author)
            .join(CircleMembership, isouter=True)
            .join(Circle, isouter=True)
            .filter(Circle.name == circle_filter)
        )
    posts = query.limit(50).all()
    circles = Circle.query.order_by(Circle.name.asc()).all()
    post_entries = [_build_post_context(post) for post in posts]
    return render_template("social/feed.html", post_entries=post_entries, circles=circles)


@social_bp.route("/posts", methods=["POST"])
@login_required
def create_post():
    body = request.form.get("body", "").strip()
    ritual_focus = request.form.get("ritual_focus", "").strip()

    if not body:
        flash("Share at least a few words with the grove.", "warning")
        return redirect(url_for("social.feed"))

    post = Post(body=body, ritual_focus=ritual_focus or None, author=current_user)
    db.session.add(post)
    db.session.commit()
    flash("Your words join the circle.", "success")
    return redirect(url_for("social.feed"))


@social_bp.route("/posts/<int:post_id>/comment", methods=["POST"])
@login_required
def comment(post_id: int):
    post = Post.query.get_or_404(post_id)
    body = request.form.get("body", "").strip()

    if not body:
        flash("A comment cannot be only silence.", "warning")
        return redirect(url_for("social.feed"))

    comm = Comment(body=body, post=post, author=current_user)
    db.session.add(comm)
    db.session.commit()
    flash("You have spoken.", "success")
    return redirect(url_for("social.feed"))


@social_bp.route("/circles", methods=["GET", "POST"])
@login_required
def circles():
    if request.method == "POST":
        name = (request.form.get("circle_name") or "").strip()
        description = (request.form.get("circle_description") or "").strip()
        if not name:
            flash("Name your circle before summoning it into being.", "warning")
            return redirect(url_for("social.circles"))
        existing = Circle.query.filter(db.func.lower(Circle.name) == name.lower()).first()
        if existing:
            flash("A circle already resonates with that name.", "warning")
            return redirect(url_for("social.circles"))
        circle = Circle(name=name, description=description or None, created_at=datetime.utcnow())
        db.session.add(circle)
        db.session.flush()

        membership = current_user.circle_membership
        if membership:
            membership.circle = circle
        else:
            db.session.add(CircleMembership(member=current_user, circle=circle))
        db.session.commit()
        flash(f"{name} circle now gathers around you.", "success")
        return redirect(url_for("social.circles"))

    _prune_circles()

    circles = (
        Circle.query.options(joinedload(Circle.members).joinedload(CircleMembership.member))
        .order_by(Circle.name.asc())
        .all()
    )
    circle_sections = []
    for circle in circles:
        members = [
            membership.member
            for membership in circle.members
            if membership.member and membership.member.status == "active"
        ]
        members.sort(key=lambda member: member.username.lower())
        circle_sections.append(
            {
                "id": circle.id,
                "name": circle.name,
                "description": circle.description
                or "New circle formed by members. Shape its path together.",
                "members": members,
            }
        )

    all_members = (
        User.query.filter_by(status="active")
        .order_by(User.username.asc())
        .all()
    )

    all_circle = {
        "name": "All One Circle",
        "description": "Every active member gathered as one grove.",
        "members": all_members,
    }

    return render_template(
        "social/circles.html",
        circle_sections=circle_sections,
        all_circle=all_circle,
    )


@social_bp.route("/grove/<username>")
@login_required
def profile(username: str):
    user = User.query.filter(
        db.func.lower(User.username) == username.lower()
    ).first_or_404()
    posts = Post.query.filter_by(author_id=user.id).order_by(Post.created_at.desc()).all()
    post_entries = [_build_post_context(post) for post in posts]
    return render_template("social/profile.html", druid=user, post_entries=post_entries)


@social_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        form_type = request.form.get("form_type", "profile")
        
        # Handle password change
        if form_type == "password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            
            if not current_password or not new_password or not confirm_password:
                flash("All password fields are required.", "warning")
                return redirect(url_for("social.edit_profile"))
            
            if not current_user.check_password(current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("social.edit_profile"))
            
            if new_password != confirm_password:
                flash("New passwords do not match.", "warning")
                return redirect(url_for("social.edit_profile"))
            
            if len(new_password) < 8:
                flash("New password must be at least 8 characters long.", "warning")
                return redirect(url_for("social.edit_profile"))
            
            from werkzeug.security import generate_password_hash
            current_user.password_hash = generate_password_hash(new_password)
            db.session.add(current_user)
            db.session.commit()
            flash("Your password has been updated successfully.", "success")
            return redirect(url_for("social.edit_profile"))
        
        # Handle profile update
        bio = request.form.get("bio", "").strip()
        grove = request.form.get("grove", "").strip()
        profile_html = request.form.get("profile_html", "")
        profile_css = request.form.get("profile_css", "")
        profile_js = request.form.get("profile_js", "")

        current_user.bio = bio or None
        current_user.grove = grove or None
        current_user.profile_html = profile_html or None
        current_user.profile_css = profile_css or None
        current_user.profile_js = profile_js or None

        image = request.files.get("profile_image")
        if image and image.filename:
            filename = secure_filename(image.filename)
            if not filename:
                flash("The uploaded image needs a name.", "warning")
                return redirect(url_for("social.edit_profile"))
            suffix = Path(filename).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                flash("Please upload a PNG, JPG, GIF, or WEBP image.", "warning")
                return redirect(url_for("social.edit_profile"))

            profile_dir = _user_profile_dir(current_user.id)
            unique_name = f"profile_{secrets.token_hex(8)}{suffix}"
            destination = profile_dir / unique_name
            image.save(destination)

            if current_user.profile_image:
                try:
                    existing = (_profile_storage_root() / current_user.profile_image).resolve()
                    # Ensure we only delete inside the profiles directory.
                    if _profile_storage_root().resolve() in existing.parents and existing.exists():
                        existing.unlink()
                except (OSError, ValueError):
                    current_app.logger.warning(
                        "Failed to remove previous profile image for user %s", current_user.id
                    )

            relative_path = destination.relative_to(_profile_storage_root())
            current_user.profile_image = relative_path.as_posix()

        db.session.add(current_user)
        db.session.commit()
        flash("Your AWEN01 profile has been refreshed.", "success")
        return redirect(url_for("social.profile", username=current_user.username))

    return render_template("social/profile_edit.html", druid=current_user)


@social_bp.route("/profile/media/<path:asset>")
def profile_media(asset: str):
    profiles_root = _profile_storage_root().resolve()
    requested = (profiles_root / asset).resolve()
    if profiles_root not in requested.parents and requested != profiles_root:
        abort(404)
    if not requested.exists() or not requested.is_file():
        abort(404)
    relative_path = requested.relative_to(profiles_root).as_posix()
    return send_from_directory(profiles_root, relative_path)


@social_bp.post("/circles/<int:circle_id>/delete")
@login_required
def delete_circle(circle_id: int):
    if not current_user.is_arch:
        abort(403)
    circle = Circle.query.get_or_404(circle_id)
    name = circle.name
    db.session.delete(circle)
    db.session.commit()
    flash(f"Circle '{name}' has been released back to the wild.", "warning")
    return redirect(url_for("social.circles"))
