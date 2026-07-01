# sdilej-search-app

Dockerized web app that proxies and enhances search for `sdilej.cz`.

## Features

- Search by keyword
- TV show mode:
  - lookup show metadata + season/episode list via TVmaze (no API key)
  - select seasons to search
  - per-season mode: search all episodes or only selected episodes
  - grouped results by season/episode (`SxxExx`)
  - multi-pattern episode queries (`SxxExx`, `x`, `Season N Episode M`)
  - result ranking: precision-first alias matching with episode-title boosts and language-aware tie breaking
- Category filters: all, video, audio, archive, image
- Movie discovery:
  - TMDB-powered trending/popular/now-playing/upcoming/top-rated movie lists
  - lightweight sdilej availability check for discovered movies
- Music search:
  - audio-category shortcut form
  - `music` destination preset for routing downloads to `/music`
- Local library management:
  - per-show TV missing-episode scan using TVMaze episode lists
  - local downloaded detection from configured TV folders via `SxxEyy` media files
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
  - providers: `sdilej` direct/probed downloads and `youtube` downloads via `yt-dlp`
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
    - `tv` -> `/tv/{series}/SNN`
    - `kids + movie` -> `/kids/movies`
    - `kids + tv` -> `/kids/tv/{series}/SNN`
    - `music` -> `/music`
  - uncertain title classification can require user confirmation before enqueue
  - queue controls: move-to-top, custom priority, clear finished jobs
  - account credentials (for subscription/premium flow)
- Kids catalog mode:
  - reads VeseleRozpravky show/episode lists
  - resolves episode pages to YouTube video URLs
  - queues selected episodes as `youtube` provider jobs with kids/TV routing
- JSON API endpoints for future download-manager integration

## Project structure

- `app/main.py` - FastAPI app factory + route registration
- `app/db.py` - shared SQLite connection policy + retry helpers
- `app/sdilej_client.py` - HTTP client + parser + URL mapping
- `app/tmdb_client.py` - TMDB client for movie discovery
- `app/routes/` - domain route modules (`search`, `tv`, `downloads`, `health`)
- `app/templates/index.html` - UI shell
- `app/static/js/app.js` - main browser runtime
- `app/static/js/saved.js` - saved-picks browser runtime
- `app/static/js/file-search.js` - file-search runtime
- `app/static/js/movie-discovery.js` - movie discovery runtime
- `app/static/js/library-management.js` - local library scan runtime
- `app/static/js/tv-search.js` - TV runtime
- `app/static/js/queue-ui.js` - shared queue rendering/actions
- `app/static/js/tv-view.js` - TV rendering helpers
- `app/kids_catalog.py` - VeseleRozpravky parser/resolver
- `app/static/js/api.js` - browser API wrapper
- `app/static/style.css` - styling
- `docs/reverse-engineering.md` - endpoint and URL analysis notes

## Run locally (no Docker)

Requires Python 3.12+.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Open: `http://localhost:8080`

## Tests

Install dev dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the default mocked suite:

```bash
pytest -m "not live"
```

Run opt-in live smoke tests against real external services:

```bash
RUN_LIVE_SMOKE=1 pytest -m live
```

Run opt-in browser E2E tests (requires Playwright browser install):

```bash
RUN_E2E=1 pytest -m e2e
```

Recommended local release gate before pushing or building for the server:

```bash
./scripts/check.sh
```

This gate expects a running Docker daemon (for example Colima or Docker Desktop) so the final image build step can complete.

GitHub Actions mirrors that release gate in `.github/workflows/ci.yml` on pull requests and pushes to `main`/`master`. A separate manual live smoke workflow lives in `.github/workflows/live-smoke.yml`.

Optional config:

- `TMDB_BEARER_TOKEN`
  - enables movie discovery via TMDB
  - when missing, the discovery UI shows a setup hint instead of failing app startup
  - in Docker Compose, set it in the `.env` file next to `docker-compose.yml`; the compose file forwards it into the container
- `TITLE_METADATA_CACHE_TTL_HOURS`
  - default: `168`
  - controls how long localized title metadata stays fresh before the resolver attempts a synchronous refresh

## Run with Docker

```bash
docker compose up --build
```

Open: `http://localhost:8080`

## Publish Image To GitHub (GHCR)

This repo now includes workflow:
- `.github/workflows/docker-publish.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/live-smoke.yml`

It publishes ARM image (`linux/arm64`) to:
- `ghcr.io/<github-user-or-org>/<repo-name>`

When it runs:
- push to `main` or `master`
- push tag `v*` (for example `v1.0.0`)
- manual run from Actions (`workflow_dispatch`)

Common tags:
- `latest` (default branch)
- branch/tag names
- `sha-<short-commit>`

Example on Raspberry Pi:

```bash
docker pull ghcr.io/<owner>/<repo>:latest
```

Persistent data is stored via Compose mounts:
- `/config/app.db` inside container (DB + settings)
- `/media` inside container (downloaded files + partial `.part` files)

Host paths are configurable via env vars in `docker-compose.yml`:
- `SDILEJ_CONFIG_DIR` -> mapped to `/config`
- `SDILEJ_MEDIA_DIR` -> mapped to `/media`

Defaults:
- `SDILEJ_CONFIG_DIR=./data`
- `SDILEJ_MEDIA_DIR=./downloads`

Example for your server-style layout (`.env` file next to `docker-compose.yml`):

```bash
SDILEJ_CONFIG_DIR=/srv/appdata/sdilej-search
SDILEJ_MEDIA_DIR=/srv/mergerfs/pool/media
TMDB_BEARER_TOKEN=your_tmdb_read_access_token
```

## Raspberry Pi deployment (arm64)

1. Copy project to Pi.
2. Ensure Docker + Compose plugin are installed.
3. From project folder:

```bash
docker compose up -d --build
```

If you use host storage paths, set `.env` first (example):

```bash
SDILEJ_CONFIG_DIR=/srv/appdata/sdilej-search
SDILEJ_MEDIA_DIR=/srv/mergerfs/pool/media
```

4. Optional auto-start is already configured via `restart: unless-stopped`.

## API endpoints

- `GET /saved` (Saved Picks page)
- `GET /api/search?query=matrix&category=video&sort=newest&language=SK&language_scope=audio&strict_dubbing=true&release_year=2003&max_results=100`
- `GET /api/search?category=video&language=SK&language_scope=audio&release_year=2003&max_results=100` (no query)
- `GET /api/detail?detail_url=https://sdilej.cz/15947667/scoob-2020-sk-.mkv&preflight=true`
- `GET /api/autocomplete?q=mat&limit=10`
- `POST /api/tv/lookup` (`show_name`) returns show + seasons/episodes
- `POST /api/movie/lookup` (`title`, optional `year`) returns localized title metadata + aliases
- `GET /api/discovery/movie-genres?language=sk-SK`
- `GET /api/discovery/movies?mode=popular&time_window=week&genre=28&year=2024&limit=12`
- `POST /api/library/tv/missing` (`show_name`) returns local downloaded/missing TV episode report
- `POST /api/tv/search` (`show_id`, `show_name`, `seasons`, optional current filters) returns grouped episode results
- `POST /api/tv/search-jobs` creates a persisted background TV search job
- `GET /api/tv/search-jobs?limit=50&status=running`
- `GET /api/tv/search-jobs/{id}`
- `POST /api/tv/search-jobs/{id}/cancel`
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
  - supports `source_type`: `sdilej` (default) or `youtube`
  - supports optional `source_metadata` for catalog/provider context
  - supports `chunk_count` override (1..8)
  - supports `destination_preset`: `auto`, `movies`, `tv`, `kids_movies`, `kids_tv`, `music`, `unsorted`
  - supports optional media routing hints: `media_kind`, `is_kids`, `series_name`, `season_number`, `episode_number`
  - duplicate queue/download protection returns `409` + `duplicate_job`
  - supports `source_saved_file_id` + `delete_saved_on_complete`
- `GET /api/downloads/settings`
- `POST /api/downloads/settings` (`max_concurrent_jobs`, `default_chunk_count`, `bandwidth_limit_kbps`)
- `GET /api/downloads/library-paths`
- `POST /api/downloads/library-paths` (`movies_dir`, `tv_dir`, `kids_movies_dir`, `kids_tv_dir`, `music_dir`, `unsorted_dir`, `confirm_on_uncertain`)
- `POST /api/media/classify` (preview auto-classification/destination preset + resolved destination path)
- `POST /api/downloads/{id}/classification` (recategorize queued job and reroute destination)
- `POST /api/downloads/{id}/cancel`
- `POST /api/downloads/{id}/cancel-complete`
- `POST /api/downloads/{id}/retry`
- `DELETE /api/downloads/{id}`
- `DELETE /api/downloads/{id}?with_data=true`
- `POST /api/downloads/{id}/priority`
- `POST /api/downloads/{id}/top`
- `POST /api/downloads/clear`
- `GET /api/kids-catalog/shows`
- `GET /api/kids-catalog/shows/{slug}`
- `POST /api/kids-catalog/resolve` (`episode_url`) resolves VeseleRozpravky episode pages to YouTube URLs
- `GET /healthz`

## YouTube / Kids Catalog downloads

YouTube downloads use `yt-dlp` inside the same background queue as sdilej downloads. The Docker image installs `ffmpeg`, which yt-dlp uses for common merge/output flows.

In the Downloads tab, use the "YouTube quick download" form for direct video links. It only needs a YouTube URL; the full download form remains available when you want to manually route a YouTube item as TV/kids content.

Example enqueue:

```bash
curl -X POST http://localhost:8080/api/downloads \\
  -H 'Content-Type: application/json' \\
  -d '{"detail_url":"https://www.youtube.com/watch?v=VIDEO_ID","source_type":"youtube","title":"Episode title","media_kind":"tv","is_kids":true,"series_name":"Show","season_number":1,"episode_number":1}'
```

Only download content you have the right to access and store.

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

## Backlog

See [docs/ux-backlog.md](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/docs/ux-backlog.md) for the closed UX and stability log.

See [docs/local-library-management.md](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/docs/local-library-management.md) for the current read-only Missing TV library scan behavior.
