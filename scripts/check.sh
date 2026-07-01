#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
PYTEST_BIN="${PYTEST_BIN:-.venv/bin/pytest}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "error: $PYTHON_BIN not found or not executable" >&2
  exit 1
fi

if [[ ! -x "$PYTEST_BIN" ]]; then
  echo "error: $PYTEST_BIN not found or not executable" >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 12):
    raise SystemExit("error: Python 3.12+ is required")
PY

echo "[1/4] Python compile check"
PYTHONPYCACHEPREFIX=/tmp/pycache "$PYTHON_BIN" -m py_compile app/*.py tests/*.py

echo "[2/4] Mocked pytest suite"
"$PYTEST_BIN" -m "not live"

echo "[3/4] Browser E2E suite"
RUN_E2E=1 "$PYTEST_BIN" -m e2e

echo "[4/4] Docker image build"
if ! docker info >/dev/null 2>&1; then
  echo "error: docker daemon is not reachable; start Docker/Colima and rerun" >&2
  exit 1
fi
docker build -t sdilej-search:test .

echo "check complete"
