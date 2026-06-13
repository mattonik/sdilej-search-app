# UX Backlog

This backlog tracks the next small product-improvement steps after the TV/file/storage refactors.

## Priority 1: Release Gate and Stability
- Keep `./scripts/check.sh` as the pre-release gate.
- Re-run the gate after any UI/runtime refactor.
- Add another narrow E2E case only if a real regression appears.

## Priority 2: TV Runtime Polish
- Keep an eye on `tv-search.js` / `queue-ui.js` coupling.
- Add a browser regression if TV polling starts shifting content again.
- Consider a small cleanup if TV action rendering starts diverging between file and TV views.

## Priority 3: File Search Polish
- Improve compact list readability if file results become harder to scan at scale.
- Add a small filter/sort shortcut only if there is a clear user need.
- Keep action hierarchy stable so `Info`, `Save`, `Queue`, and `Manage` remain predictable.

## Priority 4: Backend Maintainability
- Continue splitting any future `storage.py`-adjacent logic only if a concrete need appears.
- Avoid speculative refactors unless they remove measurable coupling or complexity.

## References
- Storage refactor log: [docs/storage-refactor-log.md](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/docs/storage-refactor-log.md)
- App JS refactor log: [docs/app-js-refactor-plan.md](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/docs/app-js-refactor-plan.md)
