#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON=${EYE_PYTHON:-python3.12}
"$PYTHON" -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
npm --prefix frontend run build
if [[ ! -f data/history/manifest.json ]]; then .venv/bin/python scripts/fetch_history.py; fi
PYTHONPATH=backend OMP_NUM_THREADS=2 .venv/bin/python -m app.research
printf '\nSetup complete. Configure DATABASE_URL in .env, then run scripts/start.sh.\n'
