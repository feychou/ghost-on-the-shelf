# Ghost on the Shelf

Ghost on the Shelf is a lightweight ghost core for a conversational archive. It turns human-written canon and memory files into generated runtime artifacts, then exposes a small FastAPI signal chamber for awakening checks, ghost chat, archive retrieval, protected API docs, and frontend type generation.

The server stays stateless about chat continuity. The frontend owns each thread's rolling `session_summary`, sends it with every chat request, and receives an updated summary in the response.

## Repository Structure

```txt
ghost-on-the-shelf/
  core/
    archive/
      canon/
        identity.md
        ontology.md
        voice.md
      memories/
        field/
          artifacts.md
          installed_modules.md
          protocols.md
        self/
          neural_adaptation_layers.md
          perception_filters.md
          preference_signals.md
          vessel_upkeep.md
    shelf/                         # generated, ignored by git
      ghost_runtime.md
      indexes/
        memory_index.json
    synapse/
      ghost.py                      # shared ghost reply and summary behavior
      protocol.py                   # shared response-shaping limits and model config
      runtime.py                    # shared generated-artifact loading
      retrieval.py                  # shared embedding and memory retrieval
  signal_chamber/
    server/
      app.py                        # FastAPI app factory: signal_chamber.server.app:app
      dependencies.py               # request/app-state helpers for route handlers
      docs.py                       # protected docs and OpenAPI schema routes
      guards.py                     # in-memory rate and concurrency limits
      middleware.py                 # CORS and production Origin checks
      routes.py                     # health, awakening, and chat endpoints
      schemas.py                    # API request/response models
      settings.py                   # environment-backed settings
      state.py                      # runtime artifact and app-state setup
  staging_chamber/
    journal.ipynb                   # private rehearsal and observation notebook
  rituals/
    summarize_runtime.py
    build_index.py
  tests/
    test_app.py
    test_retrieval.py
```

`staging_chamber/` is for rehearsal. `signal_chamber/` is the live contact surface. Shared memory mechanics and response-shaping protocol belong in `core/synapse/` so the journal and server use the same retrieval and ghost reply behavior.

## Installation

Requirements:

- Python 3.12+
- `uv`
- an OpenAI API key

Install dependencies:

```bash
uv sync
```

Create `.env` locally:

```bash
OPENAI_API_KEY=your_api_key_here
GHOST_DOCS_USERNAME=choose-a-docs-username
GHOST_DOCS_PASSWORD=choose-a-strong-docs-password

# Required in production
GHOST_ENV=production
GHOST_ALLOWED_ORIGINS=https://your-frontend.example
```

For local development, `GHOST_ENV` can be omitted. The server defaults to local browser origins such as `http://localhost:3000` and `http://localhost:5173`. Docs auth has no hard-coded fallback; `/docs` and `/openapi.json` are unavailable until both docs credential env vars are set.

## Ritual Workflow

`core/shelf/` is generated from the archive and ignored by git. Generate it before running the server locally and during deploy/build.

Run this when canon files change:

```bash
uv run --env-file .env python rituals/summarize_runtime.py
```

This writes `core/shelf/ghost_runtime.md` from:

- `core/archive/canon/identity.md`
- `core/archive/canon/ontology.md`
- `core/archive/canon/voice.md`

Run this when memory files change:

```bash
uv run --env-file .env python rituals/build_index.py
```

This writes `core/shelf/indexes/memory_index.json` from `core/archive/memories/**/*.md`.

## Local Server

Generate artifacts first:

```bash
uv run --env-file .env python rituals/summarize_runtime.py
uv run --env-file .env python rituals/build_index.py
```

Run FastAPI:

```bash
uv run uvicorn signal_chamber.server.app:app --host 0.0.0.0 --port 8000
```

Try the local endpoints:

```bash
curl http://localhost:8000/health
curl -X POST -H "Origin: http://localhost:5173" http://localhost:8000/v1/awakening
curl -u "$GHOST_DOCS_USERNAME:$GHOST_DOCS_PASSWORD" http://localhost:8000/openapi.json
```

Open docs at `http://localhost:8000/docs` and sign in with the configured docs credentials.

## Docker Deployment

The Docker image copies the locally generated `core/shelf/ghost_runtime.md` and `core/shelf/indexes/memory_index.json` into the image. Those files stay ignored in git, but the deployed server still starts with prepared runtime artifacts baked into the image.

Generate the shelf locally before building:

```bash
uv run --env-file .env python rituals/summarize_runtime.py
uv run --env-file .env python rituals/build_index.py
```

The Docker build fails if either generated shelf file is missing.

Build locally:

```bash
docker build -t ghost-on-the-shelf .
```

Run locally:

```bash
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY \
  -e GHOST_ENV=production \
  -e GHOST_ALLOWED_ORIGINS=http://localhost:5173 \
  -e GHOST_DOCS_USERNAME \
  -e GHOST_DOCS_PASSWORD \
  ghost-on-the-shelf
```

For Cloud Run, build and push this Docker image after regenerating the local shelf artifacts, then deploy the image with runtime secrets/env vars configured for:

- `OPENAI_API_KEY`
- `GHOST_ENV=production`
- `GHOST_ALLOWED_ORIGINS=https://your-frontend.example`
- `GHOST_DOCS_USERNAME`
- `GHOST_DOCS_PASSWORD`

## API Contract

### `GET /health`

Returns server health and whether generated runtime artifacts are loaded. `/health` is not origin-restricted.

Example response:

```json
{
  "status": "ok",
  "runtime_loaded": true,
  "memory_index_loaded": true,
  "archive_error": null,
  "chunk_count": 55
}
```

### `POST /v1/awakening`

Checks whether the archive can awaken before the client enables chat. This endpoint does not estimate remaining OpenAI credits. Instead, it verifies that shelf artifacts are loaded and that the server can successfully make tiny `store=false` OpenAI embedding and response probes.

Successful response:

```json
{
  "can_awaken": true,
  "reason": null,
  "message": "The archive is ready to awaken.",
  "archive_loaded": true,
  "openai_ready": true
}
```

Blocked response:

```json
{
  "can_awaken": false,
  "reason": "openai_unavailable",
  "message": "The archive cannot awaken because OpenAI access is unavailable. Check credentials, billing, quota, or rate limits.",
  "archive_loaded": true,
  "openai_ready": false
}
```

Possible `reason` values:

- `archive_unavailable`
- `openai_unconfigured`
- `openai_unavailable`

### `POST /v1/chat`

Request:

```json
{
  "message": "What do you remember about the field protocols?",
  "session_summary": "The user is asking about archive-facing behavior.",
  "k": 3
}
```

Response:

```json
{
  "reply": "The field protocols describe how the archive should be handled...",
  "session_summary": "The user asked about field protocols and archive-facing behavior.",
  "retrieved": [
    {
      "id": "core/archive/memories/field/protocols.md#introduction-abc123",
      "title": "Introduction",
      "source": "core/archive/memories/field/protocols.md",
      "score": 0.82
    }
  ]
}
```

`k` is optional and defaults to `3`. The server embeds the user message, cosine-ranks the generated memory index, injects the top fragments, calls the OpenAI Responses API with `store=false`, then runs one small summary update call after a successful reply.

## OpenAI Availability

OpenAI does not expose a simple "tokens left" endpoint for normal chat readiness. Usage and costs endpoints report historical usage and spend, not a clean remaining-token balance.

For this app, `/v1/awakening` answers the more useful runtime question: can this server talk to OpenAI right now? If the key is missing, billing/quota is exhausted, credentials are invalid, rate limits are hit, or OpenAI cannot be reached, the endpoint returns `can_awaken: false` and the client should keep chat disabled.

## Abuse Limits

The signal chamber keeps only lightweight in-memory protection:

- Awakening probe rate limit: `10` accepted requests per IP per minute
- Chat rate limit: `6` accepted requests per IP per minute
- Max concurrent chat requests: `2`
- Max message length: `100` characters
- Max summary length: `3000` characters
- Answer word limit: `150` words
- Max chat output tokens: `1500`
- Max summary output tokens: `600`
- Chat reasoning effort: `medium`
- Summary reasoning effort: `low`

The server rejects invalid or abusive requests before OpenAI calls when possible: empty messages, oversized messages, oversized summaries, disallowed production origins, IP rate limit exhaustion, and concurrency exhaustion.

The answer word limit, model IDs, retrieval `k` defaults, output-token caps, and reasoning effort are defined in `core/synapse/protocol.py`. The signal chamber and staging journal both import that protocol so the notebook remains a faithful rehearsal surface for the live API.

These limits are in memory. They reset on server restart and are only reliable for one running process.

## Production Controls

Set exact browser origins with `GHOST_ALLOWED_ORIGINS`, comma-separated:

```bash
GHOST_ALLOWED_ORIGINS=https://app.example.com,https://www.example.com
```

In production (`GHOST_ENV=production`), CORS middleware uses those origins and custom middleware rejects `/v1/*` requests with missing or unapproved `Origin` headers. CORS preflight `OPTIONS` requests are allowed through, and `/health` is not origin-restricted.

This limits normal browser calls from other domains. It is not full authentication against custom scripts because non-browser clients can spoof `Origin`.

Docs and schema routes are always protected with HTTP Basic auth:

- `GET /docs`
- `GET /openapi.json`

Configure production docs credentials:

```bash
GHOST_DOCS_USERNAME=docs-user
GHOST_DOCS_PASSWORD=docs-password
```

## Type Generation

Generate TypeScript types from OpenAPI, not a full generated fetch client.

For an unprotected or locally downloaded schema:

```bash
npx openapi-typescript https://api.example.com/openapi.json -o src/generated/ghost-api.ts
```

For protected production schema, download with Basic auth first:

```bash
curl -u "$GHOST_DOCS_USERNAME:$GHOST_DOCS_PASSWORD" \
  https://api.example.com/openapi.json \
  -o /tmp/ghost-openapi.json

npx openapi-typescript /tmp/ghost-openapi.json -o src/generated/ghost-api.ts
```

For local development:

```bash
curl -u "$GHOST_DOCS_USERNAME:$GHOST_DOCS_PASSWORD" http://localhost:8000/openapi.json -o /tmp/ghost-openapi.json
npx openapi-typescript /tmp/ghost-openapi.json -o src/generated/ghost-api.ts
```

## Hosting

Generate runtime artifacts during deploy/build:

```bash
uv run --env-file .env python rituals/summarize_runtime.py
uv run --env-file .env python rituals/build_index.py
```

Run the service:

```bash
uv run uvicorn signal_chamber.server.app:app --host 0.0.0.0 --port 8000
```

Render, Railway, and Fly are good v1 targets because they run a normal long-lived FastAPI service. Vercel is possible, but less ideal for this version because serverless instances do not reliably share in-memory counters.

## Testing

Run the test suite:

```bash
uv run pytest
```

Current tests cover retrieval ranking, health, protected docs/schema, production origin checks, awakening success and failure paths, stateless session summaries, mocked chat responses, invalid-input rejection, rate limits, and concurrency rejection before OpenAI calls.
