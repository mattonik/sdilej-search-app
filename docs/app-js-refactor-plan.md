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

## Post-Refactor Cleanup

The refactor is complete and the app remains behavior-compatible with the pre-split runtime.

### Final State

- [`app/static/js/app.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/app.js) is now a thin bootstrap/orchestration entrypoint.
- TV rendering helpers live in [`app/static/js/tv-view.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/tv-view.js).
- Queue rendering logic is centralized in [`app/static/js/queue-ui.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/queue-ui.js).
- The current validated refactor endpoint is commit [`a9c3eea`](https://github.com/mattonik/sdilej-search-app/commit/a9c3eea) `Fix TV search-anyway state handling`.

### Verified Gates

- `pytest -m "not live"` passed
- `RUN_E2E=1 pytest -m e2e` passed
- `RUN_LIVE_SMOKE=1 pytest -m live` passed
- `git diff --check` passed

### Remaining Operational Note

- `docker build -t sdilej-search:test .` requires a running Docker daemon / Colima instance.
- The code path itself is verified; only local container availability was blocking the last build smoke at the time of cleanup.

### Next Suggested Maintenance Work

- consider a small `queue-ui.js` cleanup if further TV/file queue coupling appears
- keep the TV E2E cases as the regression gate for future UI refactors
- later, split `storage.py` into domain repositories if backend maintainability becomes the next priority

## Storage Split Log

This section tracks the incremental decomposition of `app/storage.py` into smaller repositories without changing the public `Storage` facade.

### Stage 1: Settings And Metadata Repositories

**Outcome**

- extracted [`app/storage_settings.py`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/storage_settings.py)
- extracted [`app/storage_metadata.py`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/storage_metadata.py)
- `Storage` now delegates download/library settings and metadata cache access to dedicated repositories

**Verification**

- `PYTHONPYCACHEPREFIX=/tmp/pycache .venv/bin/python -m py_compile app/*.py tests/*.py`
- `.venv/bin/pytest -m 'not live'`
- `RUN_E2E=1 .venv/bin/pytest -m e2e`
- `RUN_LIVE_SMOKE=1 .venv/bin/pytest -m live`

**Result**

- all gates passed
- no public API or runtime behavior changes detected

**Commit**

- pending at the time of this document update

### Stage 2: TV Job Repository

**Outcome**

- extracted [`app/storage_tv_jobs.py`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/storage_tv_jobs.py)
- `Storage` now delegates all TV search job lifecycle operations to a dedicated repository
- TV job create/claim/update/finalize/cancel/recover behavior is unchanged

**Verification**

- `PYTHONPYCACHEPREFIX=/tmp/pycache .venv/bin/python -m py_compile app/*.py tests/*.py`
- `.venv/bin/pytest -m 'not live'`
- `RUN_E2E=1 .venv/bin/pytest -m e2e`
- `RUN_LIVE_SMOKE=1 .venv/bin/pytest -m live`

**Result**

- all gates passed
- TV job tests remained green after the split

**Commit**

- pending at the time of this document update

### Stage 3: Download Job Repository

**Outcome**

- extracted [`app/storage_downloads.py`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/storage_downloads.py)
- `Storage` now delegates all download job lifecycle operations to a dedicated repository
- download job create/claim/update/fail/cancel/retry/recover behavior is unchanged

**Verification**

- `PYTHONPYCACHEPREFIX=/tmp/pycache .venv/bin/python -m py_compile app/*.py tests/*.py`
- `.venv/bin/pytest -m 'not live'`
- `RUN_E2E=1 .venv/bin/pytest -m e2e`
- `RUN_LIVE_SMOKE=1 .venv/bin/pytest -m live`

**Result**

- all gates passed
- no API or browser behavior regressions detected

**Commit**

- pending at the time of this document update

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
  - `ad459a7` `Add app.js refactor implementation plan`

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
  - `c2f4634` `Record app.js refactor baseline verification`

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
  - `a7f27c3` `Extract shared app.js foundation modules`

## Phase 2 Log

### Entry 2.1

- Date: `2026-06-12`
- Type: `implementation`
- Summary:
  - introduced [`app/static/js/runtime-state.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/runtime-state.js)
  - introduced [`app/static/js/api.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/api.js)
  - centralized browser API access behind the `api` facade
  - removed direct raw `fetch(...)` calls from `app.js`
  - added explicit runtime bootstrap state object and started wiring shared mutable UI state through it
  - kept feature ownership inside `app.js` for now; this phase is preparation for later extraction
- Tests run:
  - `.venv/bin/pytest -m 'not live'`
  - `RUN_E2E=1 .venv/bin/pytest -m e2e`
  - `git diff --check`
- Result:
  - mocked suite: `49 passed, 1 skipped, 3 deselected`
  - browser E2E: `2 passed, 52 deselected`
  - diff check: clean
- Commit:
  - `c046ab6` `Introduce app.js runtime state and API facades`

## Phase 3 Log

### Entry 3.1

- Date: `2026-06-12`
- Type: `implementation`
- Summary:
  - extracted workspace tab behavior into [`app/static/js/workspace-tabs.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/workspace-tabs.js)
  - `app.js` now delegates tab activation and section visibility to a dedicated feature module
  - state persistence for active workspace tab remains unchanged
- Tests run:
  - `.venv/bin/pytest -m 'not live'`
  - `RUN_E2E=1 .venv/bin/pytest -m e2e`
  - `git diff --check`
- Result:
  - mocked suite: `49 passed, 1 skipped, 3 deselected`
  - browser E2E: `2 passed, 52 deselected`
  - diff check: clean
- Commit:
  - `e0dd71f` `Extract workspace tabs from app.js`

### Entry 3.2

- Date: `2026-06-12`
- Type: `implementation`
- Summary:
  - extracted queue dialog behavior into [`app/static/js/queue-dialog.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/queue-dialog.js)
  - queue dialog state is now owned by the queue dialog module instead of `app.js`
  - `app.js` now delegates:
    - dialog open/close
    - classification preview
    - edit-vs-enqueue submit flow
  - the dialog remains reusable from file search, TV results and downloads actions
- Tests run:
  - `.venv/bin/pytest -m 'not live'`
  - `RUN_E2E=1 .venv/bin/pytest -m e2e`
  - `git diff --check`
- Result:
  - mocked suite: `49 passed, 1 skipped, 3 deselected`
  - browser E2E: `2 passed, 52 deselected`
  - diff check: clean
- Commit:
  - `0e66f18` `Extract queue dialog from app.js`

### Entry 3.3

- Date: `2026-06-13`
- Type: `implementation`
- Summary:
  - extracted downloads and account panel behavior into [`app/static/js/downloads.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/downloads.js)
  - moved out of `app.js`:
    - download queue rendering
    - download queue refresh/settings/account refresh
    - download enqueue form handling
    - queue action handlers
    - download settings form handling
    - account form and clear handling
  - resolved the queue-dialog/downloads mutual dependency in bootstrap code through explicit closure callbacks instead of cross-module imports
  - kept file search toolbar controls and movie info flow in `app.js` for the next extraction step
- Tests run:
  - `.venv/bin/pytest -m 'not live'`
  - `RUN_E2E=1 .venv/bin/pytest -m e2e`
  - `git diff --check`
- Result:
  - mocked suite: `49 passed, 1 skipped, 3 deselected`
  - browser E2E: `2 passed, 52 deselected`
  - diff check: clean
- Commit:
  - `9240f94` `Extract downloads panel from app.js`

### Entry 3.4

- Date: `2026-06-13`
- Type: `implementation`
- Summary:
  - extracted file-search results runtime into [`app/static/js/file-search.js`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/app/static/js/file-search.js)
  - moved out of `app.js`:
    - file results cards/list toggle
    - file results filter chips
    - active file filter summary
    - saved-state hydration and saved badge updates
    - queue-state refresh for file results
    - movie info button behavior
    - save action handling
    - file-result queue-dialog button handling
  - kept file-vs-TV shared filter synchronization in `app.js` for now, because it still bridges both search modes
  - `app.js` now delegates file-search rendering/state behavior through explicit callbacks into the file-search module
- Tests run:
  - `.venv/bin/pytest -m 'not live'`
  - `RUN_E2E=1 .venv/bin/pytest -m e2e`
  - `git diff --check`
- Result:
  - mocked suite: `49 passed, 1 skipped, 3 deselected`
  - browser E2E: `2 passed, 52 deselected`
  - diff check: clean
- Commit:
  - `2016e7f` `Extract file search runtime from app.js`

### Entry 3.5

- Date: `2026-06-13`
- Type: `test hardening`
- Summary:
  - added a dedicated TV UI safety net before starting the high-risk `tv-search.js` extraction
  - extended [`tests/test_e2e_ui.py`](/Users/martinp/Work/Projects/lilnasx/sdilej-search-app/tests/test_e2e_ui.py) with browser-level non-regression coverage for:
    - TV polling preserving open season state and the selected results filter
    - TV episode queue state transitioning from queued to downloaded after download completion
    - `Search anyway` replacing downloaded episode state with live search results
  - kept the tests deterministic by driving real browser polling against a local uvicorn app while mutating test storage directly instead of depending on background workers
- Tests run:
  - `.venv/bin/pytest -m 'not live'`
  - `RUN_E2E=1 .venv/bin/pytest -m e2e`
  - `git diff --check`
- Result:
  - mocked suite: `49 passed, 1 skipped, 3 deselected`
  - browser E2E: `5 passed, 52 deselected`
  - diff check: clean
- Commit:
  - pending at log update time

## Phase 4 Log

### Entry 4.1

- Date: 2026-06-13
- Commit: `82b5e1f`
- Scope: extracted the TV runtime from `app.js` into `app/static/js/tv-search.js`, kept the TV lookup/search/polling/downloaded-state behavior intact, and wired the bootstrap to the extracted module.
- Verification:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache .venv/bin/python -m py_compile app/*.py tests/*.py`
  - `.venv/bin/pytest -m 'not live'`
  - `RUN_E2E=1 .venv/bin/pytest -m e2e`
  - `git diff --check`
- Result: passed


## Phase 5 Log

### Entry 5.1

- Date: 2026-06-13
- Commit: `bad98fb`
- Scope: removed the remaining queue/bootstrap glue from `app.js` by introducing `app/static/js/queue-ui.js` and wiring `app.js` to use shared queue helpers instead of inlining them.
- Verification:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache .venv/bin/python -m py_compile app/*.py tests/*.py`
  - `.venv/bin/pytest -m 'not live'`
  - `RUN_E2E=1 .venv/bin/pytest -m e2e`
  - `git diff --check`
- Result: passed
