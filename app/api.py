from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

from flask import Blueprint, current_app, jsonify, request

from .llm import (
    InferenceError,
    ModelLoadError,
    ModelNotConfiguredError,
    get_model_manager,
)
from .neod import (
    PaymentAlreadyProcessed,
    PaymentNotFound,
    PaymentVerificationError,
    RecipientAccountError,
    SolanaNetworkError,
    ServiceConfigurationError,
    get_neod_service,
)

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")
legacy_api_bp = Blueprint("api_legacy", __name__, url_prefix="/api")


def _enforce_api_key():
    allowed_keys = current_app.config.get("AI_API_KEYS", set())
    if not allowed_keys:
        return None

    supplied = request.headers.get("X-API-Key")
    if supplied in allowed_keys:
        return None

    logger.warning("Rejected API request with missing or invalid API key.")
    return jsonify({"error": "Unauthorized"}), 401


def _normalise_stop_sequences(raw_stop: Any) -> Optional[Iterable[str]]:
    if raw_stop is None:
        return None
    if isinstance(raw_stop, str):
        return [raw_stop]
    if isinstance(raw_stop, (list, tuple)):
        return [str(item) for item in raw_stop if item]
    return None


def _extract_extra_options(payload: Dict[str, Any]) -> Dict[str, Any]:
    extra: Dict[str, Any] = {}
    options = payload.get("options")
    if isinstance(options, dict):
        for key in ("top_p", "repeat_penalty", "presence_penalty", "frequency_penalty"):
            if key in options:
                extra[key] = options[key]
    return extra


@api_bp.route("/models", methods=["GET"])
def list_models():
    api_guard = _enforce_api_key()
    if api_guard:
        return api_guard

    app = current_app._get_current_object()
    manager = get_model_manager(app)
    return jsonify(
        {
            "default": current_app.config.get("AI_DEFAULT_MODEL"),
            "models": manager.describe_models(),
        }
    )


@api_bp.route("/generate", methods=["POST"])
def generate_text():
    api_guard = _enforce_api_key()
    if api_guard:
        return api_guard

    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"error": "Prompt required"}), 400

    model_name = str(
        payload.get(
            "model", current_app.config.get("AI_DEFAULT_MODEL", "archdruid")
        )
    ).strip()

    if not model_name:
        return jsonify({"error": "No model configured"}), 503

    temperature = payload.get("temperature")
    max_tokens = payload.get("max_tokens")
    system_prompt = payload.get("system_prompt")
    stop_sequences = _normalise_stop_sequences(payload.get("stop"))
    extra_options = _extract_extra_options(payload)

    app = current_app._get_current_object()
    manager = get_model_manager(app)
    try:
        result = manager.generate(
            model_name=model_name,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop_sequences,
            **extra_options,
        )
    except ModelNotConfiguredError:
        return jsonify({"error": f"Unknown model '{model_name}'"}), 404
    except ModelLoadError as exc:
        logger.error("Model '%s' failed to load: %s", model_name, exc)
        return jsonify({"error": "Model not available"}), 503
    except InferenceError as exc:
        logger.error("Generation failure for '%s': %s", model_name, exc)
        return jsonify({"error": "Generation failed"}), 500

    return jsonify(
        {
            "model": model_name,
            "completion": result.text,
            "usage": result.usage,
        }
    )


@api_bp.route("/neod/info", methods=["GET"])
def neod_info():
    try:
        service = get_neod_service()
    except ServiceConfigurationError as exc:
        return jsonify({"error": str(exc)}), 503

    try:
        details = service.describe()
    except ServiceConfigurationError as exc:
        return jsonify({"error": str(exc)}), 503
    return jsonify({"status": "ok", "neod": details})


@api_bp.route("/neod/blockhash", methods=["GET"])
def neod_blockhash():
    try:
        service = get_neod_service()
    except ServiceConfigurationError as exc:
        return jsonify({"error": str(exc)}), 503

    def extract(response: Dict[str, Any]):
        result = response.get("result") if isinstance(response, dict) else None
        value = result.get("value") if isinstance(result, dict) else None
        context = result.get("context") if isinstance(result, dict) else None
        blockhash = value.get("blockhash") if isinstance(value, dict) else None
        last_valid = value.get("lastValidBlockHeight") if isinstance(value, dict) else None
        slot = context.get("slot") if isinstance(context, dict) else None
        lamports_per_signature = None
        if isinstance(value, dict):
            fee_calculator = value.get("feeCalculator")
            if isinstance(fee_calculator, dict):
                lamports_per_signature = fee_calculator.get("lamportsPerSignature")
        return blockhash, last_valid, slot, lamports_per_signature

    try:
        latest_response = service.client.get_latest_blockhash(commitment=service.commitment)
        blockhash, last_valid, slot, _ = extract(latest_response)
        if blockhash:
            return jsonify(
                {
                    "status": "ok",
                    "blockhash": blockhash,
                    "last_valid_block_height": last_valid,
                    "slot": slot,
                    "commitment": service.commitment,
                    "source": "getLatestBlockhash",
                }
            )
    except Exception as exc:
        service.logger.warning("Primary blockhash fetch failed: %s", exc, exc_info=True)

    try:
        recent_response = service.client.get_recent_blockhash(commitment=service.commitment)
        blockhash, _, slot, lamports_per_signature = extract(recent_response)
        if blockhash:
            return jsonify(
                {
                    "status": "ok",
                    "blockhash": blockhash,
                    "last_valid_block_height": None,
                    "slot": slot,
                    "commitment": service.commitment,
                    "source": "getRecentBlockhash",
                    "lamports_per_signature": lamports_per_signature,
                }
            )
    except Exception as exc:
        service.logger.error("Fallback blockhash fetch failed: %s", exc, exc_info=True)
        return jsonify({"error": "Unable to fetch blockhash", "details": str(exc)}), 503

    return jsonify({"error": "Blockhash unavailable"}), 503


@api_bp.route("/neod/purchase", methods=["POST"])
def neod_purchase():
    try:
        service = get_neod_service()
    except ServiceConfigurationError as exc:
        return jsonify({"error": str(exc)}), 503

    payload = request.get_json(silent=True) or {}
    signature = str(payload.get("signature", "")).strip()
    recipient = str(payload.get("recipient", "")).strip()

    if not signature or not recipient:
        return jsonify({"error": "signature and recipient fields are required."}), 400

    try:
        record = service.fulfill_purchase(signature, recipient)
    except PaymentAlreadyProcessed as exc:
        return jsonify({"error": str(exc)}), 409
    except PaymentNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except PaymentVerificationError as exc:
        return jsonify({"error": str(exc)}), 400
    except RecipientAccountError as exc:
        return jsonify({"error": str(exc)}), 422
    except SolanaNetworkError as exc:
        return jsonify({"error": str(exc)}), 503
    except ServiceConfigurationError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception:
        service.logger.exception("Failed to fulfil NEOD purchase for signature %s", signature)
        return jsonify({"error": "Failed to dispense NEOD; please try again later."}), 502

    response = {
        "status": "ok",
        "neod_transfer_signature": record.neod_transfer_signature,
        "recipient": record.recipient_address,
        "payer": record.payer_address,
        "sol_lamports": record.sol_lamports,
        "tokens": record.neod_amount,
        "slot": record.slot,
    }
    return jsonify(response), 201


@legacy_api_bp.route("/neod/info", methods=["GET"])
def neod_info_legacy():
    return neod_info()


@legacy_api_bp.route("/neod/purchase", methods=["POST"])
def neod_purchase_legacy():
    return neod_purchase()


@api_bp.route("/solana/rpc", methods=["POST"])
def solana_rpc_proxy():
    """Proxy Solana RPC requests to avoid CORS and 403 issues from browser."""
    # No API key required for RPC proxy - it's used by the frontend
    payload = request.get_json(silent=True) or {}

    # Always use the public fallback RPC for browser requests to avoid auth issues
    rpc_url = "https://api.mainnet-beta.solana.com"

    try:
        import requests
        response = requests.post(
            rpc_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        return jsonify(response.json()), response.status_code
    except Exception as exc:
        logger.error("RPC proxy error: %s", exc)
        return jsonify({"error": "RPC unavailable", "details": str(exc)}), 503


@api_bp.route("/giphy/search", methods=["GET"])
def giphy_search():
    """Search GIPHY for GIFs."""
    giphy_key = current_app.config.get("GIPHY_API_KEY")
    if not giphy_key:
        return jsonify({"error": "GIPHY not configured"}), 503

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' required"}), 400

    limit = min(int(request.args.get("limit", "20")), 50)

    try:
        import requests
        response = requests.get(
            "https://api.giphy.com/v1/gifs/search",
            params={
                "api_key": giphy_key,
                "q": query,
                "limit": limit,
                "rating": "g",
                "lang": "en"
            },
            timeout=10
        )

        if response.status_code != 200:
            logger.error("GIPHY API error: %s", response.text)
            return jsonify({"error": "GIPHY search failed"}), 503

        data = response.json()
        gifs = []
        for item in data.get("data", []):
            gifs.append({
                "id": item.get("id"),
                "url": item.get("images", {}).get("fixed_height", {}).get("url"),
                "preview_url": item.get("images", {}).get("fixed_height_small", {}).get("url"),
                "title": item.get("title", ""),
                "width": item.get("images", {}).get("fixed_height", {}).get("width"),
                "height": item.get("images", {}).get("fixed_height", {}).get("height"),
            })

        return jsonify({"gifs": gifs})

    except Exception as exc:
        logger.error("GIPHY search error: %s", exc)
        return jsonify({"error": "GIPHY unavailable"}), 503


@api_bp.route("/users/search", methods=["GET"])
def user_search():
    """Search for users by username."""
    from flask_login import current_user, login_required
    from .models import User

    # Check if user is logged in
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401

    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify({"error": "Query parameter 'q' required"}), 400

    limit = min(int(request.args.get("limit", "20")), 50)

    try:
        # Search for users by username (case-insensitive)
        users = (
            User.query
            .filter(User.status == "active")
            .filter(User.username.ilike(f"%{query}%"))
            .filter(User.id != current_user.id)  # Don't include current user
            .limit(limit)
            .all()
        )

        results = []
        for user in users:
            results.append({
                "id": user.id,
                "username": user.username,
                "has_chat_keys": user.has_chat_keys,
                "circle": {
                    "id": user.circle.id,
                    "name": user.circle.name
                } if user.circle else None
            })

        return jsonify({"users": results})

    except Exception as exc:
        logger.error("User search error: %s", exc)
        return jsonify({"error": "Search failed"}), 500
