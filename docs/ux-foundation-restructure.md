# UX Foundation Restructure

## Goal

Make the app easier to learn and extend by separating everyday work from
configuration. This is an incremental UI-only restructure: existing APIs,
download behavior, saved-pick data, and deep links remain compatible.

## Target Information Architecture

Primary navigation:

1. Search: find files, TV, music, kids content, and movie discovery.
2. Downloads: inspect the queue and start one routed download flow.
3. Library: inspect local TV, kids TV, and music folders.
4. Settings: Sdilej credentials, YouTube access, and download defaults.

`Saved Picks` is retained at `/saved`, but is deliberately removed from the
primary navigation because it is an infrequent, advanced workflow.

## Delivery Blocks

### 1. Navigation And Settings Foundation

- Replace the primary `Account` label with `Settings`.
- Move download defaults into Settings.
- Remove the permanent idle queue banner and show active queue work as a
  Downloads navigation badge.
- Keep old `#account` hashes working by redirecting them to `#settings`.
- Demote Saved Picks to a secondary Settings utility link.

Verification: browser E2E navigation/account coverage and mocked suite.

Result: completed in `e7eec62` on 2026-10-19.

Verification:

- Focused browser coverage: 2 passed.
- Mocked suite: 110 passed, 1 skipped, 3 deselected.
- Legacy `#account` navigation resolves to Settings.

### 2. One Download Composer

- Replace the parallel YouTube quick form and generic URL form with one
  source-aware composer.
- Keep destination routing up front; reveal TV fields only when required.
- Hide advanced request tuning until needed.
- Make YouTube authentication discoverable through a contextual Settings link.

Verification: browser E2E for Sdilej, YouTube, playlists, TV destinations,
and duplicate queue behavior.

Result: completed in `003fb21` on 2026-10-19.

Verification:

- Focused browser coverage: 3 passed.
- Mocked suite: 110 passed, 1 skipped, 3 deselected.
- The shared composer retains YouTube playlist metadata, local TV suggestions,
  destination routing, duplicate handling, and immediate queue titles.

### 3. Search And Library Scan Flow

- Make every search mode reachable on a mobile viewport without horizontal
  clipping.
- Demote movie discovery to a secondary movie-oriented action.
- Separate TV/Kids TV/Music library tasks into explicit modes.

Verification: mobile browser E2E for navigation, search modes, and library
folder scans.

Result: completed in `ac93d6c` and `6932ec6` on 2026-10-19.

Verification:

- Focused mobile and Library browser coverage: 5 passed.
- Full browser suite: 29 passed.
- Mocked suite: 110 passed, 1 skipped, 3 deselected.
- The former horizontal mobile search strip is now a visible grid, and TV,
  Kids TV, and Music library scans are reachable through explicit modes.

## Non-Goals

- No API redesign or data migration.
- No removal of saved-pick functionality or its direct URL.
- No visual-framework replacement.
