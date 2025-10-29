from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Optional

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

from .llm import (
    InferenceError,
    ModelLoadError,
    ModelNotConfiguredError,
    get_model_manager,
)

logger = logging.getLogger(__name__)

ai_bp = Blueprint("ai", __name__, url_prefix="/ai")
_generation_pool = ThreadPoolExecutor(max_workers=2)

# OpenAI client (lazy loaded)
_openai_client = None


def _fallback_insight(prompt: str) -> str:
    ritual_focus = "steady rhythm of the seasons"
    if "ritual" in prompt.lower():
        ritual_focus = "dawn-lit grove with cedar smoke curling skyward"
    logger.warning("Using fallback insight for prompt length %d", len(prompt))
    return (
        "I am Archdruid Eldara listening beside you. "
        f"Gather the circle with intention, honor the {ritual_focus}, "
        "and let every voice be welcomed into our living grove."
    )


def _model_insight(prompt: str) -> str:
    app = current_app._get_current_object()
    manager = get_model_manager(app)
    model_name = app.config.get("AI_DEFAULT_MODEL", "archdruid")
    registry = app.config.get("AI_MODEL_REGISTRY", {})
    system_prompt = registry.get(model_name, {}).get("system_prompt")
    timeout_override = registry.get(model_name, {}).get("timeout")
    timeout_seconds = (
        float(timeout_override)
        if timeout_override is not None
        else float(app.config.get("AI_GENERATION_TIMEOUT", 45))
    )

    future = _generation_pool.submit(
        manager.generate,
        model_name=model_name,
        prompt=prompt,
        system_prompt=system_prompt,
    )

    try:
        result = future.result(timeout=timeout_seconds)
        return result.text
    except TimeoutError:
        future.cancel()
        logger.error(
            "Generation timed out after %.1f seconds for model '%s'",
            timeout_seconds,
            model_name,
        )
        return _fallback_insight(prompt)
    except ModelNotConfiguredError as exc:
        logger.error("Model configuration error: %s", exc)
        return _fallback_insight(prompt)
    except ModelLoadError as exc:
        logger.error("Local model load failed: %s", exc)
        return _fallback_insight(prompt)
    except InferenceError as exc:
        logger.error("Local model generation failed: %s", exc)
        return _fallback_insight(prompt)


@ai_bp.route("/insight", methods=["POST"])
@login_required
def insight():
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "Prompt required."}), 400

    guidance = _model_insight(prompt)
    return jsonify({"insight": guidance})
