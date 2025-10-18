# Neo Druidic Society Platform

A small community hub for the Neo Druidic Society. Members can join circles, share reflections in the communal stream, comment on one another's posts, and consult a **local-only archdruid AI** for ritual inspiration.

## Features
- Member registration, login, and profile pages with optional grove/circle affiliation.
- Gathering Stream for posting updates, ritual ideas, and commenting.
- Circle directory for quick visibility into active groups.
- AI Archdruid panel that runs against a local `llama.cpp`-compatible model to keep every inference private and offline.
- API-ready LLM access (`/api/v1`) with pluggable model registry and optional API keys.
- Shared Hollow file space for uploading, downloading, and sharing files across your local network.

## Tech Stack
- Python 3.10, Flask, SQLAlchemy, Flask-Login.
- SQLite for storage (default) — easy to swap for Postgres/MySQL via config.
- HTMX-free HTML forms with a light fetch helper for AI calls.
- Vanilla CSS/JS for a minimal dependency footprint.

## Getting Started

1. **Create and activate a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment (optional)**
   ```bash
   export FLASK_APP=main.py
   export FLASK_ENV=development  # enables auto-reload
   export NEO_DRUIDIC_SECRET_KEY="replace-with-long-random-string"
   export NEO_DRUIDIC_DATABASE_URI="sqlite:///neo_druidic.db"
   export NEO_DRUIDIC_STORAGE_DIR="/path/to/local/storage"
   export NEO_DRUIDIC_MAX_UPLOAD_MB="256"
   export NEO_DRUIDIC_URL_SCHEME="https"  # if running behind TLS-terminating proxy
   export NEO_DRUIDIC_MAX_TOKENS="128"  # tighter completions for quicker archdruid replies
   export NEO_DRUIDIC_LLM_THREADS="6"  # optional override; defaults to all detected CPU cores
   export NEO_DRUIDIC_LLM_BATCH="512"  # optional override for llama.cpp batch size (defaults to 256)
   export NEO_DRUIDIC_GENERATION_TIMEOUT="45"  # seconds before the archdruid falls back to a stock blessing
   export NEO_DRUIDIC_MODEL_PATH="/absolute/path/to/model.gguf"  # default for the registry
   export NEO_DRUIDIC_DEFAULT_MODEL="archdruid"
   export NEO_DRUIDIC_LLM_API_KEYS="comma,separated,keys"  # optional API key auth for /api/v1
   export NEO_DRUIDIC_MODELS_FILE="/absolute/path/to/model-registry.json"  # optional JSON registry
   export SOLANA_WALLET_ADDRESS="Base58AddressFromKeypair"
   export SOLANA_PRIVATE_KEY="[38,12,...]"  # JSON array or base58-encoded secret key
   export SOLANA_RPC_URL="https://api.mainnet-beta.solana.com"  # optional override
   export NEOD_INITIAL_SUPPLY="144000000"
   export NEOD_MIN_SOL="0.005"
   export NEOD_TOKENS_PER_DONATION="1"
   export NEOD_TOKEN_DECIMALS="0"
   export NEOD_MINT_ADDRESS=""  # optional: reuse an existing NEOD mint
   export SOLANA_COMMITMENT="confirmed"
 ```

4. **Initialize the app**
   ```bash
   flask run
   ```
   The site will be reachable at http://127.0.0.1:5000.

## Fonts

The interface now self-hosts the [Jost](https://fonts.google.com/specimen/Jost) variable typeface so it renders consistently on Linux (Chromium), macOS, and Windows – even when external font CDNs are blocked. Grab the asset once:

```bash
./scripts/download_fonts.sh
```

The script saves `Jost-VariableFont_wght.ttf` to `app/static/fonts/`; restart the dev server (or let the reloader pick it up) and you’re set.

## Local AI Setup

The Archdruid assistant and external API both speak to [llama.cpp](https://github.com/ggerganov/llama.cpp)-compatible GGUF models. The default Persona now targets **TinyLlama 1.1B Chat (Q4\_K\_M)** — light enough (~620 MB) for quick inference on most CPUs. A richer Phi-3 Mini build remains optional if you want a larger context and higher quality.

1. Fetch the TinyLlama artifact with the helper script (or place it manually):  
   `./scripts/download_tinyllama.sh`
2. (Optional) Drop in `neo-druidic-society/models/phi-3-mini-4k-instruct-q4.gguf` if you want the larger Phi-3 model available alongside TinyLlama.
3. Install `llama-cpp-python` for your CPU:
   ```bash
   pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/linux
   ```
   Offline installs work too — copy a compatible wheel and `pip install ./llama_cpp_python-*.whl`.
4. Start the Flask app with the usual environment variables. If TinyLlama is present it becomes the default `archdruid` persona; Phi-3 (when available) is registered as `grove_sage`.

The built-in archdruid persona speaks as Archdruid Eldara living, compassionate 
reader  offers first-person guidance grounded in seasonal rhythms and inclusive community care. Override `system_prompt` in the registry if you want to fine-tune the voice further.

If the model cannot be reached, the application drops back to a stock ritual message so the UI keeps working.

### Model Registry

The service now supports multiple local models through a JSON registry. Provide it inline or via file:

- `NEO_DRUIDIC_MODELS='{"archdruid":{"path":"/home/bodhi/neo-druidic-society/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf","context_window":4096,"temperature":0.8,"max_tokens":128,"threads":6,"system_prompt":"...custom tone..."}}'`
- or `NEO_DRUIDIC_MODELS_FILE=/home/bodhi/neo-druidic-society/models/registry.json`

Each entry accepts:

| key | purpose |
| --- | ------- |
| `path` | Absolute/`~` path to the GGUF file |
| `system_prompt` | Default system role text |
| `context_window` | llama.cpp context window (`n_ctx`) |
| `temperature` | Default sampling temperature |
| `max_tokens` | Maximum response tokens |
| `stop` | Optional list of stop sequences |
| `threads` | Optional explicit llama.cpp worker thread count |
| `batch_size` | Optional llama.cpp batch size (`n_batch`) |
| `timeout` | Optional per-model override (seconds) before timing out |

Set `NEO_DRUIDIC_DEFAULT_MODEL` to pick the default for the web UI; `/api/v1/generate` can target any configured key.

## NEOD Utility Token

The platform can mint and manage the NEOD utility coin directly on Solana mainnet-beta. Provide the treasury wallet’s public address and secret key through `SOLANA_WALLET_ADDRESS` / `SOLANA_PRIVATE_KEY` (the key can be a JSON array exported by `solana-keygen` or a base58 string). On startup the app will:

- create a fresh mint (unless `NEOD_MINT_ADDRESS` already points to an existing NEOD SPL token),
- publish an initial supply of `NEOD_INITIAL_SUPPLY` tokens (defaults to 144 000 000) into the treasury’s associated account, and
- expose API helpers for honouring 0.005 SOL donations with a 1 NEOD airdrop (`NEOD_MIN_SOL`, `NEOD_TOKENS_PER_DONATION`).
- surface a Phantom wallet flow on `/neod/` so supporters can connect, send the 0.005 SOL donation, and auto-fill the confirmation form with their transaction signature.

Endpoints under `/api/v1/neod` allow the frontend (or other services) to query the mint configuration and redeem SOL payment signatures for NEOD transfers. Each redemption verifies the on-chain SOL deposit before streaming NEOD to the donor’s associated token account.

## LLM API

A lightweight `/api/v1` namespace exposes the local models to other services.

- `GET /api/v1/models` — lists configured model keys plus metadata, honouring any API key requirement.
- `POST /api/v1/generate` — runs a completion. Body fields:
  - `model` (optional) — defaults to `NEO_DRUIDIC_DEFAULT_MODEL`.
  - `prompt` (required) — user content.
  - `system_prompt`, `temperature`, `max_tokens`, `stop` (string or list) to override registry defaults.
  - `options` (optional dict) — currently passes through `top_p`, `repeat_penalty`, `presence_penalty`, `frequency_penalty`.

Protect the API by setting `NEO_DRUIDIC_LLM_API_KEYS` to a comma-separated list. Clients send one of those values in `X-API-Key`.

Example request:

```bash
curl -X POST http://127.0.0.1:5000/api/v1/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: super-secret" \
  -d '{
    "model": "archdruid",
    "prompt": "Share sunrise ritual guidance for a small grove.",
    "temperature": 0.7,
    "max_tokens": 200
  }'
```

### Publishing the API at `llm.lancesmith.cc`

Reuse the Cloudflare Tunnel approach outlined below but target a new hostname:

1. Create a separate tunnel, e.g. `cloudflared tunnel create llm`.
2. Configure `~/.cloudflared/config-llm.yml`:
   ```yaml
   tunnel: llm
   credentials-file: /home/bodhi/.cloudflared/<llm-tunnel-id>.json

   ingress:
     - hostname: llm.lancesmith.cc
       service: http://localhost:9000
     - service: http_status:404
   ```
3. Map `llm` as a CNAME in Cloudflare's DNS tab to `llm.lancesmith.cc.cdn.cloudflare.net`.
4. Run the Flask app listening on all interfaces and a dedicated port:
   ```bash
   export FLASK_RUN_HOST=0.0.0.0
   export FLASK_RUN_PORT=9000
   export NEO_DRUIDIC_URL_SCHEME=https
   flask run
   ```
5. Launch the tunnel: `cloudflared tunnel --config ~/.cloudflared/config-llm.yml run llm`.

With TLS termination handled by Cloudflare you can lock the API down behind `X-API-Key` while still serving the web UI on a different hostname/port.

## Local File Sharing

The **Shared Hollow** blueprint turns the app into a Dropbox-style file hub that only lives on your LAN.

- Files live on disk under `NEO_DRUIDIC_STORAGE_DIR` (defaults to `<project>/storage`). Everyone on your network hits the same folder, so mount it somewhere with enough space.
- `NEO_DRUIDIC_MAX_UPLOAD_MB` (default `256`) guards the maximum per-file upload size.
- Authenticated members can upload, download, rotate share links, and remove files. Share links create tokenized URLs like `http://<your-ip>:5000/files/shared/<token>` that anyone on your LAN can use without credentials.
- Removing a file deletes both the database record and the file on disk.

### Cloudflare Tunnel Hosting

To expose the Shared Hollow at `https://fileshare.lancesmith.cc` while keeping the app running locally:

1. Install the Cloudflare connector and authenticate:
   ```bash
   curl -fsSL https://developers.cloudflare.com/cloudflare-one/static/documentation/connections/cloudflared-install-linux-amd64.deb -o cloudflared.deb
   sudo dpkg -i cloudflared.deb
   cloudflared login
   ```
2. Create a tunnel and record the generated credentials file path (usually `~/.cloudflared/<tunnel-id>.json`):
   ```bash
   cloudflared tunnel create fileshare
   ```
3. Write a config file at `~/.cloudflared/config.yml`:
   ```yaml
   tunnel: fileshare
   credentials-file: /home/bodhi/.cloudflared/<tunnel-id>.json

   ingress:
     - hostname: fileshare.lancesmith.cc
       service: http://localhost:8000
     - service: http_status:404
   ```
4. Map the hostname inside Cloudflare’s dashboard: DNS → Add CNAME `fileshare` pointing to `fileshare.lancesmith.cc.cdn.cloudflare.net`.
5. Run the Flask app bound to all interfaces so cloudflared can reach it:
   ```bash
   export FLASK_RUN_HOST=0.0.0.0
   export FLASK_RUN_PORT=8000
   export NEO_DRUIDIC_URL_SCHEME=https
   flask run
   ```
6. Start the tunnel:
   ```bash
   cloudflared tunnel run fileshare
   ```

Cloudflare terminates TLS, forwards the real client IP via `CF-Connecting-IP`, and sends `X-Forwarded-Proto=https`. The application trusts those headers via `ProxyFix`, so share links render with the correct HTTPS root.

#### Production Notes

- The public instance at `https://fileshare.lancesmith.cc` runs through the Cloudflare tunnel described above. Keep `run_fileshare.sh` pointed at the same project root; it now sources `.env`, so the TinyLlama settings (`NEO_DRUIDIC_MODEL_PATH`, `NEO_DRUIDIC_MAX_TOKENS`, `NEO_DRUIDIC_GENERATION_TIMEOUT`) flow into the live process automatically.
- If you rotate the tunnel hostname or port, update `.env` and any supervising service (systemd, launchd, etc.) so Flask keeps binding to the expected internal port (`5000` by default).
- When troubleshooting Archdruid latency in production, tail `logs/application.log` — the manager logs both model load details and per-request timings so you can confirm TinyLlama is active behind the tunnel.

## Project Layout

```
neo-druidic-society/
├── app/
│   ├── __init__.py         # Flask app factory + blueprint registration
│   ├── ai.py               # Archdruid web UI endpoint backed by default model
│   ├── api.py              # External LLM API blueprint (/api/v1)
│   ├── auth.py             # Registration/login blueprints
│   ├── config.py           # Central configuration & defaults
│   ├── database.py         # SQLAlchemy instance
│   ├── extensions.py       # Flask-Login configuration
│   ├── llm.py              # Model manager for llama.cpp-compatible runners
│   ├── models.py           # SQLAlchemy models
│   ├── social.py           # Feed, profile, circles routes
│   ├── static/
│   │   ├── css/styles.css
│   │   └── js/insight.js
│   └── templates/
│       ├── base.html
│       ├── auth/
│       └── social/
├── main.py                 # Entry point for flask run / python main.py
└── requirements.txt
```

## Requirements

See `requirements.txt` for pinned versions. Key packages:
- `Flask`
- `Flask-Login`
- `Flask-SQLAlchemy`
- `python-dotenv` (for convenient local env loading)
- `llama-cpp-python` (optional, only required for AI insight generation)

## Database Notes

- The first run automatically creates `neo_druidic.db`.
- Use `flask shell` for manual data entry, e.g. to pre-create circles.
- Replace the SQLite URI if deploying to managed infrastructure.

## Development Tips

- Enable debug reloader with `FLASK_ENV=development`.
- Templates and static assets auto-refresh without restarting.
- To reset the database during development remove `neo_druidic.db` and restart the app.

## Roadmap Ideas

- Add media uploads via S3-compatible storage.
- Expand circles into full groups with moderation.
- Integrate calendaring for seasonal rituals.
- Federation with other small communities using ActivityPub.
