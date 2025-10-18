from __future__ import annotations

from flask import Blueprint, current_app, render_template
from flask_login import login_required

from .models import NeodPurchase
from .neod import ServiceConfigurationError, get_neod_service

neod_bp = Blueprint("neod", __name__, url_prefix="/neod")


@neod_bp.route("/", methods=["GET"])
@login_required
def donate():
    service = None
    info = None
    service_error = None
    try:
        service = get_neod_service()
        info = service.describe()
    except ServiceConfigurationError as exc:
        service_error = str(exc)
    except Exception:
        current_app.logger.exception("Failed to load NEOD service metadata.")
        service_error = "NEOD is temporarily unavailable."

    purchases = (
        NeodPurchase.query.order_by(NeodPurchase.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "neod/index.html",
        info=info,
        service_error=service_error,
        purchases=purchases,
    )
