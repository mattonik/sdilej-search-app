# Local Library Management

## Current V1 Scope

The Library tab provides a read-only Missing TV scan for one show at a time.

It uses:

- TVMaze as the canonical source for season and episode numbers.
- Existing localized title metadata and aliases.
- The same alias-aware TV folder reuse logic as TV search/download routing.
- Existing local downloaded detection based on media files containing the `SxxEyy` token.

## Matching Rules

An episode is marked as downloaded only when the resolved season folder contains a regular media file whose name includes the matching `SxxEyy` token.

The scan ignores support and incomplete files such as subtitles, NFO files, images, `.part`, `.partial`, `.tmp`, `.crdownload`, and `.download` files.

The scan is intentionally limited to the resolved show folder. It does not search the whole media library.

## UI Behavior

- Use the `Library` tab.
- Enter a TV show name and run `Scan missing episodes`.
- Downloaded episodes show the first matching local filename.
- Missing episodes expose `Search missing`, which switches to the existing TV search flow and selects that episode.
- The feature does not delete, move, rename, or queue files directly.

## API

- `POST /api/library/tv/missing`
- Request: `{ "show_name": "Reacher" }`
- Response includes:
  - `show`
  - `title_metadata`
  - `local_context`
  - `summary`
  - `seasons`

## Non-Goals

- Whole-library indexing.
- File cleanup actions.
- Automatic queueing of missing episodes.
- Movie or music library management.
