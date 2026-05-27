# AGENTS.md

## Project

Ghost on the Shelf is a FastAPI service backed by generated archive/runtime artifacts. The server uses OpenAI APIs for retrieval, chat, summaries, moderation, and awakening checks.

## Setup

Use Python 3.12+ and `uv`.

```bash
uv sync
```

Runtime artifacts under `core/shelf/` are generated and ignored by git.

```bash
uv run --env-file .env python rituals/summarize_runtime.py
uv run --env-file .env python rituals/build_index.py
```

## Tests

Run the API test suite before committing backend or auth changes:

```bash
uv run pytest tests/test_app.py
```

## Python Code

Keep server changes aligned with the existing FastAPI structure:

- request routes in `signal_chamber/server/routes.py`
- environment-backed config in `signal_chamber/server/settings.py`
- middleware/auth gates in `signal_chamber/server/middleware.py`
- access-token helpers in `signal_chamber/server/access.py`
- shared request guards in `signal_chamber/server/guards.py`
- Pydantic API models in `signal_chamber/server/schemas.py`

Prefer typed, small functions and dataclasses/Pydantic models over ad hoc dicts where the code already has a structured type.

When changing behavior, add or update focused tests in `tests/test_app.py`.

## Security Notes

Do not commit `.env`, API keys, invite codes, cookie secrets, docs credentials, or generated `core/shelf/` artifacts.

Production chat access depends on:

- `GHOST_ENV=production`
- exact `GHOST_ALLOWED_ORIGINS`
- `GHOST_ACCESS_CODE` or `GHOST_ACCESS_CODE_HASH`
- `GHOST_ACCESS_COOKIE_SECRET`
- docs credentials for `/docs` and `/openapi.json`

Treat CORS/Origin checks as browser restrictions, not full authentication.

## Editing Guidelines

Prefer small, focused changes. Keep README deployment docs aligned with `signal_chamber/server/settings.py`.

When changing auth, rate limits, cookies, docs access, or production request guards, update or add tests in `tests/test_app.py`.
