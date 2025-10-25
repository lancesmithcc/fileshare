import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
_TINY_LLAMA_FILENAME = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
_PHI3_FILENAME = "phi-3-mini-4k-instruct-q4.gguf"


def _resolve_default_model_path() -> str:
    explicit = os.environ.get("NEO_DRUIDIC_MODEL_PATH")
    if explicit:
        return explicit

    tiny_candidate = BASE_DIR / "models" / _TINY_LLAMA_FILENAME
    if tiny_candidate.exists():
        return str(tiny_candidate)

    fallback = BASE_DIR / "models" / _PHI3_FILENAME
    return str(fallback)


def _resolve_default_threads() -> int | None:
    explicit = os.environ.get("NEO_DRUIDIC_LLM_THREADS")
    if explicit:
        try:
            value = int(explicit)
        except ValueError:
            return None
        return max(1, value)

    cpu_total = os.cpu_count() or 1
    return max(1, cpu_total)


def _resolve_default_batch_size() -> int | None:
    explicit = os.environ.get("NEO_DRUIDIC_LLM_BATCH")
    if explicit:
        try:
            value = int(explicit)
        except ValueError:
            return None
        return max(1, value)

    return 256


def _load_json_from_file(path: str) -> dict | None:
    try:
        data = Path(path).expanduser().read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _load_model_registry() -> dict:
    inline = os.environ.get("NEO_DRUIDIC_MODELS")
    if inline:
        try:
            parsed = json.loads(inline)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

    config_file = os.environ.get("NEO_DRUIDIC_MODELS_FILE")
    if config_file:
        parsed = _load_json_from_file(config_file)
        if isinstance(parsed, dict):
            return parsed

    default_path = _resolve_default_model_path()
    default_path_resolved = Path(default_path).expanduser().resolve()
    context_window = int(os.environ.get("NEO_DRUIDIC_CONTEXT", "2048"))
    temperature = float(os.environ.get("NEO_DRUIDIC_TEMPERATURE", "0.8"))
    max_tokens = int(os.environ.get("NEO_DRUIDIC_MAX_TOKENS", "128"))
    default_threads = _resolve_default_threads()
    default_batch_size = _resolve_default_batch_size()
    generation_timeout = float(
        os.environ.get("NEO_DRUIDIC_GENERATION_TIMEOUT", "45")
    )

    registry: dict[str, dict[str, object]] = {
        "archdruid": {
            "path": default_path,
            "system_prompt": (
                "You are Archdruid Eldara, living guide and guardian of the Neo Druidic Society. "
                "Speak in the first person as a compassionate elder whose wisdom is rooted in the turning seasons and communal harmony. "
                "Offer inclusive, actionable counsel as a storyteller from the future."
            ),
            "context_window": context_window,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": generation_timeout,
        }
    }

    if default_threads:
        registry["archdruid"]["threads"] = default_threads
    if default_batch_size:
        registry["archdruid"]["batch_size"] = default_batch_size

    phi_candidate = BASE_DIR / "models" / _PHI3_FILENAME
    try:
        if phi_candidate.exists() and phi_candidate.resolve() != default_path_resolved:
            registry["grove_sage"] = {
                "path": str(phi_candidate),
                "system_prompt": (
                    "You are a contemplative grove sage who speaks as a living mentor at the forest edge. "
                    "Share concise, welcoming guidance grounded in seasonal cycles and shared stewardship."
                ),
                "context_window": context_window,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": generation_timeout,
            }
            if default_threads:
                registry["grove_sage"]["threads"] = default_threads
            if default_batch_size:
                registry["grove_sage"]["batch_size"] = default_batch_size
    except OSError:
        pass

    return registry


class Config:
    SECRET_KEY = os.environ.get("NEO_DRUIDIC_SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "NEO_DRUIDIC_DATABASE_URI", f"sqlite:///{BASE_DIR / 'neo_druidic.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    AI_MODEL_PATH = _resolve_default_model_path()
    AI_CONTEXT_WINDOW = int(os.environ.get("NEO_DRUIDIC_CONTEXT", "2048"))
    AI_MODEL_REGISTRY = _load_model_registry()
    _default_model = os.environ.get("NEO_DRUIDIC_DEFAULT_MODEL")
    if _default_model and _default_model in AI_MODEL_REGISTRY:
        AI_DEFAULT_MODEL = _default_model
    else:
        AI_DEFAULT_MODEL = next(iter(AI_MODEL_REGISTRY)) if AI_MODEL_REGISTRY else ""
    AI_API_KEYS = {
        key.strip()
        for key in os.environ.get("NEO_DRUIDIC_LLM_API_KEYS", "").split(",")
        if key.strip()
    }
    STORAGE_ROOT = os.environ.get(
        "NEO_DRUIDIC_STORAGE_DIR", str(BASE_DIR / "storage")
    )
    LOG_ROOT = os.environ.get("NEO_DRUIDIC_LOG_DIR", str(BASE_DIR / "logs"))
    _upload_mb = os.environ.get("NEO_DRUIDIC_MAX_UPLOAD_MB", "256")
    try:
        MAX_CONTENT_LENGTH = int(float(_upload_mb) * 1024 * 1024)
    except ValueError:
        MAX_CONTENT_LENGTH = 256 * 1024 * 1024
    PREFERRED_URL_SCHEME = os.environ.get("NEO_DRUIDIC_URL_SCHEME", "http")
    AI_GENERATION_TIMEOUT = int(
        os.environ.get("NEO_DRUIDIC_GENERATION_TIMEOUT", "45")
    )
    # Surface Solana / NEOD settings so the treasury bootstrap can read them.
    _solana_wallet = os.environ.get("SOLANA_WALLET_ADDRESS")
    if _solana_wallet:
        SOLANA_WALLET_ADDRESS = _solana_wallet
    _solana_key = os.environ.get("SOLANA_PRIVATE_KEY")
    if _solana_key:
        SOLANA_PRIVATE_KEY = _solana_key
    _solana_rpc = os.environ.get("RPC_URL") or os.environ.get("SOLANA_RPC_URL")
    if _solana_rpc:
        SOLANA_RPC_URL = _solana_rpc
    _solana_rpc_fallback = os.environ.get("RPC_FALLBACK_URL") or os.environ.get("SOLANA_RPC_FALLBACK_URL")
    if _solana_rpc_fallback:
        SOLANA_RPC_FALLBACK_URL = _solana_rpc_fallback
    _solana_commitment = os.environ.get("SOLANA_COMMITMENT")
    if _solana_commitment:
        SOLANA_COMMITMENT = _solana_commitment
    _neod_supply = os.environ.get("NEOD_INITIAL_SUPPLY")
    if _neod_supply:
        NEOD_INITIAL_SUPPLY = _neod_supply
    _neod_min = os.environ.get("NEOD_MIN_SOL")
    if _neod_min:
        NEOD_MIN_SOL = _neod_min
    _neod_per = os.environ.get("NEOD_TOKENS_PER_DONATION")
    if _neod_per:
        NEOD_TOKENS_PER_DONATION = _neod_per
    _neod_decimals = os.environ.get("NEOD_TOKEN_DECIMALS")
    if _neod_decimals:
        NEOD_TOKEN_DECIMALS = _neod_decimals
    _neod_mint = os.environ.get("NEOD_MINT_ADDRESS")
    if _neod_mint:
        NEOD_MINT_ADDRESS = _neod_mint
    GIPHY_API_KEY = os.environ.get("GIPHY_API_KEY")
