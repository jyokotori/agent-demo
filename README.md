# Agent Demo Monorepo

This repository hosts both the FastAPI backend and the Vite + React front-end for the agent scheduling demo. Python 3.12.10 + Node v22.15.0.

## Directory layout

- `api/` – FastAPI application managed with [uv](https://github.com/astral-sh/uv). See `api/README.md` for full backend details.
- `web/` – Vite-powered React client that consumes the API.

## Getting started

### Backend (api)

```bash
cd api
uv sync
uv run python main.py
```

The server starts on `http://127.0.0.1:8000` and exposes a health check at `/api/health`.

### Frontend (web)

```bash
cd web
npm install
npm run dev
```

The dev server defaults to `http://127.0.0.1:5173`. Update any proxy settings to match the backend host/port as needed.

## Environment variables

Define the OpenAI-related variables before running the API:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` (optional)
- `OPENAI_MODEL`
- `RESERVATION_HOLD_MINUTES`
- `LOG_LEVEL`

These settings propagate to the agent logic. Front-end integrations typically rely on the API defaults, so changes here may require UI adjustments.
