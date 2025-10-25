import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import inspect

from flask import Flask, flash, redirect, request, url_for
from flask_login import current_user, logout_user
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from .config import Config
from .database import db
from .extensions import login_manager, sock
from .neod import init_neod_service


def _configure_logging(app: Flask) -> None:
    if any(isinstance(handler, RotatingFileHandler) for handler in app.logger.handlers):
        return

    log_dir = Path(app.config.get("LOG_ROOT", Path(app.root_path).parent / "logs")).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "application.log"

    handler = RotatingFileHandler(log_file, maxBytes=1_048_576, backupCount=5)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)

    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Logging initialized. Writing to %s", log_file)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    _configure_logging(app)

    storage_root = Path(app.config["STORAGE_ROOT"]).expanduser()
    storage_root.mkdir(parents=True, exist_ok=True)
    app.config["STORAGE_ROOT"] = str(storage_root.resolve())

    db.init_app(app)
    login_manager.init_app(app)
    sock.init_app(app)

    app.wsgi_app = ProxyFix(  # type: ignore[assignment]
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_port=1,
        x_prefix=1,
    )

    with app.app_context():
        from . import models  # noqa: F401
        inspector = inspect(db.engine)
        tables_before = set(inspector.get_table_names())

        db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
        app.logger.info("Database URI: %s", db_uri)
        if db_uri.startswith("sqlite:///"):
            db_path = Path(db_uri.replace("sqlite:///", "", 1))
            try:
                if db_path.exists():
                    app.logger.info("Database file located at %s (size: %s bytes)", db_path, db_path.stat().st_size)
                else:
                    app.logger.warning("Expected SQLite database file %s does not exist; it will be created.", db_path)
            except OSError:
                app.logger.exception("Unable to inspect database file %s", db_path)

        if not tables_before:
            app.logger.warning("Database reported no tables prior to initialization. This often indicates a fresh or reset database.")

        db.create_all()
        models.ensure_file_schema()
        models.ensure_user_schema()
        models.ensure_circle_schema()
        models.ensure_chat_schema()

        tables_after = set(inspect(db.engine).get_table_names())
        app.logger.info("Database tables present after initialization: %s", sorted(tables_after))

        try:
            user_count = db.session.execute(sa.select(sa.func.count()).select_from(models.User)).scalar_one()
            file_count = db.session.execute(sa.select(sa.func.count()).select_from(models.FileAsset)).scalar_one()
            folder_count = db.session.execute(sa.select(sa.func.count()).select_from(models.FileFolder)).scalar_one()
            app.logger.info(
                "Database counts — users: %s, file assets: %s, folders: %s",
                user_count,
                file_count,
                folder_count,
            )
        except Exception:
            app.logger.exception("Failed to collect database metrics during startup.")

        try:
            models.ensure_admin_user()
        except Exception:
            app.logger.exception("Failed to ensure arch administrator account.")

        try:
            from .chat import ensure_archdruid_user

            ensure_archdruid_user()
        except Exception:
            app.logger.exception("Failed to ensure archdruid chat account.")

        neod_service = init_neod_service(app)
        if neod_service:
            try:
                neod_service.bootstrap()
            except Exception:
                app.logger.exception("Failed to bootstrap NEOD token service.")

    from .site_settings import get_site_settings

    @app.context_processor
    def inject_site_settings():
        return {"site_settings": get_site_settings()}

    @app.before_request
    def enforce_membership_state():
        if not current_user.is_authenticated:
            return None
        changed = False
        if current_user.lift_suspension_if_expired():
            changed = True
        if current_user.status == "suspended":
            if changed:
                db.session.add(current_user)
                db.session.commit()
            until = current_user.suspended_until
            logout_user()
            if until:
                flash(
                    "Your membership is suspended until {} UTC.".format(
                        until.strftime("%Y-%m-%d %H:%M")
                    ),
                    "danger",
                )
            else:
                flash("Your membership is suspended. Await the arch's decision.", "danger")
            if request.endpoint != "auth.login":
                return redirect(url_for("auth.login"))
            return None
        now = datetime.utcnow()
        if current_user.last_seen is None or (now - current_user.last_seen).total_seconds() > 60:
            current_user.last_seen = now
            changed = True
        if changed:
            db.session.add(current_user)
            db.session.commit()
        return None

    from .auth import auth_bp
    from .files import files_bp
    from .social import social_bp
    from .ai import ai_bp
    from .api import api_bp, legacy_api_bp
    from .kyber_api import kyber_api_bp
    from .neod_views import neod_bp
    from .arch import arch_bp
    from .chat import chat_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(social_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(legacy_api_bp)
    app.register_blueprint(kyber_api_bp)
    app.register_blueprint(neod_bp)
    app.register_blueprint(arch_bp)
    app.register_blueprint(chat_bp)

    return app
