# sdilej-search-app

Dockerized web app that proxies and enhances search for `sdilej.cz`.

## Features

- Search by keyword
- Category filters: all, video, audio, archive, image
- Sort options: relevance, most downloaded, newest, largest, smallest
- Language-aware filtering with filename heuristics (e.g. `SK`, `(sk)`, `CZ EN SK`, `SKtit`, `SK dabing`)
- Release year filter from title patterns (`1999`, `2003`, ...)
- Queryless search mode: if `query` is empty, app derives one from language/year (e.g. `sk 2003`)
- Autocomplete suggestions from sdilej endpoint
- Parsed card view (title, size, duration, extension, playable marker)
- JSON API endpoints for future download-manager integration

## Project structure

- `app/main.py` - FastAPI app + routes
- `app/sdilej_client.py` - HTTP client + parser + URL mapping
- `app/templates/index.html` - UI
- `app/static/style.css` - styling
- `docs/reverse-engineering.md` - endpoint and URL analysis notes

## Run locally (no Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Open: `http://localhost:8080`

## Run with Docker

```bash
docker compose up --build
```

Open: `http://localhost:8080`

## Raspberry Pi deployment (arm64)

1. Copy project to Pi.
2. Ensure Docker + Compose plugin are installed.
3. From project folder:

```bash
docker compose up -d --build
```

4. Optional auto-start is already configured via `restart: unless-stopped`.

## API endpoints

- `GET /api/search?query=matrix&category=video&sort=newest&language=SK&language_scope=audio&release_year=2003&max_results=100`
- `GET /api/search?category=video&language=SK&language_scope=audio&release_year=2003&max_results=100` (no query)
- `GET /api/autocomplete?q=mat&limit=10`
- `GET /healthz`

## Next step

This app already exposes stable search metadata and file detail URLs, which is the base needed for a queued download manager in the next iteration.
