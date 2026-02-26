# sdilej-search-app

Dockerized web app that proxies and enhances search for `sdilej.cz`.

## Features

- Search by keyword
- Category filters: all, video, audio, archive, image
- Sort options: relevance, most downloaded, newest, largest, smallest
- Language-aware filtering with filename heuristics (e.g. `SK`, `(sk)`, `CZ EN SK`, `SKtit`, `SK dabing`)
- `strict_dubbing` mode (requires explicit `dub`/`dabing` markers)
- Release year filter from title patterns (`1999`, `2003`, ...)
- Queryless search mode: if `query` is empty, app derives one from language/year (e.g. `sk 2003`)
- Result deduplication by file ID (numeric id in detail URL)
- Autocomplete suggestions from sdilej endpoint
- Parsed card view (title, size, duration, extension, playable marker, file ID, year/language hints)
- Detail probe endpoint parses download buttons and runs optional preflight request
- SQLite persistence for:
  - search history
  - saved picks (upsert by file ID)
  - saved-pick driven download jobs (optional auto-remove save on successful download)
- Background downloader queue worker:
  - queued/running/done/failed/canceled states
  - progress tracking
  - speed controls: max concurrent jobs, per-job chunk count, global bandwidth cap
  - premium-first mode with strict premium-link validation
  - partial `.part` resume support (when server supports byte ranges)
  - startup recovery: `running` jobs are automatically re-queued after restart/rebuild
  - cancel + retry
  - duplicate protection when queueing by `file_id`/`detail_url`
  - media-aware routing for new jobs:
    - `movie` -> `/movies`
    - `tv` -> `/tv/{series}/seasonNN`
    - `kids + movie` -> `/kids/movies`
    - `kids + tv` -> `/kids/tv/{series}/seasonNN`
  - uncertain title classification can require user confirmation before enqueue
  - queue controls: move-to-top, custom priority, clear finished jobs
  - account credentials (for subscription/premium flow)
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

Persistent data is stored via Compose volume mounts:
- `./data/app.db` (queue/job DB + settings)
- `./downloads` (downloaded files + partial `.part` files for resume)

## Raspberry Pi deployment (arm64)

1. Copy project to Pi.
2. Ensure Docker + Compose plugin are installed.
3. From project folder:

```bash
docker compose up -d --build
```

4. Optional auto-start is already configured via `restart: unless-stopped`.

## API endpoints

- `GET /saved` (Saved Picks page)
- `GET /api/search?query=matrix&category=video&sort=newest&language=SK&language_scope=audio&strict_dubbing=true&release_year=2003&max_results=100`
- `GET /api/search?category=video&language=SK&language_scope=audio&release_year=2003&max_results=100` (no query)
- `GET /api/detail?detail_url=https://sdilej.cz/15947667/scoob-2020-sk-.mkv&preflight=true`
- `GET /api/autocomplete?q=mat&limit=10`
- `GET /api/history?limit=50`
- `GET /api/saved?limit=200`
- `POST /api/saved` (upsert saved pick)
  - stores inferred media metadata (`media_kind`, `is_kids`, `series_name`, `season_number`, `episode_number`)
- `DELETE /api/saved/{file_id}`
- `GET /api/account` (credential status)
- `POST /api/account` (set credentials, optional verification)
- `DELETE /api/account` (clear credentials)
- `GET /api/downloads?limit=200&status=queued`
- `POST /api/downloads` (enqueue download job)
  - supports `chunk_count` override (1..8)
  - supports optional media routing hints: `media_kind`, `is_kids`, `series_name`, `season_number`, `episode_number`
  - duplicate queue/download protection returns `409` + `duplicate_job`
  - supports `source_saved_file_id` + `delete_saved_on_complete`
- `GET /api/downloads/settings`
- `POST /api/downloads/settings` (`max_concurrent_jobs`, `default_chunk_count`, `bandwidth_limit_kbps`)
- `GET /api/downloads/library-paths`
- `POST /api/downloads/library-paths` (`movies_dir`, `tv_dir`, `kids_movies_dir`, `kids_tv_dir`, `unsorted_dir`, `confirm_on_uncertain`)
- `POST /api/media/classify` (preview auto-classification + resolved destination path)
- `POST /api/downloads/{id}/classification` (recategorize queued job and reroute destination)
- `POST /api/downloads/{id}/cancel`
- `POST /api/downloads/{id}/cancel-complete`
- `POST /api/downloads/{id}/retry`
- `DELETE /api/downloads/{id}`
- `DELETE /api/downloads/{id}?with_data=true`
- `POST /api/downloads/{id}/priority`
- `POST /api/downloads/{id}/top`
- `POST /api/downloads/clear`
- `GET /healthz`

## Subscription credentials

To use your subscription for downloader jobs:

1. Set credentials:

```bash
curl -X POST http://localhost:8080/api/account \\
  -H 'Content-Type: application/json' \\
  -d '{"login":"your_login_or_email","password":"your_password","verify":true}'
```

2. Enqueue premium-mode job:

```bash
curl -X POST http://localhost:8080/api/downloads \\
  -H 'Content-Type: application/json' \\
  -d '{"detail_url":"https://sdilej.cz/15947667/scoob-2020-sk-.mkv","preferred_mode":"premium"}'
```

3. Watch queue:

```bash
curl http://localhost:8080/api/downloads
```

## Next step

This app already exposes stable search metadata and file detail URLs, which is the base needed for a queued download manager in the next iteration.
