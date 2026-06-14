# UX Backlog

This backlog captures the next practical product improvements after the TV/file/storage refactors.

## Priority 1: Release Gate and Stability

Goal: keep the app shippable after UI/runtime changes.

- Keep `./scripts/check.sh` as the default pre-release gate.
- Run the gate after any change that touches `app/static/js/`, `app/templates/`, or queue/search behavior.
- Add one more narrow E2E test only if a real regression appears, not preemptively.
- Acceptance: mocked, E2E, live smoke, and Docker build all pass before release.

## Priority 2: TV Runtime Polish

Goal: keep the most complex surface predictable.

- Watch for new coupling between `tv-search.js`, `tv-state.js`, and `queue-ui.js`.
- If TV polling starts shifting content again, add a browser regression that checks open season state and scroll anchor preservation.
- If TV action rendering diverges between file and TV views, normalize the shared queue badge/button behavior first, not the individual TV cards.
- Acceptance: TV polling, downloaded episode state, and `Search anyway` remain stable after refreshes.

## Priority 3: File Search Polish

Goal: make scanning large result sets faster without changing search behavior.

- Keep the cards/list toggle and compact list as the default browsing model.
- Improve readability only if the result list starts feeling dense in real use.
- Add a small shortcut or filter only if there is a clear user need from actual usage.
- Keep the action order stable so `Info`, `Save`, `Queue`, and `Manage` remain predictable.
- Acceptance: view/filter state persists across reloads and queue/saved badges remain visible and accurate.

## Priority 4: Backend Maintainability

Goal: avoid re-growing the old monoliths.

- Continue splitting `storage.py`-adjacent logic only when a concrete coupling or complexity issue appears.
- Avoid speculative backend refactors unless they remove measurable duplication or risk.
- If a new domain grows large, extract it behind a repository/service boundary before adding more behavior.
- Acceptance: new logic lands in a dedicated module instead of being added back into large catch-all files.

## Priority 5: Small UX Wins

Goal: pick only low-risk improvements that are clearly useful.

- Consider a small TV summary polish only if it reduces scanning time.
- Consider a file-search density tweak only if it makes result comparison faster.
- Consider a downloads-panel polish only if queue management becomes harder to read.
- Do not add new feature scope here unless it clearly improves an existing flow.
- Acceptance: any UX tweak should be explainable in one sentence and should not require API changes.

## References

- Storage refactor log: [docs/storage-refactor-log.md](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/docs/storage-refactor-log.md)
- App JS refactor log: [docs/app-js-refactor-plan.md](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/docs/app-js-refactor-plan.md)
