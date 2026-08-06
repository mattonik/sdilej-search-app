# UX Backlog Closed

This document records the closed UX and stability backlog after the TV, file, and storage refactors.

## Completed

- File search scan flow:
  - compact list readability improved
  - saved/queued/playable markers are easier to scan
  - copy-link shortcut added to file result cards
- TV scan flow:
  - summary and badge spacing tightened
  - copy-link shortcut added to TV result items
- Downloads panel:
  - job metadata pills tightened
  - copy-path/copy-link shortcut added to download jobs

## Verified

- Release gate and stability:
  - `./scripts/check.sh` is the default pre-release gate
  - mocked, E2E, live smoke, and Docker build pass before release
  - narrow E2E coverage exists for the regressions that mattered
- TV runtime polish:
  - polling preserves open season state and scroll anchor behavior
  - downloaded episode state remains stable
  - `Search anyway` continues to work after polling and reloads
- File search polish:
  - cards/list toggle and compact list remain the default browsing model
  - view/filter state persists across reloads
  - queue/saved badges remain visible and accurate
- Backend maintainability:
  - storage logic is split into repositories/helpers instead of a monolith
  - `Storage` remains a compatibility facade
  - no additional speculative backend split is required at this time

## Deferred

- 30-day movie discovery window: add after the current day/week discovery flow has enough usage data to justify another provider query mode.

## References

- Storage refactor log: [docs/storage-refactor-log.md](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/docs/storage-refactor-log.md)
- App JS refactor log: [docs/app-js-refactor-plan.md](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/docs/app-js-refactor-plan.md)
