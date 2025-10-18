from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional
from time import perf_counter

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover - optional dependency
    Llama = None  # type: ignore[misc]  # pragma: no cover


class LLMError(RuntimeError):
    """Base exception for local model issues."""


class ModelNotConfiguredError(LLMError):
    """Requested model name is not present in the registry."""


class ModelLoadError(LLMError):
    """A configured model could not be loaded."""


class InferenceError(LLMError):
    """A model failed while generating output."""


@dataclass
class ModelSettings:
    """Normalised settings for a configured model."""

    name: str
    path: str
    system_prompt: str
    context_window: int
    temperature: float
    max_tokens: int
    stop_sequences: Optional[List[str]] = None
    threads: Optional[int] = None
    batch_size: Optional[int] = None
    timeout: Optional[float] = None


@dataclass
class GenerationResult:
    """Structured output from a model completion."""

    text: str
    usage: Dict[str, Any]
    raw: Dict[str, Any]


class ModelManager:
    """Lazy loader and orchestrator for llama.cpp-compatible models."""

    def __init__(self, registry: Dict[str, Dict[str, Any]]):
        self._registry = {
            name: self._build_settings(name, settings)
            for name, settings in registry.items()
        }
        self._models: Dict[str, Any] = {}
        self._locks: Dict[str, Lock] = {}

    @staticmethod
    def _build_settings(name: str, data: Dict[str, Any]) -> ModelSettings:
        try:
            path = Path(data["path"]).expanduser().resolve()
        except KeyError as err:
            raise ModelNotConfiguredError(
                f"Model '{name}' is missing a 'path' entry."
            ) from err
        system_prompt = str(
            data.get(
                "system_prompt",
                "You are an attentive local assistant running inside a private workspace.",
            )
        )
        context_window = int(data.get("context_window", 2048))
        temperature = float(data.get("temperature", 0.7))
        max_tokens = int(data.get("max_tokens", 128))
        stop_sequences_raw: Iterable[str] | None = data.get("stop")
        stop_sequences = list(stop_sequences_raw) if stop_sequences_raw else None
        threads_raw = data.get("threads")
        batch_size_raw = data.get("batch_size")
        timeout_raw = data.get("timeout")

        try:
            threads = (
                max(1, int(threads_raw))
                if threads_raw is not None
                else None
            )
        except (TypeError, ValueError) as exc:
            raise ModelNotConfiguredError(
                f"Model '{name}' has invalid 'threads' setting."
            ) from exc

        try:
            batch_size = (
                max(1, int(batch_size_raw))
                if batch_size_raw is not None
                else None
            )
        except (TypeError, ValueError) as exc:
            raise ModelNotConfiguredError(
                f"Model '{name}' has invalid 'batch_size' setting."
            ) from exc

        try:
            timeout = (
                max(1.0, float(timeout_raw))
                if timeout_raw is not None
                else None
            )
        except (TypeError, ValueError) as exc:
            raise ModelNotConfiguredError(
                f"Model '{name}' has invalid 'timeout' setting."
            ) from exc

        return ModelSettings(
            name=name,
            path=str(path),
            system_prompt=system_prompt,
            context_window=context_window,
            temperature=temperature,
            max_tokens=max_tokens,
            stop_sequences=stop_sequences,
            threads=threads,
            batch_size=batch_size,
            timeout=timeout,
        )

    def available_models(self) -> List[str]:
        """Return the list of configured model keys."""
        return list(self._registry.keys())

    def describe_models(self) -> Dict[str, Dict[str, Any]]:
        """Expose metadata for API responses."""
        return {
            name: {
                "filename": Path(settings.path).name,
                "context_window": settings.context_window,
                "temperature": settings.temperature,
                "max_tokens": settings.max_tokens,
                "stop": settings.stop_sequences or [],
                "threads": settings.threads,
                "batch_size": settings.batch_size,
                "timeout": settings.timeout,
            }
            for name, settings in self._registry.items()
        }

    def generate(
        self,
        *,
        model_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[Iterable[str]] = None,
        **extra_options: Any,
    ) -> GenerationResult:
        if not prompt:
            raise ValueError("Prompt must be non-empty.")

        settings = self._registry.get(model_name)
        if settings is None:
            raise ModelNotConfiguredError(
                f"Model '{model_name}' is not configured."
            )

        llm = self._ensure_model(settings)
        logger.info(
            "Starting generation with model '%s' (%s); prompt length=%d",
            model_name,
            settings.path,
            len(prompt),
        )
        start_time = perf_counter()

        chat_messages = [
            {"role": "system", "content": system_prompt or settings.system_prompt},
            {"role": "user", "content": prompt},
        ]

        completion_kwargs: Dict[str, Any] = {
            "messages": chat_messages,
            "temperature": temperature
            if temperature is not None
            else settings.temperature,
            "max_tokens": max_tokens if max_tokens is not None else settings.max_tokens,
        }

        stop_sequences = list(stop) if stop else settings.stop_sequences
        if stop_sequences:
            completion_kwargs["stop"] = stop_sequences

        completion_kwargs.update(extra_options)

        try:
            output = llm.create_chat_completion(**completion_kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Generation failed for model '%s'", model_name)
            raise InferenceError(
                f"Model '{model_name}' failed during generation."
            ) from exc

        try:
            text = output["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError) as exc:
            logger.exception(
                "Unexpected response shape from model '%s': %s",
                model_name,
                output,
            )
            raise InferenceError(
                f"Model '{model_name}' returned malformed output."
            ) from exc
        usage = output.get("usage", {})
        duration = perf_counter() - start_time
        logger.info(
            "Completed generation with model '%s' in %.2fs; usage=%s",
            model_name,
            duration,
            usage or {},
        )
        return GenerationResult(text=text, usage=usage, raw=output)

    def _ensure_model(self, settings: ModelSettings):
        cached = self._models.get(settings.name)
        if cached is not None:
            return cached

        lock = self._locks.setdefault(settings.name, Lock())
        with lock:
            cached = self._models.get(settings.name)
            if cached is not None:
                return cached

            if Llama is None:
                raise ModelLoadError(
                    "llama_cpp is not installed. Install llama-cpp-python to enable local inference."
                )

            model_path = Path(settings.path)
            if not model_path.exists():
                raise ModelLoadError(
                    f"Model file for '{settings.name}' not found at {settings.path}"
                )

            try:
                llm_kwargs: Dict[str, Any] = {
                    "model_path": str(model_path),
                    "n_ctx": settings.context_window,
                    "logits_all": False,
                    "verbose": False,
                }
                if settings.threads:
                    llm_kwargs["n_threads"] = settings.threads
                if settings.batch_size:
                    llm_kwargs["n_batch"] = settings.batch_size

                llm = Llama(**llm_kwargs)
                logger.info(
                    "Loaded model '%s' from %s (threads=%s, batch=%s)",
                    settings.name,
                    settings.path,
                    settings.threads,
                    settings.batch_size,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception(
                    "Failed to load model '%s' from %s",
                    settings.name,
                    settings.path,
                )
                raise ModelLoadError(
                    f"Could not load model '{settings.name}'."
                ) from exc

            self._models[settings.name] = llm
            return llm


def get_model_manager(app) -> ModelManager:
    """Retrieve or create the model manager for a Flask app instance."""
    manager: ModelManager | None = app.extensions.get("llm_manager")  # type: ignore[assignment]
    if manager is None:
        registry = app.config.get("AI_MODEL_REGISTRY", {})
        manager = ModelManager(registry)
        app.extensions["llm_manager"] = manager
    return manager
