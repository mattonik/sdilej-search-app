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

Result: pending.

### 2. One Download Composer

- Replace the parallel YouTube quick form and generic URL form with one
  source-aware composer.
- Keep destination routing up front; reveal TV fields only when required.
- Hide advanced request tuning until needed.
- Make YouTube authentication discoverable through a contextual Settings link.

Verification: browser E2E for Sdilej, YouTube, playlists, TV destinations,
and duplicate queue behavior.

Result: pending.

### 3. Search And Library Scan Flow

- Make every search mode reachable on a mobile viewport without horizontal
  clipping.
- Demote movie discovery to a secondary movie-oriented action.
- Separate TV/Kids TV/Music library tasks into explicit modes.

Verification: mobile browser E2E for navigation, search modes, and library
folder scans.

Result: pending.

## Non-Goals

- No API redesign or data migration.
- No removal of saved-pick functionality or its direct URL.
- No visual-framework replacement.
