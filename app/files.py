from __future__ import annotations

import mimetypes
import secrets
from pathlib import Path
from typing import List, Optional, Tuple

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename


from .database import db
from .models import FileAsset, FileFolder

files_bp = Blueprint("files", __name__, url_prefix="/files")


def _storage_root() -> Path:
    root = Path(current_app.config["STORAGE_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def _user_storage_root(owner_id: Optional[int] = None) -> Path:
    root = _storage_root()
    target = root / f"user_{owner_id or current_user.id}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _folder_path(folder: FileFolder) -> Path:
    return _user_storage_root(folder.owner_id) / f"folder_{folder.id}"


def _ensure_folder_directory(folder: FileFolder) -> Path:
    path = _folder_path(folder)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _destination_for(
    owner_id: int, stored_basename: str, folder: Optional[FileFolder]
) -> Tuple[Path, str]:
    root = _storage_root()
    user_dir = root / f"user_{owner_id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    if folder:
        target_dir = user_dir / f"folder_{folder.id}"
        target_dir.mkdir(parents=True, exist_ok=True)
    else:
        target_dir = user_dir
    destination = target_dir / stored_basename
    relative = destination.relative_to(root).as_posix()
    return destination, relative


def _asset_path(asset: FileAsset) -> Path:
    root = _storage_root()
    candidate = root / asset.stored_name
    if candidate.exists():
        return candidate
    # Backwards compatibility with legacy flat storage.
    fallback = root / Path(asset.stored_name).name
    if fallback.exists():
        return fallback
    user_dir = root / f"user_{asset.owner_id}"
    alt = user_dir / Path(asset.stored_name).name
    return alt


def _cleanup_empty_dirs(path: Path, stop: Path) -> None:
    try:
        path = path.resolve()
        stop = stop.resolve()
    except FileNotFoundError:
        return
    while path != stop and stop in path.parents:
        try:
            path.rmdir()
        except OSError:
            break
        path = path.parent


def _unique_storage_name(original: str) -> str:
    suffix = Path(original).suffix
    return f"{secrets.token_hex(16)}{suffix}"


def _folder_breadcrumbs(folder: Optional[FileFolder]) -> List[FileFolder]:
    crumbs: List[FileFolder] = []
    node = folder
    while node:
        crumbs.append(node)
        node = node.parent
    return list(reversed(crumbs))


def _folder_options(exclude: Optional[FileFolder] = None) -> List[Tuple[str, str]]:
    options: List[Tuple[str, str]] = [("", "Shared Hollow")]

    def visit(folder: FileFolder, prefix: str = "") -> None:
        if exclude and folder.id == exclude.id:
            return
        label = f"{prefix}{folder.name}"
        options.append((str(folder.id), label))
        child_prefix = f"{label} / "
        for child in folder.children:
            visit(child, child_prefix)

    roots = (
        FileFolder.query.filter_by(owner_id=current_user.id, parent_id=None)
        .order_by(FileFolder.name.asc())
        .all()
    )
    for folder in roots:
        visit(folder)
    return options


def _resolve_folder(folder_id: Optional[int]) -> Optional[FileFolder]:
    if not folder_id:
        return None
    return FileFolder.query.filter_by(
        id=folder_id, owner_id=current_user.id
    ).first_or_404()


def _current_folder_id() -> Optional[int]:
    folder_param = request.args.get("folder", type=int)
    return folder_param


@files_bp.route("/", methods=["GET"])
@login_required
def index():
    folder_id = request.args.get("folder", type=int)
    current_folder = _resolve_folder(folder_id)

    child_folders = (
        FileFolder.query.filter_by(
            owner_id=current_user.id,
            parent_id=current_folder.id if current_folder else None,
        )
        .order_by(FileFolder.name.asc())
        .all()
    )

    file_query = FileAsset.query.filter_by(owner_id=current_user.id)
    if current_folder:
        file_query = file_query.filter(FileAsset.folder_id == current_folder.id)
    else:
        file_query = file_query.filter(FileAsset.folder_id.is_(None))
    files = file_query.order_by(FileAsset.created_at.desc()).all()

    breadcrumbs = _folder_breadcrumbs(current_folder)
    folder_options = _folder_options()

    return render_template(
        "files/index.html",
        files=files,
        folders=child_folders,
        current_folder=current_folder,
        breadcrumbs=breadcrumbs,
        folder_options=folder_options,
    )


@files_bp.route("/folders", methods=["POST"])
@login_required
def create_folder():
    name = (request.form.get("name") or "").strip()
    parent_id = request.form.get("parent_id", type=int)
    if not name:
        flash("Name your new folder to continue.", "warning")
        return redirect(url_for("files.index", folder=parent_id))

    name = name.replace("/", "-")[:120]
    parent = _resolve_folder(parent_id)

    duplicate = FileFolder.query.filter_by(
        owner_id=current_user.id,
        parent_id=parent.id if parent else None,
        name=name,
    ).first()
    if duplicate:
        flash("A folder with that name already exists here.", "warning")
        return redirect(url_for("files.index", folder=parent_id))

    folder = FileFolder(owner=current_user, name=name, parent=parent)
    db.session.add(folder)
    db.session.commit()
    _ensure_folder_directory(folder)

    if request.is_json:
        return jsonify(
            {
                "status": "ok",
                "folder": {
                    "id": folder.id,
                    "name": folder.name,
                    "pos_x": folder.pos_x,
                    "pos_y": folder.pos_y,
                },
            }
        )

    flash("Folder conjured successfully.", "success")
    return redirect(url_for("files.index", folder=folder.id))


@files_bp.route("/folders/<int:folder_id>/delete", methods=["POST"])
@login_required
def delete_folder(folder_id: int):
    folder = FileFolder.query.filter_by(
        id=folder_id, owner_id=current_user.id
    ).first_or_404()
    return_folder = request.form.get("current_folder_id", type=int)

    if folder.children or folder.files:
        flash("Empty that folder before returning it to the forest.", "warning")
        return redirect(url_for("files.index", folder=return_folder or folder.id))

    folder_path = _folder_path(folder)
    parent_id = folder.parent_id

    db.session.delete(folder)
    db.session.commit()

    _cleanup_empty_dirs(folder_path, _user_storage_root(folder.owner_id))

    if request.is_json:
        return jsonify({"status": "ok", "parent_id": parent_id})

    flash("Folder released.", "info")
    return redirect(url_for("files.index", folder=parent_id))




@files_bp.route("/folders/<int:folder_id>/rename", methods=["POST"])
@login_required
def rename_folder(folder_id: int):
    folder = FileFolder.query.filter_by(id=folder_id, owner_id=current_user.id).first_or_404()
    new_name = (request.form.get("name") or "").strip()
    current_folder_id = request.form.get("current_folder_id", type=int)

    if not new_name:
        flash("Name your folder before saving.", "warning")
        return redirect(url_for("files.index", folder=current_folder_id or folder.id))

    new_name = new_name.replace("/", "-")[:120]

    duplicate = (
        FileFolder.query.filter_by(
            owner_id=current_user.id,
            parent_id=folder.parent_id,
            name=new_name,
        )
        .filter(FileFolder.id != folder.id)
        .first()
    )
    if duplicate:
        flash("Another folder already holds that name here.", "warning")
        return redirect(url_for("files.index", folder=current_folder_id or folder.id))

    folder.name = new_name
    db.session.commit()

    if request.is_json:
        return jsonify(
            {
                "status": "ok",
                "folder": {
                    "id": folder.id,
                    "name": folder.name,
                },
            }
        )

    flash("Folder renamed.", "success")
    return redirect(url_for("files.index", folder=current_folder_id or folder.id))


@files_bp.route("/files/<int:file_id>/rename", methods=["POST"])
@login_required
def rename_file(file_id: int):
    asset = FileAsset.query.get_or_404(file_id)
    if asset.owner_id != current_user.id:
        abort(403)

    new_name = (request.form.get("name") if not request.is_json else (request.json or {}).get("name")) or ""
    new_name = new_name.strip()
    current_folder_id = request.form.get("current_folder_id", type=int)

    if not new_name:
        if request.is_json:
            return jsonify({"status": "error", "message": "Name required."}), 400
        flash("Provide a new name before saving.", "warning")
        return redirect(url_for("files.index", folder=current_folder_id or asset.folder_id))

    asset.original_name = new_name
    db.session.commit()

    if request.is_json:
        return jsonify({"status": "ok", "file": {"id": asset.id, "name": asset.original_name}})

    flash("File renamed.", "success")
    return redirect(url_for("files.index", folder=current_folder_id or asset.folder_id))


@files_bp.route("/position", methods=["POST"])
@login_required
def update_position():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"status": "error", "message": "JSON body required."}), 400

    obj_type = payload.get("type")
    obj_id = payload.get("id")
    try:
        pos_x = float(payload.get("x", 0))
        pos_y = float(payload.get("y", 0))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid coordinates."}), 400

    if obj_type == "file":
        asset = FileAsset.query.get_or_404(int(obj_id))
        if asset.owner_id != current_user.id:
            abort(403)
        asset.pos_x = pos_x
        asset.pos_y = pos_y
        db.session.commit()
        return jsonify({"status": "ok"})

    if obj_type == "folder":
        folder = FileFolder.query.get_or_404(int(obj_id))
        if folder.owner_id != current_user.id:
            abort(403)
        folder.pos_x = pos_x
        folder.pos_y = pos_y
        db.session.commit()
        return jsonify({"status": "ok"})

    return jsonify({"status": "error", "message": "Unknown object type."}), 400


@files_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    uploaded = request.files.get("file")
    if uploaded is None or uploaded.filename == "":
        flash("Select a file to share with the grove.", "warning")
        return redirect(url_for("files.index", folder=_current_folder_id()))

    safe_name = secure_filename(uploaded.filename) or uploaded.filename
    folder_id = request.form.get("folder_id", type=int)
    target_folder = _resolve_folder(folder_id)

    stored_basename = _unique_storage_name(safe_name)
    destination, relative_name = _destination_for(
        current_user.id, stored_basename, target_folder
    )
    while destination.exists():
        stored_basename = _unique_storage_name(safe_name)
        destination, relative_name = _destination_for(
            current_user.id, stored_basename, target_folder
        )

    try:
        uploaded.save(destination)
        size = destination.stat().st_size
    except OSError:
        flash("The forest rejected that upload. Try again.", "danger")
        if destination.exists():
            destination.unlink(missing_ok=True)
        return redirect(url_for("files.index", folder=_current_folder_id()))

    mime_type, _ = mimetypes.guess_type(safe_name)

    asset = FileAsset(
        owner=current_user,
        original_name=safe_name,
        stored_name=relative_name,
        mime_type=mime_type,
        size=size,
        folder=target_folder,
    )
    db.session.add(asset)
    db.session.commit()
    flash("Your file now rests in the shared hollow.", "success")
    return redirect(url_for("files.index", folder=target_folder.id if target_folder else None))


@files_bp.route("/move/<int:file_id>", methods=["POST"])
@login_required
def move(file_id: int):
    asset = FileAsset.query.get_or_404(file_id)
    if asset.owner_id != current_user.id:
        abort(403)

    target_folder_id = request.form.get("folder_id")
    current_folder_id = request.form.get("current_folder_id", type=int)

    target_folder = _resolve_folder(int(target_folder_id)) if target_folder_id else None
    if asset.folder_id == (target_folder.id if target_folder else None):
        flash("That file is already resting there.", "info")
        return redirect(url_for("files.index", folder=current_folder_id))

    current_path = _asset_path(asset)
    if not current_path.exists():
        flash("The file could not be found on disk.", "danger")
        return redirect(url_for("files.index", folder=current_folder_id))

    stored_basename = _unique_storage_name(asset.original_name)
    destination, relative_name = _destination_for(
        asset.owner_id, stored_basename, target_folder
    )
    while destination.exists():
        stored_basename = _unique_storage_name(asset.original_name)
        destination, relative_name = _destination_for(
            asset.owner_id, stored_basename, target_folder
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    current_path.rename(destination)

    asset.folder = target_folder
    asset.stored_name = relative_name
    asset.pos_x = 0.0
    asset.pos_y = 0.0
    db.session.commit()

    _cleanup_empty_dirs(current_path.parent, _user_storage_root(asset.owner_id))

    flash("File moved with care.", "success")
    redirect_folder = current_folder_id if current_folder_id is not None else (target_folder.id if target_folder else None)
    return redirect(url_for("files.index", folder=redirect_folder))


@files_bp.route("/download/<int:file_id>", methods=["GET"])
@login_required
def download(file_id: int):
    asset = FileAsset.query.get_or_404(file_id)
    if asset.owner_id != current_user.id:
        abort(403)

    file_path = _asset_path(asset)
    if not file_path.exists():
        flash("That file has wandered off into the woods.", "warning")
        return redirect(url_for("files.index", folder=_current_folder_id()))

    return send_from_directory(
        _storage_root(),
        asset.stored_name,
        as_attachment=True,
        download_name=asset.original_name,
        mimetype=asset.mime_type,
    )


@files_bp.route("/preview/<int:file_id>", methods=["GET"])
@login_required
def preview(file_id: int):
    asset = FileAsset.query.get_or_404(file_id)
    if asset.owner_id != current_user.id:
        abort(403)

    if not asset.mime_type or not asset.mime_type.startswith("image/"):
        abort(404)

    file_path = _asset_path(asset)
    if not file_path.exists():
        abort(404)

    return send_from_directory(
        file_path.parent,
        file_path.name,
        as_attachment=False,
        download_name=asset.original_name,
        mimetype=asset.mime_type,
        max_age=60,
    )


@files_bp.route("/share/<int:file_id>", methods=["POST"])
@login_required
def enable_share(file_id: int):
    asset = FileAsset.query.get_or_404(file_id)
    if asset.owner_id != current_user.id:
        abort(403)

    rotate = request.form.get("rotate") == "1"
    if asset.share_token is None or rotate:
        asset.share_token = secrets.token_urlsafe(16)
        db.session.commit()
        flash("Share link refreshed for the circle.", "success")
    else:
        flash("That file is already shared. Use rotate to renew the link.", "info")

    current_folder = request.form.get("current_folder_id", type=int)
    return redirect(url_for("files.index", folder=current_folder))


@files_bp.route("/unshare/<int:file_id>", methods=["POST"])
@login_required
def disable_share(file_id: int):
    asset = FileAsset.query.get_or_404(file_id)
    if asset.owner_id != current_user.id:
        abort(403)

    if asset.share_token is None:
        flash("That file was not shared beyond your grove.", "info")
    else:
        asset.share_token = None
        db.session.commit()
        flash("The share link has been withdrawn.", "info")

    current_folder = request.form.get("current_folder_id", type=int)
    return redirect(url_for("files.index", folder=current_folder))


@files_bp.route("/delete/<int:file_id>", methods=["POST"])
@login_required
def delete(file_id: int):
    asset = FileAsset.query.get_or_404(file_id)
    if asset.owner_id != current_user.id:
        abort(403)

    file_path = _asset_path(asset)
    user_root = _user_storage_root(asset.owner_id)
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            current_app.logger.warning("Unable to delete file at %s", file_path)
    _cleanup_empty_dirs(file_path.parent, user_root)

    db.session.delete(asset)
    db.session.commit()
    flash("The file has been released back to the earth.", "info")

    current_folder = request.form.get("current_folder_id", type=int)
    return redirect(url_for("files.index", folder=current_folder))


@files_bp.route("/shared/<token>", methods=["GET"])
def shared_download(token: str):
    asset = FileAsset.query.filter_by(share_token=token).first_or_404()
    file_path = _asset_path(asset)
    if not file_path.exists():
        abort(404)

    return send_from_directory(
        file_path.parent,
        file_path.name,
        as_attachment=True,
        download_name=asset.original_name,
        mimetype=asset.mime_type,
    )
