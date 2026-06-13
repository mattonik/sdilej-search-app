# Storage Refactor Log

## Goal
Split `app/storage.py` into small repositories and helpers without changing public behavior or HTTP APIs.

## Scope
- storage settings and library paths
- metadata cache
- search history
- saved candidates
- download jobs
- TV jobs
- schema/migration helpers
- row mappers

## Completed Phases

### Phase 1: Foundation Split
- Extracted shared DB and schema helpers.
- Moved row mapping helpers into `storage_rows.py`.
- Moved search/history logic into `storage_search.py`.
- Moved metadata cache logic into `storage_metadata.py`.
- Moved settings/library path logic into `storage_settings.py`.

### Phase 2: Job Repositories
- Moved TV job lifecycle logic into `storage_tv_jobs.py`.
- Moved download job lifecycle logic into `storage_downloads.py`.
- Kept `Storage` as a compatibility facade.

### Phase 3: Saved Candidates Split
- Moved saved candidate CRUD into `storage_saved.py`.
- Kept current API and response shapes unchanged.

### Phase 4: Storage Facade Cleanup
- Removed remaining inline row mapping and migration helper logic from `storage.py`.
- Added explicit delegations to the repository layer.

## Verification Gates
- Mocked suite: `.venv/bin/pytest -m 'not live'`
- Browser E2E: `RUN_E2E=1 .venv/bin/pytest -m e2e`
- Live smoke: `RUN_LIVE_SMOKE=1 .venv/bin/pytest -m live`
- Bytecode: `PYTHONPYCACHEPREFIX=/tmp/pycache .venv/bin/python -m py_compile app/*.py tests/*.py`
- Diff hygiene: `git diff --check`

## Execution Log

### Phase 4: Storage Facade Cleanup
- Status: completed
- Date: 2026-06-13
- Test gate:
  - `.venv/bin/pytest -m 'not live'` -> `49 passed, 1 skipped, 3 deselected`
  - `RUN_E2E=1 .venv/bin/pytest -m e2e` -> `5 passed, 52 deselected`
  - `RUN_LIVE_SMOKE=1 .venv/bin/pytest -m live` -> `3 passed, 1 skipped, 49 deselected`
  - `PYTHONPYCACHEPREFIX=/tmp/pycache .venv/bin/python -m py_compile app/*.py tests/*.py` -> passed
  - `git diff --check` -> passed
- Commit: pending
