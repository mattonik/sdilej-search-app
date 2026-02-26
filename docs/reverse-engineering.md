# Sdilej Search Reverse Engineering (2026-02-25)

## Entry points

- Direct search page:
  - `GET https://sdilej.cz/sk/s`
- Search form submit:
  - `POST https://sdilej.cz/search.php` with fields:
    - `q` (search term)
    - `csrf` (hidden form token; required for POST route)
- Query shortcut:
  - `GET https://sdilej.cz/sk/s?q=<term>`
  - Returns `302 Location: /<slug>/s`

## Slug behavior

`q` is normalized into a path slug:

- `harry potter` -> `/harry-potter/s`
- `Šest pušek` -> `/sest-pusek/s`
- `c# test` -> `/c-test/s`
- `test+abc` -> `/test-abc/s`
- `avatar (2009)` -> `/avatar-2009/s`

## Search URL schema

Canonical pattern:

- `https://sdilej.cz/<slug>/s/<segment>`

Where `<segment>` combines category and sort.

### Category segments

- `-` -> all
- `video-` -> video
- `audio-` -> audio
- `archive-` -> archives
- `image-` -> images

### Sort suffixes

Appended to category segment:

- `` (empty) -> relevance
- `3` -> most downloaded
- `4` -> newest
- `1` -> largest first
- `2` -> smallest first

Examples:

- all + relevance: `/<slug>/s/-`
- all + newest: `/<slug>/s/-4`
- video + relevance: `/<slug>/s/video-`
- video + downloads: `/<slug>/s/video-3`

## Autocomplete endpoint

- `GET https://sdilej.cz/autocomplete.php?q=<term>`
- Returns plain text, newline-separated suggestions.
- UI behavior on sdilej uses `minLength: 2`.

## Result card structure

Each result appears as a `div.videobox` with:

- detail link (`a[href]`) to file page
- display title (`.videobox-title a`)
- thumbnail (`img.img-responsive`)
- metadata line (size and optional duration `Délka:`)
- optional `span.playable` marker for playable media

## Notes and caveats

- Direct POST to `/search.php` without valid CSRF usually redirects to `/`.
- Legacy JS (`main.js`) still references older filter controls (`images`, `documents`, `everything`) that are not present in current search markup.
- No explicit pagination links were observed in sampled pages; responses can include many cards in a single HTML response.

## App-side language filtering heuristics

The web app adds an extra post-filtering layer over parsed filenames:

- Accepts language code (`SK`, `EN`, `CZ`) or common names (`slovak`, `english`, etc.).
- Detects standalone tags: `SK`, `(sk)`, `CZ EN SK`.
- Detects compact forms: `SKtit`, `SKdabing`, `dubSK`.
- Detects contextual words: `dabing`, `dub`, `titulky`, `subtitles`.

Filter scopes:

- `any` - any language mention.
- `audio` - dubbing/audio-like mentions plus generic language tags (`CZ EN SK`).
- `subtitles` - subtitle-specific mentions only.
- `strict_dubbing=true` - only keeps entries where selected language is explicitly tied to dub markers (`dub`, `dabing`).

Year filtering:

- App parses 4-digit year tokens in titles (`19xx`, `20xx`).
- `release_year=2003` keeps only items where title contains `2003`.

Deduplication:

- App extracts file id from detail URL pattern `https://sdilej.cz/<id>/<slug>`.
- Results are deduplicated by this numeric `file_id` (fallback to `detail_url` if id is missing).

Detail page probe:

- App can parse detail pages to discover download entry points and metadata.
- Key selectors:
  - `div.detail-buttons a.btn.btn-success` -> fast download button
  - `div.detail-buttons a.btn.btn-danger` -> slow/free download button
- Probe also records preflight headers for selected download URL (`status`, `location`, `content-type`, `content-length`, `accept-ranges`).

Login form (for subscription-based downloader):

- Login page: `GET https://sdilej.cz/prihlasit`
- Form selector: `form#loginform`
- Submit action: `/sql.php` (relative on current page)
- Main fields:
  - `login` (email or username)
  - `heslo` (password)
  - optional `remember=1`
