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
from .rag import build_rag_context

logger = logging.getLogger(__name__)

ai_bp = Blueprint("ai", __name__, url_prefix="/ai")
_generation_pool = ThreadPoolExecutor(max_workers=2)

# OpenAI client (lazy loaded)
_openai_client = None


def _get_openai_client():
    """Get or create OpenAI client (lazy initialization)."""
    global _openai_client
    if _openai_client is None:
        import openai
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        _openai_client = openai.OpenAI(api_key=api_key)
    return _openai_client


def _openai_insight(prompt: str, system_prompt: Optional[str] = None, use_rag: bool = True) -> tuple[str, list[dict]]:
    """Generate insight using OpenAI API (fast and reliable) with optional RAG context."""
    try:
        client = _get_openai_client()

        # Build RAG context if enabled
        rag_context = ""
        sources = []
        if use_rag:
            try:
                rag_context, sources = build_rag_context(prompt, top_k=3)
                if rag_context:
                    logger.info("Added RAG context from Knowledge Garden (%d chars, %d sources)", len(rag_context), len(sources))
            except Exception as rag_exc:
                logger.warning("Failed to get RAG context: %s", rag_exc)

        # Build the user message with RAG context
        user_message = prompt
        if rag_context:
            user_message = f"{rag_context}\nUser question: {prompt}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        logger.info("Calling OpenAI API with %d message(s) (RAG: %s)", len(messages), bool(rag_context))

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )

        insight_text = response.choices[0].message.content
        logger.info("OpenAI API returned %d chars", len(insight_text))
        return insight_text, sources

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("OpenAI API failed: %s", exc)
        raise


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


def _model_insight(prompt: str) -> tuple[str, list[dict]]:
    """Generate insight using best available AI model with RAG context."""
    app = current_app._get_current_object()
    use_openai = app.config.get("AI_USE_OPENAI", True)
    use_rag = app.config.get("RAG_ENABLED", True)

    # Try OpenAI first (fast and reliable)
    if use_openai and os.environ.get("OPENAI_API_KEY"):
        try:
            registry = app.config.get("AI_MODEL_REGISTRY", {})
            model_name = app.config.get("AI_DEFAULT_MODEL", "archdruid")
            system_prompt = registry.get(model_name, {}).get("system_prompt")

            logger.info("Using OpenAI API for insight generation (RAG: %s)", use_rag)
            return _openai_insight(prompt, system_prompt, use_rag=use_rag)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("OpenAI failed, falling back to local model: %s", exc)

    # Fall back to local model (no RAG support)
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

    logger.info("Using local model '%s' for insight generation", model_name)
    future = _generation_pool.submit(
        manager.generate,
        model_name=model_name,
        prompt=prompt,
        system_prompt=system_prompt,
    )

    try:
        result = future.result(timeout=timeout_seconds)
        return result.text, []
    except TimeoutError:
        future.cancel()
        logger.error(
            "Generation timed out after %.1f seconds for model '%s'",
            timeout_seconds,
            model_name,
        )
        return _fallback_insight(prompt), []
    except ModelNotConfiguredError as exc:
        logger.error("Model configuration error: %s", exc)
        return _fallback_insight(prompt), []
    except ModelLoadError as exc:
        logger.error("Local model load failed: %s", exc)
        return _fallback_insight(prompt), []
    except InferenceError as exc:
        logger.error("Local model generation failed: %s", exc)
        return _fallback_insight(prompt), []


@ai_bp.route("/insight", methods=["POST"])
@login_required
def insight():
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "Prompt required."}), 400

    guidance, sources = _model_insight(prompt)
    return jsonify({
        "insight": guidance,
        "sources": sources
    })


@ai_bp.route("/index-files", methods=["POST"])
@login_required
def index_files():
    """Index all files in Knowledge Garden for RAG."""
    from .rag import index_all_files

    try:
        data = request.get_json(silent=True) or {}
        folder_id = data.get("folder_id")  # Optional: index specific folder

        logger.info("Starting file indexing (folder_id=%s)", folder_id)
        stats = index_all_files(folder_id=folder_id)

        return jsonify({
            "success": True,
            "stats": stats,
            "message": f"Indexed {stats['indexed']} files, {stats['skipped']} skipped, {stats['failed']} failed"
        })

    except Exception as exc:
        logger.error("File indexing failed: %s", exc)
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500


@ai_bp.route("/rag-status", methods=["GET"])
@login_required
def rag_status():
    """Get RAG system status."""
    from .models import DocumentEmbedding, FileAsset

    try:
        total_files = FileAsset.query.count()
        total_embeddings = DocumentEmbedding.query.count()
        indexed_files = DocumentEmbedding.query.with_entities(
            DocumentEmbedding.file_asset_id
        ).distinct().count()

        app = current_app._get_current_object()

        return jsonify({
            "enabled": app.config.get("RAG_ENABLED", False),
            "total_files": total_files,
            "indexed_files": indexed_files,
            "total_chunks": total_embeddings,
            "config": {
                "top_k": app.config.get("RAG_TOP_K", 3),
                "chunk_size": app.config.get("RAG_CHUNK_SIZE", 512),
                "chunk_overlap": app.config.get("RAG_CHUNK_OVERLAP", 128),
            }
        })

    except Exception as exc:
        logger.error("Failed to get RAG status: %s", exc)
        return jsonify({"error": str(exc)}), 500
