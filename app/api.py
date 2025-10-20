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
