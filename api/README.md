# Agent Demo API

FastAPI backend for the intelligent agent demo. The project is managed with [uv](https://github.com/astral-sh/uv) and follows an application-factory pattern to keep routing and business logic cleanly separated.

## Quick start

```bash
uv sync
uv run python main.py
```

The default server listens on `http://127.0.0.1:8000` and exposes a health check at `/api/health`.

### Environment variables

Define these environment variables before starting the API so the LangGraph agent can reach your model provider:

- `OPENAI_API_KEY` – API key for the target OpenAI-compatible service
- `OPENAI_BASE_URL` – Optional override when using a compatible proxy (defaults to `https://api.openai.com/v1`)
- `OPENAI_MODEL` – Target chat completion model (defaults to `gpt-4o-mini`)
- `RESERVATION_HOLD_MINUTES` – Length of time a mock reservation hold is kept (defaults to `10`)
- `LOG_LEVEL` – Logging verbosity (`DEBUG`, `INFO`, etc.; defaults to `INFO`)

## Project layout

- `app/` – FastAPI application package
  - `api/` – versioned API routers and agent endpoints
  - `core/` – configuration and shared infrastructure
  - `services/` – LangGraph agent and mock scheduler logic
- `docs/` – API documentation for front-end integration
- `main.py` – local development entrypoint that launches Uvicorn

Refer to `docs/api.md` when adding new endpoints so the front-end team can stay aligned.
