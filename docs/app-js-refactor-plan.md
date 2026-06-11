# `app/static/js/app.js` Refactor Plan

## Document Purpose

This document is the implementation reference for splitting [`app/static/js/app.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/app.js) into smaller modules without changing product behavior.

It has two roles:

1. Implementation plan
2. Historical execution log

The intent is to avoid using Git history alone as the source of truth for why a refactor step happened, how it was verified, and what risks were accepted at that point.

## Current Baseline

- Repository: `sdilej-search-app`
- Active branch at plan creation: `main`
- Baseline commit at plan creation: `615e4b8`
- Main target file: [`app/static/js/app.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/app.js)
- Current target file size at plan creation: about `2800` lines

## Refactor Goals

The refactor must achieve all of the following:

- reduce the size and responsibility of `app.js`
- isolate feature-specific UI logic by domain
- make shared state explicit instead of accidental
- reduce the chance that TV changes break file search or downloads UI
- keep existing API contracts unchanged
- keep existing UX behavior unchanged unless a change is explicitly scoped
- preserve current polling, queue, saved-state and TV background-job behavior
- keep the browser runtime framework-free and bundler-free

## Non-Goals

These are explicitly out of scope unless later added as separate work:

- changing FastAPI APIs
- rewriting templates
- changing CSS architecture
- introducing a frontend framework
- changing ranking/search logic
- feature redesigns

## Main Risks

The largest risks during implementation are:

1. Initialization order regressions
2. Shared state drift between file search, TV search and downloads panel
3. Duplicate event binding after rerenders
4. Polling side effects after extraction
5. Broken `localStorage` restore timing
6. TV results rerender instability
7. Queue dialog behavior drift between file and TV contexts
8. Cyclic ES module dependencies

## Guardrails

These rules apply to every implementation phase:

- no behavior changes bundled together with structural refactor
- no “small cleanup” mixed into refactor commits unless required for correctness
- every major phase must be verified before moving on
- every major phase must be logged in this document
- every major phase must be committed separately
- feature modules should prefer dependency injection over cross-importing each other
- `app.js` remains the browser entrypoint until the refactor is complete

## Target Module Layout

The intended end state is:

- [`app/static/js/app.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/app.js)
  - thin bootstrap only
- [`app/static/js/dom-utils.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/dom-utils.js)
  - escaping, text cleanup, small DOM-safe helpers
- [`app/static/js/formatters.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/formatters.js)
  - formatting helpers
- [`app/static/js/keys.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/keys.js)
  - queue keys, episode keys, storage keys
- [`app/static/js/storage-state.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/storage-state.js)
  - localStorage-backed preferences
- [`app/static/js/runtime-state.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/runtime-state.js)
  - mutable runtime state facade
- [`app/static/js/api.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/api.js)
  - fetch wrappers and API helpers
- [`app/static/js/workspace-tabs.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/workspace-tabs.js)
  - tabs only
- [`app/static/js/queue-dialog.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/queue-dialog.js)
  - enqueue dialog only
- [`app/static/js/downloads.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/downloads.js)
  - downloads panel only
- [`app/static/js/file-search.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/file-search.js)
  - file-search mode only
- [`app/static/js/tv-search.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/tv-search.js)
  - TV mode only

## Verification Gates

### Default gate

```bash
.venv/bin/pytest -m "not live"
```

### Live smoke gate

```bash
RUN_LIVE_SMOKE=1 .venv/bin/pytest -m live
```

### Browser E2E gate

```bash
RUN_E2E=1 .venv/bin/pytest -m e2e
```

### Docker build gate

```bash
docker build -t sdilej-search:test .
```

### When to run which gate

- Every major refactor phase:
  - default gate required
- Any phase touching polling, rendering, event binding, or persisted UI state:
  - default gate required
  - E2E gate required
- Any phase intended to close out a major milestone:
  - default gate required
  - live smoke gate required
  - E2E gate required
  - Docker build gate required

## Phase Plan

## Phase 0: Baseline Freeze

### Goal

Freeze the current runtime behavior and make sure the critical flows are documented and covered well enough before extraction starts.

### Scope

- identify critical user flows
- confirm which E2E coverage already exists
- add missing E2E coverage only where needed to protect refactor work
- document non-regression flows

### Exit Criteria

- core flows are explicitly listed
- current test coverage is understood
- refactor-sensitive flows are protected by tests or explicitly listed for manual verification

## Phase 1: Shared Foundation Extraction

### Goal

Move pure helpers and storage key logic out of `app.js` first, with minimal runtime risk.

### Scope

- extract pure helper functions
- extract queue key builders
- extract normalization helpers
- extract localStorage key constants
- keep DOM mutation and fetch logic inside `app.js`

### Planned Files

- `dom-utils.js`
- `formatters.js`
- `keys.js`
- `storage-state.js`

### Exit Criteria

- helper logic is imported from modules
- no feature behavior changes
- `app.js` is smaller and less utility-heavy

## Phase 2: Runtime State And API Facade

### Goal

Introduce explicit shared runtime state and centralized API wrappers before splitting feature logic.

### Scope

- add runtime state container or accessor facade
- add fetch/API wrapper module
- move in-flight flags and persisted preference handling behind stable interfaces

### Planned Files

- `runtime-state.js`
- `api.js`

### Exit Criteria

- feature logic no longer depends on loose shared mutable variables
- direct raw `fetch` usage starts shrinking
- state ownership is clearer

## Phase 3: Low-Risk Feature Extraction

### Goal

Split simpler UI areas first, before touching TV search.

### Scope

- workspace tabs
- downloads panel
- queue dialog
- file search mode

### Planned Files

- `workspace-tabs.js`
- `downloads.js`
- `queue-dialog.js`
- `file-search.js`

### Exit Criteria

- these features are initialized from `app.js`
- feature behavior unchanged
- cross-module interactions remain stable

## Phase 4: TV Search Extraction

### Goal

Move the most complex feature last, once the shared runtime and lower-risk extractions are stable.

### Scope

- TV lookup form
- TV season picker
- TV background job creation/polling
- TV render/update logic
- downloaded episode state sync
- alias reruns
- no-jump UI behavior

### Planned Files

- `tv-search.js`

### Exit Criteria

- TV runtime logic is mostly outside `app.js`
- polling and rerender behavior remain stable
- existing E2E coverage stays green

## Phase 5: Final Bootstrap Cleanup

### Goal

Reduce `app.js` to a thin composition root.

### Scope

- collect DOM references
- create runtime state
- create API facade
- initialize feature modules in explicit order
- remove leftover dead utility code

### Exit Criteria

- `app.js` is bootstrap only
- feature ownership is obvious
- initialization order is explicit

## Non-Regression Checklist

The following behaviors must be preserved unless a separate task changes them intentionally:

- file search cards/list toggle survives reload
- file search saved and queued badges hydrate correctly
- movie info button still works
- queue dialog still works from file results
- TV show lookup by Enter works
- TV search job polling does not jump or collapse unexpectedly
- TV queue state does not shift content aggressively during refresh
- downloaded TV episodes remain marked correctly
- TV `Search anyway` and alias rerun flows still work
- downloads panel actions still work

## Execution Log

## Phase 0 Log

### Entry 0.1

- Date: `2026-06-11`
- Type: `planning`
- Summary:
  - created the implementation reference document
  - established phase structure
  - established verification policy
  - established logging format for future refactor steps
- Tests run:
  - none
- Result:
  - not applicable
- Commit:
  - pending at document creation time

### Entry 0.2

- Date: `2026-06-11`
- Type: `baseline verification`
- Summary:
  - verified that the current `app.js` behavior is covered well enough to start extraction work
  - no additional baseline test had to be added before Phase 1
  - existing browser coverage already protects:
    - file search view/filter persistence
    - TV downloaded episode state in the current collapsed-season UI
- Tests run:
  - `.venv/bin/pytest -m 'not live'`
  - `RUN_E2E=1 .venv/bin/pytest -m e2e`
- Result:
  - mocked suite: `49 passed, 1 skipped, 3 deselected`
  - browser E2E: `2 passed, 52 deselected`
- Commit:
  - `e7c51bf` `Extract shared app.js foundation modules`

## Phase 1 Log

### Entry 1.1

- Date: `2026-06-11`
- Type: `implementation`
- Summary:
  - extracted the first shared foundation modules from `app.js`
  - created:
    - [`app/static/js/dom-utils.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/dom-utils.js)
    - [`app/static/js/keys.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/keys.js)
    - [`app/static/js/formatters.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/formatters.js)
    - [`app/static/js/storage-state.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/storage-state.js)
  - moved only pure helpers, key builders, formatter helpers and localStorage wrappers
  - kept rendering, polling and feature orchestration inside `app.js`
- Tests run:
  - `.venv/bin/pytest -m 'not live'`
  - `RUN_E2E=1 .venv/bin/pytest -m e2e`
  - `git diff --check`
- Result:
  - mocked suite: `49 passed, 1 skipped, 3 deselected`
  - browser E2E: `2 passed, 52 deselected`
  - diff check: clean
- Commit:
  - pending at log update time

## Phase 2 Log

- No entries yet.

## Phase 3 Log

- No entries yet.

## Phase 4 Log

- No entries yet.

## Phase 5 Log

- No entries yet.
